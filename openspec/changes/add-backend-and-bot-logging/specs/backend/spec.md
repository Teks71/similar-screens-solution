## ADDED Requirements

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

