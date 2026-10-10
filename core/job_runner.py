from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from core.jobs import create_job
from core.job_store import save_job, load_job
from core.github_jobs import create_github_job
from core.downloader import download_video
from core.pipeline import execute_video_pipeline


def _copy_final_video_to_phone(result, output_dir) -> Optional[str]:
    """Best-effort export of the rendered MP4 to Android shared storage."""
    home = Path.home()
    candidates = []

    def collect(value, preferred=False):
        if isinstance(value, dict):
            for key, item in value.items():
                key_is_path = any(
                    token in str(key).lower()
                    for token in ("output", "final", "render", "video_path")
                )
                collect(item, preferred or key_is_path)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item, preferred)
        elif isinstance(value, str) and value.lower().endswith(".mp4"):
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            if path.is_file():
                candidates.append((preferred, path))

    try:
        collect(result)
        candidates.sort(key=lambda item: item[0], reverse=True)
        source = candidates[0][1] if candidates else None

        if source is None:
            output = Path(output_dir)
            if output.exists():
                matches = [
                    path for path in output.rglob("*.mp4")
                    if path.is_file()
                    and (
                        path.name.lower().startswith("final_")
                        or "final" in path.name.lower()
                    )
                ]
                if matches:
                    source = max(matches, key=lambda path: path.stat().st_mtime)

        if source is None:
            print("[V2 PHONE COPY] Skipped: final MP4 path not found.")
            return None

        destinations = [
            home / "storage" / "shared" / "Movies" / "AutoFaceless",
            home / "storage" / "shared" / "DCIM" / "AutoFaceless",
        ]
        saved_path = None
        for directory in destinations:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / source.name
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
                try:
                    subprocess.run(
                        ["termux-media-scan", str(target)],
                        timeout=15,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
                if saved_path is None:
                    saved_path = str(target)
            except Exception as copy_error:
                print("[V2 PHONE COPY] Destination skipped:", str(copy_error)[:180])

        if saved_path:
            print("[V2 PHONE COPY] Final MP4 saved:", saved_path)
        return saved_path
    except Exception as copy_error:
        # Storage permission must never turn a valid render into a failed job.
        print("[V2 PHONE COPY] Skipped:", str(copy_error)[:240])
        return None


def create_and_store_job(
    job_id: str,
    job_type: str,
    input_value: str,
    reference_url: Optional[str] = None,
    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """
    Create a job object and persist it locally.
    """

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


def submit_job_to_github(
    token: str,
    job: dict,
) -> str:
    """
    Push a queued job to the GitHub jobs directory.
    """

    return create_github_job(
        token=token,
        job=job,
    )


def download_job_video(
    job: dict,
    output_dir: str | Path = "downloads",
) -> str:
    """
    Download the source video for a video-based job.

    Existing downloader remains unchanged.
    """

    input_value = job.get("input_value")

    if not input_value:
        raise ValueError(
            "Job does not contain an input_value."
        )

    downloaded_path = download_video(input_value)

    source = Path(downloaded_path)

    if not source.exists():
        raise FileNotFoundError(
            f"Downloaded video was not found: {downloaded_path}"
        )

    destination_dir = Path(output_dir)
    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = destination_dir / source.name

    if source.resolve() != destination.resolve():
        destination.write_bytes(
            source.read_bytes()
        )

    return str(destination)


def update_job_status(
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

    if status != "failed":
        job["error"] = None

    job_file = (
        Path(__file__).resolve().parent.parent
        / "jobs"
        / f"{job_id}.json"
    )

    job_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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


def run_video_job(
    job_id: str,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = "en",
    max_clips: int = 10,
    output_dir: str | Path = "output/jobs",
    make_vertical: bool = True,
    keep_audio: bool = False,
) -> dict:
    """
    Execute a stored video job.

    Existing download stage is intentionally preserved.

    Flow:

        Job
          ↓
        Download
          ↓
        Pro V2 Pipeline
          ↓
        Final processing
          ↓
        Result
    """

    job = load_job(job_id)

    try:
        update_job_status(
            job_id=job_id,
            status="downloading",
        )

        # Existing downloader — DO NOT MODIFY.
        video_path = download_job_video(
            job=job,
        )

        update_job_status(
            job_id=job_id,
            status="processing",
        )

        # Read Pro V2 settings from the stored GitHub/local job.
        duration = job.get(
            "duration",
            30,
        )

        caption_style = job.get(
            "caption_style",
            "Bold Viral",
        )

        caption_settings = job.get(
            "caption_settings",
            {},
        )

        editing_settings = job.get(
            "editing_settings",
            {},
        )

        # Keep job-level vertical setting authoritative when present.
        if isinstance(editing_settings, dict):
            make_vertical = editing_settings.get(
                "make_vertical",
                make_vertical,
            )

        result = execute_video_pipeline(
            video_path=video_path,
            topic=job.get("input_value"),
            reference_url=job.get("reference_url"),
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

        if not result.get("success"):
            error = str(result.get("error", "Pipeline execution failed."))
            # Last-resort recovery for FFmpeg drawtext/parser errors. The
            # renderer normally retries the affected segment itself; if an
            # older local renderer or another caption edge case still fails,
            # rerun the same downloaded source and edit plan without captions.
            # This does not touch the frozen downloader or other edit settings.
            caption_settings_enabled = (
                isinstance(caption_settings, dict)
                and caption_settings.get("enabled", True) is not False
            )
            if caption_settings_enabled and "drawtext" in error.lower():
                print(
                    "[V2 JOB] Caption rendering failed; retrying the full "
                    "pipeline once with captions disabled."
                )
                safe_caption_settings = dict(caption_settings)
                safe_caption_settings["enabled"] = False
                result = execute_video_pipeline(
                    video_path=video_path,
                    topic=job.get("input_value"),
                    reference_url=job.get("reference_url"),
                    whisper_command=whisper_command,
                    model_path=model_path,
                    language=language,
                    max_clips=max_clips,
                    output_dir=output_dir,
                    make_vertical=make_vertical,
                    keep_audio=keep_audio,
                    duration=duration,
                    caption_style=caption_style,
                    caption_settings=safe_caption_settings,
                    editing_settings=editing_settings,
                )
                if result.get("success"):
                    result["caption_fallback_used"] = True
                    result["caption_fallback_reason"] = (
                        "FFmpeg drawtext parser failure; captions disabled "
                        "for this render to preserve the final video."
                    )
                else:
                    error = str(result.get("error", error))

            if not result.get("success"):
                update_job_status(
                    job_id=job_id,
                    status="failed",
                    error=error,
                )
                return result

        phone_copy_path = _copy_final_video_to_phone(result, output_dir)
        if phone_copy_path:
            result["phone_copy_path"] = phone_copy_path

        result_file = (
            Path(output_dir)
            / f"{job_id}_result.json"
        )

        result_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with result_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                result,
                file,
                indent=2,
                ensure_ascii=False,
            )

        update_job_status(
            job_id=job_id,
            status="completed",
            result_path=str(result_file),
        )

        result["job_id"] = job_id
        result["result_path"] = str(result_file)

        return result

    except Exception as exc:
        update_job_status(
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


def submit_and_run_video_job(
    token: str,
    job_id: str,
    input_value: str,
    reference_url: Optional[str] = None,
    job_type: str = "video",
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = "en",
    max_clips: int = 10,
    output_dir: str | Path = "output/jobs",
    make_vertical: bool = True,
    keep_audio: bool = False,
    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """
    Convenience function for creating, storing,
    submitting, and executing a Pro V2 video job.
    """

    job = create_and_store_job(
        job_id=job_id,
        job_type=job_type,
        input_value=input_value,
        reference_url=reference_url,
        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    github_path = submit_job_to_github(
        token=token,
        job=job,
    )

    result = run_video_job(
        job_id=job_id,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
        max_clips=max_clips,
        output_dir=output_dir,
        make_vertical=make_vertical,
        keep_audio=keep_audio,
    )

    result["github_job_path"] = github_path

    return result
