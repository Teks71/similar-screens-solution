# telegram-bot Specification

## Purpose
TBD - created by archiving change add-telegram-similar-gallery. Update Purpose after archive.
## Requirements
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

### Requirement: Bot logs incoming updates
The Telegram bot MUST log incoming updates so that user interactions and bot behaviour can be reconstructed.

#### Scenario: Logs photo uploads and commands
- **WHEN** a user sends a photo or text command to the bot
- **THEN** the bot logs the update type, Telegram user and chat identifiers, and the message text or caption (when present)

### Requirement: Bot logs outgoing responses
The Telegram bot MUST log outgoing responses so that bot actions can be correlated with incoming updates.

#### Scenario: Logs media group responses
- **WHEN** the bot sends a media group with similar screenshots
- **THEN** it logs the chat identifier, the number of media items, and a reference to the triggering update (such as its message identifier)

#### Scenario: Logs error messages to users
- **WHEN** the bot sends a user-facing error message due to a failure in upload, MinIO access, backend call, or response parsing
- **THEN** it logs the chat identifier, the type of failure, and a reference to the triggering update

### Requirement: Bot logs errors with update context
The Telegram bot MUST log errors together with enough update context to understand what failed.

#### Scenario: Logs unhandled handler exceptions
- **WHEN** an unhandled exception occurs in a bot handler while processing an update
- **THEN** a global error handler logs the error with stack trace and includes update context (update type, user and chat identifiers, and message text or caption when present)

#### Scenario: Logs locally handled integration errors
- **WHEN** a handler catches an expected error while uploading to MinIO, calling the backend `/similar` endpoint, or formatting a gallery response
- **THEN** the bot logs the error and its context (including MinIO bucket/key or backend endpoint URL and HTTP status when available) in addition to sending a user-friendly error message as required by “Graceful user feedback on failure”

