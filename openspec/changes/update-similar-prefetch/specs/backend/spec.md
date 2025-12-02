## ADDED Requirements
### Requirement: Similarity prefetch and deduplication are configurable
The backend SHALL control how many candidates are fetched and deduplicated for `/similar` via environment variables.

#### Scenario: Prefetch multiplier is applied
- **WHEN** `/similar` is called without an explicit `top_k`
- **THEN** the backend resolves the limit from `SIMILAR_TOP_K`
- **AND** fetches at least `SIMILAR_PREFETCH_MULTIPLIER` × that limit from the vector store before deduplication
- **AND** returns up to the requested number of unique results after deduplication

#### Scenario: Missing or invalid prefetch settings fail fast
- **WHEN** the backend starts without `SIMILAR_TOP_K` or `SIMILAR_PREFETCH_MULTIPLIER` set to a positive integer
- **THEN** the service fails to start with a clear configuration error instead of serving requests
