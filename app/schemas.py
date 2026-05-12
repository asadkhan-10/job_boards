# app/schemas.py

from pydantic import BaseModel, EmailStr # type: ignore
from datetime import datetime
from typing import Optional
from .enums import JobStatus, UserRole, JobType, ApplicationStatus

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[int] = None

# User schemas
    
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
     
class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    created_at: datetime
    class Config:
        from_attributes = True
        
# job schemas

class JobCreate(BaseModel):
    title: str
    description: str
    company: str
    location: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    job_type: JobType
    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: int
    title: str
    description: str
    company: str
    location: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    job_type: JobType
    created_at: datetime
    status: JobStatus
    employer_id: int
    class Config:
        from_attributes = True
    
class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    job_type: Optional[JobType] = None

# application schemas
class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: Optional[str] = None

class ApplicationOut(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    cover_letter: Optional[str] = None
    status: ApplicationStatus
    created_at: datetime
    class Config:
        from_attributes = True
        
class ApplicationStatusUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None