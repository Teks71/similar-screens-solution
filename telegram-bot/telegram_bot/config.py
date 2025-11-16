import os
from dataclasses import dataclass
from functools import lru_cache


_BOOL_TRUE = {"1", "true", "yes", "on"}


def _bool_from_env(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in _BOOL_TRUE


@dataclass
class BotSettings:
    token: str
    backend_base_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_user_bucket: str
    minio_secure: bool = False
    default_top_k: int = 5

    @classmethod
    def from_env(cls) -> "BotSettings":
        missing = [
            env
            for env in [
                "TELEGRAM_BOT_TOKEN",
                "BACKEND_BASE_URL",
                "MINIO_ENDPOINT",
                "MINIO_ACCESS_KEY",
                "MINIO_SECRET_KEY",
                "MINIO_USER_BUCKET",
            ]
            if not os.getenv(env)
        ]

        if missing:
            raise RuntimeError(f"Missing required bot settings: {', '.join(sorted(missing))}")

        default_top_k = os.getenv("SIMILAR_TOP_K")
        top_k_value = int(default_top_k) if default_top_k else 5

        return cls(
            token=os.environ["TELEGRAM_BOT_TOKEN"],
            backend_base_url=os.environ["BACKEND_BASE_URL"],
            minio_endpoint=os.environ["MINIO_ENDPOINT"],
            minio_access_key=os.environ["MINIO_ACCESS_KEY"],
            minio_secret_key=os.environ["MINIO_SECRET_KEY"],
            minio_user_bucket=os.environ["MINIO_USER_BUCKET"],
            minio_secure=_bool_from_env("MINIO_SECURE", default=False),
            default_top_k=top_k_value,
        )


@lru_cache(maxsize=1)
def get_settings() -> BotSettings:
    return BotSettings.from_env()
