## ADDED Requirements
### Requirement: Backend ingests and indexes processed screenshots
The backend SHALL expose a POST endpoint to ingest a screenshot from MinIO, preprocess it to a normalized format, embed it via the embedding service, and store the vector in Qdrant along with source metadata.

#### Scenario: Ingests image and writes processed copy
- **WHEN** a client posts a MinIO bucket/key for an image to the ingest endpoint
- **THEN** the backend downloads the object, converts it to grayscale (L-channel from LAB or equivalent), duplicates the single channel to three channels, resizes the image to width 585 while preserving aspect ratio, and stores the processed image in a configured MinIO bucket with a deterministic key.

#### Scenario: Embeds processed image via embedding service
- **WHEN** preprocessing succeeds
- **THEN** the backend calls the embedding service with the processed MinIO reference, receives a 768-dim embedding, and proceeds only on success; otherwise it returns a clear error.

#### Scenario: Indexes vector in Qdrant with source metadata
- **WHEN** an embedding is obtained
- **THEN** the backend inserts a point into Qdrant containing the vector and payload that includes the original bucket/key (and the processed bucket/key) so the source can be traced.

#### Scenario: Validates source object availability
- **WHEN** the source MinIO object is missing or unreadable
- **THEN** the ingest endpoint responds with an error (404 for missing, 5xx for upstream issues) and does not attempt embedding or indexing.

#### Scenario: Rejects invalid image content
- **WHEN** the fetched object is not a valid image
- **THEN** the ingest endpoint responds with 4xx and skips embedding/indexing.

#### Scenario: Logs ingest steps and failures
- **WHEN** ingest requests are handled
- **THEN** the backend logs key steps (fetch, preprocess, upload processed, embed call, Qdrant insert) and any errors with correlation/request identifiers and referenced bucket/key values.

### Requirement: Backend config supports embedding and processed storage
The backend SHALL read configuration for the embedding service URL and the MinIO bucket used for processed images, and ensure the Qdrant collection is initialized for ingest use.

#### Scenario: Uses env-configured embedding service URL
- **WHEN** the backend starts
- **THEN** it reads the embedding service base URL from environment variables and uses it for embed calls during ingest.

#### Scenario: Uses env-configured processed image bucket
- **WHEN** preprocessing completes
- **THEN** the backend writes the processed image to the MinIO bucket configured via environment and uses that reference for embedding.

#### Scenario: Initializes/validates Qdrant collection for ingest
- **WHEN** the backend starts
- **THEN** it ensures the Qdrant collection is created/validated (size/distance) so ingest inserts succeed without runtime schema errors.
