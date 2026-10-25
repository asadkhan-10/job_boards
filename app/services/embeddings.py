import logging
import time

import voyageai
from voyageai.error import RateLimitError

from ..config import settings  # adjust to match your config import

logger = logging.getLogger(__name__)

MODEL = "voyage-4"
DIMENSION = 1024      # must match the vector(1024) column
BATCH_SIZE = 64
MAX_RETRIES = 5


class EmbeddingError(Exception):
    pass

class EmbeddingRateLimited(EmbeddingError):
    """Voyage kept returning 429. Transient, so a task retry makes sense."""


def embed(texts: list[str], input_type: str = "document") -> list[list[float]]:
    if input_type not in ("document", "query"):
        raise ValueError("input_type must be 'document' or 'query'")
    if not settings.voyage_api_key:
        raise EmbeddingError("voyage_api_key is not set")
    if not texts:
        return []

    client = voyageai.Client(api_key=settings.voyage_api_key)
    vectors: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        for attempt in range(MAX_RETRIES):
            try:
                result = client.embed(
                    batch,
                    model=MODEL,
                    input_type=input_type,
                    output_dimension=DIMENSION,
                )
                vectors.extend(result.embeddings)
                break
            except RateLimitError:
                wait = 2 ** attempt
                logger.warning("Voyage 429, retrying in %ss", wait)
                time.sleep(wait)
        else:
            raise EmbeddingRateLimited("Voyage rate limit: retries exhausted")

    return vectors