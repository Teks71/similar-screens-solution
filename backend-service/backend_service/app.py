from fastapi import FastAPI
from contracts.dto import HealthStatus

app = FastAPI(title="Similar Screens Backend")

@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok")
