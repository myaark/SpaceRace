from fastapi import FastAPI, WebSocket

from app.config import settings

app = FastAPI(title="Game Session Service")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name, "room_id": settings.room_id}


@app.websocket("/ws/{room_id}")
async def match_socket(websocket: WebSocket, room_id: str):
    await websocket.accept()
    # TODO: register connection with the match's game loop, relay inputs,
    # stream authoritative state broadcasts.
