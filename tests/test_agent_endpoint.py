import copy
import json

import pytest

from app import models
from app.services import llm
from app.services.embeddings import EmbeddingError

from fastapi.testclient import TestClient

from app.main import app


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": copy.deepcopy(messages), **kwargs})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _reply(content="", tool_calls=None):
    return llm.LLMReply(
        content=content, prompt_tokens=10, completion_tokens=5,
        latency_ms=100, tool_calls=tool_calls or [],
    )


def _install(monkeypatch, script):
    fake = FakeLLM(script)
    monkeypatch.setattr(llm, "chat", fake)
    return fake


def _tool_messages(recorded_call):
    return [m for m in recorded_call["messages"] if m["role"] == "tool"]


def _apply(db, job_id, user_id):
    row = models.Application(job_id=job_id, candidate_id=user_id)
    db.add(row)
    db.flush()
    return row


URL = "/agent/chat"


def test_requires_login(client, monkeypatch):
    fake = _install(monkeypatch, [])

    res = client.post(URL, json={"message": "find me a job"})

    assert res.status_code == 401
    assert fake.calls == []


@pytest.mark.parametrize("body", [
    {"message": "x"},
    {"message": "a" * 301},
    {},
])
def test_input_is_validated_before_any_llm_call(candidate_client, monkeypatch, body):
    fake = _install(monkeypatch, [])

    res = candidate_client.post(URL, json=body)

    assert res.status_code == 422
    assert fake.calls == []


def test_plain_answer(candidate_client, monkeypatch):
    _install(monkeypatch, [_reply("Hello there")])

    res = candidate_client.post(URL, json={"message": "hello agent"})

    assert res.status_code == 200
    assert res.json() == {"answer": "Hello there", "tools_used": []}


def test_candidate_sees_only_own_applications(
    db, candidate_client, test_candidate, other_candidate, test_job, monkeypatch
):
    mine = _apply(db, test_job["id"], test_candidate["id"])
    _apply(db, test_job["id"], other_candidate.id)
    fake = _install(monkeypatch, [
        _reply(tool_calls=[llm.ToolCall("c1", "list_my_applications", "{}")]),
        _reply("You applied to one job."),
    ])

    res = candidate_client.post(URL, json={"message": "what have I applied to?"})

    assert res.status_code == 200
    assert res.json()["tools_used"] == ["list_my_applications"]
    (tool_msg,) = _tool_messages(fake.calls[1])
    ids = [a["application_id"] for a in json.loads(tool_msg["content"])["applications"]]
    assert ids == [mine.id]


def test_user_id_in_body_is_ignored(
    db, candidate_client, test_candidate, other_candidate, test_job, monkeypatch
):
    """Identity comes from the token. A user_id in the body must change nothing."""
    mine = _apply(db, test_job["id"], test_candidate["id"])
    _apply(db, test_job["id"], other_candidate.id)
    fake = _install(monkeypatch, [
        _reply(tool_calls=[llm.ToolCall("c1", "list_my_applications", "{}")]),
        _reply("done"),
    ])

    res = candidate_client.post(
        URL, json={"message": "what have I applied to?", "user_id": other_candidate.id}
    )

    assert res.status_code == 200
    (tool_msg,) = _tool_messages(fake.calls[1])
    ids = [a["application_id"] for a in json.loads(tool_msg["content"])["applications"]]
    assert ids == [mine.id]


def test_employer_cannot_reach_candidate_tool(employer_client, monkeypatch):
    fake = _install(monkeypatch, [
        _reply(tool_calls=[llm.ToolCall("c1", "list_my_applications", "{}")]),
        _reply("I can't do that."),
    ])

    res = employer_client.post(URL, json={"message": "show applications"})

    assert res.status_code == 200
    offered = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert "list_my_applications" not in offered
    (tool_msg,) = _tool_messages(fake.calls[1])
    assert json.loads(tool_msg["content"]) == {"error": "Unknown tool"}


@pytest.mark.parametrize("exc, detail", [
    (EmbeddingError("secret embedding text"), "Search is temporarily unavailable"),
    (llm.LLMUnavailable("secret provider text"), "The assistant is temporarily unavailable"),
    (llm.LLMNotConfigured("secret key text"), "The assistant is temporarily unavailable"),
    (llm.LLMToolCallRejected("secret generation text"), "The assistant is temporarily unavailable"),
])
def test_failures_become_generic_503(candidate_client, monkeypatch, exc, detail):
    def boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr("app.routers.agent.run_agent", boom)

    res = candidate_client.post(URL, json={"message": "find me a job"})

    assert res.status_code == 503
    assert detail in res.text
    assert "secret" not in res.text

def test_rate_limit_applies(candidate_client, rate_limit_on, monkeypatch):
    _install(monkeypatch, [_reply("ok")] * 10)

    statuses = [
        candidate_client.post(URL, json={"message": "hello agent"}).status_code
        for _ in range(10)
    ]

    assert statuses[0] == 200
    assert 429 in statuses




class _SetClientIP:
    """Test-only ASGI wrapper: takes the source IP from the X-Test-IP header.
    Works on any Starlette version, unlike TestClient(client=...)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            for key, value in scope["headers"]:
                if key == b"x-test-ip":
                    scope["client"] = (value.decode(), 5000)
        await self.inner(scope, receive, send)


def _client_from(ip, like):
    """Same user and DB override, different source IP."""
    c = TestClient(_SetClientIP(app))
    c.headers = {
        **c.headers,
        "Authorization": like.headers["Authorization"],
        "X-Test-IP": ip,
    }
    return c


MSG = {"message": "hello agent"}


def test_per_ip_limit_is_three_per_minute(candidate_client, rate_limit_on, monkeypatch):
    _install(monkeypatch, [_reply("ok")] * 10)

    statuses = [candidate_client.post(URL, json=MSG).status_code for _ in range(5)]

    assert statuses == [200, 200, 200, 429, 429]


def test_global_bucket_caps_all_callers(candidate_client, rate_limit_on, monkeypatch):
    _install(monkeypatch, [_reply("ok")] * 10)

    statuses = [
        _client_from(f"10.0.0.{i}", candidate_client).post(URL, json=MSG).status_code
        for i in range(7)
    ]

    assert statuses == [200] * 5 + [429, 429]


def test_abuser_does_not_lock_out_other_users(candidate_client, rate_limit_on, monkeypatch):
    """Locks in the decorator order: rejected requests must not drain the global bucket."""
    _install(monkeypatch, [_reply("ok")] * 10)
    abuser = _client_from("9.9.9.9", candidate_client)
    for _ in range(10):
        abuser.post(URL, json=MSG)

    other = _client_from("2.2.2.2", candidate_client)

    assert other.post(URL, json=MSG).status_code == 200