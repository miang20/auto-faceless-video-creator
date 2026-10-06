from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Job:
    job_id: str
    job_type: str
    input_value: str
    status: str = "queued"
    result_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""

    def to_dict(self):
        return asdict(self)


def create_job(job_id: str, job_type: str, input_value: str) -> Job:
    return Job(
        job_id=job_id,
        job_type=job_type,
        input_value=input_value,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
