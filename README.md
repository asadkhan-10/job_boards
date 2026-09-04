# Job Boards API

A production-hardened REST API for a job board platform. Employers post and manage jobs, candidates apply and track their applications, with role-based access control enforced throughout.

---

## Tech Stack

- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL with SQLAlchemy 2.0 and Alembic migrations
- **Auth:** JWT via python-jose, bcrypt password hashing (passlib)
- **Validation:** Pydantic v2
- **Logging:** loguru — structured logs with per-request correlation IDs
- **Containerization:** Docker + Docker Compose (separate dev/prod configs)
- **CI:** GitHub Actions (pytest against a PostgreSQL service container)
- **Testing:** pytest + httpx

---

## Features

- JWT authentication with role-aware tokens (`employer` / `candidate`)
- Role-based access control (RBAC) enforced at the route dependency level
- Full CRUD on jobs, with search, location, and job-type filtering
- Application workflow: apply, withdraw, view own applications, review applicants
- Pagination on all list endpoints (`skip` / `limit`)
- Global exception handling — consistent JSON error shape for HTTP and unhandled exceptions
- Request ID middleware — every request/response is tagged with a UUID, propagated through structured logs via `loguru.contextualize`, and returned as an `X-Request-ID` response header
- Structured JSON-style logging to stdout and rotating log files (10 MB rotation, 7-day retention, gzip compression)

---

## Roles & Permissions (RBAC)

| Action | Employer | Candidate |
|---|---|---|
| Post a job | ✅ | ❌ |
| Edit/delete own job | ✅ | ❌ |
| View jobs | ✅ | ✅ |
| Apply to a job | ❌ | ✅ |
| View own applications | ❌ | ✅ |
| Withdraw application | ❌ | ✅ |
| View applicants for own job | ✅ | ❌ |
| Update application status | ✅ | ❌ |

---

## Project Structure

```
JOB_BOARDS/
├── .github/
│   └── workflows/
│       └── build-deploy.yml
├── alembic/
│   └── versions/
├── app/
│   ├── routers/
│   │   ├── applications.py
│   │   ├── auth.py
│   │   ├── jobs.py
│   │   └── users.py
│   ├── config.py
│   ├── database.py
│   ├── enums.py
│   ├── main.py
│   ├── models.py
│   ├── oauth2.py
│   ├── request_id.py
│   ├── schemas.py
│   └── utils.py
├── tests/
├── .dockerignore
├── .env
├── alembic.ini
├── docker-compose-dev.yml
├── docker-compose-prod.yml
├── Dockerfile
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Get JWT access token |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/users/` | Register a new user (employer or candidate) |
| GET | `/users/me` | Get the current authenticated user |
| DELETE | `/users/{id}` | Delete own account |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs/` | Create a job (employer only) |
| GET | `/jobs/` | List open jobs — supports `search`, `location`, `job_type`, `skip`, `limit` |
| GET | `/jobs/{id}` | Get a specific job |
| PATCH | `/jobs/{id}` | Update own job (employer only) |
| DELETE | `/jobs/{id}` | Delete own job (employer only) |

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/applications/` | Apply to a job (candidate only) |
| GET | `/applications/my` | List own applications (candidate only) |
| GET | `/applications/job/{job_id}` | List applicants for own job (employer only) |
| PATCH | `/applications/{id}/status` | Update an application's status (employer only) |

---

## Running Locally

### Prerequisites

- Docker and Docker Compose installed

### Setup

1. Clone the repo:

```bash
git clone https://github.com/asadkhan-10/job_boards.git
cd job_boards
```

2. Create a `.env` file in the project root:

```env
database_hostname=postgres
database_port=5432
database_username=postgres
database_password=yourpassword
database_name=job_boards
secret_key=your_secret_key
algorithm=HS256
access_token_expire_minutes=30
```

3. Start the containers:

```bash
docker-compose -f docker-compose-dev.yml up -d
```

4. Run database migrations:

```bash
docker-compose -f docker-compose-dev.yml exec api alembic upgrade head
```

5. Visit the interactive docs at `http://localhost:8000/docs`

---

## Running Tests

```bash
pytest -v
```

Tests run against a dedicated `_test` database, with each test wrapped in a transaction that's rolled back afterward for isolation.

---

## CI Pipeline

Every push and pull request to `main` triggers the following GitHub Actions pipeline:

```
push / PR to main
    → Spin up a PostgreSQL service container
    → Install dependencies
    → Create the test database
    → Run pytest
```

This currently covers testing only — there is no automated deploy stage yet.

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DATABASE_PASSWORD` | PostgreSQL password (testing environment) |
| `SECRET_KEY` | JWT secret key (testing environment) |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `database_hostname` | PostgreSQL host |
| `database_port` | PostgreSQL port |
| `database_username` | PostgreSQL username |
| `database_password` | PostgreSQL password |
| `database_name` | PostgreSQL database name |
| `secret_key` | JWT signing secret |
| `algorithm` | JWT algorithm (HS256) |
| `access_token_expire_minutes` | Token expiry duration |

---
"

## Author

**Asad Ali Khan**

- GitHub: [@asadkhan-10](https://github.com/asadkhan-10)
- LinkedIn: [linkedin.com/in/asadkhn10](https://linkedin.com/in/asadkhn10)