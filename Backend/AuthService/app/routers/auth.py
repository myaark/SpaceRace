from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

# TODO: register, login, token refresh, JWT issuance/verification.
