# tests/test_job_text.py
from types import SimpleNamespace

from app.enums import JobType
from app.services import job_text
from app.services.job_text import build_job_text, job_text_hash


def make_job(**over):
    base = dict(
        title="Backend Developer",
        company="Test Co",
        location="Lahore",
        job_type="full_time",
        description="Build APIs with FastAPI.",
        status="open",
        salary_min=100,
        salary_max=200,
    )
    base.update(over)
    return SimpleNamespace(**base)


def h(job):
    return job_text_hash(build_job_text(job))


def test_contains_expected_fields():
    text = build_job_text(make_job())
    assert "Title: Backend Developer" in text
    assert "Company: Test Co" in text
    assert "Location: Lahore" in text
    assert "Type: full time" in text
    assert "Description: Build APIs with FastAPI." in text


def test_works_with_enum_job_type():
    text = build_job_text(make_job(job_type=JobType.part_time))
    assert "Type: part time" in text


def test_excludes_salary_and_status():
    text = build_job_text(make_job()).lower()
    assert "salary" not in text
    assert "status" not in text
    assert "200" not in text


def test_status_change_keeps_hash():
    assert h(make_job(status="open")) == h(make_job(status="closed"))


def test_description_change_changes_hash():
    assert h(make_job()) != h(make_job(description="Something else."))


def test_whitespace_noise_keeps_hash():
    a = make_job(description="Build APIs.")
    b = make_job(description="  Build   APIs.\n")
    assert h(a) == h(b)


def test_description_is_capped():
    text = build_job_text(make_job(description="x" * 20000))
    assert len(text) < job_text.MAX_DESCRIPTION_CHARS + 200


def test_version_bump_changes_hash(monkeypatch):
    text = build_job_text(make_job())
    before = job_text_hash(text)
    monkeypatch.setattr(job_text, "TEXT_VERSION", 2)
    assert job_text_hash(text) != before