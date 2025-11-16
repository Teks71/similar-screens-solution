## ADDED Requirements

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

