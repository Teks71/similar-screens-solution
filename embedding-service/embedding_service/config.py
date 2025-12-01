import os
from functools import lru_cache


_DEF_BOOL_TRUE = {"1", "true", "yes", "on"}


def _bool_from_env(key: str, default: bool = False) -> bool:
    raw_value = os.getenv(key)
    if raw_value is None:
        return default
    return raw_value.lower() in _DEF_BOOL_TRUE


class EmbeddingSettings:
    """Configuration for the embedding service."""

    def __init__(self) -> None:
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        self.minio_secure = _bool_from_env("MINIO_SECURE", default=False)
        self.minio_allowed_bucket = os.getenv("MINIO_ALLOWED_BUCKET")

        self.device = os.getenv("EMBEDDING_DEVICE", "cuda")
        self.model_name = os.getenv("EMBEDDING_MODEL_NAME", "vit_base_patch14_dinov2")

        missing = [
            key
            for key, value in {
                "MINIO_ENDPOINT": self.minio_endpoint,
                "MINIO_ACCESS_KEY": self.minio_access_key,
                "MINIO_SECRET_KEY": self.minio_secret_key,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required embedding settings: {', '.join(sorted(missing))}")


@lru_cache(maxsize=1)
def get_settings() -> EmbeddingSettings:
    return EmbeddingSettings()
