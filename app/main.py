# app/main.py
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger 
from .routers import users, auth, jobs, applications

# --- Loguru configuration ---
logger.remove()  # remove the default handler

logger.add(
    sys.stdout,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}",
    colorize=True
)

logger.add(
    "logs/app.log",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)

# --- App ---
app = FastAPI(title="Job Board API")

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(applications.router)


# --- Middleware: log every request ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Completed: {request.method} {request.url} | Status: {response.status_code}")
    return response


# --- Exception handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url} | {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500
        }
    )


@app.get("/")
def root():
    return {"message": "Job Board API is running!"}