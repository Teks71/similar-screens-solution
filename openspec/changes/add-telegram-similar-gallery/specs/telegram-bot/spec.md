## ADDED Requirements

### Requirement: Bot handles photo uploads and stores them in MinIO
The Telegram bot MUST accept user photo messages, pick the best-quality version, and upload it to MinIO with a unique key.

#### Scenario: Uploads incoming screenshot
- **WHEN** a user sends a photo to the bot
- **THEN** the bot downloads the highest-resolution variant, saves it to the configured MinIO bucket with a deterministic key, and keeps the object reference for downstream calls

### Requirement: Bot requests similar screens from backend
After storing the screenshot, the bot MUST request similarity results from the backend `/similar` endpoint using contract models.

#### Scenario: Requests similarity for uploaded image
- **WHEN** the upload succeeds
- **THEN** the bot calls `/similar` with the stored object reference (bucket/key) and optional `top_k`, and handles timeouts or HTTP errors with a user-friendly failure message

### Requirement: Bot returns gallery of similar screenshots
The bot MUST send users a gallery of the returned matches with context on relevance.

#### Scenario: Sends media group with captions
- **WHEN** the backend responds with similar screenshots
- **THEN** the bot replies with a media group of the result images (using URLs or downloaded content), ordered by similarity, and captions each item with title and score when available

### Requirement: Graceful user feedback on failure
The bot MUST inform users when uploads or similarity requests fail.

#### Scenario: Notifies about processing errors
- **WHEN** MinIO upload, backend call, or response parsing fails
- **THEN** the bot sends a clear error message explaining the failure and suggests retrying later
