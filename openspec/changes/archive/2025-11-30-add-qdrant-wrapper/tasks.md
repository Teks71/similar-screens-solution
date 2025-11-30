## 1. Backend Qdrant Integration
- [x] 1.1 Add Qdrant env configuration (URL, API key optional, collection name, vector size/distance) and wire through Compose/env templates.
- [x] 1.2 Add Qdrant client wrapper to create/validate collection on startup.
- [x] 1.3 Hook startup/shutdown to init collection and close client resources; add minimal health/ping helper if needed.
