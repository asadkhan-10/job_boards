
import pytest
from fastapi import status


def test_register_employer(client):
    res = client.post("/users/", json={
        "email": "newemployer@test.com",
        "password": "password123",
        "role": "employer"
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["email"] == "newemployer@test.com"
    assert data["role"] == "employer"
    assert "password" not in data


def test_register_candidate(client):
    res = client.post("/users/", json={
        "email": "newcandidate@test.com",
        "password": "password123",
        "role": "candidate"
    })
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["role"] == "candidate"


def test_register_duplicate_email(client):
    user_data = {"email": "dup@test.com", "password": "password123", "role": "candidate"}
    client.post("/users/", json=user_data)
    res = client.post("/users/", json=user_data)
    assert res.status_code == status.HTTP_409_CONFLICT
    assert res.json()["message"] == "Email already registered"


def test_register_invalid_role(client):
    res = client.post("/users/", json={
        "email": "badrole@test.com",
        "password": "password123",
        "role": "superadmin"
    })
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_missing_field(client):
    res = client.post("/users/", json={
        "email": "missing@test.com",
        "role": "candidate"
    })
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_me(employer_client, test_employer):
    res = employer_client.get("/users/me")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["email"] == test_employer["email"]
    assert data["role"] == "employer"


def test_get_me_unauthorized(client):
    res = client.get("/users/me")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED