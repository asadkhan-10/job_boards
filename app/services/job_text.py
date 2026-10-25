# app/services/job_text.py
import hashlib
import re

TEXT_VERSION = 1
MAX_DESCRIPTION_CHARS = 8000


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def build_job_text(job) -> str:
    job_type = getattr(job.job_type, "value", job.job_type)
    description = _clean(job.description)[:MAX_DESCRIPTION_CHARS]
    return "\n".join([
        f"Title: {_clean(job.title)}",
        f"Company: {_clean(job.company)}",
        f"Location: {_clean(job.location)}",
        f"Type: {_clean(job_type).replace('_', ' ')}",
        f"Description: {description}",
    ])


def job_text_hash(text: str) -> str:
    return hashlib.sha256(f"v{TEXT_VERSION}\n{text}".encode("utf-8")).hexdigest()