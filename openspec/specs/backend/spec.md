# backend Specification

## Purpose
TBD - created by archiving change add-telegram-similar-gallery. Update Purpose after archive.
## Requirements
### Requirement: Similarity search endpoint accepts MinIO references
The backend MUST expose a POST `/similar` endpoint that reads a request pointing to a screenshot stored in MinIO.

#### Scenario: Accepts stored screenshot key
- **WHEN** a client sends `/similar` with a payload containing the MinIO bucket and object key for the source screenshot and an optional `top_k` limit
- **THEN** the service validates the payload using shared contract models and begins similarity lookup based on the referenced object

### Requirement: Similarity results are ordered and usable by clients
The backend MUST return matches with enough data for clients to fetch or display images and understand ranking.

#### Scenario: Returns sorted similar results
- **WHEN** similarity search produces matches
- **THEN** the response includes a list sorted by descending similarity score, and each match carries a retrievable URL or MinIO object key plus optional title/metadata

### Requirement: Clear errors for missing or inaccessible source objects
The backend MUST notify clients when the source screenshot cannot be read from MinIO.

#### Scenario: Reports missing object
- **WHEN** the referenced MinIO object cannot be fetched or is missing
- **THEN** `/similar` responds with an error payload explaining the missing object and does not return partial similarity results

### Requirement: Backend logs similarity requests and responses
The backend MUST log incoming `/similar` requests and the corresponding responses with enough detail to reconstruct the flow of a similarity search.

#### Scenario: Logs incoming similarity request body
- **WHEN** a client sends a POST `/similar` request
- **THEN** the backend logs the HTTP method, path, correlation or request identifier (when available), and the request body based on the shared contract model (excluding raw binary data)

#### Scenario: Logs similarity responses and latency
- **WHEN** the backend finishes processing a `/similar` request
- **THEN** it logs the response status code, an indicator of success or error, the total processing time, and high-level information about the similarity results (such as number of matches and their identifiers, not the image content itself)

### Requirement: Backend logs errors with request context
The backend MUST log errors with enough context to understand which request and operation failed.

#### Scenario: Logs unhandled exceptions with request context
- **WHEN** an unhandled exception occurs while processing `/similar`
- **THEN** the backend logs the error with stack trace and includes request context (HTTP method, path, correlation or request identifier, and referenced MinIO bucket/key when available) before returning an error response to the client

#### Scenario: Logs handled integration errors
- **WHEN** a handled error occurs while calling MinIO or performing similarity search (for example, missing or inaccessible source object)
- **THEN** the backend logs the error and its context (including the MinIO bucket/key and operation being performed) and still satisfies the requirement “Clear errors for missing or inaccessible source objects”

### Requirement: Backend exposes PostgreSQL dependency and configuration
The backend MUST be deployable with PostgreSQL via Docker Compose and accept environment variables that describe how to connect to the database.

#### Scenario: Compose provides PostgreSQL dependency
- **WHEN** the backend is started with the provided `docker-compose.yml`
- **THEN** the Compose file defines a `postgres` service with persistent storage, and the `backend` service lists both `qdrant` and `postgres` under `depends_on`.

#### Scenario: Backend reads PostgreSQL connection settings from environment
- **WHEN** the backend container starts
- **THEN** it receives PostgreSQL connection parameters (host, port, database, user, password, and optionally a full DSN) from environment variables defined in the deployment configuration.

#### Scenario: Backend initializes SQLAlchemy using env-supplied Postgres DSN
- **WHEN** the backend starts
- **THEN** it constructs an async SQLAlchemy engine/session using the Postgres DSN from environment variables, fails fast when configuration is missing, and successfully pings the database during startup.

### Requirement: Backend initializes Qdrant collection at startup
The backend MUST configure and initialize the Qdrant collection used to store screenshot vectors when the service starts.

#### Scenario: Creates or validates collection on startup
- **WHEN** the backend starts
- **THEN** it uses environment-provided Qdrant settings (URL, collection name, vector size/distance) to create the collection if missing, or validate it if it exists.

