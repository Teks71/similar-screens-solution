## 1. Specification
- [x] 1.1 Draft embedding-service requirements for GPU-enforced DINOv2 embeddings from MinIO images and error handling.
- [x] 1.2 Validate the change with `openspec validate add-embedding-service --strict`.

## 2. Implementation
- [x] 2.1 Add shared contract models for embedding request/response.
- [x] 2.2 Build the embedding FastAPI service with MinIO fetch, image validation, and DINOv2-base GPU inference endpoint.
- [x] 2.3 Wire configuration, Dockerfile, docker-compose entry, and env templates for the new service (GPU-ready).
- [x] 2.4 Add minimal logging/health checks or tests to verify startup and embedding vector shape.
