from __future__ import annotations

import os
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CORE_DIR = BASE_DIR / "core"
JOBS_DIR = BASE_DIR / "jobs"
DOWNLOADS_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"

PIPELINE_OUTPUT_DIR = OUTPUT_DIR / "pipeline"
JOB_OUTPUT_DIR = OUTPUT_DIR / "jobs"

RESEARCH_OUTPUT_DIR = OUTPUT_DIR / "research"
ANALYSIS_OUTPUT_DIR = OUTPUT_DIR / "analysis"
SCRIPT_OUTPUT_DIR = OUTPUT_DIR / "scripts"
CLIPS_OUTPUT_DIR = OUTPUT_DIR / "clips"


# ============================================================
# CREATE REQUIRED DIRECTORIES
# ============================================================

for directory in (
    JOBS_DIR,
    DOWNLOADS_DIR,
    OUTPUT_DIR,
    PIPELINE_OUTPUT_DIR,
    JOB_OUTPUT_DIR,
    RESEARCH_OUTPUT_DIR,
    ANALYSIS_OUTPUT_DIR,
    SCRIPT_OUTPUT_DIR,
    CLIPS_OUTPUT_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# ============================================================
# GITHUB
# ============================================================

GITHUB_OWNER = os.getenv(
    "GITHUB_OWNER",
    "miang20",
)

GITHUB_REPO = os.getenv(
    "GITHUB_REPO",
    "auto-faceless-video-creator",
)

GITHUB_TOKEN_ENV = "GITHUB_TOKEN"


def get_github_token() -> str | None:
    """
    Return the GitHub token from the environment.
    """

    return os.getenv(GITHUB_TOKEN_ENV)


# ============================================================
# PIPELINE
# ============================================================

PIPELINE_VERSION = "1.0"

DEFAULT_RESEARCH_LIMIT = 10

DEFAULT_MAX_CLIPS = 10

DEFAULT_LANGUAGE = "en"

DEFAULT_MAKE_VERTICAL = True

DEFAULT_KEEP_AUDIO = False


# ============================================================
# VIDEO
# ============================================================

DEFAULT_VIDEO_EXTENSION = ".mp4"

DEFAULT_CLIP_EXTENSION = ".mp4"

DEFAULT_OUTPUT_FPS = 30

DEFAULT_VERTICAL_WIDTH = 1080

DEFAULT_VERTICAL_HEIGHT = 1920


# ============================================================
# TRANSCRIPTION
# ============================================================

WHISPER_COMMAND_ENV = "WHISPER_COMMAND"

WHISPER_MODEL_ENV = "WHISPER_MODEL"


def get_whisper_command() -> str | None:
    """
    Return configured Whisper executable path/command.
    """

    return os.getenv(WHISPER_COMMAND_ENV)


def get_whisper_model() -> str | None:
    """
    Return configured Whisper model path.
    """

    return os.getenv(WHISPER_MODEL_ENV)


# ============================================================
# FFmpeg
# ============================================================

FFMPEG_COMMAND = os.getenv(
    "FFMPEG_COMMAND",
    "ffmpeg",
)

FFPROBE_COMMAND = os.getenv(
    "FFPROBE_COMMAND",
    "ffprobe",
)


# ============================================================
# JOB SETTINGS
# ============================================================

JOB_STATUS_QUEUED = "queued"

JOB_STATUS_DOWNLOADING = "downloading"

JOB_STATUS_PROCESSING = "processing"

JOB_STATUS_COMPLETED = "completed"

JOB_STATUS_FAILED = "failed"


VALID_JOB_STATUSES = {
    JOB_STATUS_QUEUED,
    JOB_STATUS_DOWNLOADING,
    JOB_STATUS_PROCESSING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
}


# ============================================================
# JOB TYPES
# ============================================================

JOB_TYPE_VIDEO = "video"

JOB_TYPE_TOPIC = "topic"


# ============================================================
# FILE NAMES
# ============================================================

def get_job_file(job_id: str) -> Path:
    """
    Return the local JSON path for a job.
    """

    return JOBS_DIR / f"{job_id}.json"


def get_job_output_dir(job_id: str) -> Path:
    """
    Return the dedicated output directory for a job.
    """

    directory = JOB_OUTPUT_DIR / job_id
    directory.mkdir(parents=True, exist_ok=True)

    return directory


def get_download_path(filename: str) -> Path:
    """
    Return a path inside the downloads directory.
    """

    return DOWNLOADS_DIR / filename


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def get_env(
    name: str,
    default: str | None = None,
) -> str | None:
    """
    Read an environment variable safely.
    """

    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return value.strip()


def get_env_bool(
    name: str,
    default: bool = False,
) -> bool:
    """
    Read a boolean environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_env_int(
    name: str,
    default: int,
) -> int:
    """
    Read an integer environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


# ============================================================
# CONFIG SUMMARY
# ============================================================

def get_config() -> dict:
    """
    Return the complete non-secret application configuration.

    Secrets such as GitHub tokens are intentionally excluded.
    """

    return {
        "base_dir": str(BASE_DIR),
        "core_dir": str(CORE_DIR),
        "jobs_dir": str(JOBS_DIR),
        "downloads_dir": str(DOWNLOADS_DIR),
        "output_dir": str(OUTPUT_DIR),
        "pipeline_output_dir": str(PIPELINE_OUTPUT_DIR),
        "job_output_dir": str(JOB_OUTPUT_DIR),
        "research_output_dir": str(RESEARCH_OUTPUT_DIR),
        "analysis_output_dir": str(ANALYSIS_OUTPUT_DIR),
        "script_output_dir": str(SCRIPT_OUTPUT_DIR),
        "clips_output_dir": str(CLIPS_OUTPUT_DIR),
        "github_owner": GITHUB_OWNER,
        "github_repo": GITHUB_REPO,
        "pipeline_version": PIPELINE_VERSION,
        "default_research_limit": DEFAULT_RESEARCH_LIMIT,
        "default_max_clips": DEFAULT_MAX_CLIPS,
        "default_language": DEFAULT_LANGUAGE,
        "default_make_vertical": DEFAULT_MAKE_VERTICAL,
        "default_keep_audio": DEFAULT_KEEP_AUDIO,
        "default_video_extension": DEFAULT_VIDEO_EXTENSION,
        "default_clip_extension": DEFAULT_CLIP_EXTENSION,
        "default_output_fps": DEFAULT_OUTPUT_FPS,
        "default_vertical_width": DEFAULT_VERTICAL_WIDTH,
        "default_vertical_height": DEFAULT_VERTICAL_HEIGHT,
        "ffmpeg_command": FFMPEG_COMMAND,
        "ffprobe_command": FFPROBE_COMMAND,
        "whisper_command_configured": get_whisper_command()
        is not None,
        "whisper_model_configured": get_whisper_model()
        is not None,
    }
