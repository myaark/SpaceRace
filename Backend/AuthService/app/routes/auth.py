from fastapi import APIRouter

from app.controllers import auth as auth_controller  # noqa: F401

router = APIRouter(prefix="/auth", tags=["auth"])

# TODO: register, login, token refresh, JWT issuance/verification.
# Path operations here stay thin — call into app/controllers/auth.py for
# business logic and app/models/ for request/response/persistence shapes.
