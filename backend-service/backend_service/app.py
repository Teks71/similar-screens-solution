import logging
import time
import uuid
from pathlib import Path

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
    provide_minio_client,
    verify_source_object,
)
from .embed_client import fetch_embedding
from .qdrant import upsert_vector_point, search_similar_points
from .pipeline import ImageProcessingPipeline

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

    pipeline = ImageProcessingPipeline(client)

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

        # Preprocess query image and store in dedicated bucket
        try:
            query_processed_ref, _ = await pipeline.preprocess_and_store(
                request.source,
                settings.minio_query_bucket,
                correlation_id=correlation_id,
            )
        except HTTPException:
            raise

        # Embed processed query image
        embed_response = await fetch_embedding(
            query_processed_ref, settings=settings, correlation_id=correlation_id
        )

        # Search for nearest neighbors
        limit = request.top_k or 10
        scored_points = await search_similar_points(embed_response.vector, limit=limit, settings=settings)

        results: list[SimilarResult] = []
        for point in scored_points:
            payload = point.payload or {}
            source_key = payload.get("source_key")
            source_bucket = payload.get("source_bucket")
            title = payload.get("title") or (Path(source_key).name if source_key else None)

            if not source_key:
                continue

            cdn_url = settings.cdn_url_template.format(key=source_key)
            object_ref = None
            if source_bucket:
                object_ref = MinioObjectReference(bucket=source_bucket, object_key=source_key)

            results.append(
                SimilarResult(
                    score=point.score,
                    title=title,
                    url=cdn_url,
                    object=object_ref,
                )
            )

        response = SimilarResponse(results=results)

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

    pipeline = ImageProcessingPipeline(client)

    logger.info(
        "Received ingest request",
        extra={
            "event": "backend.ingest.request",
            "correlation_id": correlation_id,
            "bucket": request.source.bucket,
            "object_key": request.source.object_key,
        },
    )

    try:
        processed_ref, _content_type = await pipeline.preprocess_and_store(
            request.source,
            settings.minio_processed_bucket,
            correlation_id=correlation_id,
        )
    except HTTPException:
        # Already logged inside pipeline
        raise

    # Embed processed image
    embed_response = await fetch_embedding(processed_ref, settings=settings, correlation_id=correlation_id)

    # Upsert to Qdrant
    payload = {
        "source_bucket": request.source.bucket,
        "source_key": request.source.object_key,
        "processed_bucket": processed_ref.bucket,
        "processed_key": processed_ref.object_key,
        "title": ImageProcessingPipeline.derive_title(request.source.object_key),
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
