# tests/test_embeddings.py
import pytest
from voyageai.error import RateLimitError

from app.services import embeddings
from app.services.embeddings import EmbeddingError, embed


class FakeResult:
    def __init__(self, n):
        self.embeddings = [[0.1] * embeddings.DIMENSION for _ in range(n)]


class FakeClient:
    calls = []
    fail_times = 0

    def __init__(self, api_key=None):
        self.api_key = api_key

    def embed(self, texts, **kwargs):
        FakeClient.calls.append((list(texts), kwargs))
        if FakeClient.fail_times > 0:
            FakeClient.fail_times -= 1
            raise RateLimitError("slow down")
        return FakeResult(len(texts))


@pytest.fixture(autouse=True)
def fake_voyage(monkeypatch):
    FakeClient.calls = []
    FakeClient.fail_times = 0
    monkeypatch.setattr(embeddings.voyageai, "Client", FakeClient)
    monkeypatch.setattr(embeddings.settings, "voyage_api_key", "test-key")
    monkeypatch.setattr(embeddings.time, "sleep", lambda s: None)


def test_returns_one_vector_per_text():
    out = embed(["a", "b", "c"])
    assert len(out) == 3
    assert all(len(v) == embeddings.DIMENSION for v in out)


def test_sends_model_dimension_and_input_type():
    embed(["a"], input_type="query")
    _, kwargs = FakeClient.calls[0]
    assert kwargs["model"] == embeddings.MODEL
    assert kwargs["output_dimension"] == embeddings.DIMENSION
    assert kwargs["input_type"] == "query"


def test_batches_requests():
    out = embed(["x"] * 130)
    assert len(out) == 130
    assert [len(c[0]) for c in FakeClient.calls] == [64, 64, 2]


def test_empty_list_makes_no_call():
    assert embed([]) == []
    assert FakeClient.calls == []


def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "voyage_api_key", "")
    with pytest.raises(EmbeddingError):
        embed(["a"])
    assert FakeClient.calls == []


def test_bad_input_type_raises():
    with pytest.raises(ValueError):
        embed(["a"], input_type="banana")


def test_retries_on_429_then_succeeds():
    FakeClient.fail_times = 2
    out = embed(["a"])
    assert len(out) == 1
    assert len(FakeClient.calls) == 3  # 2 failures + 1 success


def test_gives_up_after_max_retries():
    FakeClient.fail_times = 100
    with pytest.raises(EmbeddingError):
        embed(["a"])
    assert len(FakeClient.calls) == embeddings.MAX_RETRIES