from fastapi import APIRouter

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

# TODO: ingest match score events, maintain Redis sorted-set live rankings,
# persist historical results to PostgreSQL.
