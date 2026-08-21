from fastapi import APIRouter

from app.controllers import players as players_controller  # noqa: F401

router = APIRouter(prefix="/players", tags=["players"])

# TODO: profile CRUD, persistent stats, cosmetic data.
# Path operations here stay thin — call into app/controllers/players.py for
# business logic and app/models/ for request/response/persistence shapes.
