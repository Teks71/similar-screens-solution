## 1. Specification
- [x] 1.1 Add backend requirements for ingest endpoint (preprocess, store processed image, embed via embedding service, index in Qdrant).
- [x] 1.2 Validate change with `openspec validate add-ingest-endpoint --strict`.

## 2. Implementation
- [x] 2.1 Add backend config/env for embedding service URL and processed output bucket; update compose/env templates.
- [x] 2.2 Implement image preprocessing pipeline (LAB/gray L-channel → 3-channel, resize width 585) with MinIO fetch/store.
- [x] 2.3 Call embedding service with processed MinIO reference, persist vector + metadata (bucket/key) to Qdrant; ensure collection init covers ingest.
- [x] 2.4 Add API endpoint, contracts wiring (if needed), logging, and minimal tests/smoke script if feasible.
