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


class EmbedRequest(BaseModel):
    source: MinioObjectReference


class EmbedResponse(BaseModel):
    model: str = Field(..., description="Identifier of the embedding model used")
    dimension: int = Field(..., description="Dimension of the embedding vector")
    vector: list[float] = Field(..., description="Embedding values in model order")


class IngestRequest(BaseModel):
    source: MinioObjectReference


class IngestResponse(BaseModel):
    processed: MinioObjectReference = Field(..., description="Reference to the processed image stored in MinIO")
    embedding_model: str = Field(..., description="Embedding model used for vectorization")
    embedding_dimension: int = Field(..., description="Dimension of the stored embedding vector")
