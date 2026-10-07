from __future__ import annotations

from typing import Optional

from core.config import (
    DEFAULT_LANGUAGE,
    DEFAULT_MAX_CLIPS,
)
from core.validator import validate_input
from core.jobs import create_job
from core.job_store import save_job, load_job
from core.pipeline import (
    run_topic_pipeline,
    execute_video_pipeline,
)


def create_orchestrator_job(
    job_type: str,
    input_value: str,
    reference_url: Optional[str] = None,
    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """
    Create and persist a queued Pro V2 job.

    New Pro V2 settings are stored directly inside the job so
    the existing GitHub queue can carry them without requiring
    a separate configuration system.
    """

    validation = validate_input(
        job_type=job_type,
        input_value=input_value,
        reference_url=reference_url,
    )

    if isinstance(validation, dict):
        if not validation.get("valid", True):
            raise ValueError(
                validation.get(
                    "error",
                    "Invalid job input.",
                )
            )
    elif validation is False:
        raise ValueError("Invalid job input.")

    job_id = create_job_id()

    job = create_job(
        job_id=job_id,
        job_type=job_type,
        input_value=input_value,
        reference_url=reference_url,
        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    save_job(job)

    return job.to_dict()


def create_job_id() -> str:
    """
    Generate a unique job ID.
    """

    import uuid

    return uuid.uuid4().hex


def execute_topic_job(
    topic: str,
    reference_url: Optional[str] = None,
    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """
    Execute a topic-based Pro V2 research workflow.
    """

    validation = validate_input(
        job_type="topic",
        input_value=topic,
        reference_url=reference_url,
    )

    if isinstance(validation, dict):
        if not validation.get("valid", True):
            return {
                "success": False,
                "status": "failed",
                "error": validation.get(
                    "error",
                    "Invalid topic input.",
                ),
            }
    elif validation is False:
        return {
            "success": False,
            "status": "failed",
            "error": "Invalid topic input.",
        }

    job_id = create_job_id()

    job = create_job(
        job_id=job_id,
        job_type="topic",
        input_value=topic,
        reference_url=reference_url,
        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    save_job(job)

    try:
        result = run_topic_pipeline(
            topic=topic,
            reference_url=reference_url,
            duration=duration,
            caption_style=caption_style,
            caption_settings=caption_settings,
            editing_settings=editing_settings,
        )

        if result.get("success"):
            update_job(
                job_id=job_id,
                status="completed",
                result_path=result.get("script_path"),
            )
        else:
            update_job(
                job_id=job_id,
                status="failed",
                error=result.get(
                    "error",
                    "Topic pipeline failed.",
                ),
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


def execute_video_job(
    video_path: str,
    reference_url: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    max_clips: int = DEFAULT_MAX_CLIPS,
    output_dir: str = "output/jobs",
    make_vertical: bool = True,
    keep_audio: bool = False,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """
    Execute a video job directly through the Pro V2 pipeline.
    """

    validation = validate_input(
        job_type="video",
        input_value=video_path,
        reference_url=reference_url,
    )

    if isinstance(validation, dict):
        if not validation.get("valid", True):
            return {
                "success": False,
                "status": "failed",
                "error": validation.get(
                    "error",
                    "Invalid video input.",
                ),
            }
    elif validation is False:
        return {
            "success": False,
            "status": "failed",
            "error": "Invalid video input.",
        }

    job_id = create_job_id()

    job = create_job(
        job_id=job_id,
        job_type="video",
        input_value=video_path,
        reference_url=reference_url,
        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    save_job(job)

    try:
        result = execute_video_pipeline(
            video_path=video_path,
            topic=video_path,
            reference_url=reference_url,
            whisper_command=whisper_command,
            model_path=model_path,
            language=language,
            max_clips=max_clips,
            output_dir=output_dir,
            make_vertical=make_vertical,
            keep_audio=keep_audio,
            duration=duration,
            caption_style=caption_style,
            caption_settings=caption_settings,
            editing_settings=editing_settings,
        )

        if result.get("success"):
            result_path = result.get("processing_report_path")

            update_job(
                job_id=job_id,
                status="completed",
                result_path=result_path,
            )
        else:
            update_job(
                job_id=job_id,
                status="failed",
                error=result.get(
                    "error",
                    "Video pipeline failed.",
                ),
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


def execute_queued_video_job(
    job_id: str,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    max_clips: int = DEFAULT_MAX_CLIPS,
    output_dir: str = "output/jobs",
    make_vertical: bool = True,
    keep_audio: bool = False,
) -> dict:
    """
    Execute a queued video job.

    The job's stored Pro V2 settings are used automatically.
    """

    job = load_job(job_id)

    from core.job_runner import run_video_job

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


def update_job(
    job_id: str,
    status: str,
    result_path: Optional[str] = None,
    error: Optional[str] = None,
) -> dict:
    """
    Update persisted job state.
    """

    job = load_job(job_id)

    job["status"] = status

    if result_path is not None:
        job["result_path"] = result_path

    if error is not None:
        job["error"] = error

    if status != "failed":
        job["error"] = None

    save_job_dict(job)

    return job


def save_job_dict(job: dict) -> str:
    """
    Persist a dictionary job without requiring a Job dataclass.
    """

    from pathlib import Path
    import json

    job_file = (
        Path(__file__).resolve().parent.parent
        / "jobs"
        / f"{job['job_id']}.json"
    )

    job_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with job_file.open("w", encoding="utf-8") as file:
        json.dump(
            job,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(job_file)


def execute_job(
    job_id: str,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    max_clips: int = DEFAULT_MAX_CLIPS,
    output_dir: str = "output/jobs",
    make_vertical: bool = True,
    keep_audio: bool = False,
) -> dict:
    """
    Generic job dispatcher.
    """

    job = load_job(job_id)

    job_type = job.get("job_type")

    if job_type == "video":
        return execute_queued_video_job(
            job_id=job_id,
            whisper_command=whisper_command,
            model_path=model_path,
            language=language,
            max_clips=max_clips,
            output_dir=output_dir,
            make_vertical=make_vertical,
            keep_audio=keep_audio,
        )

    if job_type == "topic":
        return execute_topic_job(
            topic=job.get("input_value", ""),
            reference_url=job.get("reference_url"),
            duration=job.get("duration", 30),
            caption_style=job.get(
                "caption_style",
                "Bold Viral",
            ),
            caption_settings=job.get(
                "caption_settings"
            ),
            editing_settings=job.get(
                "editing_settings"
            ),
        )

    return {
        "success": False,
        "status": "failed",
        "job_id": job_id,
        "error": f"Unsupported job type: {job_type}",
    }


def get_orchestrator_info() -> dict:
    """
    Return information about supported workflows.
    """

    return {
        "name": "Auto Faceless Video Creator V2",
        "version": "2.0",
        "workflows": {
            "topic": True,
            "video": True,
            "queued_video": True,
        },
        "pro_features": {
            "duration_control": True,
            "caption_settings": True,
            "dynamic_editing": True,
            "story_rebuild": True,
            "multi_source_research": True,
        },
    }
