import pytest

from app import models
from app.enums import JobStatus
from app.services import job_embedding
from app.services.embeddings import DIMENSION


@pytest.fixture()
def fake_embed(monkeypatch):
    calls = []

    def _embed(texts, input_type="document"):
        calls.append((list(texts), input_type))
        return [[0.5] * DIMENSION for _ in texts]

    monkeypatch.setattr(job_embedding, "embed", _embed)
    return calls


def test_embeds_new_job(db, test_job, fake_embed):
    assert job_embedding.embed_job(db, test_job["id"]) == "embedded"
    job = db.get(models.Job, test_job["id"])
    assert job.embedding_text_hash is not None
    assert job.embedding is not None
    assert len(fake_embed) == 1
    assert fake_embed[0][1] == "document"


def test_second_run_is_unchanged(db, test_job, fake_embed):
    job_embedding.embed_job(db, test_job["id"])
    assert job_embedding.embed_job(db, test_job["id"]) == "unchanged"
    assert len(fake_embed) == 1


def test_text_change_reembeds(db, test_job, fake_embed):
    job_embedding.embed_job(db, test_job["id"])
    job = db.get(models.Job, test_job["id"])
    job.description = "A completely different description"
    db.commit()
    assert job_embedding.embed_job(db, test_job["id"]) == "embedded"
    assert len(fake_embed) == 2


def test_status_change_does_not_reembed(db, test_job, fake_embed):
    job_embedding.embed_job(db, test_job["id"])
    job = db.get(models.Job, test_job["id"])
    job.status = JobStatus.closed
    db.commit()
    assert job_embedding.embed_job(db, test_job["id"]) == "unchanged"
    assert len(fake_embed) == 1


def test_missing_job(db, fake_embed):
    assert job_embedding.embed_job(db, 999999) == "not_found"
    assert fake_embed == []


def test_concurrent_edit_discards_stale_vector(db, test_job, monkeypatch):
    def racing_embed(texts, input_type="document"):
        job = db.get(models.Job, test_job["id"])
        job.description = "edited while embedding"
        db.commit()
        return [[0.5] * DIMENSION for _ in texts]

    monkeypatch.setattr(job_embedding, "embed", racing_embed)
    assert job_embedding.embed_job(db, test_job["id"]) == "stale"
    job = db.get(models.Job, test_job["id"])
    assert job.embedding_text_hash is None