# Change: Add PostgreSQL service for backend

## Why
- The stack currently runs without a relational database, but we need PostgreSQL available for future persistence.
- Docker Compose does not provision PostgreSQL or declare it as a backend dependency, and environment variables for database connectivity are absent.

## What Changes
- Add a PostgreSQL service to `docker-compose.yml` with persistent storage and configurable credentials.
- Extend backend environment configuration to include PostgreSQL connection parameters/DSN and document them in env templates.
- Update the backend service in Compose to depend on both `qdrant` and `postgres` so startup ordering is explicit.
- Integrate SQLAlchemy-based Postgres connectivity in the backend using 12-factor env configuration (async engine/session, startup ping).

## Impact
- Affected specs: backend
- Affected code: docker-compose.yml, .env.example (and related env templates), backend configuration
