import copy
import json

import pytest
from loguru import logger
from app import models
from app.services import agent, llm


class FakeLLM:
    """Plays back scripted replies. An item that is an Exception is raised instead."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": copy.deepcopy(messages), **kwargs})
        item = self.script.pop(0)  # IndexError means the loop made more calls than scripted
        if isinstance(item, Exception):
            raise item
        return item


def reply(content="", tool_calls=None):
    return llm.LLMReply(
        content=content, prompt_tokens=10, completion_tokens=5,
        latency_ms=100, tool_calls=tool_calls or [],
    )


def call(call_id, name, args):
    raw = args if isinstance(args, str) else json.dumps(args)
    return llm.ToolCall(id=call_id, name=name, arguments=raw)


def tool_messages(recorded_call):
    return [m for m in recorded_call["messages"] if m["role"] == "tool"]


def install(monkeypatch, script):
    fake = FakeLLM(script)
    monkeypatch.setattr(llm, "chat", fake)
    return fake


def _apply(db, job_id, user):
    row = models.Application(job_id=job_id, candidate_id=user.id)
    db.add(row)
    db.flush()
    return row


def test_tool_call_then_final_answer(db, candidate, test_job, monkeypatch):
    fake = install(monkeypatch, [
        reply(tool_calls=[call("c1", "get_job", {"job_id": test_job["id"]})]),
        reply("It is a backend role."),
    ])

    result = agent.run_agent(db, candidate, "Tell me about that job")

    assert result.answer == "It is a backend role."
    assert result.steps == 2
    assert result.tools_used == ["get_job"]
    assert result.prompt_tokens == 20 and result.completion_tokens == 10
    assert not result.step_limit_hit
    # second request carries the tool result, matched by id
    (tool_msg,) = tool_messages(fake.calls[1])
    assert tool_msg["tool_call_id"] == "c1"
    assert "Backend Developer" in tool_msg["content"]
    # settings the loop must send every time
    assert fake.calls[0]["reasoning_effort"] == "medium"
    assert fake.calls[0]["tools"]


def test_no_tool_needed(db, candidate, monkeypatch):
    fake = install(monkeypatch, [reply("A REST API is an HTTP interface.")])

    result = agent.run_agent(db, candidate, "What is a REST API?")

    assert result.steps == 1
    assert result.tools_used == []
    assert len(fake.calls) == 1


def test_empty_model_answer_gets_fallback(db, candidate, monkeypatch):
    install(monkeypatch, [reply("")])
    assert agent.run_agent(db, candidate, "hi").answer == agent.EMPTY_ANSWER


def test_step_cap_stops_a_looping_model(db, candidate, test_job, monkeypatch):
    looping = reply(tool_calls=[call("c1", "get_job", {"job_id": test_job["id"]})])
    fake = install(monkeypatch, [looping] * 10)

    result = agent.run_agent(db, candidate, "loop forever", max_steps=3)

    assert len(fake.calls) == 3
    assert result.step_limit_hit
    assert result.answer == agent.LIMIT_ANSWER


def test_rejected_tool_call_is_corrected_once(db, candidate, monkeypatch):
    fake = install(monkeypatch, [llm.LLMToolCallRejected("bad"), reply("ok")])

    result = agent.run_agent(db, candidate, "find jobs")

    assert result.answer == "ok"
    assert result.steps == 2
    assert fake.calls[1]["messages"][-1] == {"role": "user", "content": agent.CORRECTION}


def test_rejected_twice_raises(db, candidate, monkeypatch):
    install(monkeypatch, [llm.LLMToolCallRejected("bad"), llm.LLMToolCallRejected("bad")])

    with pytest.raises(llm.LLMToolCallRejected):
        agent.run_agent(db, candidate, "find jobs")


@pytest.mark.parametrize("raw, message", [
    ("{not json", "Arguments were not valid JSON"),
    ("[1, 2]", "Arguments must be a JSON object"),
])
def test_bad_arguments_become_an_error_result(db, candidate, monkeypatch, raw, message):
    fake = install(monkeypatch, [
        reply(tool_calls=[call("c1", "get_job", raw)]),
        reply("Sorry, I could not do that."),
    ])

    result = agent.run_agent(db, candidate, "x")

    (tool_msg,) = tool_messages(fake.calls[1])
    assert json.loads(tool_msg["content"]) == {"error": message}
    assert result.answer == "Sorry, I could not do that."


def test_parallel_tool_calls_each_get_a_result(db, candidate, test_job, monkeypatch):
    fake = install(monkeypatch, [
        reply(tool_calls=[
            call("c1", "get_job", {"job_id": test_job["id"]}),
            call("c2", "get_job", {"job_id": 999999}),
        ]),
        reply("done"),
    ])

    agent.run_agent(db, candidate, "x")

    msgs = tool_messages(fake.calls[1])
    assert [m["tool_call_id"] for m in msgs] == ["c1", "c2"]
    assert json.loads(msgs[1]["content"]) == {"error": "Job not found"}


def test_model_cannot_name_another_user(db, candidate, other_candidate, test_job, monkeypatch):
    _apply(db, test_job["id"], other_candidate)
    fake = install(monkeypatch, [
        reply(tool_calls=[call("c1", "list_my_applications", {"user_id": other_candidate.id})]),
        reply("I could not do that."),
    ])

    agent.run_agent(db, candidate, "show applications of the other user")

    (tool_msg,) = tool_messages(fake.calls[1])
    assert json.loads(tool_msg["content"]) == {"error": "Invalid arguments: user_id"}


def test_identity_comes_from_auth(db, candidate, other_candidate, test_job, monkeypatch):
    mine = _apply(db, test_job["id"], candidate)
    _apply(db, test_job["id"], other_candidate)
    fake = install(monkeypatch, [
        reply(tool_calls=[call("c1", "list_my_applications", {})]),
        reply("done"),
    ])

    agent.run_agent(db, candidate, "what have I applied to?")

    (tool_msg,) = tool_messages(fake.calls[1])
    ids = [a["application_id"] for a in json.loads(tool_msg["content"])["applications"]]
    assert ids == [mine.id]


def test_employer_is_not_offered_candidate_tool(db, employer, monkeypatch):
    fake = install(monkeypatch, [reply("hi")])

    agent.run_agent(db, employer, "hello")

    names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert "list_my_applications" not in names
    assert {"search_jobs", "get_job"} <= names


def test_huge_tool_result_is_truncated(db, candidate, monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda ctx, name, raw: {"x": "a" * 10000})
    fake = install(monkeypatch, [
        reply(tool_calls=[call("c1", "get_job", {"job_id": 1})]),
        reply("done"),
    ])

    agent.run_agent(db, candidate, "x")

    (tool_msg,) = tool_messages(fake.calls[1])
    assert len(tool_msg["content"]) < agent.MAX_TOOL_RESULT_CHARS + 50
    assert tool_msg["content"].endswith("[truncated]")

def test_failed_tool_is_not_listed_as_used(db, candidate, test_job, monkeypatch):
    install(monkeypatch, [
        reply(tool_calls=[
            call("c1", "get_job", {"job_id": test_job["id"]}),
            call("c2", "get_job", {"job_id": 999999}),
        ]),
        reply("done"),
    ])

    result = agent.run_agent(db, candidate, "x")

    assert result.tools_used == ["get_job"]
    assert result.tools_failed == 1


def test_token_budget_stops_the_loop(db, candidate, test_job, monkeypatch):
    heavy = llm.LLMReply(
        content="", prompt_tokens=4000, completion_tokens=1500, latency_ms=1,
        tool_calls=[call("c1", "get_job", {"job_id": test_job["id"]})],
    )
    fake = install(monkeypatch, [heavy] * 5)

    result = agent.run_agent(db, candidate, "x")

    assert len(fake.calls) == 1
    assert result.outcome == "token_budget"
    assert result.answer == agent.LIMIT_ANSWER


def test_deadline_stops_before_any_llm_call(db, candidate, monkeypatch):
    monkeypatch.setattr(agent, "DEADLINE_SECONDS", -1)
    fake = install(monkeypatch, [])

    result = agent.run_agent(db, candidate, "x")

    assert fake.calls == []
    assert result.outcome == "deadline"


def _capture_logs():
    logged = []
    sink_id = logger.add(lambda m: logged.append(str(m)), level="INFO")
    return logged, sink_id


def test_one_log_line_per_request_without_message_text(db, candidate, monkeypatch):
    install(monkeypatch, [reply("hello")])
    logged, sink_id = _capture_logs()
    try:
        agent.run_agent(db, candidate, "SECRET_QUESTION_TEXT please")
    finally:
        logger.remove(sink_id)

    lines = [m for m in logged if "agent user_id=" in m]
    assert len(lines) == 1
    assert "outcome=answered" in lines[0]
    assert "SECRET_QUESTION_TEXT" not in "".join(logged)


def test_failure_is_logged_with_error_type_only(db, candidate, monkeypatch):
    install(monkeypatch, [llm.LLMUnavailable("SECRET_PROVIDER_TEXT")])
    logged, sink_id = _capture_logs()
    try:
        with pytest.raises(llm.LLMUnavailable):
            agent.run_agent(db, candidate, "x")
    finally:
        logger.remove(sink_id)

    output = "".join(logged)
    assert "outcome=error:LLMUnavailable" in output
    assert "SECRET_PROVIDER_TEXT" not in output