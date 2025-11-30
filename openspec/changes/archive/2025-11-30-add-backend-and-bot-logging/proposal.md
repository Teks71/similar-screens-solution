# Proposal: add-backend-and-bot-logging

## Why

The project currently has no explicit requirements for logging incoming requests, outgoing responses, and errors in the backend or Telegram bot.
Without structured logging it is difficult to debug failures, correlate behaviour across services, or understand how users interact with the system.

## What Changes

- Define logging requirements for the backend so that `/similar` requests and responses are logged, including the request body, basic metadata, and any errors with request context.
- Define logging requirements for the Telegram bot so that incoming updates (messages/photos) and outgoing responses (galleries and error messages) are logged, including message text and identifiers.
- Require both services to log errors in a way that captures contextual information (such as MinIO object references, backend endpoints, and Telegram chat/user identifiers) for both globally handled and locally handled exceptions.

