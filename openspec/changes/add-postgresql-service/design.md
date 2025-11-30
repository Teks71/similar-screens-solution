## Context
The deployment currently provisions Qdrant and MinIO but lacks a relational database. We need PostgreSQL available for future persistence and metadata while keeping configuration consistent across `.env` templates and Docker Compose.

## Goals / Non-Goals
- Goals: add a PostgreSQL service with persistent storage; define environment variables for backend DB connectivity; express backend dependencies on Qdrant and PostgreSQL in Compose.
- Non-Goals: schema design, migrations, or code-level database interactions.

## Decisions
- Use the official `postgres:16` image with a named volume for data durability in local/dev environments.
- Expose credentials via env vars (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, optional `POSTGRES_URL`) and pass them into the backend service.
- Keep backend wired to Qdrant; update `depends_on` to include both `qdrant` and `postgres` for clear startup ordering.

## Risks / Trade-offs
- Local developers must manage new env variables; mitigate by updating `.env.example` and documentation.
- Compose startup time increases slightly; acceptable for added capability.

## Migration Plan
1. Add PostgreSQL service and volume in `docker-compose.yml` with healthcheck.
2. Document/env-vars in `.env.example` and wire them into backend Compose environment.
3. Validate Compose up; no application code changes required yet.

## Open Questions
- Should we standardize on a full DSN vs discrete parameters for ORM clients? (default to both for flexibility)
