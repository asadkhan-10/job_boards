
import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from groq import APIError, BadRequestError, Groq  # type: ignore

from app.config import settings

logger = logging.getLogger(__name__)


class LLMNotConfigured(Exception):
    """GROQ_API_KEY is missing."""


class LLMUnavailable(Exception):
    """The provider failed, timed out, or rate limited us."""

class LLMToolCallRejected(LLMUnavailable):
    """The model produced a tool call that failed the provider's schema check."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string from the model, not yet validated


@dataclass
class LLMReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict:
        """The assistant turn, in the shape the next request must carry."""
        msg: dict = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in self.tool_calls
            ]
        return msg

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
    tools: list[dict] | None = None,
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
    if tools:
        kwargs["tools"] = tools
    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(**kwargs)
    except BadRequestError as exc:
        if "tool_use_failed" in str(exc):
            logger.warning("Model produced an invalid tool call")  # no traceback: it contains user-derived text
            raise LLMToolCallRejected("invalid tool call from model") from exc
        logger.exception("Groq call failed")
        raise LLMUnavailable("LLM provider call failed") from exc
    except APIError as exc:
        logger.exception("Groq call failed")
        raise LLMUnavailable("LLM provider call failed") from exc

    msg = resp.choices[0].message
    tool_calls = [
        ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
        for tc in (getattr(msg, "tool_calls", None) or [])
    ]
    usage = resp.usage
    return LLMReply(
        content=msg.content or "",
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        latency_ms=int((time.perf_counter() - start) * 1000),
        tool_calls=tool_calls,
    )