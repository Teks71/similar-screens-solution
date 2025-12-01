# embedding-service Specification

## Purpose
TBD - created by archiving change add-embedding-service. Update Purpose after archive.
## Requirements
### Requirement: Embed endpoint returns GPU DINOv2-base vectors for MinIO images
The embedding service SHALL expose a POST `/embed` endpoint that fetches a MinIO object by bucket/key, validates it as an image, and responds with a DINOv2-base embedding vector computed on GPU.

#### Scenario: Returns embedding for valid image reference
- **WHEN** a client posts JSON containing a MinIO bucket and object key for an accessible image
- **THEN** the service downloads the object using configured MinIO credentials, decodes it as an image, runs DINOv2-base on GPU, and returns HTTP 200 with the embedding vector (dimension 768) and model identifier.

#### Scenario: Rejects non-image content
- **WHEN** the referenced MinIO object is fetched but cannot be parsed as an image
- **THEN** the service responds with a 4xx error explaining the unsupported content and does not attempt model inference.

#### Scenario: Errors for missing or unreadable object
- **WHEN** MinIO reports that the requested bucket/key is missing or cannot be read
- **THEN** the service responds with a clear error (404 for missing, 5xx for upstream errors) and no embedding vector.

### Requirement: Embedding service enforces GPU availability for inference
The embedding service SHALL refuse to serve embed requests if a CUDA-capable GPU is unavailable or the DINOv2-base model cannot be loaded onto GPU.

#### Scenario: Startup fails without CUDA
- **WHEN** the service starts on a host without available CUDA devices
- **THEN** it fails fast (or reports unhealthy) with an explicit message instead of silently falling back to CPU.

#### Scenario: Health reflects model readiness
- **WHEN** the model fails to load onto GPU at startup
- **THEN** the `/health` endpoint indicates an error and the service logs the failure, preventing embed requests from succeeding.

### Requirement: MinIO access is configurable via environment
The embedding service SHALL read MinIO connection parameters from environment variables and optionally enforce an allowed bucket.

#### Scenario: Uses env-supplied MinIO credentials
- **WHEN** the service starts
- **THEN** it reads endpoint, credentials, and secure flag from environment variables and uses them for MinIO operations.

#### Scenario: Rejects requests to disallowed buckets when configured
- **WHEN** an embed request references a bucket that is not equal to the configured allowlisted bucket (when provided)
- **THEN** the service rejects the request with a client error before attempting to fetch the object.

