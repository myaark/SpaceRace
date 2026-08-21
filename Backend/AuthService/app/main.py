from fastapi import FastAPI

from app.config import settings
from app.routers import auth

app = FastAPI(title="Auth Service")

app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}
