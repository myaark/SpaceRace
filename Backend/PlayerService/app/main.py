from fastapi import FastAPI

from app.config import settings
from app.routers import players

app = FastAPI(title="Player Service")

app.include_router(players.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}
