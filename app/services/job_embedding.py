from loguru import logger
from sqlalchemy.orm import Session

from app import models
from app.services.embeddings import embed
from app.services.job_text import build_job_text, job_text_hash


def embed_job(db: Session, job_id: int) -> str:
    job = db.get(models.Job, job_id)
    if job is None:
        return "not_found"

    text = build_job_text(job)
    new_hash = job_text_hash(text)
    if job.embedding_text_hash == new_hash:
        return "unchanged"

    # End the read transaction: do not hold a DB connection during the network call.
    db.commit()

    vector = embed([text], input_type="document")[0]

    job = db.get(models.Job, job_id)
    if job is None:
        return "not_found"
    if job_text_hash(build_job_text(job)) != new_hash:
        logger.info(f"embed_job: job {job_id} changed while embedding, discarding")
        return "stale"

    job.embedding = vector
    job.embedding_text_hash = new_hash
    db.commit()
    return "embedded"