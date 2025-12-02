import asyncio
import logging
import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import urlparse

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


logger = logging.getLogger(__name__)


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


def _message_context(message: types.Message) -> dict:
    return {
        "chat_id": getattr(message.chat, "id", None),
        "user_id": getattr(getattr(message, "from_user", None), "id", None),
        "message_id": message.message_id,
        "text": message.text,
        "caption": message.caption,
        "has_photo": bool(message.photo),
    }


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


async def ensure_bucket(client: Minio, bucket: str) -> None:
    exists = await asyncio.to_thread(client.bucket_exists, bucket)
    if not exists:
        await asyncio.to_thread(client.make_bucket, bucket)
        logger.info(
            "Created missing MinIO bucket for bot",
            extra={
                "event": "bot.storage.ensure_bucket.created",
                "bucket": bucket,
            },
        )


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
        logger.exception(
            "Failed to download photo from Telegram",
            extra={
                "event": "bot.error.download_photo",
                **_message_context(message),
            },
        )
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
        logger.exception(
            "Failed to upload photo to MinIO",
            extra={
                "event": "bot.error.minio_upload",
                **_message_context(message),
                "bucket": settings.minio_user_bucket,
                "object_key": object_key,
            },
        )
        await message.answer("Не удалось сохранить снимок в хранилище. Попробуйте позже.")
        return None

    logger.info(
        "Uploaded photo to MinIO",
        extra={
            "event": "bot.storage.upload.success",
            **_message_context(message),
            "bucket": settings.minio_user_bucket,
            "object_key": object_key,
        },
    )

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
        logger.info(
            "Backend similarity request succeeded",
            extra={
                "event": "bot.backend.similar.success",
                "endpoint": "/similar",
                "backend_base_url": settings.backend_base_url,
                "status_code": response.status_code,
                "bucket": reference.bucket,
                "object_key": reference.object_key,
            },
        )
        return SimilarResponse.model_validate_json(response.text)
    except httpx.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        logger.exception(
            "Backend similarity request failed",
            extra={
                "event": "bot.error.backend_similar",
                "endpoint": "/similar",
                "backend_base_url": settings.backend_base_url,
                "status_code": status_code,
                "bucket": reference.bucket,
                "object_key": reference.object_key,
            },
        )
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
        logger.exception(
            "Failed to presign MinIO object for result",
            extra={
                "event": "bot.error.presign_result",
                "bucket": result_reference.bucket,
                "object_key": result_reference.object_key,
            },
        )
        return None


async def build_media_group(
    results: Sequence[SimilarResult],
    minio_client: Minio,
) -> list[types.InputMediaPhoto]:
    media: list[types.InputMediaPhoto] = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as fetch_client:
        for idx, result in enumerate(results):
            url_value = result.url or await _presign_if_needed(result.object, minio_client)

            if url_value is None:
                continue

            url = str(url_value)
            if not _is_valid_http_url(url):
                logger.warning(
                    "Skipping invalid URL in similarity result",
                    extra={
                        "event": "bot.response.media_group.invalid_url",
                        "url": url_value,
                        "title": result.title,
                    },
                )
                continue

            try:
                response = await fetch_client.get(url)
                response.raise_for_status()
                content = response.content
            except Exception:
                logger.warning(
                    "Failed to fetch image for media group",
                    exc_info=True,
                    extra={
                        "event": "bot.response.media_group.fetch_failed",
                        "url": url,
                        "title": result.title,
                    },
                )
                continue

            caption_parts = []
            if result.title:
                caption_parts.append(result.title)
            if result.score is not None:
                caption_parts.append(f"score: {result.score:.2f}")
            caption = " | ".join(caption_parts) if caption_parts else "Похожий экран"

            media.append(
                types.InputMediaPhoto(
                    media=types.BufferedInputFile(content, filename=f"similar-{idx}.jpg"),
                    caption=caption,
                )
            )

    return media


async def send_gallery(
    message: types.Message,
    response: SimilarResponse,
    minio_client: Minio,
) -> None:
    media_items = await build_media_group(response.results, minio_client)
    if not media_items:
        logger.warning(
            "No media generated for similarity response",
            extra={
                "event": "bot.response.media_group.empty",
                **_message_context(message),
            },
        )
        await message.answer("Не удалось собрать результаты для отправки пользователю.")
        return

    # Telegram limits media groups to 10 items, so send in batches.
    batch_size = 10
    try:
        for offset in range(0, len(media_items), batch_size):
            chunk = media_items[offset : offset + batch_size]
            try:
                await message.answer_media_group(chunk)
            except Exception:
                logger.warning(
                    "Failed to send media group chunk, will retry items individually",
                    exc_info=True,
                    extra={
                        "event": "bot.response.media_group.chunk_failed",
                        **_message_context(message),
                        "chunk_size": len(chunk),
                    },
                )
                for item in chunk:
                    try:
                        await message.answer_photo(item.media, caption=item.caption)
                    except Exception:
                        logger.warning(
                            "Failed to send individual media item",
                            exc_info=True,
                            extra={
                                "event": "bot.response.media_group.item_failed",
                                **_message_context(message),
                                "caption": item.caption,
                            },
                        )

        logger.info(
            "Sent media group with similar screenshots",
            extra={
                "event": "bot.response.media_group",
                **_message_context(message),
                "media_count": len(media_items),
                "batches": (len(media_items) + batch_size - 1) // batch_size,
                "trigger_message_id": message.message_id,
            },
        )
    except Exception:
        logger.exception(
            "Backend send_gallery failed",
            extra={
                "event": "bot.error.send_gallery",
            },
        )
        await message.answer("Ошибка при отправке похожих экранов. Попробуйте ещё раз позже.")


async def handle_photo_message(
    message: types.Message,
    bot: Bot,
    http_client: httpx.AsyncClient,
    minio_client: Minio,
    settings: BotSettings,
) -> None:
    logger.info(
        "Received photo message",
        extra={
            "event": "bot.update.photo",
            **_message_context(message),
        },
    )

    reference = await upload_to_minio(bot, message, minio_client, settings)
    if reference is None:
        return

    response = await fetch_similar(http_client, reference, settings)
    if response is None:
        logger.error(
            "Failed to fetch similar results from backend",
            extra={
                "event": "bot.error.similar_response_missing",
                **_message_context(message),
                "bucket": reference.bucket,
                "object_key": reference.object_key,
            },
        )
        await message.answer("Не удалось получить похожие экраны. Попробуйте ещё раз позже.")
        return

    await send_gallery(message, response, minio_client)


async def describe_backend_health(http_client: httpx.AsyncClient) -> str:
    try:
        response = await http_client.get("/health")
        response.raise_for_status()
        payload = HealthStatus.model_validate_json(response.text)
        logger.info(
            "Backend health check succeeded",
            extra={
                "event": "bot.backend.health.success",
                "backend_base_url": str(http_client.base_url),
                "status_code": response.status_code,
                "health_status": payload.status,
            },
        )
        return f"Backend status: {payload.status}"
    except Exception:
        logger.exception(
            "Backend health check failed",
            extra={
                "event": "bot.error.health_check",
                "backend_base_url": str(http_client.base_url),
            },
        )
        return "Backend health check failed."


async def main() -> None:
    settings = get_settings()
    minio_client = create_minio_client(settings)
    bot = Bot(token=settings.token)
    dp = Dispatcher()

    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=20.0) as http_client:

        @dp.message(CommandStart())
        async def cmd_start(message: types.Message) -> None:
            logger.info(
                "Received /start command",
                extra={
                    "event": "bot.update.command_start",
                    **_message_context(message),
                },
            )
            await message.answer(
                "Привет! Отправь мне скриншот, и я найду похожие экраны."
            )

        @dp.message(Command("health"))
        async def cmd_health(message: types.Message) -> None:
            logger.info(
                "Received /health command",
                extra={
                    "event": "bot.update.command_health",
                    **_message_context(message),
                },
            )
            status_text = await describe_backend_health(http_client)
            await message.answer(status_text)

        @dp.message(F.photo)
        async def on_photo(message: types.Message) -> None:
            await handle_photo_message(message, bot, http_client, minio_client, settings)

        @dp.errors()
        async def global_error_handler(update: types.Update, exception: BaseException | None = None) -> None:
            message_obj = getattr(update, "message", None)
            context = {
                "event": "bot.error.unhandled",
                "update_id": getattr(update, "update_id", None),
                "exception_type": type(exception).__name__ if exception else None,
            }
            if isinstance(message_obj, types.Message):
                context.update(_message_context(message_obj))
            if exception is not None:
                context["exception_message"] = str(exception)

            logger.exception(
                "Unhandled error while processing update",
                extra=context,
            )

        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
