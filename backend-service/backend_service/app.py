import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status

from contracts.dto import (
    HealthStatus,
    SimilarRequest,
    SimilarResponse,
    SimilarResult,
    IngestRequest,
    IngestResponse,
    MinioObjectReference,
)
from .config import BackendSettings, get_settings
from .database import close_database, ping_database
from .qdrant import close_qdrant_client, init_qdrant_collection
from .storage import (
    ensure_bucket,
    presign_url,
    provide_minio_client,
    verify_source_object,
    fetch_object_bytes,
    upload_object_bytes,
)
from .image_processing import process_image_bytes, build_processed_key
from .embed_client import fetch_embedding
from .qdrant import upsert_vector_point

app = FastAPI(
    title="Similar Screens Backend",
    version="0.1.0",
    description=(
        "Service for processing screenshots: ingest from MinIO, preprocess, embed via the embedding service, "
        "and index vectors in Qdrant. Includes similarity lookup endpoint."
    ),
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup() -> None:
    await ping_database()
    await init_qdrant_collection()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_database()
    await close_qdrant_client()


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


@app.post(
    "/similar",
    response_model=SimilarResponse,
    summary="Find similar screenshots",
    tags=["similarity"],
)
async def find_similar(
    request: SimilarRequest,
    http_request: Request,
    settings: BackendSettings = Depends(get_settings),
    client=Depends(provide_minio_client),
) -> SimilarResponse:
    correlation_id = http_request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    logger.info(
        "Received similarity request",
        extra={
            "event": "backend.similar.request",
            "correlation_id": correlation_id,
            "http_method": http_request.method,
            "path": http_request.url.path,
            "bucket": request.source.bucket,
            "object_key": request.source.object_key,
            "top_k": request.top_k,
        },
    )

    try:
        if request.source.bucket != settings.minio_user_bucket:
            detail = "Invalid bucket provided for similarity search"
            logger.warning(
                "Rejecting similarity request due to invalid bucket",
                extra={
                    "event": "backend.similar.invalid_bucket",
                    "correlation_id": correlation_id,
                    "expected_bucket": settings.minio_user_bucket,
                    "provided_bucket": request.source.bucket,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

        await ensure_bucket(client, request.source.bucket, correlation_id=correlation_id)
        await verify_source_object(client, request.source, correlation_id=correlation_id)
        presigned_url = str(
            await presign_url(client, request.source, correlation_id=correlation_id)
        )

        score = 1.0
        results = [
            SimilarResult(
                score=score,
                title="Uploaded screenshot",
                url=presigned_url,
                object=request.source,
            )
        ]

        top_k = request.top_k or len(results)
        response = SimilarResponse(results=results[:top_k])

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Similarity response ready",
            extra={
                "event": "backend.similar.response",
                "correlation_id": correlation_id,
                "status_code": status.HTTP_200_OK,
                "success": True,
                "duration_ms": round(duration_ms, 2),
                "results_count": len(response.results),
                "result_object_keys": [
                    result.object.object_key
                    for result in response.results
                    if result.object is not None
                ],
                "bucket": request.source.bucket,
            },
        )
        return response
    except HTTPException:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "Similarity request failed with HTTP error",
            extra={
                "event": "backend.similar.http_error",
                "correlation_id": correlation_id,
                "duration_ms": round(duration_ms, 2),
                "bucket": request.source.bucket,
                "object_key": request.source.object_key,
            },
        )
        raise
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "Unhandled error while processing similarity request",
            extra={
                "event": "backend.similar.unhandled_error",
                "correlation_id": correlation_id,
                "duration_ms": round(duration_ms, 2),
                "bucket": request.source.bucket,
                "object_key": request.source.object_key,
            },
        )
        raise


@app.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest and index screenshot",
    tags=["ingest"],
)
async def ingest_screen(
    request: IngestRequest,
    http_request: Request,
    settings: BackendSettings = Depends(get_settings),
    client=Depends(provide_minio_client),
) -> IngestResponse:
    correlation_id = http_request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    logger.info(
        "Received ingest request",
        extra={
            "event": "backend.ingest.request",
            "correlation_id": correlation_id,
            "bucket": request.source.bucket,
            "object_key": request.source.object_key,
        },
    )

    # Ensure buckets exist
    await ensure_bucket(client, request.source.bucket, correlation_id=correlation_id)
    await ensure_bucket(client, settings.minio_processed_bucket, correlation_id=correlation_id)

    # Fetch and process
    data = await fetch_object_bytes(client, request.source, correlation_id=correlation_id)
    try:
        processed_bytes, content_type, ext = process_image_bytes(data, target_width=585)
    except ValueError as exc:
        logger.warning(
            "Invalid image content during ingest",
            extra={
                "event": "backend.ingest.invalid_image",
                "correlation_id": correlation_id,
                "bucket": request.source.bucket,
                "object_key": request.source.object_key,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    processed_key = build_processed_key(request.source.object_key, ext)
    processed_ref = MinioObjectReference(bucket=settings.minio_processed_bucket, object_key=processed_key)

    await upload_object_bytes(
        client,
        processed_ref.bucket,
        processed_ref.object_key,
        processed_bytes,
        content_type,
        correlation_id=correlation_id,
    )

    # Embed processed image
    embed_response = await fetch_embedding(processed_ref, settings=settings, correlation_id=correlation_id)

    # Upsert to Qdrant
    payload = {
        "source_bucket": request.source.bucket,
        "source_key": request.source.object_key,
        "processed_bucket": processed_ref.bucket,
        "processed_key": processed_ref.object_key,
    }
    await upsert_vector_point(embed_response.vector, payload, settings=settings)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Ingest completed",
        extra={
            "event": "backend.ingest.completed",
            "correlation_id": correlation_id,
            "duration_ms": round(duration_ms, 2),
            "source_bucket": request.source.bucket,
            "source_key": request.source.object_key,
            "processed_bucket": processed_ref.bucket,
            "processed_key": processed_ref.object_key,
        },
    )

    return IngestResponse(
        processed=processed_ref,
        embedding_model=embed_response.model,
        embedding_dimension=embed_response.dimension,
    )
