# app/models.py
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql.expression import text
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String, nullable=False)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    job_type = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default="open")
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    employer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # nullable for external jobs
    external_id = Column(String, unique=True, nullable=True)  # Adzuna job ID
    source = Column(String, nullable=False, server_default="internal")  # "internal" or "adzuna"


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cover_letter = Column(Text)
    status = Column(String, nullable=False, server_default="pending")
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="unique_application"),
    )