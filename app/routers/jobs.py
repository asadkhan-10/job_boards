
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..oauth2 import get_current_user   
from ..enums import UserRole


router = APIRouter(prefix="/jobs", tags=["Jobs"])
@router.get("/", response_model=list[schemas.JobOut])
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(models.Job).all()
    return jobs

@router.get("/{id}", response_model=schemas.JobOut)
def get_job(id: int, db: Session = Depends(get_db)):     
    job = db.query(models.Job).filter(models.Job.id == id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job

@router.post("/", response_model=schemas.JobOut, status_code=status.HTTP_201_CREATED)
def create_job(job: schemas.JobCreate, db: Session = Depends(get_db), current_user: schemas.UserOut = Depends(get_current_user)):
    if current_user.role != UserRole.employer: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only employers can create jobs")
    new_job = models.Job(**job.model_dump(), employer_id=current_user.id) # type: ignore
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job