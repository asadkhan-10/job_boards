# app/tasks.py
from datetime import datetime, timezone
from loguru import logger
from app.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.enums import JobStatus
import logging
import urllib.request
from app.services.embeddings import EmbeddingRateLimited
from app.services.job_embedding import embed_job

from app.config import settings

logger = logging.getLogger(__name__)

def send_email(to: str, subject: str, body: str) -> None:
    """
    Stub for actual email delivery. Swap this out for a real provider
    (SMTP, SendGrid, Resend, etc.) later, everything that calls this
    function stays exactly the same.
    """
    logger.info(f"[EMAIL STUB] To: {to} | Subject: {subject} | Body: {body}")


@celery_app.task
def send_application_email_task(application_id: int):
    db = SessionLocal()
    try:
        application = (
            db.query(models.Application)
            .filter(models.Application.id == application_id)
            .first()
        )
        if not application:
            logger.warning(
                f"send_application_email_task: application {application_id} not found"
            )
            return {"status": "skipped", "reason": "application not found"}

        job = db.query(models.Job).filter(models.Job.id == application.job_id).first()
        candidate = (
            db.query(models.User).filter(models.User.id == application.candidate_id).first()
        )

        send_email(
            to=candidate.email,
            subject=f"Application received: {job.title}",
            body=(
                f"Your application for {job.title} at {job.company} has been "
                f"received and is currently marked as {application.status.value}."
            ),
        )
        return {"status": "sent", "application_id": application_id}
    except Exception as e:
        logger.exception(
            f"send_application_email_task failed for application {application_id}: {e}"
        )
        raise
    finally:
        db.close()


@celery_app.task
def cleanup_expired_jobs_task():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired_jobs = (
            db.query(models.Job)
            .filter(models.Job.expires_at < now, models.Job.status == JobStatus.open)
            .all()
        )

        for job in expired_jobs:
            job.status = JobStatus.closed

        db.commit()
        logger.info(f"cleanup_expired_jobs_task closed {len(expired_jobs)} expired job(s)")
        return {"status": "success", "jobs_closed": len(expired_jobs)}
    except Exception as e:
        db.rollback()
        logger.exception(f"cleanup_expired_jobs_task failed: {e}")
        raise
    finally:
        db.close()





@celery_app.task
def heartbeat_task():
    if not settings.healthcheck_url:
        return "skipped"
    try:
        with urllib.request.urlopen(settings.healthcheck_url, timeout=10):
            pass
    except Exception as exc:
        logger.warning("heartbeat ping failed: %s", exc)
        return "failed"
    return "ok"




@celery_app.task(
    autoretry_for=(EmbeddingRateLimited,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
    soft_time_limit=120,
)
def embed_job_task(job_id: int):
    db = SessionLocal()
    try:
        status = embed_job(db, job_id)
        logger.info(f"embed_job_task job {job_id}: {status}")
        return {"status": status, "job_id": job_id}
    except Exception as e:
        db.rollback()
        logger.error(f"embed_job_task failed for job {job_id}: {type(e).__name__}")
        raise
    finally:
        db.close()