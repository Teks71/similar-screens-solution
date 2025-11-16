import asyncio
from datetime import timedelta
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from minio import Minio
from minio.error import S3Error

from contracts.dto import MinioObjectReference
from .config import BackendSettings, get_settings


@lru_cache(maxsize=1)
def get_minio_client(settings: BackendSettings) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def provide_minio_client(settings: BackendSettings = Depends(get_settings)) -> Minio:
    return get_minio_client(settings)


async def ensure_bucket(client: Minio, bucket: str) -> None:
    exists = await asyncio.to_thread(client.bucket_exists, bucket)
    if not exists:
        await asyncio.to_thread(client.make_bucket, bucket)


async def verify_source_object(client: Minio, reference: MinioObjectReference) -> None:
    response = None
    try:
        response = await asyncio.to_thread(client.get_object, reference.bucket, reference.object_key)
        await asyncio.to_thread(response.read, 1)
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source object not found in storage",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        if response is not None:
            try:
                response.close()
                response.release_conn()
            except Exception:
                pass


async def presign_url(client: Minio, reference: MinioObjectReference) -> str:
    return await asyncio.to_thread(
        client.get_presigned_url,
        "GET",
        reference.bucket,
        reference.object_key,
        expires=timedelta(hours=1),
    )
