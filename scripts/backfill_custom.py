"""
Backfill titles in Qdrant payloads from screens_meta.tsv.

- Reads screens_meta.tsv, builds a lookup by `src` with filename/title.
- Scrolls the Qdrant collection, matches points by payload.source_key == src.
- Updates payload.title when missing or different, without touching other fields or vectors.
- Logs progress with timestamps and reports points missing source_key.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from qdrant_client import QdrantClient


DEFAULT_TSV_PATH = Path("screens_meta.tsv")
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "screens"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ScreenMeta:
    src: str
    filename: str


def load_meta(tsv_path: Path, limit: int | None = None) -> dict[str, ScreenMeta]:
    lookup: dict[str, ScreenMeta] = {}
    with tsv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for idx, row in enumerate(reader, start=1):
            if limit is not None and idx > limit:
                break
            src = (row.get("src") or "").strip()
            filename = (row.get("filename") or "").strip()
            if not src:
                continue
            lookup[src] = ScreenMeta(src=src, filename=filename or src)
    return lookup


def count_points(client: QdrantClient, collection: str) -> int | None:
    try:
        res = client.count(collection_name=collection, exact=True)
        return getattr(res, "count", None) or res.count  # type: ignore[attr-defined]
    except Exception:
        return None


def iter_points(client: QdrantClient, collection: str, batch_size: int = 256) -> Iterable:
    offset = None
    while True:
        scroll_result = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=batch_size,
            with_vectors=False,
            with_payload=True,
        )
        if len(scroll_result) == 3:
            points, offset, _ = scroll_result
        else:
            points, offset = scroll_result
        for point in points:
            yield point
        if offset is None:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill payload.title in Qdrant from screens_meta.tsv")
    parser.add_argument("--tsv", type=Path, default=DEFAULT_TSV_PATH, help="Path to screens_meta.tsv")
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL, help="Qdrant URL")
    parser.add_argument("--qdrant-api-key", default=None, help="Qdrant API key")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Qdrant collection name")
    parser.add_argument("--batch-size", type=int, default=256, help="Scroll batch size")
    parser.add_argument("--limit-tsv", type=int, default=None, help="Optional row limit when loading TSV (for dry runs)")
    args = parser.parse_args()

    if not args.tsv.exists():
        raise SystemExit(f"TSV file not found: {args.tsv}")

    meta_lookup = load_meta(args.tsv, limit=args.limit_tsv)
    print(f"[{_now()}] Loaded {len(meta_lookup)} rows from {args.tsv}")

    client = QdrantClient(url=args.qdrant_url, api_key=args.qdrant_api_key)
    total_points = count_points(client, args.collection)
    if total_points is None:
        print(f"[{_now()}] Warning: failed to count points; progress will be approximate")

    updates = 0
    missing_source_key = 0
    missing_examples: list[str] = []
    processed = 0
    payload_updates: list[tuple[str | int, str]] = []

    def flush_updates() -> None:
        nonlocal updates
        if not payload_updates:
            return
        for pid, title in payload_updates:
            client.set_payload(
                collection_name=args.collection,
                payload={"title": title},
                points=[pid],
            )
        updates += len(payload_updates)
        payload_updates.clear()

    for point in iter_points(client, args.collection, batch_size=args.batch_size):
        processed += 1
        payload = point.payload or {}
        source_key = payload.get("source_key")
        if not source_key:
            missing_source_key += 1
            if len(missing_examples) < 5:
                missing_examples.append(str(getattr(point, "id", "unknown")))
            continue

        meta = meta_lookup.get(source_key)
        if meta is None:
            continue

        current_title = payload.get("title")
        if current_title == meta.filename:
            continue

        payload_updates.append((point.id, meta.filename))  # type: ignore[attr-defined]

        if len(payload_updates) >= args.batch_size:
            flush_updates()

        if processed % max(10, args.batch_size) == 0 or (total_points and processed == total_points):
            if total_points:
                pct = (processed / total_points) * 100
                print(f"[{_now()}] Progress: {processed}/{total_points} ({pct:.1f}%)")
            else:
                print(f"[{_now()}] Progress: processed {processed} points (total unknown)")

    flush_updates()

    print(
        f"[{_now()}] Completed. Processed: {processed}, updated titles: {updates}, "
        f"missing source_key: {missing_source_key}"
    )
    if missing_examples:
        print(f"[{_now()}] Examples of points without source_key: {', '.join(missing_examples)}")


if __name__ == "__main__":
    main()
