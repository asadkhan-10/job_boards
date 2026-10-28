# scripts/seed_demo_jobs.py
import argparse

from app import models
from app.database import SessionLocal
from app.enums import JobType, UserRole

FT, PT = JobType.full_time, JobType.part_time

DEMO_JOBS = [
    ("Backend Developer", "Northwind Systems (demo)", "Lahore", FT,
     "Design and build REST APIs with FastAPI and PostgreSQL. Write tests, review code and keep the services reliable."),
    ("Junior DevOps Engineer", "Cloudline (demo)", "Remote", FT,
     "Maintain Linux servers, build CI/CD pipelines with Docker and GitHub Actions, and set up monitoring and alerts."),
    ("IT Support Officer", "Greenfield NGO (demo)", "Faisalabad", FT,
     "First-line help desk for staff. Fix laptops and printers, reset passwords and manage Active Directory accounts."),
    ("Frontend Developer", "Pixel Forge (demo)", "Karachi", FT,
     "Build responsive interfaces in React and TypeScript, working closely with designers and backend engineers."),
    ("Data Analyst", "Insight Labs (demo)", "Islamabad", FT,
     "Turn raw data into dashboards and weekly reports using SQL and spreadsheets. Present findings to managers."),
    ("Network Administrator", "Metro Telecom (demo)", "Lahore", FT,
     "Configure routers, switches, VLANs and firewalls. Troubleshoot connectivity problems across branch offices."),
    ("Content Writer", "Brightside Media (demo)", "Remote", PT,
     "Write blog posts and product descriptions for our clients. Flexible hours, strong English required."),
    ("Accounts Assistant", "Al-Noor Traders (demo)", "Faisalabad", FT,
     "Handle invoices, bookkeeping and monthly reconciliations. Basic accounting knowledge required."),
    ("Mobile App Developer", "Appsmith Studio (demo)", "Islamabad", FT,
     "Create cross-platform mobile apps with Flutter. Publish to app stores and fix reported crashes."),
    ("Customer Support Agent", "ReachOut Services (demo)", "Karachi", PT,
     "Answer customer calls and chats, log tickets and follow up on complaints in a shift-based call center."),
    ("QA Engineer", "Northwind Systems (demo)", "Lahore", FT,
     "Plan test cases and automate them with pytest and Selenium. Report bugs and verify fixes before releases."),
    ("Cloud Engineer", "Cloudline (demo)", "Remote", FT,
     "Provision cloud infrastructure with Terraform on AWS, manage cost and security, and document the setup."),
]


def _employer(db, email):
    employer = (
        db.query(models.User)
        .filter(models.User.email == email, models.User.role == UserRole.employer)
        .first()
    )
    if not employer:
        raise SystemExit(f"No employer account with email {email}")
    return employer


def seed(email: str) -> int:
    db = SessionLocal()
    try:
        employer = _employer(db, email)
        added = 0
        for title, company, location, job_type, description in DEMO_JOBS:
            exists = db.query(models.Job).filter(
                models.Job.employer_id == employer.id,
                models.Job.title == title,
                models.Job.company == company,
            ).first()
            if exists:
                continue
            db.add(models.Job(
                title=title, company=company, location=location,
                job_type=job_type, description=description,
                employer_id=employer.id,
            ))
            added += 1
        db.commit()
        return added
    finally:
        db.close()


def remove(email: str) -> int:
    db = SessionLocal()
    try:
        employer = _employer(db, email)
        removed = 0
        for title, company, *_ in DEMO_JOBS:
            removed += db.query(models.Job).filter(
                models.Job.employer_id == employer.id,
                models.Job.title == title,
                models.Job.company == company,
            ).delete(synchronize_session=False)
        db.commit()
        return removed
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DEV ONLY: seed or remove demo jobs")
    parser.add_argument("--employer-email", required=True)
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    if args.remove:
        print({"removed": remove(args.employer_email)})
    else:
        print({"added": seed(args.employer_email)})