# Tasks for add-telegram-similar-gallery

- [ ] Define `/similar` request/response Pydantic models in `contracts` with MinIO object references and result metadata (URL or object key, similarity score, optional title).
- [ ] Implement FastAPI `/similar` POST endpoint in `backend-service` that accepts the contract request, pulls the source image from MinIO, invokes similarity search (stubbed if necessary), and returns sorted matches using the response contract.
- [ ] Add MinIO client configuration (endpoint, bucket, credentials) to backend settings and wire it into the similarity handler.
- [ ] Extend the Telegram bot to handle photo messages: download the best-quality photo, upload to MinIO with a unique key, call backend `/similar`, and return the results as a media group with descriptive captions and fallback error messages.
- [ ] Add configuration handling for the bot (MinIO credentials/bucket, backend base URL) plus simple health/start command updates and happy-path tests where feasible.
