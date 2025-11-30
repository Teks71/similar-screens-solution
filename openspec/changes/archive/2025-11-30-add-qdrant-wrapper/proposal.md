# Change: Add Qdrant client wrapper and collection initialization

## Why
- The backend currently lacks a Qdrant client wrapper and startup initialization for the vector collection that will store screenshot embeddings.
- Without automated collection creation, deployments risk missing required indexes and schema.

## What Changes
- Introduce a Qdrant client wrapper configured via environment variables.
- Initialize the target Qdrant collection on backend startup (create if missing, validate schema).
- Ensure configuration and dependency wiring follow 12-factor patterns.

## Impact
- Affected specs: backend
- Affected code: backend configuration, Qdrant client module, app startup
