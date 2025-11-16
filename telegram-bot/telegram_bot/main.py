import asyncio
import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional, Sequence

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
import httpx
from minio import Minio
from minio.error import S3Error

from contracts.dto import (
    HealthStatus,
    MinioObjectReference,
    SimilarRequest,
    SimilarResponse,
    SimilarResult,
)
from .config import BotSettings, get_settings


def create_minio_client(settings: BotSettings) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _object_key(file_path: Optional[str], unique_id: str) -> str:
    extension = Path(file_path).suffix if file_path else ".jpg"
    if not extension:
        extension = ".jpg"
    return f"{unique_id}{extension}"


async def ensure_bucket(client: Minio, bucket: str) -> None:
    exists = await asyncio.to_thread(client.bucket_exists, bucket)
    if not exists:
        await asyncio.to_thread(client.make_bucket, bucket)


async def download_photo(bot: Bot, photo: types.PhotoSize) -> tuple[BytesIO, str]:
    file = await bot.get_file(photo.file_id)
    buffer = BytesIO()
    await bot.download(file, destination=buffer)
    return buffer, file.file_path or "uploaded.jpg"


async def upload_to_minio(
    bot: Bot,
    message: types.Message,
    minio_client: Minio,
    settings: BotSettings,
) -> Optional[MinioObjectReference]:
    photo = message.photo[-1]

    try:
        buffer, file_path = await download_photo(bot, photo)
    except Exception:
        await message.answer("Не удалось скачать фото из Telegram. Попробуйте ещё раз позже.")
        return None

    object_key = _object_key(file_path, photo.file_unique_id)
    await ensure_bucket(minio_client, settings.minio_user_bucket)

    buffer.seek(0, os.SEEK_END)
    length = buffer.tell()
    buffer.seek(0)

    try:
        await asyncio.to_thread(
            minio_client.put_object,
            settings.minio_user_bucket,
            object_key,
            buffer,
            length=length,
            content_type="image/jpeg",
        )
    except S3Error:
        await message.answer("Не удалось сохранить снимок в хранилище. Попробуйте позже.")
        return None

    return MinioObjectReference(bucket=settings.minio_user_bucket, object_key=object_key)


async def fetch_similar(
    http_client: httpx.AsyncClient,
    reference: MinioObjectReference,
    settings: BotSettings,
) -> Optional[SimilarResponse]:
    try:
        request_payload = SimilarRequest(source=reference, top_k=settings.default_top_k)
        response = await http_client.post("/similar", json=request_payload.model_dump(mode="json"))
        response.raise_for_status()
        return SimilarResponse.model_validate_json(response.text)
    except httpx.HTTPError:
        return None


async def _presign_if_needed(
    result_reference: Optional[MinioObjectReference],
    minio_client: Minio,
) -> Optional[str]:
    if result_reference is None:
        return None

    try:
        return await asyncio.to_thread(
            minio_client.get_presigned_url,
            "GET",
            result_reference.bucket,
            result_reference.object_key,
            expires=timedelta(hours=1),
        )
    except S3Error:
        return None


async def build_media_group(
    results: Sequence[SimilarResult],
    minio_client: Minio,
) -> list[types.InputMediaPhoto]:
    media: list[types.InputMediaPhoto] = []
    for result in results:
        url = result.url
        if url is None:
            url = await _presign_if_needed(result.object, minio_client)

        if url is None:
            continue

        caption_parts = []
        if result.title:
            caption_parts.append(result.title)
        if result.score is not None:
            caption_parts.append(f"score: {result.score:.2f}")
        caption = " | ".join(caption_parts) if caption_parts else "Похожий экран"

        media.append(types.InputMediaPhoto(media=url, caption=caption))

    return media


async def send_gallery(
    message: types.Message,
    response: SimilarResponse,
    minio_client: Minio,
) -> None:
    media_group = await build_media_group(response.results, minio_client)
    if not media_group:
        await message.answer("Не удалось собрать результаты для отправки пользователю.")
        return

    try:
        await message.answer_media_group(media_group)
    except Exception:
        await message.answer("Ошибка при отправке похожих экранов. Попробуйте ещё раз позже.")


async def handle_photo_message(
    message: types.Message,
    bot: Bot,
    http_client: httpx.AsyncClient,
    minio_client: Minio,
    settings: BotSettings,
) -> None:
    reference = await upload_to_minio(bot, message, minio_client, settings)
    if reference is None:
        return

    response = await fetch_similar(http_client, reference, settings)
    if response is None:
        await message.answer("Не удалось получить похожие экраны. Попробуйте ещё раз позже.")
        return

    await send_gallery(message, response, minio_client)


async def describe_backend_health(http_client: httpx.AsyncClient) -> str:
    try:
        response = await http_client.get("/health")
        response.raise_for_status()
        payload = HealthStatus.model_validate_json(response.text)
        return f"Backend status: {payload.status}"
    except Exception:
        return "Backend health check failed."


async def main() -> None:
    settings = get_settings()
    minio_client = create_minio_client(settings)
    bot = Bot(token=settings.token)
    dp = Dispatcher()

    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=20.0) as http_client:

        @dp.message(CommandStart())
        async def cmd_start(message: types.Message) -> None:
            await message.answer(
                "Привет! Отправь мне скриншот, и я найду похожие экраны."
            )

        @dp.message(Command("health"))
        async def cmd_health(message: types.Message) -> None:
            status_text = await describe_backend_health(http_client)
            await message.answer(status_text)

        @dp.message(F.photo)
        async def on_photo(message: types.Message) -> None:
            await handle_photo_message(message, bot, http_client, minio_client, settings)

        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
