from fastapi import Depends, FastAPI, HTTPException, status

from contracts.dto import HealthStatus, SimilarRequest, SimilarResponse, SimilarResult
from .config import BackendSettings, get_settings
from .storage import ensure_bucket, presign_url, provide_minio_client, verify_source_object

app = FastAPI(title="Similar Screens Backend")


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")


@app.post("/similar", response_model=SimilarResponse)
async def find_similar(
    request: SimilarRequest,
    settings: BackendSettings = Depends(get_settings),
    client=Depends(provide_minio_client),
) -> SimilarResponse:
    if request.source.bucket != settings.minio_user_bucket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bucket provided for similarity search",
        )

    await ensure_bucket(client, request.source.bucket)
    await verify_source_object(client, request.source)
    presigned_url = await presign_url(client, request.source)

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
    return SimilarResponse(results=results[:top_k])
