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
    """

    def __init__(self) -> None:
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        self.minio_user_bucket = os.getenv("MINIO_USER_BUCKET") or os.getenv("MINIO_BUCKET")
        self.minio_secure = _bool_from_env("MINIO_SECURE", default=False)

        self.postgres_host = os.getenv("POSTGRES_HOST")
        self.postgres_port = os.getenv("POSTGRES_PORT")
        self.postgres_db = os.getenv("POSTGRES_DB")
        self.postgres_user = os.getenv("POSTGRES_USER")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD")
        self.postgres_url = os.getenv("POSTGRES_URL") or self._build_postgres_url()

        missing = [
            key
            for key, value in {
                "MINIO_ENDPOINT": self.minio_endpoint,
                "MINIO_ACCESS_KEY": self.minio_access_key,
                "MINIO_SECRET_KEY": self.minio_secret_key,
                "MINIO_USER_BUCKET": self.minio_user_bucket,
            }.items()
            if not value
        ]

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
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> BackendSettings:
    return BackendSettings()
