
import pytest
from fastapi import status
from app.oauth2 import verify_access_token
from fastapi import HTTPException


def get_credentials_exception():
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")


def test_login_employer(client, test_employer):
    res = client.post("/login", data={
        "username": test_employer["email"],
        "password": test_employer["password"]
    })
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "employer"


def test_login_candidate(client, test_candidate):
    res = client.post("/login", data={
        "username": test_candidate["email"],
        "password": test_candidate["password"]
    })
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["role"] == "candidate"


def test_token_contains_correct_data(client, test_employer):
    res = client.post("/login", data={
        "username": test_employer["email"],
        "password": test_employer["password"]
    })
    token = res.json()["access_token"]
    payload = verify_access_token(token, get_credentials_exception())
    assert payload.id == test_employer["id"]
    assert payload.role == "employer"


def test_login_wrong_password(client, test_employer):
    res = client.post("/login", data={
        "username": test_employer["email"],
        "password": "wrongpassword"
    })
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_login_wrong_email(client):
    res = client.post("/login", data={
        "username": "nobody@test.com",
        "password": "password123"
    })
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_login_missing_fields(client):
    res = client.post("/login", data={})
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY