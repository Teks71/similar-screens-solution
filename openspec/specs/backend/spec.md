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

