import asyncio
import logging
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, status
from minio import Minio

from contracts.dto import MinioObjectReference
from .image_processing import process_image_bytes, build_processed_key
from .storage import ensure_bucket, fetch_object_bytes, upload_object_bytes


logger = logging.getLogger(__name__)


class ImageProcessingPipeline:
    """Reusable pipeline to fetch, preprocess, and persist images in MinIO."""

    def __init__(self, client: Minio) -> None:
        self.client = client

    async def preprocess_and_store(
        self,
        source: MinioObjectReference,
        target_bucket: str,
        *,
        correlation_id: str | None = None,
        target_width: int = 585,
    ) -> Tuple[MinioObjectReference, str]:
        """Fetch source image, preprocess, upload to target bucket. Returns processed ref and content-type."""
        await ensure_bucket(self.client, source.bucket, correlation_id=correlation_id)
        await ensure_bucket(self.client, target_bucket, correlation_id=correlation_id)

        data = await fetch_object_bytes(self.client, source, correlation_id=correlation_id)

        try:
            processed_bytes, content_type, ext = await asyncio.to_thread(
                process_image_bytes, data, target_width=target_width
            )
        except ValueError as exc:
            logger.warning(
                "Invalid image content during preprocessing",
                extra={
                    "event": "backend.pipeline.invalid_image",
                    "correlation_id": correlation_id,
                    "bucket": source.bucket,
                    "object_key": source.object_key,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(exc),
            ) from exc

        processed_key = build_processed_key(source.object_key, ext)
        processed_ref = MinioObjectReference(bucket=target_bucket, object_key=processed_key)

        await upload_object_bytes(
            self.client,
            processed_ref.bucket,
            processed_ref.object_key,
            processed_bytes,
            content_type,
            correlation_id=correlation_id,
        )

        return processed_ref, content_type

    @staticmethod
    def derive_title(source_key: str) -> str:
        return Path(source_key).name
