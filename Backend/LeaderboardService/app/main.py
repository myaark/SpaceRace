from fastapi import FastAPI

from app.config import settings
from app.routers import leaderboard

app = FastAPI(title="Leaderboard Service")

app.include_router(leaderboard.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}
