"""
Backfill Qdrant payload fields (source_bucket/title) using screens_meta.tsv.

Intended for restoring missing data needed by the backend/Telegram bot.
"""

import argparse
from pathlib import Path

from qdrant_client import QdrantClient


DEFAULT_TSV_PATH = Path("screens_meta.tsv")
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "screens"
DEFAULT_BUCKET = "screenoteka"


def load_titles(tsv_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with tsv_path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            object_key = parts[1].strip()
            if not object_key:
                continue
            title = parts[-2].strip() if len(parts) >= 2 else object_key
            if not title:
                title = Path(object_key).name
            mapping[object_key] = title
    return mapping


def main() -> None:
    # Fixed targets as requested
    tsv_path = DEFAULT_TSV_PATH
    qdrant_url = DEFAULT_QDRANT_URL
    qdrant_api_key = None
    collection = DEFAULT_COLLECTION
    source_bucket = DEFAULT_BUCKET

    if not tsv_path.exists():
        raise SystemExit(f"TSV not found: {tsv_path}")

    titles = load_titles(tsv_path)
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    updates = 0
    scanned = 0
    offset = None
    while True:
        scroll_result = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_vectors=False,
            with_payload=True,
        )
        if len(scroll_result) == 3:
            points, offset, _ = scroll_result
        else:
            points, offset = scroll_result

        for point in points:
            scanned += 1
            payload = point.payload or {}
            source_key = payload.get("source_key")
            needs_update = False
            patch: dict[str, str] = {}

            if not payload.get("source_bucket"):
                patch["source_bucket"] = source_bucket
                needs_update = True

            if not payload.get("title") and source_key:
                title = titles.get(source_key) or Path(source_key).name
                patch["title"] = title
                needs_update = True

            if needs_update and source_key:
                client.set_payload(collection_name=collection, payload=patch, points=[point.id])
                updates += 1

        if offset is None:
            break

    print(f"Scanned {scanned} points; updated {updates} with missing payload fields.")


if __name__ == "__main__":
    main()
