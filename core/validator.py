from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


# ============================================================
# CONSTANTS
# ============================================================

SUPPORTED_JOB_TYPES = {
    "video",
    "topic",
}

SUPPORTED_LANGUAGES = {
    "en",
}

SUPPORTED_STATUSES = {
    "queued",
    "downloading",
    "processing",
    "completed",
    "failed",
}

MAX_TOPIC_LENGTH = 500

MAX_REFERENCE_URL_LENGTH = 2048

MAX_JOB_ID_LENGTH = 128

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def clean_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def validate_length(
    value: str,
    field_name: str,
    max_length: int,
) -> None:
    if len(value) > max_length:
        raise ValueError(
            f"{field_name} exceeds maximum length of "
            f"{max_length} characters."
        )


# ============================================================
# JOB ID
# ============================================================

def validate_job_id(job_id: str) -> str:
    job_id = clean_string(job_id)

    if not job_id:
        raise ValueError("Job ID is required.")

    validate_length(
        job_id,
        "Job ID",
        MAX_JOB_ID_LENGTH,
    )

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        job_id,
    ):
        raise ValueError(
            "Job ID may contain only letters, numbers, "
            "underscores, and hyphens."
        )

    return job_id


# ============================================================
# URL VALIDATION
# ============================================================

def is_valid_url(url: str) -> bool:
    if not is_non_empty_string(url):
        return False

    try:
        parsed = urlparse(url.strip())

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def is_youtube_url(url: str) -> bool:
    if not is_valid_url(url):
        return False

    parsed = urlparse(url.strip())

    hostname = (
        parsed.hostname or ""
    ).lower().rstrip(".")

    return hostname in YOUTUBE_HOSTS


def validate_reference_url(
    reference_url: Optional[str],
) -> Optional[str]:

    if reference_url is None:
        return None

    reference_url = clean_string(reference_url)

    if not reference_url:
        return None

    validate_length(
        reference_url,
        "Reference URL",
        MAX_REFERENCE_URL_LENGTH,
    )

    if not is_valid_url(reference_url):
        raise ValueError(
            "Reference URL must be a valid HTTP/HTTPS URL."
        )

    return reference_url


def validate_video_url(
    video_url: str,
) -> str:

    video_url = clean_string(video_url)

    if not video_url:
        raise ValueError(
            "Video URL is required."
        )

    validate_length(
        video_url,
        "Video URL",
        MAX_REFERENCE_URL_LENGTH,
    )

    if not is_youtube_url(video_url):
        raise ValueError(
            "Video URL must be a valid YouTube URL."
        )

    return video_url


# ============================================================
# TOPIC VALIDATION
# ============================================================

def validate_topic(
    topic: str,
) -> str:

    topic = clean_string(topic)

    if not topic:
        raise ValueError(
            "Topic, idea, or keyword is required."
        )

    validate_length(
        topic,
        "Topic",
        MAX_TOPIC_LENGTH,
    )

    return topic


# ============================================================
# LANGUAGE
# ============================================================

def validate_language(
    language: str,
) -> str:

    language = clean_string(language).lower()

    if not language:
        language = "en"

    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {language}"
        )

    return language


# ============================================================
# NUMERIC SETTINGS
# ============================================================

def validate_positive_integer(
    value: Any,
    field_name: str,
    minimum: int = 1,
    maximum: Optional[int] = None,
) -> int:

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    if value < minimum:
        raise ValueError(
            f"{field_name} must be at least {minimum}."
        )

    if maximum is not None and value > maximum:
        raise ValueError(
            f"{field_name} must not exceed {maximum}."
        )

    return value


def validate_max_clips(
    max_clips: Any,
) -> int:

    return validate_positive_integer(
        value=max_clips,
        field_name="Max clips",
        minimum=1,
        maximum=100,
    )


def validate_research_limit(
    research_limit: Any,
) -> int:

    return validate_positive_integer(
        value=research_limit,
        field_name="Research limit",
        minimum=1,
        maximum=50,
    )


# ============================================================
# PATH VALIDATION
# ============================================================

def validate_file_path(
    file_path: str | Path,
    field_name: str = "File",
    must_exist: bool = False,
) -> str:

    if file_path is None:
        raise ValueError(
            f"{field_name} path is required."
        )

    path = Path(file_path)

    if must_exist and not path.exists():
        raise FileNotFoundError(
            f"{field_name} does not exist: {path}"
        )

    return str(path)


def validate_video_file(
    video_path: str | Path,
    must_exist: bool = True,
) -> str:

    path = Path(
        validate_file_path(
            video_path,
            field_name="Video",
            must_exist=must_exist,
        )
    )

    if path.suffix.lower() not in {
        ".mp4",
        ".mkv",
        ".mov",
        ".webm",
        ".avi",
        ".m4v",
    }:
        raise ValueError(
            f"Unsupported video format: {path.suffix}"
        )

    return str(path)


# ============================================================
# JOB VALIDATION
# ============================================================

def validate_job_type(
    job_type: str,
) -> str:

    job_type = clean_string(job_type).lower()

    if job_type not in SUPPORTED_JOB_TYPES:
        raise ValueError(
            f"Unsupported job type: {job_type}"
        )

    return job_type


def validate_status(
    status: str,
) -> str:

    status = clean_string(status).lower()

    if status not in SUPPORTED_STATUSES:
        raise ValueError(
            f"Unsupported job status: {status}"
        )

    return status


def validate_job(
    job: dict,
) -> dict:

    if not isinstance(job, dict):
        raise ValueError(
            "Job must be a dictionary."
        )

    job_id = validate_job_id(
        job.get("job_id", "")
    )

    job_type = validate_job_type(
        job.get("job_type", "")
    )

    input_value = clean_string(
        job.get("input_value", "")
    )

    if not input_value:
        raise ValueError(
            "Job input_value is required."
        )

    if job_type == "video":
        input_value = validate_video_url(
            input_value
        )
    else:
        input_value = validate_topic(
            input_value
        )

    reference_url = validate_reference_url(
        job.get("reference_url")
    )

    status = job.get(
        "status",
        "queued",
    )

    status = validate_status(status)

    return {
        **job,
        "job_id": job_id,
        "job_type": job_type,
        "input_value": input_value,
        "reference_url": reference_url,
        "status": status,
    }


# ============================================================
# PIPELINE SETTINGS VALIDATION
# ============================================================

def validate_pipeline_settings(
    language: str = "en",
    max_clips: int = 10,
    make_vertical: bool = True,
    keep_audio: bool = False,
) -> dict:

    language = validate_language(
        language
    )

    max_clips = validate_max_clips(
        max_clips
    )

    if not isinstance(
        make_vertical,
        bool,
    ):
        raise ValueError(
            "make_vertical must be True or False."
        )

    if not isinstance(
        keep_audio,
        bool,
    ):
        raise ValueError(
            "keep_audio must be True or False."
        )

    return {
        "language": language,
        "max_clips": max_clips,
        "make_vertical": make_vertical,
        "keep_audio": keep_audio,
    }


# ============================================================
# TOPIC REQUEST VALIDATION
# ============================================================

def validate_topic_request(
    topic: str,
    reference_url: Optional[str] = None,
    research_limit: int = 10,
) -> dict:

    topic = validate_topic(topic)

    reference_url = validate_reference_url(
        reference_url
    )

    research_limit = validate_research_limit(
        research_limit
    )

    return {
        "topic": topic,
        "reference_url": reference_url,
        "research_limit": research_limit,
    }


# ============================================================
# VIDEO REQUEST VALIDATION
# ============================================================

def validate_video_request(
    video_path: str | Path,
    topic: Optional[str] = None,
    reference_url: Optional[str] = None,
    language: str = "en",
    max_clips: int = 10,
    make_vertical: bool = True,
    keep_audio: bool = False,
) -> dict:

    video_path = validate_video_file(
        video_path,
        must_exist=True,
    )

    if topic is not None:
        topic = validate_topic(topic)

    reference_url = validate_reference_url(
        reference_url
    )

    settings = validate_pipeline_settings(
        language=language,
        max_clips=max_clips,
        make_vertical=make_vertical,
        keep_audio=keep_audio,
    )

    return {
        "video_path": video_path,
        "topic": topic,
        "reference_url": reference_url,
        **settings,
    }


# ============================================================
# GENERAL VALIDATION
# ============================================================

def validate_job_input(
    job_type: str,
    input_value: str,
    reference_url: Optional[str] = None,
) -> dict:

    job_type = validate_job_type(
        job_type
    )

    if job_type == "video":
        input_value = validate_video_url(
            input_value
        )
    else:
        input_value = validate_topic(
            input_value
        )

    reference_url = validate_reference_url(
        reference_url
    )

    return {
        "job_type": job_type,
        "input_value": input_value,
        "reference_url": reference_url,
    }


def validate_all(
    *,
    job: Optional[dict] = None,
    topic: Optional[str] = None,
    video_path: Optional[str | Path] = None,
    video_url: Optional[str] = None,
    reference_url: Optional[str] = None,
    language: str = "en",
    max_clips: int = 10,
    research_limit: int = 10,
    make_vertical: bool = True,
    keep_audio: bool = False,
) -> dict:
    """
    Central validation entry point.

    Used by higher-level orchestration code so validation
    stays in one place.
    """

    result: dict = {}

    if job is not None:
        result["job"] = validate_job(job)

    if topic is not None:
        result["topic"] = validate_topic(topic)

    if video_url is not None:
        result["video_url"] = validate_video_url(
            video_url
        )

    if video_path is not None:
        result["video_path"] = validate_video_file(
            video_path,
            must_exist=True,
        )

    if reference_url is not None:
        result["reference_url"] = validate_reference_url(
            reference_url
        )

    result["settings"] = validate_pipeline_settings(
        language=language,
        max_clips=max_clips,
        make_vertical=make_vertical,
        keep_audio=keep_audio,
    )

    result["research_limit"] = validate_research_limit(
        research_limit
    )

    return result
