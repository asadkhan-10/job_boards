from dataclasses import dataclass
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app import models
from app.enums import JobStatus, JobType, UserRole
from app.services.search import retrieve_jobs


class ToolError(Exception):
    """Message is safe to show to the model."""


@dataclass(frozen=True)
class ToolContext:
    db: Session
    user: models.User  # comes from auth, never from model output


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchJobsArgs(_Args):
    query: str = Field(min_length=2, max_length=200)
    location: Optional[str] = Field(default=None, max_length=100)
    job_type: Optional[JobType] = None
    limit: int = Field(default=5, ge=1, le=5)


class GetJobArgs(_Args):
    job_id: int = Field(gt=0)


class ListMyApplicationsArgs(_Args):
    limit: int = Field(default=10, ge=1, le=10)


def _summary(job: models.Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "job_type": job.job_type.value,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
    }


def search_jobs(ctx: ToolContext, args: SearchJobsArgs) -> dict:
    jobs = retrieve_jobs(
        ctx.db, args.query,
        location=args.location, job_type=args.job_type, limit=args.limit,
    )
    return {"jobs": [{**_summary(j), "snippet": j.description[:200]} for j in jobs]}


def get_job(ctx: ToolContext, args: GetJobArgs) -> dict:
    job = (
        ctx.db.query(models.Job)
        .filter(models.Job.id == args.job_id, models.Job.status == JobStatus.open)
        .first()
    )
    if not job:
        raise ToolError("Job not found")
    return {**_summary(job), "description": job.description[:1200]}


def list_my_applications(ctx: ToolContext, args: ListMyApplicationsArgs) -> dict:
    if ctx.user.role != UserRole.candidate:
        raise ToolError("Only candidates have applications")
    rows = (
        ctx.db.query(models.Application, models.Job)
        .join(models.Job, models.Job.id == models.Application.job_id)
        .filter(models.Application.candidate_id == ctx.user.id)
        .order_by(models.Application.created_at.desc())
        .limit(args.limit)
        .all()
    )
    return {
        "applications": [
            {
                "application_id": a.id,
                "job_id": j.id,
                "title": j.title,
                "company": j.company,
                "status": a.status.value,
                "applied_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a, j in rows
        ]
    }


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[_Args]
    fn: Callable[[ToolContext, Any], dict]
    roles: frozenset


_ALL = frozenset({UserRole.candidate, UserRole.employer})

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool("search_jobs", "Semantic search over open jobs.", SearchJobsArgs, search_jobs, _ALL),
        Tool("get_job", "Get one open job by id.", GetJobArgs, get_job, _ALL),
        Tool("list_my_applications", "List the current candidate's own applications.",
             ListMyApplicationsArgs, list_my_applications, frozenset({UserRole.candidate})),
    ]
}


def tools_for(user: models.User) -> list[Tool]:
    return [t for t in TOOLS.values() if user.role in t.roles]


def tool_specs(user: models.User) -> list[dict]:
    """OpenAI-style tool list that Groq accepts."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_model.model_json_schema(),
            },
        }
        for t in tools_for(user)
    ]


def run_tool(ctx: ToolContext, name: str, raw_args: dict) -> dict:
    tool = next((t for t in tools_for(ctx.user) if t.name == name), None)
    if tool is None:
        raise ToolError("Unknown tool")
    try:
        args = tool.args_model.model_validate(raw_args)
    except ValidationError as e:
        fields = sorted({str(err["loc"][0]) for err in e.errors() if err["loc"]})
        raise ToolError(f"Invalid arguments: {', '.join(fields) or 'unknown'}")
    return tool.fn(ctx, args)