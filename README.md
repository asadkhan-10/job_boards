# Job Boards API

A REST API for a job board. Employers post and manage jobs, candidates apply and track applications, and role-based access control is enforced throughout.

**Live:** https://job-boards-api.duckdns.org (interactive docs at [`/docs`](https://job-boards-api.duckdns.org/docs))

---

## Tech Stack

- **API:** FastAPI (Python 3.12), Pydantic v2, JWT (python-jose) with bcrypt
- **Data:** PostgreSQL, SQLAlchemy 2.0, Alembic migrations
- **Background jobs:** Celery worker + Celery Beat, Redis broker
- **Operations:** slowapi rate limiting, loguru structured logs with request IDs
- **Infra:** Docker Compose, Nginx with Let's Encrypt, Oracle Cloud
- **CI/CD:** GitHub Actions, Docker Hub, automated SSH deploy
- **Testing:** pytest + httpx

---

## Features

- Role-aware JWT auth (`employer` / `candidate`) with RBAC enforced at the route dependency level
- Job CRUD with search, location and job-type filters, plus pagination on all list endpoints
- Application workflow: apply, withdraw, view own applications, review applicants
- Rate limiting: requests over the limit get a `429` in the standard JSON error shape
- Daily Celery Beat task (03:00) that cleans up expired jobs
- Consistent JSON errors, and a UUID `X-Request-ID` on every response that is carried through the logs

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

## Architecture

```
Client ──HTTPS──► Nginx ──► FastAPI ──► PostgreSQL
                              │
                              └──► Redis ◄── Celery worker + Celery Beat
```

Seven Compose services run in production: `api`, `nginx`, `postgres`, `redis`, `celery_worker`, `celery_beat` and `certbot`. The API publishes no host port, so it is reachable only through Nginx.

```
JOB_BOARDS/
├── .github/workflows/build-deploy.yml
├── alembic/versions/
├── app/
│   ├── routers/
│   │   ├── applications.py
│   │   ├── auth.py
│   │   ├── jobs.py
│   │   └── users.py
│   ├── celery_app.py
│   ├── config.py
│   ├── database.py
│   ├── enums.py
│   ├── limiter.py
│   ├── main.py
│   ├── models.py
│   ├── oauth2.py
│   ├── request_id.py
│   ├── schemas.py
│   ├── tasks.py
│   └── utils.py
├── tests/
├── alembic.ini
├── docker-compose-dev.yml
├── docker-compose-prod.yml
├── Dockerfile
├── nginx.conf
└── requirements.txt
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/login` | Get a JWT access token |
| POST | `/users/` | Register (employer or candidate) |
| GET | `/users/me` | Current authenticated user |
| DELETE | `/users/{id}` | Delete own account |
| POST | `/jobs/` | Create a job (employer) |
| GET | `/jobs/` | List open jobs: `search`, `location`, `job_type`, `skip`, `limit` |
| GET | `/jobs/{id}` | Get a job |
| PATCH | `/jobs/{id}` | Update own job (employer) |
| DELETE | `/jobs/{id}` | Delete own job (employer) |
| POST | `/applications/` | Apply to a job (candidate) |
| GET | `/applications/my` | List own applications (candidate) |
| DELETE | `/applications/{id}` | Withdraw own application (candidate) |
| GET | `/applications/job/{job_id}` | List applicants for own job (employer) |
| PATCH | `/applications/{id}/status` | Update an application's status (employer) |

---

## Running Locally

Requires Docker and Docker Compose.

```bash
git clone https://github.com/asadkhan-10/job_boards.git
cd job_boards
```

Create a `.env` in the project root:

```env
database_hostname=postgres
database_port=5432
database_username=postgres
database_password=yourpassword
database_name=job_boards
secret_key=your_secret_key
algorithm=HS256
access_token_expire_minutes=30
redis_url=redis://redis:6379/0
```

Start the stack, run migrations, then open http://localhost:8000/docs:

```bash
docker-compose -f docker-compose-dev.yml up -d
docker-compose -f docker-compose-dev.yml exec api alembic upgrade head
```

The dev compose publishes Redis on host port `6380` to avoid clashing with a local Redis on `6379`.

**Tests:** run `pytest -v`. Each test runs in a transaction that is rolled back, against a dedicated `_test` database. The rate limiter is off for the normal suite, and one dedicated test checks the `429`.

---

## CI/CD

Pushes and pull requests to `main` run the tests. Merges to `main` also build and deploy:

```
test    → PostgreSQL + Redis service containers, pytest
docker  → build the image, push to Docker Hub (tagged `latest` and the commit SHA)
deploy  → over SSH: pull, run migrations with the new image, `up -d --wait`,
          reload Nginx, smoke test the public HTTPS URL
```

- Migrations run before the new containers start, so new code never meets an old schema.
- Nginx is reloaded after each deploy because it resolves the `api` address only once at startup.
- `docker` and `deploy` run only on `main`, and the `production` environment is restricted to `main`, so pull requests cannot build images or read deploy secrets.
- **Rollback:** revert the commit on `main` and the pipeline redeploys. Images are also tagged by commit SHA.
- **Secrets:** `testing` environment: `DATABASE_PASSWORD`, `SECRET_KEY`. `production` environment: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `OCI_HOST`, `OCI_USERNAME`, `OCI_SSH_KEY`.

---

## Production

One Oracle Cloud VM runs `docker-compose-prod.yml` behind Nginx. TLS certificates come from Let's Encrypt via certbot and are renewed weekly. The pipeline ships the application image only. `docker-compose-prod.yml` and `nginx.conf` are copied to the server by hand, and the server's `.env` (same variables as above) is never committed.

---

## Roadmap

Planned, not built yet: semantic job search with pgvector, and a job search assistant that acts with the caller's permissions.