import asyncio
import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from minio import Minio
from minio.error import S3Error

from contracts.dto import MinioObjectReference
from .config import EmbeddingSettings, get_settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_minio_client(settings: EmbeddingSettings) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def provide_minio_client(settings: EmbeddingSettings = Depends(get_settings)) -> Minio:
    return get_minio_client(settings)


async def fetch_object_bytes(
    client: Minio,
    reference: MinioObjectReference,
    *,
    correlation_id: str | None = None,
) -> bytes:
    response = None
    try:
        response = await asyncio.to_thread(client.get_object, reference.bucket, reference.object_key)
        data = await asyncio.to_thread(response.read)
        return data
    except S3Error as exc:
        logger.warning(
            "Error fetching object from MinIO",
            extra={
                "event": "embedding.storage.fetch_object.error",
                "correlation_id": correlation_id,
                "bucket": reference.bucket,
                "object_key": reference.object_key,
                "error_code": getattr(exc, "code", None),
            },
        )
        if exc.code in {"NoSuchKey", "NoSuchBucket"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source object not found in storage",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage access error",
        )
    finally:
        if response is not None:
            try:
                response.close()
                response.release_conn()
            except Exception:
                logger.debug(
                    "Error while cleaning up MinIO response",
                    exc_info=True,
                    extra={
                        "event": "embedding.storage.fetch_object.cleanup_error",
                        "correlation_id": correlation_id,
                        "bucket": reference.bucket,
                        "object_key": reference.object_key,
                    },
                )
