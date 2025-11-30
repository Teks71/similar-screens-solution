## ADDED Requirements
### Requirement: Backend initializes Qdrant collection at startup
The backend MUST configure and initialize the Qdrant collection used to store screenshot vectors when the service starts.

#### Scenario: Creates or validates collection on startup
- **WHEN** the backend starts
- **THEN** it uses environment-provided Qdrant settings (URL, collection name, vector size/distance) to create the collection if missing, or validate it if it exists.
