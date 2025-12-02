import asyncio
import logging
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.conversions import common_types
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.models import ScoredPoint

from .config import BackendSettings, get_settings


logger = logging.getLogger(__name__)

_qdrant_client: QdrantClient | None = None


def _distance_from_str(raw: str) -> Distance:
    normalized = raw.strip().upper()
    try:
        return Distance[normalized]
    except KeyError as exc:
        raise RuntimeError(
            f"Unsupported Qdrant distance '{raw}'. Use one of: {', '.join(Distance.__members__.keys())}"
        ) from exc


def get_qdrant_client(settings: Optional[BackendSettings] = None) -> QdrantClient:
    """Return a singleton Qdrant client configured from settings."""
    global _qdrant_client
    if _qdrant_client is None:
        settings = settings or get_settings()
        if not settings.qdrant_url:
            raise RuntimeError("QDRANT_URL is required to initialize Qdrant client")
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return _qdrant_client


async def init_qdrant_collection(settings: Optional[BackendSettings] = None) -> None:
    """Ensure Qdrant collection exists with expected vector params."""
    settings = settings or get_settings()
    client = get_qdrant_client(settings)
    distance = _distance_from_str(settings.qdrant_distance)
    vectors_config = VectorParams(size=settings.qdrant_vector_size, distance=distance)
    collection = settings.qdrant_collection

    try:
        exists = await asyncio.to_thread(client.collection_exists, collection)
    except Exception:
        logger.exception(
            "Failed to check Qdrant collection existence",
            extra={
                "event": "backend.qdrant.collection_check_failed",
                "collection": collection,
                "qdrant_url": settings.qdrant_url,
            },
        )
        raise

    if not exists:
        try:
            await asyncio.to_thread(
                client.create_collection,
                collection_name=collection,
                vectors_config=vectors_config,
            )
            logger.info(
                "Created Qdrant collection",
                extra={
                    "event": "backend.qdrant.collection_created",
                    "collection": collection,
                    "vector_size": settings.qdrant_vector_size,
                    "distance": settings.qdrant_distance,
                },
            )
        except Exception:
            logger.exception(
                "Failed to create Qdrant collection",
                extra={
                    "event": "backend.qdrant.collection_create_failed",
                    "collection": collection,
                    "vector_size": settings.qdrant_vector_size,
                    "distance": settings.qdrant_distance,
                },
            )
            raise
        return

    # Validate existing collection params
    try:
        info = await asyncio.to_thread(client.get_collection, collection)
    except UnexpectedResponse:
        logger.exception(
            "Failed to fetch existing Qdrant collection details",
            extra={
                "event": "backend.qdrant.collection_fetch_failed",
                "collection": collection,
            },
        )
        raise

    configured_vectors: common_types.VectorParams = info.config.params.vectors  # type: ignore[attr-defined]
    configured_size = getattr(configured_vectors, "size", None) or configured_vectors["size"]
    configured_distance = getattr(configured_vectors, "distance", None) or configured_vectors["distance"]

    if configured_size != settings.qdrant_vector_size or str(configured_distance).lower() != settings.qdrant_distance:
        logger.error(
            "Existing Qdrant collection has incompatible vector config",
            extra={
                "event": "backend.qdrant.collection_mismatch",
                "collection": collection,
                "expected_size": settings.qdrant_vector_size,
                "actual_size": configured_size,
                "expected_distance": settings.qdrant_distance,
                "actual_distance": str(configured_distance),
            },
        )
        raise RuntimeError(
            f"Qdrant collection '{collection}' has mismatched vector config: "
            f"size {configured_size} vs expected {settings.qdrant_vector_size}, "
            f"distance {configured_distance} vs expected {settings.qdrant_distance}"
        )

    logger.info(
        "Qdrant collection already exists with expected config",
        extra={
            "event": "backend.qdrant.collection_valid",
            "collection": collection,
            "vector_size": configured_size,
            "distance": str(configured_distance),
        },
    )


async def close_qdrant_client() -> None:
    global _qdrant_client
    if _qdrant_client is not None:
        try:
            _qdrant_client.close()
        finally:
            _qdrant_client = None


async def upsert_vector_point(
    vector: list[float],
    payload: dict,
    *,
    settings: Optional[BackendSettings] = None,
    point_id: str | int | None = None,
) -> None:
    client = get_qdrant_client(settings)
    settings = settings or get_settings()
    collection = settings.qdrant_collection

    # Use caller-provided ID when given; otherwise generate deterministic UUIDv5 from known keys
    if point_id is not None:
        resolved_id = point_id
    else:
        seed = payload.get("processed_key") or payload.get("source_key") or str(uuid.uuid4())
        resolved_id = str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

    point = rest.PointStruct(
        id=resolved_id,
        vector=vector,
        payload=payload,
    )
    try:
        await asyncio.to_thread(
            client.upsert,
            collection_name=collection,
            points=[point],
            wait=True,
        )
    except Exception:
        logger.exception(
            "Failed to upsert point into Qdrant",
            extra={
                "event": "backend.qdrant.upsert_failed",
                "collection": collection,
            },
        )
        raise


async def search_similar_points(
    vector: list[float],
    *,
    limit: int = 10,
    settings: Optional[BackendSettings] = None,
) -> list[ScoredPoint]:
    client = get_qdrant_client(settings)
    settings = settings or get_settings()
    collection = settings.qdrant_collection

    try:
        if hasattr(client, "search"):
            return await asyncio.to_thread(
                client.search,
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        # Fallback for client versions without .search
        response = await asyncio.to_thread(
            client.query_points,
            collection_name=collection,
            query=vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return response.points  # type: ignore[attr-defined]
    except Exception:
        logger.exception(
            "Failed to search similar points in Qdrant",
            extra={
                "event": "backend.qdrant.search_failed",
                "collection": collection,
            },
        )
        raise
