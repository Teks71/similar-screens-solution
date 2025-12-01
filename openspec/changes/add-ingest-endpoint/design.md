## Context
- Need a backend POST endpoint to ingest a screenshot referenced by MinIO bucket/key.
- Pipeline: fetch original from MinIO → convert to grayscale (prefer L-channel from LAB; fallback to standard grayscale) → duplicate channel to 3 channels → resize to width 585 preserving aspect ratio → store processed image in a dedicated bucket → request embedding service with processed bucket/key → index vector in Qdrant with original bucket/key metadata.
- Embedding service already available at a configurable URL; Qdrant collection exists but must contain new points with source metadata.

## Goals / Non-Goals
- Goals: deterministic preprocessing, GPU embedding via embedding-service, Qdrant insert with source bucket/key stored in payload, processed image persisted in MinIO.
- Non-Goals: batch ingest, CPU fallback for embedding, advanced validation beyond image/content checks, multi-format outputs.

## Decisions
- Use Pillow for image processing: convert to LAB, take L channel; if LAB unavailable, use `.convert("L")`; then stack into 3 channels by merging L three times. Resize with `Image.LANCZOS` to width 585, keeping aspect ratio.
- Save processed image (e.g., JPEG/PNG) to a dedicated MinIO bucket provided via env; keep original key or prefix for traceability.
- Call embedding-service via HTTP (env `EMBEDDING_SERVICE_URL`), send MinIO reference of processed object.
- Extend backend config for processed bucket and embedding service URL; reuse MinIO client; ensure Qdrant collection is initialized as before.
- Store original bucket/key in Qdrant payload along with processed bucket/key for retrieval/debug.

## Risks / Trade-offs
- Additional processing time (LAB/resize + upload/download); acceptable for single-item ingest.
- Image format conversions may introduce slight changes; acceptable for pipeline determinism.
- Dependency on embedding-service availability; handle HTTP errors gracefully.

## Open Questions
- Output image format (JPEG vs PNG); default to JPEG for size unless alpha present, else fallback to PNG.
- Should we enforce allowed source bucket? (follow existing validation or allow any configured) — default to configured user bucket check.
