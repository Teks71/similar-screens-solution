import asyncio
import io
import logging
from datetime import timedelta
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from minio import Minio
from minio.error import S3Error

from contracts.dto import MinioObjectReference
from .config import BackendSettings, get_settings


logger = logging.getLogger(__name__)


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


async def ensure_bucket(client: Minio, bucket: str, *, correlation_id: str | None = None) -> None:
    try:
        exists = await asyncio.to_thread(client.bucket_exists, bucket)
    except S3Error as exc:
        logger.exception(
            "Error checking bucket existence",
            extra={
                "event": "backend.storage.ensure_bucket.error",
                "correlation_id": correlation_id,
                "bucket": bucket,
                "operation": "bucket_exists",
                "error_code": getattr(exc, "code", None),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage access error",
        )

    if not exists:
        try:
            await asyncio.to_thread(client.make_bucket, bucket)
            logger.info(
                "Created missing bucket",
                extra={
                    "event": "backend.storage.ensure_bucket.created",
                    "correlation_id": correlation_id,
                    "bucket": bucket,
                },
            )
        except S3Error as exc:
            logger.exception(
                "Error creating bucket",
                extra={
                    "event": "backend.storage.ensure_bucket.create_error",
                    "correlation_id": correlation_id,
                    "bucket": bucket,
                    "operation": "make_bucket",
                    "error_code": getattr(exc, "code", None),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage access error",
            )


async def verify_source_object(
    client: Minio,
    reference: MinioObjectReference,
    *,
    correlation_id: str | None = None,
) -> None:
    response = None
    try:
        response = await asyncio.to_thread(client.get_object, reference.bucket, reference.object_key)
        await asyncio.to_thread(response.read, 1)
    except S3Error as exc:
        logger.warning(
            "Error verifying source object in storage",
            extra={
                "event": "backend.storage.verify_source_object.error",
                "correlation_id": correlation_id,
                "bucket": reference.bucket,
                "object_key": reference.object_key,
                "error_code": getattr(exc, "code", None),
            },
        )
        if exc.code == "NoSuchKey":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source object not found in storage",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
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
                        "event": "backend.storage.verify_source_object.cleanup_error",
                        "correlation_id": correlation_id,
                        "bucket": reference.bucket,
                        "object_key": reference.object_key,
                    },
                )


async def presign_url(
    client: Minio,
    reference: MinioObjectReference,
    *,
    correlation_id: str | None = None,
) -> str:
    try:
        return await asyncio.to_thread(
            client.get_presigned_url,
            "GET",
            reference.bucket,
            reference.object_key,
            expires=timedelta(hours=1),
        )
    except S3Error as exc:
        logger.exception(
            "Error generating presigned URL",
            extra={
                "event": "backend.storage.presign_url.error",
                "correlation_id": correlation_id,
                "bucket": reference.bucket,
                "object_key": reference.object_key,
                "error_code": getattr(exc, "code", None),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL",
        )


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
                "event": "backend.storage.fetch_object.error",
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
                        "event": "backend.storage.fetch_object.cleanup_error",
                        "correlation_id": correlation_id,
                        "bucket": reference.bucket,
                        "object_key": reference.object_key,
                    },
                )


async def upload_object_bytes(
    client: Minio,
    bucket: str,
    object_key: str,
    data: bytes,
    content_type: str,
    *,
    correlation_id: str | None = None,
) -> None:
    try:
        await asyncio.to_thread(
            client.put_object,
            bucket,
            object_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
    except S3Error as exc:
        logger.exception(
            "Error uploading object to MinIO",
            extra={
                "event": "backend.storage.upload_object.error",
                "correlation_id": correlation_id,
                "bucket": bucket,
                "object_key": object_key,
                "error_code": getattr(exc, "code", None),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store processed object",
        )
