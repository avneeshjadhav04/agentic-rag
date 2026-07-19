"""Configuration endpoints for the Agentic RAG backend."""
from fastapi import APIRouter

from app.config.providers import get_provider_list

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/providers")
def get_providers():
    return {"providers": get_provider_list()}
