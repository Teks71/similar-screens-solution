## 1. Infrastructure
- [x] 1.1 Add PostgreSQL service to `docker-compose.yml` with volume, healthcheck, and configurable credentials/ports.
- [x] 1.2 Add backend database env vars (host, port, database, user, password, DSN) to `.env.example` and ensure Compose passes them through.
- [x] 1.3 Update backend Compose service to depend on `qdrant` and `postgres` and document the new dependency.
- [ ] 1.4 Verify Compose startup succeeds with the new services and document connection variables for local development.

## 2. Backend
- [x] 2.1 Add SQLAlchemy (async) and driver dependencies.
- [x] 2.2 Add backend DB configuration to build/require a Postgres DSN via env vars (12-factor).
- [x] 2.3 Create SQLAlchemy engine/session helpers and ping database on startup to validate connectivity.
