import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status

from contracts.dto import EmbedRequest, EmbedResponse, MinioObjectReference
from .config import BackendSettings, get_settings


logger = logging.getLogger(__name__)


async def fetch_embedding(
    reference: MinioObjectReference,
    *,
    settings: Optional[BackendSettings] = None,
    correlation_id: Optional[str] = None,
) -> EmbedResponse:
    settings = settings or get_settings()
    if not settings.embedding_service_url:
        raise RuntimeError("EMBEDDING_SERVICE_URL is not configured")

    url = settings.embedding_service_url.rstrip("/") + "/embed"
    payload = EmbedRequest(source=reference).model_dump()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError:
        logger.exception(
            "Failed to call embedding service",
            extra={
                "event": "backend.embed.request_failed",
                "url": url,
                "correlation_id": correlation_id,
                "bucket": reference.bucket,
                "object_key": reference.object_key,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach embedding service",
        )

    if response.status_code != status.HTTP_200_OK:
        logger.warning(
            "Embedding service returned error",
            extra={
                "event": "backend.embed.error_response",
                "status_code": response.status_code,
                "url": url,
                "correlation_id": correlation_id,
                "body": response.text,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding service error: {response.text}",
        )

    try:
        data = response.json()
        return EmbedResponse(**data)
    except Exception as exc:
        logger.exception(
            "Failed to parse embedding response",
            extra={
                "event": "backend.embed.parse_failed",
                "url": url,
                "correlation_id": correlation_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid embedding service response",
        ) from exc
