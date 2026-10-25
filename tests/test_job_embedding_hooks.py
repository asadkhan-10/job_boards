from app.routers import jobs

NEW_JOB = {
    "title": "Backend Developer",
    "company": "Test Co",
    "description": "Build APIs",
    "location": "Lahore",
    "job_type": "full_time",
}


def test_create_job_enqueues_embedding(employer_client, fake_embed_task):
    res = employer_client.post("/jobs/", json=NEW_JOB)
    assert res.status_code == 201
    assert fake_embed_task == [res.json()["id"]]


def test_update_job_enqueues_embedding(employer_client, test_job, fake_embed_task):
    fake_embed_task.clear()  # the test_job fixture already enqueued once
    res = employer_client.patch(f"/jobs/{test_job['id']}", json={"description": "new text"})
    assert res.status_code == 200
    assert fake_embed_task == [test_job["id"]]


def test_rejected_create_does_not_enqueue(candidate_client, fake_embed_task):
    res = candidate_client.post("/jobs/", json=NEW_JOB)
    assert res.status_code == 403
    assert fake_embed_task == []


def test_update_missing_job_does_not_enqueue(employer_client, fake_embed_task):
    res = employer_client.patch("/jobs/999999", json={"description": "x"})
    assert res.status_code == 404
    assert fake_embed_task == []


def test_queue_outage_does_not_fail_request(employer_client, monkeypatch):
    class DownTask:
        def delay(self, job_id):
            raise ConnectionError("redis down")

    monkeypatch.setattr(jobs, "embed_job_task", DownTask())
    res = employer_client.post("/jobs/", json=NEW_JOB)
    assert res.status_code == 201