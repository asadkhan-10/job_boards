# tests/test_ask_endpoint.py
import json

import pytest

from app.limiter import limiter
from app.services import ask, job_embedding, llm, search
from app.services.embeddings import DIMENSION, EmbeddingError


def fake_vector(text):
    v = [0.0] * DIMENSION
    v[0 if "python" in text.lower() else 1] = 1.0
    return v


@pytest.fixture(autouse=True)
def reset_rate_limit():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def fake_voyage(monkeypatch):
    def _embed(texts, input_type="document", **kwargs):
        return [fake_vector(t) for t in texts]

    monkeypatch.setattr(job_embedding, "embed", _embed)
    monkeypatch.setattr(search, "embed", _embed)


def fake_chat(monkeypatch, *replies):
    calls = []
    queue = list(replies)

    def _chat(messages, **kwargs):
        calls.append(messages)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return llm.LLMReply(item, 100, 20, 5)

    monkeypatch.setattr(llm, "chat", _chat)
    return calls


def add_job(client, db, title):
    res = client.post("/jobs/", json={
        "title": title, "company": "Co", "description": f"{title} role",
        "location": "Lahore", "job_type": "full_time",
    })
    job_id = res.json()["id"]
    job_embedding.embed_job(db, job_id)
    return job_id


def test_requires_login(client):
    res = client.post("/jobs/ask", json={"question": "python jobs?"})
    assert res.status_code == 401


def test_returns_answer_and_cited_jobs(employer_client, db, fake_voyage, monkeypatch):
    add_job(employer_client, db, "Chef")
    py = add_job(employer_client, db, "Python Developer")
    fake_chat(monkeypatch, json.dumps(
        {"answer": "The Python role fits.", "cited_job_ids": [py]}
    ))
    res = employer_client.post("/jobs/ask", json={"question": "python backend roles?"})
    assert res.status_code == 200
    assert res.json() == {
        "answer": "The Python role fits.",
        "cited_jobs": [{"id": py, "title": "Python Developer", "company": "Co"}],
    }


def test_fake_cited_id_never_reaches_the_client(employer_client, db, fake_voyage, monkeypatch):
    py = add_job(employer_client, db, "Python Developer")
    fake_chat(monkeypatch, json.dumps(
        {"answer": "Jobs.", "cited_job_ids": [py, 99999]}
    ))
    res = employer_client.post("/jobs/ask", json={"question": "python?"})
    assert [j["id"] for j in res.json()["cited_jobs"]] == [py]


def test_only_fake_ids_gives_unverified_answer(employer_client, db, fake_voyage, monkeypatch):
    add_job(employer_client, db, "Python Developer")
    fake_chat(monkeypatch, json.dumps(
        {"answer": "Job 99999 pays well.", "cited_job_ids": [99999]}
    ))
    res = employer_client.post("/jobs/ask", json={"question": "python?"})
    assert res.json() == {"answer": ask.UNVERIFIED_ANSWER, "cited_jobs": []}


def test_no_matching_jobs_skips_the_llm(employer_client, fake_voyage, monkeypatch):
    calls = fake_chat(monkeypatch)
    res = employer_client.post("/jobs/ask", json={"question": "python?"})
    assert res.status_code == 200
    assert res.json() == {"answer": ask.NO_JOBS_ANSWER, "cited_jobs": []}
    assert calls == []


@pytest.mark.parametrize("body", [
    {"question": "a"},
    {"question": "     "},
    {"question": "x" * 301},
    {},
])
def test_input_validation(employer_client, body):
    assert employer_client.post("/jobs/ask", json=body).status_code == 422


def test_llm_failure_returns_generic_503(employer_client, db, fake_voyage, monkeypatch):
    add_job(employer_client, db, "Python Developer")
    fake_chat(monkeypatch, llm.LLMUnavailable("groq secret details"))
    res = employer_client.post("/jobs/ask", json={"question": "python?"})
    assert res.status_code == 503
    assert "groq" not in res.text.lower()


def test_two_bad_replies_return_503(employer_client, db, fake_voyage, monkeypatch):
    add_job(employer_client, db, "Python Developer")
    fake_chat(monkeypatch, "garbage", "still garbage")
    res = employer_client.post("/jobs/ask", json={"question": "python?"})
    assert res.status_code == 503


def test_embedding_failure_returns_generic_503(employer_client, monkeypatch):
    def boom(*args, **kwargs):
        raise EmbeddingError("voyage secret details")

    monkeypatch.setattr(search, "embed", boom)
    res = employer_client.post("/jobs/ask", json={"question": "python?"})
    assert res.status_code == 503
    assert "voyage" not in res.text.lower()


def test_rate_limit_kicks_in_on_the_fourth_call(employer_client, fake_voyage):
    codes = [
        employer_client.post("/jobs/ask", json={"question": "python?"}).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]