# Job Boards API

[![CI](https://github.com/asadkhan-10/job_boards/actions/workflows/build-deploy.yml/badge.svg)](https://github.com/asadkhan-10/job_boards/actions/workflows/build-deploy.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%20%2B%20pgvector-336791)

A REST API for a job board, deployed to production. Employers post jobs and review applicants, candidates search and apply, and every action is gated by role. On top of the core API it has semantic job search, question answering over job listings with checked citations, and a tool-calling assistant that can only do what the signed-in user is allowed to do.

**Live:** https://job-boards-api.duckdns.org (interactive docs at [`/docs`](https://job-boards-api.duckdns.org/docs))

---

## Try it

The live instance is seeded with sample jobs (company names marked "(demo)").

1. Open [`/docs`](https://job-boards-api.duckdns.org/docs) and register with `POST /users/` as a `candidate` or an `employer`.
2. Click **Authorize**, enter your email as the username, and your password.
3. Call `GET /jobs/search?q=fix employee laptops`, `POST /jobs/ask` with `{"question": "Which jobs involve Docker?"}`, or `POST /agent/chat` with `{"message": "Find me a job that suits a Linux person"}`.

Registration is limited to 10 per hour per IP, and the AI endpoints are rate limited (see [Rate limits](#rate-limits)).

---

## Tech Stack

| Layer | Tools |
|---|---|
| API | FastAPI (Python 3.12), Pydantic v2, JWT (PyJWT) with bcrypt |
| Data | PostgreSQL 15 with pgvector, SQLAlchemy 2.0, Alembic migrations |
| AI | Voyage AI embeddings (`voyage-4`, 1024 dimensions), Groq-hosted LLM (`openai/gpt-oss-120b` by default, configurable) |
| Background jobs | Celery worker and Celery Beat, Redis broker |
| Operations | slowapi rate limiting (Redis-backed), loguru structured logs with request IDs |
| Infrastructure | Docker Compose, Nginx with Let's Encrypt, Oracle Cloud |
| CI/CD | GitHub Actions, Docker Hub, automated SSH deploy |
| Testing | pytest, httpx |

---

## Features

**Core API**

- Role-aware JWT auth (`employer` / `candidate`) with RBAC enforced as route dependencies, and ownership checks on every write
- Job CRUD with title search, location and job-type filters, and pagination on list endpoints
- Application workflow: apply (one application per candidate per job), withdraw, view your own, review applicants and update their status
- Consistent JSON errors, and a UUID `X-Request-ID` on every response that is carried through the logs

**Search and AI**

- Semantic job search that matches meaning, not only keywords
- Question answering over job listings, with citations that are checked against the retrieved jobs
- A job search assistant that calls tools on the user's behalf

**Operations**

- Daily Celery Beat task (03:00 UTC) that closes expired jobs
- A heartbeat task every 5 minutes that pings an external health-check URL
- Application confirmation task (email delivery is currently a stub that logs)
- Rate limiting on sensitive and costly endpoints, returning `429` in the standard JSON error shape

---

## Semantic Search and AI

```
GET  /jobs/search   query    -> embed -> pgvector cosine search -> ranked open jobs
POST /jobs/ask      question -> same retrieval (top 5) -> LLM answers from those jobs -> answer + citations
POST /agent/chat    message  -> LLM <-> tools (search_jobs, get_job, list_my_applications) -> answer
```

**Embeddings.** A job's text (title, company, location, type, description) is embedded with Voyage AI and stored in a pgvector column. A Celery task embeds a job when it is created or edited. It skips unchanged text, retries with backoff when the provider rate-limits, and discards its result if the job changed while it was being embedded. If the queue is unavailable, job creation still succeeds, and `scripts/backfill_embeddings.py` embeds anything that was missed.

**Ask.** The model sees only the retrieved jobs and must reply in a fixed JSON shape. Every job ID it cites is checked against the jobs that were actually retrieved. Unverifiable citations are dropped, and if none of the citations hold up the endpoint returns a fallback message instead of the model's answer. Job text is passed to the model as untrusted data, not as instructions.

**Assistant.**

- Tools are filtered by role. `search_jobs` and `get_job` are available to everyone, and `list_my_applications` only to candidates, returning only their own rows.
- The user's identity comes from the JWT, never from the model. Tool arguments are validated with Pydantic and unknown arguments are rejected.
- Each request is bounded: at most 5 model steps, 5,000 tokens and 25 seconds, and tool output is truncated.
- It is stateless. One log line per request records steps, tools, token counts and latency, never the message text.
- Provider failures return a generic `503`, not provider error details.

---

## Roles & Permissions (RBAC)

| Action | Employer | Candidate |
|---|---|---|
| Post a job | ✅ | ❌ |
| Edit/delete own job | ✅ | ❌ |
| View jobs | ✅ | ✅ |
| Semantic search, Ask, Assistant | ✅ | ✅ |
| Assistant: list own applications | ❌ | ✅ |
| Apply to a job | ❌ | ✅ |
| View own applications | ❌ | ✅ |
| Withdraw application | ❌ | ✅ |
| View applicants for own job | ✅ | ❌ |
| Update application status | ✅ | ❌ |

---

## Architecture

```
Client ──HTTPS──► Nginx ──► FastAPI ──► PostgreSQL + pgvector
                              │   │
                              │   └──► Voyage AI (query embeddings), Groq (LLM)
                              │
                              └──► Redis ◄── Celery worker ──► Voyage AI (job embeddings)
                                         ◄── Celery Beat
```

Seven Compose services run in production: `api`, `nginx`, `postgres`, `redis`, `celery_worker`, `celery_beat` and `certbot`. The API publishes no host port, so it is reachable only through Nginx.

```
job_boards/
├── .github/workflows/build-deploy.yml
├── alembic/versions/                 # migrations: native enums, indexes, pgvector, embeddings
├── app/
│   ├── routers/
│   │   ├── agent.py
│   │   ├── applications.py
│   │   ├── auth.py
│   │   ├── jobs.py
│   │   └── users.py
│   ├── services/
│   │   ├── agent.py                  # tool-calling loop
│   │   ├── agent_tools.py            # role-filtered tools
│   │   ├── ask.py                    # grounded answers + citation check
│   │   ├── embeddings.py             # Voyage client with retry
│   │   ├── job_embedding.py          # embed one job (idempotent)
│   │   ├── job_text.py
│   │   ├── llm.py                    # Groq client
│   │   └── search.py                 # pgvector retrieval
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
├── scripts/
│   ├── backfill_embeddings.py
│   └── seed_demo_jobs.py
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

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/` | Public | Health check |
| POST | `/login` | Public | Get a JWT access token (form data: `username` is the email) |
| POST | `/users/` | Public | Register (employer or candidate) |
| GET | `/users/me` | Signed in | Current user |
| DELETE | `/users/{id}` | Signed in | Delete own account |
| POST | `/jobs/` | Employer | Create a job |
| GET | `/jobs/` | Public | List open jobs: `search`, `location`, `job_type`, `skip`, `limit` |
| GET | `/jobs/search` | Signed in | Semantic search: `q`, `location`, `job_type`, `limit` |
| POST | `/jobs/ask` | Signed in | Answer a question from job listings, with cited jobs |
| GET | `/jobs/{id}` | Public | Get a job |
| PATCH | `/jobs/{id}` | Employer | Update own job |
| DELETE | `/jobs/{id}` | Employer | Delete own job |
| POST | `/agent/chat` | Signed in | Job search assistant |
| POST | `/applications/` | Candidate | Apply to a job |
| GET | `/applications/my` | Candidate | List own applications |
| DELETE | `/applications/{id}` | Candidate | Withdraw own application |
| GET | `/applications/job/{job_id}` | Employer | List applicants for own job |
| PATCH | `/applications/{id}/status` | Employer | Update an application's status |

### Rate limits

| Endpoint | Limit |
|---|---|
| `POST /users/` | 10 per hour per IP |
| `POST /login` | 5 per minute per IP |
| `GET /jobs/search` | 10 per minute per IP |
| `POST /jobs/ask` | 3 per minute per IP |
| `POST /agent/chat` | 3 per minute and 30 per day per IP, plus a shared 5 per minute and 100 per day across all callers |

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

# Optional: needed for semantic search, /jobs/ask and the assistant.
# Without them the rest of the API works and those endpoints return 503.
voyage_api_key=
groq_api_key=
# groq_model=openai/gpt-oss-120b
```

Start the stack, run migrations, then open http://localhost:8000/docs:

```bash
docker compose -f docker-compose-dev.yml up -d
docker compose -f docker-compose-dev.yml exec api alembic upgrade head
```

The dev compose uses the `pgvector/pgvector:pg15` image and publishes Postgres on host port `5433` and Redis on `6380`, to avoid clashing with local installs.

**Sample data (optional).** Register an employer through `/docs`, then:

```bash
docker compose -f docker-compose-dev.yml exec api python -m scripts.seed_demo_jobs --employer-email you@example.com
docker compose -f docker-compose-dev.yml exec api python -m scripts.backfill_embeddings
```

The first command adds 12 sample jobs and is safe to rerun. The second embeds them, which needs `voyage_api_key`.

---

## Testing

```bash
pytest -v
```

The suite has 170+ tests. It needs a PostgreSQL with pgvector and a `<database_name>_test` database. Each test runs in a transaction that is rolled back. External services are mocked, so no API keys or network access are needed. The rate limiter is off for the normal suite, and dedicated tests check the `429` behavior.

Dependencies are pinned, and `pip-audit -r requirements.txt` reports no known vulnerabilities as of the last update.

---

## CI/CD

Pushes and pull requests to `main` run the tests. Merges to `main` also build and deploy:

```
test    → pgvector PostgreSQL + Redis service containers, pytest
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

One Oracle Cloud VM runs `docker-compose-prod.yml` behind Nginx, with PostgreSQL from the `pgvector/pgvector` image. TLS certificates come from Let's Encrypt via certbot and are renewed weekly. The pipeline ships the application image only. `docker-compose-prod.yml` and `nginx.conf` are copied to the server by hand, and the server's `.env` (the variables above, including the two API keys) is never committed. Nginx passes the real client IP to the API, so rate limits apply per client.

---

## Known Limitations

- Application confirmation emails are a stub: the task runs, but the message is logged, not sent.
- The assistant is stateless. Each request stands alone, with no conversation memory.
- Retrieval quality has not been measured against an evaluation set yet.