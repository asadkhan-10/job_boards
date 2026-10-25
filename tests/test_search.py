import pytest

from app import models
from app.enums import JobStatus
from app.routers import jobs
from app.services import job_embedding
from app.services.embeddings import DIMENSION, EmbeddingError


def fake_vector(text):
    v = [0.0] * DIMENSION
    v[0 if "python" in text.lower() else 1] = 1.0
    return v


@pytest.fixture()
def fake_voyage(monkeypatch):
    calls = []

    def _embed(texts, input_type="document", **kwargs):
        calls.append(input_type)
        return [fake_vector(t) for t in texts]

    monkeypatch.setattr(job_embedding, "embed", _embed)
    monkeypatch.setattr(jobs, "embed", _embed)
    return calls


def add_job(client, db, title, location="Lahore", embed=True):
    res = client.post("/jobs/", json={
        "title": title, "company": "Co", "description": f"{title} role",
        "location": location, "job_type": "full_time",
    })
    job_id = res.json()["id"]
    if embed:
        job_embedding.embed_job(db, job_id)
    return job_id


def test_results_ordered_by_relevance(employer_client, db, fake_voyage):
    chef = add_job(employer_client, db, "Chef")
    py = add_job(employer_client, db, "Python Developer")
    res = employer_client.get("/jobs/search", params={"q": "python backend"})
    assert res.status_code == 200
    assert [j["id"] for j in res.json()] == [py, chef]
    assert "query" in fake_voyage


def test_closed_jobs_excluded(employer_client, db, fake_voyage):
    py = add_job(employer_client, db, "Python Developer")
    job = db.get(models.Job, py)
    job.status = JobStatus.closed
    db.commit()
    assert employer_client.get("/jobs/search", params={"q": "python"}).json() == []


def test_unembedded_jobs_skipped(employer_client, db, fake_voyage):
    add_job(employer_client, db, "Python Developer", embed=False)
    assert employer_client.get("/jobs/search", params={"q": "python"}).json() == []


def test_location_filter(employer_client, db, fake_voyage):
    lhr = add_job(employer_client, db, "Python Developer", "Lahore")
    add_job(employer_client, db, "Python Engineer", "Karachi")
    res = employer_client.get("/jobs/search", params={"q": "python", "location": "Lahore"})
    assert [j["id"] for j in res.json()] == [lhr]


def test_requires_login(client):
    # 401, not 422: proves /search is not swallowed by /{id}
    assert client.get("/jobs/search", params={"q": "python"}).status_code == 401


@pytest.mark.parametrize("params", [
    {"q": "a"},
    {"q": "     "},
    {"q": "x" * 301},
    {"q": "python", "limit": 100},
    {},
])
def test_input_validation(employer_client, fake_voyage, params):
    assert employer_client.get("/jobs/search", params=params).status_code == 422


def test_provider_failure_returns_generic_503(employer_client, monkeypatch):
    def boom(*args, **kwargs):
        raise EmbeddingError("voyage secret details")

    monkeypatch.setattr(jobs, "embed", boom)
    res = employer_client.get("/jobs/search", params={"q": "python"})
    assert res.status_code == 503
    assert "voyage" not in res.text.lower()

    