"""
Bulk ingest screenshots listed in screens_meta.tsv.

Reads object keys from the second column of the TSV, skips ones already indexed
in Qdrant (by payload.source_key), and sends ingest requests to the backend.
"""

import argparse
import asyncio
import csv
import os
from pathlib import Path
from typing import Iterable

import httpx
from qdrant_client import QdrantClient


DEFAULT_TSV_PATH = Path("screens_meta.tsv")
DEFAULT_BUCKET = "screenoteka"
DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "screens"


def iter_object_keys(tsv_path: Path) -> Iterable[str]:
    with tsv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            yield row[1].strip()


def load_existing_keys(qdrant_url: str, qdrant_api_key: str | None, collection: str) -> set[str]:
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    existing: set[str] = set()
    offset = None

    while True:
        scroll_result = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_vectors=False,
            with_payload=True,
        )
        # qdrant-client API changed: older server returns (points, next_offset), newer (points, next_offset, _)
        if len(scroll_result) == 3:
            points, offset, _ = scroll_result
        else:
            points, offset = scroll_result
        for point in points:
            payload = point.payload or {}
            source_key = payload.get("source_key")
            if isinstance(source_key, str):
                existing.add(source_key)
        if offset is None:
            break

    return existing


async def ingest_object(client: httpx.AsyncClient, backend_url: str, bucket: str, object_key: str) -> None:
    payload = {"source": {"bucket": bucket, "object_key": object_key}}
    resp = await client.post(f"{backend_url}/ingest", json=payload, timeout=120)
    resp.raise_for_status()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk ingest screenshots from screens_meta.tsv")
    parser.add_argument("--tsv", type=Path, default=DEFAULT_TSV_PATH, help="Path to screens_meta.tsv")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Source bucket name")
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL))
    parser.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--qdrant-api-key", default=os.environ.get("QDRANT_API_KEY"))
    parser.add_argument("--collection", default=os.environ.get("QDRANT_COLLECTION", DEFAULT_COLLECTION))
    parser.add_argument("--concurrency", type=int, default=4, help="Number of concurrent ingest requests")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit of rows to process")
    args = parser.parse_args()

    if not args.tsv.exists():
        raise SystemExit(f"TSV file not found: {args.tsv}")

    existing_keys = load_existing_keys(args.qdrant_url, args.qdrant_api_key, args.collection)
    print(f"Loaded {len(existing_keys)} existing points from Qdrant collection '{args.collection}'")

    object_keys: list[str] = []
    total_rows = 0
    skipped_existing = 0
    for key in iter_object_keys(args.tsv):
        total_rows += 1
        if args.limit is not None and len(object_keys) >= args.limit:
            break
        if not key:
            continue
        if key in existing_keys:
            skipped_existing += 1
            continue
        object_keys.append(key)
    print(f"Pending ingest: {len(object_keys)} objects (skipped {skipped_existing} already indexed; total rows read: {total_rows})")

    semaphore = asyncio.Semaphore(args.concurrency)
    total = len(object_keys)
    progress_every = 25 if total > 100 else 5
    completed = 0

    async with httpx.AsyncClient() as client:
        async def worker(k: str) -> None:
            nonlocal completed
            async with semaphore:
                await ingest_object(client, args.backend_url, args.bucket, k)
                completed += 1
                if completed % progress_every == 0 or completed == total:
                    pct = (completed / total) * 100 if total else 100
                    print(f"[{completed}/{total}] {pct:.1f}%")

        tasks = [asyncio.create_task(worker(k)) for k in object_keys]
        failures = 0
        for task in asyncio.as_completed(tasks):
            try:
                await task
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"✖ failed: {exc}")

    if failures:
        print(f"Completed with {failures} failures")
        raise SystemExit(1)
    print("Done")


if __name__ == "__main__":
    asyncio.run(main())
