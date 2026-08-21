from fastapi import APIRouter

router = APIRouter(prefix="/matchmaking", tags=["matchmaking"])

# TODO: queue join/leave, room assembly (2-10 players), signal Game Session
# Service to start a match, return session connection details.
