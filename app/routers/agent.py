from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from app import models, oauth2, schemas
from app.database import get_db
from app.limiter import limiter
from app.services.agent import run_agent
from app.services.embeddings import EmbeddingError
from app.services.llm import LLMNotConfigured, LLMUnavailable

router = APIRouter(prefix="/agent", tags=["Agent"])

PER_IP_LIMIT = "3/minute;30/day"
GLOBAL_LIMIT = "5/minute;100/day"  # shared by all callers, protects the Groq quota


def _global_key(request: Request) -> str:
    return "agent-global"


@router.post("/chat", response_model=schemas.AgentChatResponse)
# ORDER MATTERS: slowapi checks the decorator closest to the function first.
# Per-IP must stay below the global one, so a request rejected by its own IP
# limit never uses up the shared bucket.
@limiter.limit(GLOBAL_LIMIT, key_func=_global_key)
@limiter.limit(PER_IP_LIMIT)
def agent_chat(
    request: Request,
    body: schemas.AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        result = run_agent(db, current_user, body.message)
    except EmbeddingError as e:
        logger.error(f"agent embedding failed: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )
    except (LLMUnavailable, LLMNotConfigured) as e:
        logger.error(f"agent answer failed: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The assistant is temporarily unavailable",
        )

    return {"answer": result.answer, "tools_used": result.tools_used}