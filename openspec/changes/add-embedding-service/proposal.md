# Change: GPU-based embedding service for MinIO screenshots

## Why
- Need a dedicated API that turns stored screenshots into embeddings using the DINOv2-base model on GPU.
- Downstream services require a reliable way to fetch MinIO objects, validate they are images, and obtain vectors for similarity workflows.

## What Changes
- Add a FastAPI service that pulls objects from MinIO, verifies image content, and returns DINOv2-base embeddings computed on GPU.
- Wire configuration for MinIO access and GPU enforcement, including health/startup checks for CUDA availability.
- Provide container/workspace wiring so the service can be built and run alongside existing components.

## Impact
- Affected specs: embedding-service
- Affected code: new embedding-service package, shared contracts for embed request/response models, docker-compose/env templates, root workspace config
