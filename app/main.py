# app/main.py
from fastapi import FastAPI
from .routers import users, auth, jobs, applications

app = FastAPI(title="Job Board API")

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(applications.router)

@app.get("/")
def root():
    return {"message": "Job Board API is running!"}