# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.config import settings
from app.oauth2 import create_access_token

TEST_DATABASE_URL = (
    f"postgresql://{settings.database_username}:"
    f"{settings.database_password}@"
    f"{settings.database_hostname}:"
    f"{settings.database_port}/"
    f"{settings.database_name}_test"
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def employer_client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    res = c.post("/users/", json={
        "email": "employer@test.com",
        "password": "password123",
        "role": "employer"
    })
    user = res.json()
    token = create_access_token({"user_id": user["id"], "role": "employer"})
    c.headers = {**c.headers, "Authorization": f"Bearer {token}"}
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def candidate_client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    res = c.post("/users/", json={
        "email": "candidate@test.com",
        "password": "password123",
        "role": "candidate"
    })
    user = res.json()
    token = create_access_token({"user_id": user["id"], "role": "candidate"})
    c.headers = {**c.headers, "Authorization": f"Bearer {token}"}
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_employer(employer_client):
    res = employer_client.get("/users/me")
    user = res.json()
    user["password"] = "password123"
    return user


@pytest.fixture()
def test_candidate(candidate_client):
    res = candidate_client.get("/users/me")
    user = res.json()
    user["password"] = "password123"
    return user

@pytest.fixture()
def test_job(employer_client):
    res = employer_client.post("/jobs/", json={
        "title": "Backend Developer",
        "company": "Test Company",
        "description": "A test job",
        "location": "Lahore",
        "job_type": "full_time"
    })
    assert res.status_code == 201
    return res.json()