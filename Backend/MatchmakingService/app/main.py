from fastapi import FastAPI

from app.config import settings
from app.routers import matchmaking

app = FastAPI(title="Matchmaking Service")

app.include_router(matchmaking.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}
