# tests/test_backfill.py
import pytest

from app.services import job_embedding
from app.services.embeddings import DIMENSION
from scripts import backfill_embeddings as backfill

JOB = {"title": "Dev", "company": "Co", "description": "Build things",
       "location": "Lahore", "job_type": "full_time"}


@pytest.fixture()
def use_test_session(db, monkeypatch):
    monkeypatch.setattr(db, "close", lambda: None)   # keep the test transaction alive
    monkeypatch.setattr(backfill, "SessionLocal", lambda: db)
    monkeypatch.setattr(backfill.time, "sleep", lambda s: None)
    monkeypatch.setattr(backfill.settings, "voyage_api_key", "test-key")


@pytest.fixture()
def calls(monkeypatch):
    made = []

    def fake(texts, input_type="document"):
        made.append(list(texts))
        return [[0.5] * DIMENSION for _ in texts]

    monkeypatch.setattr(job_embedding, "embed", fake)
    return made


def make_jobs(client, n):
    for i in range(n):
        assert client.post("/jobs/", json={**JOB, "title": f"Dev {i}"}).status_code == 201


def test_embeds_all_then_second_run_is_noop(employer_client, use_test_session, calls):
    make_jobs(employer_client, 2)
    assert backfill.run()["embedded"] == 2
    second = backfill.run()
    assert second["embedded"] == 0 and second["unchanged"] == 2
    assert len(calls) == 2


def test_dry_run_calls_nothing(employer_client, use_test_session, calls):
    make_jobs(employer_client, 2)
    counts = backfill.run(dry_run=True)
    assert counts["would_embed"] == 2
    assert calls == []


def test_pagination_covers_every_job(employer_client, use_test_session, calls, monkeypatch):
    monkeypatch.setattr(backfill, "BATCH_SIZE", 1)
    make_jobs(employer_client, 3)
    assert backfill.run()["embedded"] == 3


def test_one_failure_does_not_stop_the_run(employer_client, use_test_session, monkeypatch):
    make_jobs(employer_client, 2)
    state = {"n": 0}

    def flaky(texts, input_type="document"):
        state["n"] += 1
        if state["n"] == 1:
            raise ValueError("boom")
        return [[0.5] * DIMENSION for _ in texts]

    monkeypatch.setattr(job_embedding, "embed", flaky)
    counts = backfill.run()
    assert counts["failed"] == 1 and counts["embedded"] == 1


def test_missing_key_stops_before_any_work(monkeypatch):
    monkeypatch.setattr(backfill.settings, "voyage_api_key", "")
    with pytest.raises(SystemExit):
        backfill.run()