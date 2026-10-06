from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from core.config import (
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_CLIPS,
    DEFAULT_MAKE_VERTICAL,
    DEFAULT_KEEP_AUDIO,
    DEFAULT_RESEARCH_LIMIT,
    JOB_OUTPUT_DIR,
)

from core.validator import (
    validate_job_input,
    validate_topic_request,
    validate_video_request,
)

from core.jobs import create_job
from core.job_store import save_job, load_job

from core.pipeline import (
    run_topic_pipeline,
    execute_video_pipeline,
)

from core.job_runner import (
    run_video_job,
)


# ============================================================
# ID
# ============================================================

def create_job_id() -> str:
    """
    Generate a unique job ID.
    """

    return uuid.uuid4().hex


# ============================================================
# JOB CREATION
# ============================================================

def create_orchestrator_job(
    job_type: str,
    input_value: str,
    reference_url: Optional[str] = None,
) -> dict:
    """
    Validate and create a new queued job.
    """

    validated = validate_job_input(
        job_type=job_type,
        input_value=input_value,
        reference_url=reference_url,
    )

    job = create_job(
        job_id=create_job_id(),
        job_type=validated["job_type"],
        input_value=validated["input_value"],
        reference_url=validated["reference_url"],
    )

    save_job(job)

    return job.to_dict()


# ============================================================
# TOPIC WORKFLOW
# ============================================================

def execute_topic_job(
    topic: str,
    reference_url: Optional[str] = None,
    research_limit: int = DEFAULT_RESEARCH_LIMIT,
    output_dir: str | Path = JOB_OUTPUT_DIR,
) -> dict:
    """
    Execute a complete topic-based workflow.

    Flow:

        Topic
          ↓
        Validation
          ↓
        Research
          ↓
        Source Analysis
          ↓
        Script
          ↓
        Saved Artifacts
    """

    validated = validate_topic_request(
        topic=topic,
        reference_url=reference_url,
        research_limit=research_limit,
    )

    job_id = create_job_id()

    job = create_job(
        job_id=job_id,
        job_type="topic",
        input_value=validated["topic"],
        reference_url=validated["reference_url"],
    )

    save_job(job)

    try:
        result = run_topic_pipeline(
            topic=validated["topic"],
            reference_url=validated["reference_url"],
            research_limit=validated["research_limit"],
            output_dir=output_dir,
        )

        update_job(
            job_id=job_id,
            status="completed",
            result_path=result.get(
                "artifacts",
                {},
            ).get("script"),
        )

        result["job_id"] = job_id
        result["success"] = True

        return result

    except Exception as exc:

        update_job(
            job_id=job_id,
            status="failed",
            error=str(exc),
        )

        return {
            "success": False,
            "status": "failed",
            "job_id": job_id,
            "error": str(exc),
        }


# ============================================================
# VIDEO WORKFLOW
# ============================================================

def execute_video_job(
    video_path: str | Path,
    topic: Optional[str] = None,
    reference_url: Optional[str] = None,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    max_clips: int = DEFAULT_MAX_CLIPS,
    output_dir: str | Path = JOB_OUTPUT_DIR,
    make_vertical: bool = DEFAULT_MAKE_VERTICAL,
    keep_audio: bool = DEFAULT_KEEP_AUDIO,
) -> dict:
    """
    Execute a complete local video workflow.

    Flow:

        Video
          ↓
        Validation
          ↓
        Transcription
          ↓
        Clip Analysis
          ↓
        Clip Processing
          ↓
        Optional Research
          ↓
        Optional Script
    """

    validated = validate_video_request(
        video_path=video_path,
        topic=topic,
        reference_url=reference_url,
        language=language,
        max_clips=max_clips,
        make_vertical=make_vertical,
        keep_audio=keep_audio,
    )

    job_id = create_job_id()

    job_input = (
        validated["topic"]
        if validated["topic"]
        else validated["video_path"]
    )

    job = create_job(
        job_id=job_id,
        job_type="video",
        input_value=job_input,
        reference_url=validated["reference_url"],
    )

    save_job(job)

    try:

        result = execute_video_pipeline(
            video_path=validated["video_path"],
            topic=validated["topic"],
            reference_url=validated["reference_url"],
            whisper_command=whisper_command,
            model_path=model_path,
            language=validated["language"],
            max_clips=validated["max_clips"],
            output_dir=output_dir,
            make_vertical=validated["make_vertical"],
            keep_audio=validated["keep_audio"],
        )

        if not result.get("success"):

            error = result.get(
                "error",
                "Video pipeline failed.",
            )

            update_job(
                job_id=job_id,
                status="failed",
                error=error,
            )

            result["job_id"] = job_id

            return result

        result_path = result.get(
            "artifacts",
            {},
        ).get("processing")

        update_job(
            job_id=job_id,
            status="completed",
            result_path=result_path,
        )

        result["job_id"] = job_id

        return result

    except Exception as exc:

        update_job(
            job_id=job_id,
            status="failed",
            error=str(exc),
        )

        return {
            "success": False,
            "status": "failed",
            "job_id": job_id,
            "error": str(exc),
        }


# ============================================================
# DOWNLOADED / QUEUED VIDEO JOB
# ============================================================

def execute_queued_video_job(
    job_id: str,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    max_clips: int = DEFAULT_MAX_CLIPS,
    output_dir: str | Path = JOB_OUTPUT_DIR,
    make_vertical: bool = DEFAULT_MAKE_VERTICAL,
    keep_audio: bool = DEFAULT_KEEP_AUDIO,
) -> dict:
    """
    Execute an already-created video job.

    This delegates downloading and processing to job_runner.
    """

    job = load_job(job_id)

    if job.get("job_type") != "video":
        raise ValueError(
            f"Job {job_id} is not a video job."
        )

    return run_video_job(
        job_id=job_id,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
        max_clips=max_clips,
        output_dir=output_dir,
        make_vertical=make_vertical,
        keep_audio=keep_audio,
    )


# ============================================================
# JOB UPDATE
# ============================================================

def update_job(
    job_id: str,
    status: str,
    result_path: Optional[str] = None,
    error: Optional[str] = None,
) -> dict:
    """
    Update an existing persisted job.
    """

    job = load_job(job_id)

    job["status"] = status

    if result_path is not None:
        job["result_path"] = result_path

    if error is not None:
        job["error"] = error
    elif status != "failed":
        job["error"] = None

    from core.config import get_job_file
    import json

    job_file = get_job_file(job_id)

    with job_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            job,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return job


# ============================================================
# JOB STATUS
# ============================================================

def get_job_status(
    job_id: str,
) -> dict:
    """
    Return the current persisted job state.
    """

    return load_job(job_id)


# ============================================================
# GENERIC DISPATCHER
# ============================================================

def execute_job(
    job_type: str,
    input_value: str,
    reference_url: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Generic high-level dispatcher.

    Supported:

        topic
        video

    """

    job_type = job_type.strip().lower()

    if job_type == "topic":

        return execute_topic_job(
            topic=input_value,
            reference_url=reference_url,
            research_limit=kwargs.get(
                "research_limit",
                DEFAULT_RESEARCH_LIMIT,
            ),
            output_dir=kwargs.get(
                "output_dir",
                JOB_OUTPUT_DIR,
            ),
        )

    if job_type == "video":

        return execute_video_job(
            video_path=input_value,
            topic=kwargs.get("topic"),
            reference_url=reference_url,
            whisper_command=kwargs.get(
                "whisper_command"
            ),
            model_path=kwargs.get(
                "model_path"
            ),
            language=kwargs.get(
                "language",
                DEFAULT_LANGUAGE,
            ),
            max_clips=kwargs.get(
                "max_clips",
                DEFAULT_MAX_CLIPS,
            ),
            output_dir=kwargs.get(
                "output_dir",
                JOB_OUTPUT_DIR,
            ),
            make_vertical=kwargs.get(
                "make_vertical",
                DEFAULT_MAKE_VERTICAL,
            ),
            keep_audio=kwargs.get(
                "keep_audio",
                DEFAULT_KEEP_AUDIO,
            ),
        )

    raise ValueError(
        f"Unsupported job type: {job_type}"
    )


# ============================================================
# HEALTH / CAPABILITY SUMMARY
# ============================================================

def get_orchestrator_info() -> dict:
    """
    Return a simple overview of available workflows.
    """

    return {
        "status": "ready",
        "workflows": {
            "topic": {
                "enabled": True,
                "stages": [
                    "validation",
                    "research",
                    "source_analysis",
                    "script_generation",
                ],
            },
            "video": {
                "enabled": True,
                "stages": [
                    "validation",
                    "transcription",
                    "clip_analysis",
                    "video_processing",
                    "optional_research",
                    "optional_script_generation",
                ],
            },
            "queued_video": {
                "enabled": True,
                "stages": [
                    "job_loading",
                    "download",
                    "pipeline_execution",
                ],
            },
        },
    }
