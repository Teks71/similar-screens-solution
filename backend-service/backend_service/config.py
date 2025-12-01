import os
from functools import lru_cache


_DEF_BOOL_TRUE = {"1", "true", "yes", "on"}


def _bool_from_env(key: str, default: bool = False) -> bool:
    raw_value = os.getenv(key)
    if raw_value is None:
        return default
    return raw_value.lower() in _DEF_BOOL_TRUE


class BackendSettings:
    """Backend configuration loaded from environment variables.

    `MINIO_USER_BUCKET` (or legacy `MINIO_BUCKET`) holds user-uploaded screenshots that
    are used to search for similar content. Additional buckets may be introduced for
    original or derived assets later, so this value specifically targets user uploads.

    PostgreSQL connection settings are sourced from env vars to comply with 12-factor
    configuration; a DSN may be provided directly or derived from individual parts.

    Qdrant connection settings are also sourced from env vars; collection parameters
    must be provided to allow startup initialization/validation.
    """

    def __init__(self) -> None:
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        self.minio_user_bucket = os.getenv("MINIO_USER_BUCKET") or os.getenv("MINIO_BUCKET")
        self.minio_processed_bucket = os.getenv("MINIO_PROCESSED_BUCKET")
        self.minio_secure = _bool_from_env("MINIO_SECURE", default=False)

        self.postgres_host = os.getenv("POSTGRES_HOST")
        self.postgres_port = os.getenv("POSTGRES_PORT")
        self.postgres_db = os.getenv("POSTGRES_DB")
        self.postgres_user = os.getenv("POSTGRES_USER")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD")
        self.postgres_url = os.getenv("POSTGRES_URL") or self._build_postgres_url()

        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION")
        self.qdrant_distance = os.getenv("QDRANT_DISTANCE", "cosine").lower()
        self.qdrant_vector_size = self._int_from_env("QDRANT_VECTOR_SIZE")

        self.embedding_service_url = os.getenv("EMBEDDING_SERVICE_URL")

        missing = [
            key
            for key, value in {
                "MINIO_ENDPOINT": self.minio_endpoint,
                "MINIO_ACCESS_KEY": self.minio_access_key,
                "MINIO_SECRET_KEY": self.minio_secret_key,
                "MINIO_USER_BUCKET": self.minio_user_bucket,
                "MINIO_PROCESSED_BUCKET": self.minio_processed_bucket,
                "QDRANT_URL": self.qdrant_url,
                "QDRANT_COLLECTION": self.qdrant_collection,
                "EMBEDDING_SERVICE_URL": self.embedding_service_url,
            }.items()
            if not value
        ]

        if not self.postgres_url:
            missing.append(
                "POSTGRES_URL or POSTGRES_HOST/POSTGRES_PORT/POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD"
            )

        if self.qdrant_vector_size is None:
            missing.append("QDRANT_VECTOR_SIZE (int)")

        if missing:
            raise RuntimeError(f"Missing required backend settings: {', '.join(sorted(missing))}")

    def _build_postgres_url(self) -> str | None:
        parts = (
            self.postgres_host,
            self.postgres_port,
            self.postgres_db,
            self.postgres_user,
            self.postgres_password,
        )
        if not all(parts):
            return None
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def _int_from_env(self, key: str) -> int | None:
        raw = os.getenv(key)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError as exc:
            raise RuntimeError(f"{key} must be an integer") from exc


@lru_cache(maxsize=1)
def get_settings() -> BackendSettings:
    return BackendSettings()
