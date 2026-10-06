from pathlib import Path
import json


BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = BASE_DIR / "jobs"

JOBS_DIR.mkdir(parents=True, exist_ok=True)


def save_job(job) -> str:
    job_file = JOBS_DIR / f"{job.job_id}.json"

    with job_file.open("w", encoding="utf-8") as f:
        json.dump(job.to_dict(), f, indent=2)

    return str(job_file)


def load_job(job_id: str) -> dict:
    job_file = JOBS_DIR / f"{job_id}.json"

    if not job_file.exists():
        raise FileNotFoundError(f"Job not found: {job_id}")

    with job_file.open("r", encoding="utf-8") as f:
        return json.load(f)
