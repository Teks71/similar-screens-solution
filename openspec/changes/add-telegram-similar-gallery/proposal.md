# Proposal: Telegram bot similarity search flow

## Summary
Implement a Telegram bot flow that accepts user screenshots, uploads them to MinIO, requests similar screens from the backend `/similar` endpoint, and responds with an album of matching screenshots.

## Motivation
Users need a simple chat interface to request visually similar screens. The bot should orchestrate storage (MinIO) and backend inference so that users only interact through Telegram while the service handles uploads and retrieval automatically.

## Goals
- Accept photo messages and store the original image in MinIO with stable object naming.
- Call the backend `/similar` endpoint using contracts shared in `contracts`.
- Deliver a gallery of similar screenshots back to the user, including captions with similarity context.
- Provide error feedback when uploads or backend calls fail.

## Non-Goals
- Implementing the similarity algorithm itself beyond consuming the backend API.
- Persisting conversational context or user preferences beyond a single request.
- Building a web UI; scope is limited to the Telegram bot and supporting backend API surface.

## Proposed Changes
- Add contracts for the `/similar` request/response, including MinIO object references and result metadata (URLs, similarity scores, titles).
- Extend the backend FastAPI app with a `/similar` POST endpoint that reads MinIO-stored inputs, invokes similarity search (stubbed or delegated), and returns sorted results.
- Enhance the Telegram bot to accept photo uploads, store them to MinIO, call the backend with the stored object key, and send the resulting images as a media group with captions.
- Add configuration for MinIO (endpoint, bucket, credentials) and backend base URL to the bot and backend services.

## Open Questions
- What payload does the similarity engine expect beyond an object key (e.g., top-k limit)?
- Should bot messages include clickable links to the stored results or embed images via Telegram file uploads?
- Do we need authentication between the bot and backend beyond network-level access?
