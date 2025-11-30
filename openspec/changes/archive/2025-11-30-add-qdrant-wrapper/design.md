## Context
We need to ensure a Qdrant collection exists for screenshot vectors and is configured consistently across environments. Currently the backend has no Qdrant client wrapper or startup initialization.

## Goals / Non-Goals
- Goals: add Qdrant client wrapper with env-based configuration; initialize (create/validate) the collection at startup; keep 12-factor configuration.
- Non-Goals: defining vector ingestion/query logic; schema migrations beyond collection creation; performance tuning of Qdrant.

## Decisions
- Use `qdrant-client` with environment variables for URL, API key (optional), collection name, vector size, and distance metric.
- Initialize collection on startup: create if missing; if present, validate vector params to fail fast on mismatch.
- Keep collection parameters minimal (size, distance; optionally payload index default).

## Risks / Trade-offs
- Mismatched vector size/distance across environments will fail startup; this is acceptable to surface misconfiguration early.
- Qdrant availability at startup is required; mitigate with Compose `depends_on` (already present) and clear errors.

## Migration Plan
1. Add env variables and compose wiring for Qdrant settings.
2. Implement Qdrant client module with create/validate logic.
3. Hook app startup/shutdown to initialize and close the client.
