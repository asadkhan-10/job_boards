# app/routers/jobs.py
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from .. import models, schemas, oauth2
from ..database import get_db
from ..enums import UserRole, JobStatus, JobType
from loguru import logger
from ..tasks import embed_job_task
from ..limiter import limiter
from ..services.embeddings import EmbeddingError
from ..services.search import retrieve_jobs
from ..services.ask import generate_answer, AnswerParseError
from ..services.llm import LLMUnavailable, LLMNotConfigured



router = APIRouter(prefix="/jobs", tags=["Jobs"])

def _enqueue_embedding(job_id: int) -> None:
    # The job is already committed. A queue outage must not fail the request;
    # the backfill script repairs any job that missed its task.
    try:
        embed_job_task.delay(job_id)
    except Exception as e:
        logger.error(f"could not enqueue embedding for job {job_id}: {type(e).__name__}")


def require_employer(current_user: models.User = Depends(oauth2.get_current_user)):
    if current_user.role != UserRole.employer: # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can perform this action"
        )
    return current_user


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.JobOut)
def create_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_employer)
):
    new_job = models.Job(**job.model_dump(), employer_id=current_user.id)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    _enqueue_embedding(new_job.id)
    return new_job


@router.get("/", response_model=list[schemas.JobOut])
def get_jobs(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    job_type: Optional[JobType] = Query(None),
    limit: int = Query(10, le=50),
    skip: int = Query(0)
):
    query = db.query(models.Job).filter(models.Job.status == JobStatus.open)

    if search:
        query = query.filter(models.Job.title.ilike(f"%{search}%"))
    if location:
        query = query.filter(models.Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter(models.Job.job_type == job_type)

    return query.offset(skip).limit(limit).all()

@router.get("/search", response_model=list[schemas.JobOut])
@limiter.limit("10/minute")
def search_jobs(
    request: Request,
    q: str = Query(..., max_length=300),
    location: Optional[str] = Query(None, max_length=100),
    job_type: Optional[JobType] = Query(None),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must be at least 2 characters",
        )

    try:
        return retrieve_jobs(
            db, q, location=location, job_type=job_type, limit=limit
        )
    except EmbeddingError as e:
        logger.error(f"search embedding failed: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )

@router.post("/ask", response_model=schemas.AskResponse)
@limiter.limit("3/minute")
def ask_jobs(
    request: Request,
    body: schemas.AskRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        jobs = retrieve_jobs(db, body.question, limit=5)
    except EmbeddingError as e:
        logger.error(f"ask embedding failed: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )

    try:
        result = generate_answer(body.question, jobs)
    except (LLMUnavailable, LLMNotConfigured, AnswerParseError) as e:
        logger.error(f"ask answer failed: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answers are temporarily unavailable",
        )

    by_id = {j.id: j for j in jobs}
    return {
        "answer": result.answer,
        "cited_jobs": [
            {"id": by_id[i].id, "title": by_id[i].title, "company": by_id[i].company}
            for i in result.cited_job_ids
        ],
    }

@router.get("/{id}", response_model=schemas.JobOut)
def get_job(id: int, db: Session = Depends(get_db)):
    job = db.query(models.Job).filter(models.Job.id == id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.patch("/{id}", response_model=schemas.JobOut)
def update_job(
    id: int,
    job_update: schemas.JobUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_employer)
):
    job_query = db.query(models.Job).filter(
        models.Job.id == id,
        models.Job.employer_id == current_user.id
    )
    job = job_query.first()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job_query.update(
        job_update.model_dump(exclude_unset=True),  # type: ignore
        synchronize_session=False
    )
    db.commit()
    db.refresh(job)
    _enqueue_embedding(job.id)
    return job


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_employer)
):
    job_query = db.query(models.Job).filter(
        models.Job.id == id,
        models.Job.employer_id == current_user.id
    )
    if not job_query.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job_query.delete(synchronize_session=False)
    db.commit()