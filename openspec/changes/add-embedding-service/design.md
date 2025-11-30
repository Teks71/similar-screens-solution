## Context
- We need a GPU-first FastAPI service that turns MinIO-stored screenshots into embeddings using the DINOv2-base model.
- The service must pull objects from MinIO, validate that the payload is an image, and return the vector so downstream similarity search can consume it.
- Existing components already use shared Pydantic contracts and MinIO; we should follow the same patterns for configuration and logging.

## Goals / Non-Goals
- Goals: GPU-only inference with DINOv2-base, MinIO fetch/validation, clear API contract for request/response, containerized service that fits the current docker-compose stack.
- Non-Goals: CPU fallback, multi-model routing, batching/queueing, persistence of embeddings.

## Decisions
- FastAPI + shared `contracts` models for request/response; keep handler async while running blocking I/O/inference in threads.
- Use `timm` + `torch` to load `dinov2_vitb14` pretrained with `num_classes=0` and `global_pool="token"` to get a 768-dim embedding; run `model.to(torch.device("cuda"))` at startup and fail fast if CUDA is unavailable.
- Derive preprocessing from `timm.data.create_transform` resolved from the model config; open images with Pillow, force RGB, and reject non-image payloads with a 400-level error.
- Reuse MinIO client wiring similar to backend: credentials/endpoint from env, optional allowed bucket check via env, presigned URL not required—download object bytes directly.
- Provide `/embed` endpoint returning the vector and model metadata (name/dimension) for traceability; include `/health` for readiness once CUDA/model is loaded.
- Update docker-compose with a GPU-ready service entry and root workspace to include the package; document GPU requirement in env template.
- We can accept any bucket in minio

## Risks / Trade-offs
- CUDA-only startup will fail on hosts without GPU drivers; mitigated by clear error and health behavior.
- Model download (~hundreds of MB) requires network/cache; rely on runtime availability and document the expectation.
- In-memory buffering of images is simple but can spike memory for very large objects; acceptable for initial scope.

## Migration Plan
- Add contracts, service package, and compose wiring in one change; no data migration required.
- Validate with `openspec validate add-embedding-service --strict` and manual health check once built.

