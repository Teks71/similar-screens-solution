import logging
import time
import uuid
from io import BytesIO

from fastapi import Depends, FastAPI, HTTPException, Request, status
from PIL import Image, UnidentifiedImageError

from contracts.dto import EmbedRequest, EmbedResponse, HealthStatus
from .config import EmbeddingSettings, get_settings
from .model import generate_embedding, get_model_bundle, load_model
from .storage import fetch_object_bytes, provide_minio_client


app = FastAPI(title="Embedding Service")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup() -> None:
    settings = get_settings()
    try:
        await load_model(settings.model_name, settings.device)
    except Exception:
        logger.exception("Failed to load embedding model during startup")
        raise


@app.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    try:
        bundle = get_model_bundle()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return HealthStatus(status=f"ok:{bundle.name}")


def _validate_bucket(settings: EmbeddingSettings, bucket: str) -> None:
    if settings.minio_allowed_bucket and bucket != settings.minio_allowed_bucket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bucket is not allowed for embedding",
        )


@app.post("/embed", response_model=EmbedResponse)
async def embed_image(
    request: EmbedRequest,
    http_request: Request,
    settings: EmbeddingSettings = Depends(get_settings),
    client=Depends(provide_minio_client),
) -> EmbedResponse:
    correlation_id = http_request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    logger.info(
        "Received embedding request",
        extra={
            "event": "embedding.request",
            "correlation_id": correlation_id,
            "bucket": request.source.bucket,
            "object_key": request.source.object_key,
        },
    )

    _validate_bucket(settings, request.source.bucket)

    try:
        bundle = get_model_bundle()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    data = await fetch_object_bytes(client, request.source, correlation_id=correlation_id)
    try:
        image = Image.open(BytesIO(data)).convert("RGB")
    except UnidentifiedImageError as exc:
        logger.warning(
            "Unsupported content type for embedding",
            extra={
                "event": "embedding.image.invalid",
                "correlation_id": correlation_id,
                "bucket": request.source.bucket,
                "object_key": request.source.object_key,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Source object is not a valid image",
        ) from exc

    try:
        vector = await generate_embedding(image)
    except Exception as exc:
        logger.exception(
            "Failed to generate embedding",
            extra={
                "event": "embedding.error",
                "correlation_id": correlation_id,
                "bucket": request.source.bucket,
                "object_key": request.source.object_key,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embedding",
        ) from exc

    if len(vector) != bundle.dimension:
        logger.error(
            "Embedding dimension mismatch",
            extra={
                "event": "embedding.dimension_mismatch",
                "expected": bundle.dimension,
                "actual": len(vector),
                "correlation_id": correlation_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding dimension mismatch",
        )

    response = EmbedResponse(
        model=bundle.name,
        dimension=bundle.dimension,
        vector=vector,
    )

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Embedding generated",
        extra={
            "event": "embedding.response",
            "correlation_id": correlation_id,
            "duration_ms": round(duration_ms, 2),
            "bucket": request.source.bucket,
            "object_key": request.source.object_key,
            "dimension": bundle.dimension,
        },
    )
    return response
