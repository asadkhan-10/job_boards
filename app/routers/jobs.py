# app/routers/jobs.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from .. import models, schemas, oauth2
from ..database import get_db
from ..enums import UserRole, JobStatus, JobType

router = APIRouter(prefix="/jobs", tags=["Jobs"])


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