# tests/test_llm.py
from types import SimpleNamespace

import httpx
import pytest
from groq import APIConnectionError

from app.config import settings
from app.services import llm


class FakeCompletions:
    def __init__(self, resp=None, exc=None):
        self.resp = resp
        self.exc = exc
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return self.resp


def fake_client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def fake_response(text="hello", prompt=11, completion=7):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def test_chat_returns_text_tokens_and_latency(monkeypatch):
    completions = FakeCompletions(resp=fake_response("hi there", 11, 7))
    monkeypatch.setattr(llm, "_client", lambda: fake_client(completions))

    reply = llm.chat([{"role": "user", "content": "hello"}])

    assert reply.content == "hi there"
    assert reply.prompt_tokens == 11
    assert reply.completion_tokens == 7
    assert reply.latency_ms >= 0
    assert completions.kwargs["model"] == settings.groq_model


def test_provider_error_becomes_llm_unavailable(monkeypatch):
    request = httpx.Request("POST", "https://api.groq.com/test")
    completions = FakeCompletions(exc=APIConnectionError(request=request))
    monkeypatch.setattr(llm, "_client", lambda: fake_client(completions))

    with pytest.raises(llm.LLMUnavailable):
        llm.chat([{"role": "user", "content": "hello"}])


def test_missing_key_raises_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    llm._client.cache_clear()

    with pytest.raises(llm.LLMNotConfigured):
        llm.chat([{"role": "user", "content": "hello"}])


def test_optional_params_sent_only_when_set(monkeypatch):
    completions = FakeCompletions(resp=fake_response())
    monkeypatch.setattr(llm, "_client", lambda: fake_client(completions))
    msgs = [{"role": "user", "content": "hello"}]

    llm.chat(msgs)
    assert "response_format" not in completions.kwargs
    assert "reasoning_effort" not in completions.kwargs

    fmt = {"type": "json_object"}
    llm.chat(msgs, response_format=fmt, reasoning_effort="low")
    assert completions.kwargs["response_format"] == fmt
    assert completions.kwargs["reasoning_effort"] == "low"


from types import SimpleNamespace

from app.services import llm


def _fake_client(message):
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    create = lambda **kwargs: resp
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    ), create


def test_chat_parses_tool_calls(monkeypatch):
    msg = SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="get_job", arguments='{"job_id": 3}'),
        )],
    )
    client, _ = _fake_client(msg)
    monkeypatch.setattr(llm, "_client", lambda: client)

    reply = llm.chat([{"role": "user", "content": "x"}], tools=[{"type": "function"}])

    assert reply.tool_calls == [llm.ToolCall("call_1", "get_job", '{"job_id": 3}')]
    assert reply.as_message()["tool_calls"][0]["function"]["name"] == "get_job"


def test_chat_sends_tools_only_when_given(monkeypatch):
    seen = {}
    msg = SimpleNamespace(content="hi", tool_calls=None)
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )

    def create(**kwargs):
        seen.update(kwargs)
        return resp

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "_client", lambda: client)

    llm.chat([{"role": "user", "content": "x"}])
    assert "tools" not in seen
import httpx
from groq import BadRequestError


def _bad_request(text: str) -> BadRequestError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    resp = httpx.Response(400, request=req, json={"error": {"message": text}})
    return BadRequestError(text, response=resp, body=None)


def _client_raising(exc):
    def create(**kwargs):
        raise exc
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_tool_use_failed_is_its_own_error(monkeypatch):
    client = _client_raising(_bad_request("Error code: 400 - tool_use_failed"))
    monkeypatch.setattr(llm, "_client", lambda: client)

    with pytest.raises(llm.LLMToolCallRejected):
        llm.chat([{"role": "user", "content": "x"}])


def test_other_400_stays_generic(monkeypatch):
    client = _client_raising(_bad_request("Error code: 400 - something else"))
    monkeypatch.setattr(llm, "_client", lambda: client)

    with pytest.raises(llm.LLMUnavailable) as exc:
        llm.chat([{"role": "user", "content": "x"}])
    assert not isinstance(exc.value, llm.LLMToolCallRejected)

def test_chat_calls_provider_exactly_once(monkeypatch):
    calls = []
    msg = SimpleNamespace(content="hi", tool_calls=None)
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=msg)],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )

    def create(**kwargs):
        calls.append(kwargs)
        return resp

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "_client", lambda: client)

    llm.chat([{"role": "user", "content": "x"}])

    assert len(calls) == 1