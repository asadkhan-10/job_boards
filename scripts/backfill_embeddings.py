import argparse
import time

from loguru import logger
from sqlalchemy import select

from app import models
from app.config import settings
from app.database import SessionLocal
from app.services.job_embedding import embed_job
from app.services.job_text import build_job_text, job_text_hash

BATCH_SIZE = 50
PAUSE_SECONDS = 1.0


def list_ids(last_id: int) -> list[int]:
    db = SessionLocal()
    try:
        stmt = (
            select(models.Job.id)
            .where(models.Job.id > last_id)
            .order_by(models.Job.id)
            .limit(BATCH_SIZE)
        )
        return list(db.execute(stmt).scalars())
    finally:
        db.close()


def process(job_id: int, dry_run: bool) -> str:
    db = SessionLocal()
    try:
        if dry_run:
            job = db.get(models.Job, job_id)
            if job is None:
                return "not_found"
            current = job_text_hash(build_job_text(job))
            return "would_embed" if job.embedding_text_hash != current else "unchanged"
        return embed_job(db, job_id)
    finally:
        db.close()


def run(dry_run: bool = False) -> dict:
    if not dry_run and not settings.voyage_api_key:
        raise SystemExit("voyage_api_key is not set, nothing was done")

    counts = {"embedded": 0, "unchanged": 0, "stale": 0,
              "not_found": 0, "failed": 0, "would_embed": 0}
    last_id = 0
    while True:
        ids = list_ids(last_id)
        if not ids:
            break
        for job_id in ids:
            try:
                counts[process(job_id, dry_run)] += 1
            except Exception as e:
                counts["failed"] += 1
                logger.error(f"backfill: job {job_id} failed: {type(e).__name__}")
        last_id = ids[-1]
        if not dry_run:
            time.sleep(PAUSE_SECONDS)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed jobs that are missing or out of date")
    parser.add_argument("--dry-run", action="store_true", help="count only, no Voyage calls")
    args = parser.parse_args()
    print(run(dry_run=args.dry_run))