## ADDED Requirements
### Requirement: Backend exposes PostgreSQL dependency and configuration
The backend MUST be deployable with PostgreSQL via Docker Compose and accept environment variables that describe how to connect to the database.

#### Scenario: Compose provides PostgreSQL dependency
- **WHEN** the backend is started with the provided `docker-compose.yml`
- **THEN** the Compose file defines a `postgres` service with persistent storage, and the `backend` service lists both `qdrant` and `postgres` under `depends_on`.

#### Scenario: Backend reads PostgreSQL connection settings from environment
- **WHEN** the backend container starts
- **THEN** it receives PostgreSQL connection parameters (host, port, database, user, password, and optionally a full DSN) from environment variables defined in the deployment configuration.
