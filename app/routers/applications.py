# app/routers/applications.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .. import models, schemas, oauth2
from ..database import get_db
from ..enums import UserRole
from ..tasks import send_application_email_task

router = APIRouter(prefix="/applications", tags=["Applications"])


def require_candidate(current_user: models.User = Depends(oauth2.get_current_user)):
    if current_user.role != UserRole.candidate:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can perform this action"
        )
    return current_user


def require_employer(current_user: models.User = Depends(oauth2.get_current_user)):
    if current_user.role != UserRole.employer:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employers can perform this action"
        )
    return current_user


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ApplicationOut)
def apply(
    application: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_candidate)
):
    job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    new_application = models.Application(
        **application.model_dump(),
        candidate_id=current_user.id
    )
    db.add(new_application)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied for this job"
        )
    db.refresh(new_application)
    send_application_email_task.delay(new_application.id)
    return new_application


@router.get("/my", response_model=list[schemas.ApplicationOut])
def get_my_applications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_candidate),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50)
):
    return db.query(models.Application).filter(
        models.Application.candidate_id == current_user.id
    ).offset(skip).limit(limit).all()


@router.get("/job/{job_id}", response_model=list[schemas.ApplicationOut])
def get_applications_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_employer),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50)
):
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.employer_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return db.query(models.Application).filter(
        models.Application.job_id == job_id
    ).offset(skip).limit(limit).all()


@router.patch("/{id}/status", response_model=schemas.ApplicationOut)
def update_application_status(
    id: int,
    update: schemas.ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_employer)
):
    application = db.query(models.Application).filter(
        models.Application.id == id
    ).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    job = db.query(models.Job).filter(
        models.Job.id == application.job_id,
        models.Job.employer_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    application.status = update.status  # type: ignore
    db.commit()
    db.refresh(application)
    return application