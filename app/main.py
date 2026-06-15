# app/main.py
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from .routers import users, auth, jobs, applications

logger = logging.getLogger(__name__)

app = FastAPI(title="Job Board API")

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(applications.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
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
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True)
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