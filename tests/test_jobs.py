# tests/test_jobs.py
import pytest
from fastapi import status


def test_create_job(employer_client):
    res = employer_client.post("/jobs/", json={
        "title": "Backend Developer",
        "company": "Test Co",
        "description": "A great job",
        "location": "Lahore",
        "job_type": "full_time"
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["title"] == "Backend Developer"
    assert data["source"] == "internal"
    assert data["status"] == "open"


def test_create_job_as_candidate(candidate_client):
    res = candidate_client.post("/jobs/", json={
        "title": "Backend Developer",
        "company": "Test Co",
        "description": "A great job",
        "location": "Lahore",
        "job_type": "full_time"
    })
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_create_job_unauthorized(client):
    res = client.post("/jobs/", json={
        "title": "Backend Developer",
        "company": "Test Co",
        "description": "A great job",
        "location": "Lahore",
        "job_type": "full_time"
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_jobs(client, test_job):
    res = client.get("/jobs/")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) >= 1


def test_get_jobs_search(client, test_job):
    res = client.get("/jobs/?search=Backend")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert all("Backend" in job["title"] for job in data)


def test_get_jobs_location_filter(client, test_job):
    res = client.get("/jobs/?location=Lahore")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert all("Lahore" in job["location"] for job in data)


def test_get_jobs_pagination(client, test_job):
    res = client.get("/jobs/?limit=1&skip=0")
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) <= 1


def test_get_single_job(client, test_job):
    res = client.get(f"/jobs/{test_job['id']}")
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["id"] == test_job["id"]


def test_get_single_job_not_found(client):
    res = client.get("/jobs/99999")
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_update_job(employer_client, test_job):
    res = employer_client.patch(f"/jobs/{test_job['id']}", json={
        "title": "Senior Backend Developer"
    })
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["title"] == "Senior Backend Developer"


def test_update_job_as_candidate(candidate_client, test_job):
    res = candidate_client.patch(f"/jobs/{test_job['id']}", json={
        "title": "Hacked"
    })
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_delete_job(employer_client, test_job):
    res = employer_client.delete(f"/jobs/{test_job['id']}")
    assert res.status_code == status.HTTP_204_NO_CONTENT


def test_delete_job_as_candidate(candidate_client, test_job):
    res = candidate_client.delete(f"/jobs/{test_job['id']}")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_delete_job_not_found(employer_client):
    res = employer_client.delete("/jobs/99999")
    assert res.status_code == status.HTTP_404_NOT_FOUND