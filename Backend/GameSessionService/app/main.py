from fastapi import FastAPI

from app.routes.game_session import router

app = FastAPI(title="Game Session Service")
app.include_router(router)
