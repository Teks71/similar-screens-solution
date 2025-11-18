import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status

from contracts.dto import HealthStatus, SimilarRequest, SimilarResponse, SimilarResult
from .config import BackendSettings, get_settings
from .storage import ensure_bucket, presign_url, provide_minio_client, verify_source_object

app = FastAPI(title="Similar Screens Backend")
logger = logging.getLogger(__name__)


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


@app.post("/similar", response_model=SimilarResponse)
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
        presigned_url = await presign_url(client, request.source, correlation_id=correlation_id)

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
