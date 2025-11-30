from typing import Optional

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str


class MinioObjectReference(BaseModel):
    bucket: str = Field(..., description="MinIO bucket name")
    object_key: str = Field(..., description="Key of the stored object inside the bucket")


class SimilarRequest(BaseModel):
    source: MinioObjectReference
    top_k: Optional[int] = Field(
        default=None,
        description="Maximum number of similar items to return; backend may apply a default",
    )


class SimilarResult(BaseModel):
    score: float = Field(..., description="Similarity score in descending order")
    title: Optional[str] = Field(default=None, description="Optional human-friendly title for the match")    
    url: Optional[str] = Field(
        default=None,
        description="Directly retrievable URL for the similar object",
    )
    object: Optional[MinioObjectReference] = Field(
        default=None,
        description="MinIO reference for the similar object",
    )


class SimilarResponse(BaseModel):
    results: list[SimilarResult]
