# tests/test_applications.py
import pytest
from fastapi import status


def test_apply_to_job(candidate_client, test_job):
    res = candidate_client.post("/applications/", json={
        "job_id": test_job["id"],
        "cover_letter": "I am a great candidate"
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["job_id"] == test_job["id"]
    assert data["status"] == "pending"


def test_apply_duplicate(candidate_client, test_job):
    candidate_client.post("/applications/", json={"job_id": test_job["id"]})
    res = candidate_client.post("/applications/", json={"job_id": test_job["id"]})
    assert res.status_code == status.HTTP_409_CONFLICT


def test_apply_as_employer(employer_client, test_job):
    res = employer_client.post("/applications/", json={"job_id": test_job["id"]})
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_apply_unauthorized(client, test_job):
    res = client.post("/applications/", json={"job_id": test_job["id"]})
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_apply_nonexistent_job(candidate_client):
    res = candidate_client.post("/applications/", json={"job_id": 99999})
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_get_my_applications(candidate_client, test_job):
    candidate_client.post("/applications/", json={"job_id": test_job["id"]})
    res = candidate_client.get("/applications/my")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) >= 1


def test_get_my_applications_as_employer(employer_client):
    res = employer_client.get("/applications/my")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_get_applications_for_job(employer_client, candidate_client, test_job):
    candidate_client.post("/applications/", json={"job_id": test_job["id"]})
    res = employer_client.get(f"/applications/job/{test_job['id']}")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) >= 1


def test_get_applications_for_job_as_candidate(candidate_client, test_job):
    res = candidate_client.get(f"/applications/job/{test_job['id']}")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_update_application_status(employer_client, candidate_client, test_job):
    apply_res = candidate_client.post("/applications/", json={"job_id": test_job["id"]})
    application_id = apply_res.json()["id"]

    res = employer_client.patch(f"/applications/{application_id}/status", json={
        "status": "accepted"
    })
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "accepted"


def test_update_application_status_as_candidate(candidate_client, test_job):
    apply_res = candidate_client.post("/applications/", json={"job_id": test_job["id"]})
    application_id = apply_res.json()["id"]

    res = candidate_client.patch(f"/applications/{application_id}/status", json={
        "status": "accepted"
    })
    assert res.status_code == status.HTTP_403_FORBIDDEN