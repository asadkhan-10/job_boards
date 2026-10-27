import pytest

from app import models
from app.enums import JobStatus
from app.services import agent_tools
from app.services.agent_tools import ToolContext, ToolError, run_tool, tool_specs, tools_for


def _apply(db, job_id, user):
    app_row = models.Application(job_id=job_id, candidate_id=user.id)
    db.add(app_row)
    db.flush()
    return app_row


def test_model_cannot_pass_user_id(db, candidate, other_candidate, test_job):
    """The model tries to read someone else's applications by passing user_id."""
    _apply(db, test_job["id"], other_candidate)
    ctx = ToolContext(db=db, user=candidate)

    with pytest.raises(ToolError) as exc:
        run_tool(ctx, "list_my_applications", {"user_id": other_candidate.id})

    assert "user_id" in str(exc.value)


def test_candidate_sees_only_own_applications(db, candidate, other_candidate, test_job):
    mine = _apply(db, test_job["id"], candidate)
    _apply(db, test_job["id"], other_candidate)
    ctx = ToolContext(db=db, user=candidate)

    result = run_tool(ctx, "list_my_applications", {})

    assert [a["application_id"] for a in result["applications"]] == [mine.id]


def test_employer_cannot_use_candidate_tool(db, employer, candidate, test_job):
    _apply(db, test_job["id"], candidate)
    ctx = ToolContext(db=db, user=employer)

    # Not offered to the model...
    assert "list_my_applications" not in {t["function"]["name"] for t in tool_specs(employer)}
    # ...and refused if the model names it anyway.
    with pytest.raises(ToolError):
        run_tool(ctx, "list_my_applications", {})


def test_tool_function_checks_role_itself(db, employer):
    """Second layer: even if the registry filter were bypassed, the tool refuses."""
    ctx = ToolContext(db=db, user=employer)
    with pytest.raises(ToolError):
        agent_tools.list_my_applications(ctx, agent_tools.ListMyApplicationsArgs())


def test_unknown_tool_name(db, candidate):
    with pytest.raises(ToolError):
        run_tool(ToolContext(db=db, user=candidate), "delete_everything", {})


def test_limit_is_capped(db, candidate):
    with pytest.raises(ToolError):
        run_tool(ToolContext(db=db, user=candidate), "search_jobs", {"query": "python", "limit": 50})


def test_get_job_hides_internal_fields(db, candidate, test_job):
    result = run_tool(ToolContext(db=db, user=candidate), "get_job", {"job_id": test_job["id"]})

    assert result["id"] == test_job["id"]
    for forbidden in ("employer_id", "external_id", "embedding", "source"):
        assert forbidden not in result


def test_get_job_closed_job_not_found(db, candidate, test_job):
    job = db.get(models.Job, test_job["id"])
    job.status = next(s for s in JobStatus if s != JobStatus.open)
    db.flush()

    with pytest.raises(ToolError):
        run_tool(ToolContext(db=db, user=candidate), "get_job", {"job_id": job.id})


def test_search_jobs_returns_trimmed_results(db, candidate, test_job, monkeypatch):
    monkeypatch.setattr("app.services.search.embed", lambda *a, **k: [[0.1] * 1024])
    job = db.get(models.Job, test_job["id"])
    job.embedding = [0.1] * 1024
    db.flush()

    result = run_tool(ToolContext(db=db, user=candidate), "search_jobs", {"query": "backend developer"})

    assert [j["id"] for j in result["jobs"]] == [job.id]
    assert "employer_id" not in result["jobs"][0]