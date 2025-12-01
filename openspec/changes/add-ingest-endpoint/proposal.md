# Change: Backend ingest endpoint for indexing screenshots

## Why
- Need a backend API to ingest screenshots from MinIO, preprocess them, embed via the embedding service, and index vectors in Qdrant.
- Downstream services require consistent preprocessing (grayscale/L-channel, resize to width 585) and storage of processed assets in a dedicated bucket.

## What Changes
- Add a POST endpoint to backend-service that fetches an image from MinIO (bucket/key), preprocesses it (L-channel/grayscale, 3-channel duplicate, resize width 585), saves the processed image to a separate MinIO bucket, and calls the embedding service for vectorization.
- Store resulting vectors in Qdrant with original bucket/key metadata and ensure collection initialization covers ingest use.
- Wire configuration for embedding service URL and processed-output bucket; log and validate failure cases.

## Impact
- Affected specs: backend
- Affected code: backend-service (new ingest endpoint, image pipeline, Qdrant insert), env/compose for embedding service URL and processed bucket
