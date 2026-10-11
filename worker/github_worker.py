from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


HOME = Path.home()
BASE = HOME / "v2-test"
REPO_DIR = BASE / "repo"
WORKER_DIR = BASE / "worker"
JOBS_DIR = REPO_DIR / "jobs"
OUTPUT_DIR = BASE / "output" / "jobs"
LOCK_PATH = WORKER_DIR / ".github_worker.lock"
REPO_NAME = "miang20/auto-faceless-video-creator"
API_ROOT = f"https://api.github.com/repos/{REPO_NAME}"
POLL_SECONDS = max(5, int(os.environ.get("POLL_SECONDS", "15")))
TERMINAL_STATES = {"completed", "failed"}
STOP = False


def log(*items: Any) -> None:
    print("[V2]", *items, flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_github_token() -> str:
    candidates = [
        Path(os.environ.get("PREFIX", str(HOME.parent / "usr")))
        / "var" / "service" / "af-v2-worker" / "env" / "GITHUB_TOKEN",
        HOME.parent / "usr" / "var" / "service" / "af-v2-worker" / "env" / "GITHUB_TOKEN",
    ]
    for path in candidates:
        try:
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            pass
    value = os.environ.get("GITHUB_TOKEN", "").strip()
    if value:
        return value
    raise RuntimeError("GITHUB_TOKEN was not found in the af-v2-worker service environment or process environment.")


TOKEN = None
SESSION = requests.Session()


def headers() -> dict[str, str]:
    if not TOKEN:
        raise RuntimeError("GitHub token is not loaded.")
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def job_api_url(job_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
        raise ValueError(f"Unsafe job ID: {job_id!r}")
    return f"{API_ROOT}/contents/jobs/{job_id}.json"


def read_remote_job(job_id: str) -> tuple[dict, str]:
    response = SESSION.get(job_api_url(job_id), headers=headers(), params={"ref": "main"}, timeout=30)
    response.raise_for_status()
    body = response.json()
    encoded = body.get("content", "")
    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
    return payload, str(body["sha"])


def update_remote_job(job_id: str, changes: dict, allowed_current: set[str] | None = None) -> dict:
    """Contents-API compare-and-update with terminal-state protection and 409 retry."""
    last_error = None
    for attempt in range(1, 7):
        try:
            current, sha = read_remote_job(job_id)
            status = str(current.get("status", "queued")).lower()
            desired = str(changes.get("status", status)).lower()

            if allowed_current is not None and status not in allowed_current:
                return current
            if status in TERMINAL_STATES and desired not in TERMINAL_STATES:
                return current
            if status in TERMINAL_STATES and desired in TERMINAL_STATES:
                return current

            merged = dict(current)
            merged.update(changes)
            merged["updated_at"] = utc_now()
            payload = {
                "message": f"V2 job {job_id}: {merged.get('status', status)}",
                "content": base64.b64encode(
                    (json.dumps(merged, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                ).decode("ascii"),
                "sha": sha,
                "branch": "main",
            }
            response = SESSION.put(job_api_url(job_id), headers=headers(), json=payload, timeout=30)
            if response.status_code == 409:
                last_error = f"GitHub 409 while updating {job_id}, attempt {attempt}/6"
                time.sleep(min(attempt, 3))
                continue
            response.raise_for_status()
            return merged
        except Exception as exc:
            last_error = str(exc)
            if attempt < 6:
                time.sleep(min(attempt, 3))
                continue
    raise RuntimeError(f"Could not update GitHub job {job_id}: {last_error}")


def list_remote_jobs() -> list[dict]:
    response = SESSION.get(f"{API_ROOT}/contents/jobs", headers=headers(), params={"ref": "main"}, timeout=30)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    result = []
    for item in response.json():
        name = str(item.get("name", ""))
        if not name.endswith(".json") or not item.get("download_url"):
            continue
        try:
            raw = SESSION.get(item["download_url"], timeout=30)
            raw.raise_for_status()
            job = raw.json()
            if isinstance(job, dict) and job.get("job_id"):
                result.append(job)
        except Exception as exc:
            log("Could not read job", name, str(exc)[:180])
    result.sort(key=lambda item: str(item.get("created_at") or item.get("updated_at") or ""))
    return result


def write_local_job(job: dict) -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = str(job.get("job_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
        raise ValueError(f"Invalid job ID: {job_id!r}")
    path = JOBS_DIR / f"{job_id}.json"
    path.write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def find_existing_whisper_path() -> tuple[str | None, str | None]:
    # runit services can start with an incomplete HOME environment. Resolve the
    # Termux home from PREFIX as well as the process HOME so an installed
    # Whisper binary remains discoverable under the service account.
    homes: list[Path] = []
    for raw in (
        str(HOME),
        os.environ.get("HOME", ""),
        str(Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")).parent / "home"),
        "/data/data/com.termux/files/home",
    ):
        if raw:
            candidate = Path(raw).expanduser()
            if candidate not in homes:
                homes.append(candidate)

    commands: list[Path] = []
    models: list[Path] = []
    for home in homes:
        roots = [home / "FaisalClipFactory" / "whisper.cpp", home / "whisper.cpp"]
        for root in roots:
            commands.extend([
                root / "build" / "bin" / "whisper-cli",
                root / "build" / "bin" / "main",
            ])
            for model_name in ("ggml-small.bin", "ggml-small.en.bin", "ggml-base.bin", "ggml-base.en.bin"):
                models.extend([
                    root / "models" / model_name,
                    root / model_name,
                    root / "build" / "bin" / model_name,
                ])

    command = next((str(path) for path in commands if path.is_file() and os.access(path, os.X_OK)), None)
    if command is None:
        for name in ("whisper-cli", "whisper", "main"):
            from_path = shutil.which(name)
            if from_path:
                command = from_path
                break
    model = next((str(path) for path in models if path.is_file()), None)
    return command, model


def verify_final_mp4(path_value: str, make_vertical: bool = True) -> dict:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = REPO_DIR / path
    if not path.is_file() or path.stat().st_size < 100_000:
        raise RuntimeError(f"Renderer reported success but final MP4 is missing or too small: {path}")
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate",
            "-show_entries", "format=duration,size",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError("Final MP4 failed ffprobe validation: " + (probe.stderr or "")[-1000:])
    data = json.loads(probe.stdout or "{}")
    streams = data.get("streams") or []
    fmt = data.get("format") or {}
    if not streams:
        raise RuntimeError("Final MP4 contains no video stream.")
    stream = streams[0]
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    duration = float(fmt.get("duration", 0) or 0)
    expected_width, expected_height = (1080, 1920) if make_vertical else (1920, 1080)
    if (width, height) != (expected_width, expected_height):
        raise RuntimeError(
            f"Final MP4 is {width}x{height}, expected {expected_width}x{expected_height} "
            f"for {'vertical' if make_vertical else 'landscape'} output."
        )
    if duration < 1.0:
        raise RuntimeError(f"Final MP4 duration is invalid: {duration:.2f}s.")
    return {
        "output_path": str(path),
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "fps": stream.get("avg_frame_rate"),
    }


def process_job(remote_job: dict) -> None:
    job_id = str(remote_job["job_id"])
    current = update_remote_job(
        job_id,
        {"status": "running", "error": None},
        allowed_current={"queued"},
    )
    if str(current.get("status", "")).lower() != "running":
        log("Skipping job whose state changed before claim:", job_id, current.get("status"))
        return

    job = dict(current)
    job["status"] = "running"
    write_local_job(job)
    log("JOB FOUND:", job_id, "URL:", job.get("input_value"))

    try:
        from core.job_runner import run_video_job

        whisper_command, model_path = find_existing_whisper_path()
        if not whisper_command or not model_path:
            log("Whisper executable/model not found; pipeline will use its configured fallback if available.")

        result = run_video_job(
            job_id=job_id,
            whisper_command=whisper_command,
            model_path=model_path,
            language=str(job.get("language") or "en"),
            max_clips=int(job.get("max_clips", 10) or 10),
            output_dir=str(OUTPUT_DIR),
            make_vertical=bool((job.get("editing_settings") or {}).get("make_vertical", True)),
            keep_audio=False,
        )
        if not isinstance(result, dict) or not result.get("success"):
            detail = result.get("error", "Pipeline returned no successful result.") if isinstance(result, dict) else "Pipeline returned an invalid result."
            raise RuntimeError(str(detail))

        final_path = str(
            result.get("output_path")
            or result.get("final_video")
            or result.get("rendered_path")
            or ""
        ).strip()
        make_vertical = bool((job.get("editing_settings") or {}).get("make_vertical", True))
        verified = verify_final_mp4(final_path, make_vertical=make_vertical)
        changes = {
            "status": "completed",
            "error": None,
            "result_path": verified["output_path"],
            "output_path": verified["output_path"],
            "size_bytes": verified["size_bytes"],
            "duration_seconds": verified["duration_seconds"],
            "resolution": f'{verified["width"]}x{verified["height"]}',
            "fps": verified["fps"],
            "phone_copy_path": result.get("phone_copy_path"),
            "pipeline_result_path": result.get("result_path"),
        }
        final_job = update_remote_job(job_id, changes, allowed_current={"running"})
        log("JOB COMPLETED:", job_id, final_job.get("result_path"), verified["duration_seconds"], "sec", verified["resolution"])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        try:
            update_remote_job(
                job_id,
                {"status": "failed", "error": error[:7000]},
                allowed_current={"running"},
            )
        except Exception as status_error:
            log("Could not persist failed status:", job_id, str(status_error)[:250])
        log("JOB FAILED:", job_id, error[:1200])


def recover_abandoned_running_jobs() -> None:
    """After this sole worker acquires the process lock, requeue jobs left running by a killed worker."""
    for job in list_remote_jobs():
        if str(job.get("status", "")).lower() == "running":
            job_id = str(job.get("job_id", ""))
            try:
                update_remote_job(
                    job_id,
                    {"status": "queued", "error": "Recovered after worker restart; retrying automatically."},
                    allowed_current={"running"},
                )
                log("Recovered interrupted job:", job_id)
            except Exception as exc:
                log("Could not recover interrupted job:", job_id, str(exc)[:200])


def _handle_stop(signum, frame) -> None:
    global STOP
    STOP = True
    log("Stop signal received; finishing current job before exit.")


def main() -> None:
    global TOKEN
    if not REPO_DIR.is_dir():
        raise RuntimeError(f"Local repository directory is missing: {REPO_DIR}")
    sys.path.insert(0, str(REPO_DIR))
    os.chdir(REPO_DIR)
    WORKER_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN = load_github_token()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    # Keep one and only one active worker, even if an orphan/manual process exists.
    lock_handle = LOCK_PATH.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Another worker owns the lock; this process will wait and cannot process duplicate jobs.")
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

        log("CLEAN WORKER STARTED; repo:", REPO_DIR, "poll:", POLL_SECONDS, "seconds")
        recover_abandoned_running_jobs()

        while not STOP:
            try:
                jobs = list_remote_jobs()
                queued = [job for job in jobs if str(job.get("status", "")).lower() == "queued"]
                if not queued:
                    log("No queued jobs.")
                else:
                    for job in queued:
                        if STOP:
                            break
                        process_job(job)
            except Exception as exc:
                log("Poll cycle error:", type(exc).__name__, str(exc)[:500])
            if not STOP:
                time.sleep(POLL_SECONDS)
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        lock_handle.close()


if __name__ == "__main__":
    main()
