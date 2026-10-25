from types import SimpleNamespace

import pytest

from app import tasks
from app.services.embeddings import EmbeddingRateLimited


def fake_session():
    s = SimpleNamespace(closed=False, rolled_back=False)
    s.close = lambda: setattr(s, "closed", True)
    s.rollback = lambda: setattr(s, "rolled_back", True)
    return s


def test_task_runs_service_and_closes_session(monkeypatch):
    session = fake_session()
    monkeypatch.setattr(tasks, "SessionLocal", lambda: session)
    monkeypatch.setattr(tasks, "embed_job", lambda db, job_id: "embedded")

    assert tasks.embed_job_task(7) == {"status": "embedded", "job_id": 7}
    assert session.closed
    assert not session.rolled_back


def test_task_rolls_back_and_closes_on_error(monkeypatch):
    session = fake_session()

    def boom(db, job_id):
        raise ValueError("bug")

    monkeypatch.setattr(tasks, "SessionLocal", lambda: session)
    monkeypatch.setattr(tasks, "embed_job", boom)

    with pytest.raises(ValueError):
        tasks.embed_job_task(7)
    assert session.rolled_back
    assert session.closed


def test_retry_policy_only_covers_rate_limits():
    t = tasks.embed_job_task
    assert t.autoretry_for == (EmbeddingRateLimited,)
    assert t.max_retries == 5
    assert t.acks_late is True