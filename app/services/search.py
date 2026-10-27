
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.embeddings import embed
from ..enums import UserRole, JobStatus, JobType


def retrieve_jobs(
    db: Session,
    q: str,
    *,
    location: Optional[str] = None,
    job_type: Optional[JobType] = None,
    limit: int = 10,
) -> list[models.Job]:
    """Embed q and return the closest open jobs. Raises EmbeddingError."""
    query_vector = embed([q], input_type="query", max_retries=2)[0]

    query = db.query(models.Job).filter(
        models.Job.status == JobStatus.open,
        models.Job.embedding.isnot(None),
    )
    if location:
        query = query.filter(models.Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter(models.Job.job_type == job_type)

    return (
        query.order_by(models.Job.embedding.cosine_distance(query_vector))
        .limit(limit)
        .all()
    )