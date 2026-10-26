
import logging
import time
from dataclasses import dataclass
from functools import lru_cache

from groq import APIError, Groq # type: ignore

from app.config import settings

logger = logging.getLogger(__name__)


class LLMNotConfigured(Exception):
    """GROQ_API_KEY is missing."""


class LLMUnavailable(Exception):
    """The provider failed, timed out, or rate limited us."""


@dataclass
class LLMReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


@lru_cache
def _client() -> Groq:
    if not settings.groq_api_key:
        raise LLMNotConfigured("GROQ_API_KEY is not set")
    return Groq(api_key=settings.groq_api_key, timeout=20.0, max_retries=0)

def chat(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    response_format: dict | None = None,
    reasoning_effort: str | None = None,
) -> LLMReply:
    client = _client()
    kwargs: dict = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort

    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(**kwargs)
    except APIError as exc:
        logger.exception("Groq call failed")
        raise LLMUnavailable("LLM provider call failed") from exc

    usage = resp.usage
    return LLMReply(
        content=resp.choices[0].message.content or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )