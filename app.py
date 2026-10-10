import base64
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

REPO = "miang20/auto-faceless-video-creator"
BASE = Path.home() / "v2-test"
JOBS_DIR = BASE / "jobs"

PHONE_MOVIES = Path.home() / "storage" / "shared" / "Movies" / "AutoFaceless"
PHONE_DCIM = Path.home() / "storage" / "shared" / "DCIM" / "AutoFaceless"


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Auto Faceless Studio V2",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PREMIUM UI
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1400px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .hero {
        padding: 24px;
        border-radius: 18px;
        background: linear-gradient(
            135deg,
            rgba(90,70,180,.25),
            rgba(20,120,180,.15)
        );
        border: 1px solid rgba(255,255,255,.10);
        margin-bottom: 24px;
    }

    .hero h1 {
        margin: 0;
        font-size: 2.3rem;
    }

    .hero p {
        margin: 8px 0 0 0;
        opacity: .75;
    }

    .status-card {
        padding: 16px;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,.10);
        background: rgba(255,255,255,.035);
        margin-bottom: 12px;
    }

    .small {
        opacity: .65;
        font-size: .85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GITHUB
# ============================================================

def load_github_token():
    env_path = (
        Path.home().parent
        / "usr"
        / "var"
        / "service"
        / "af-v2-worker"
        / "env"
        / "GITHUB_TOKEN"
    )

    if env_path.exists():
        token = env_path.read_text().strip()
        if token:
            return token

    return os.environ.get("GITHUB_TOKEN")


def github_headers():
    token = load_github_token()

    if not token:
        raise RuntimeError("GITHUB_TOKEN not found.")

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def github_jobs():
    url = f"https://api.github.com/repos/{REPO}/contents/jobs"

    r = requests.get(
        url,
        headers=github_headers(),
        timeout=30,
    )
    r.raise_for_status()

    jobs = []

    for item in r.json():
        if not item.get("name", "").endswith(".json"):
            continue

        try:
            jr = requests.get(
                item["download_url"],
                timeout=30,
            )
            jr.raise_for_status()
            job = jr.json()

            if "job_id" in job:
                jobs.append(job)

        except Exception:
            continue

    # Sort by actual creation time; legacy/requeued jobs fall back to updated_at.
    # UUID-based job_id sorting is random and can show an older job as the latest.
    jobs.sort(
        key=lambda x: x.get("created_at") or x.get("updated_at") or "",
        reverse=True,
    )

    return jobs


def create_v2_job(
    input_value,
    duration,
    max_clips,
    caption_style,
    caption_settings,
    editing_settings,
):
    # GitHub Contents API can return 409 when the worker commits another job
    # at the same time. Retry with a fresh unique ID instead of failing the UI.
    last_error = None
    for attempt in range(1, 6):
        job_id = f"v2_{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued",
            "pipeline": "video",
            "pipeline_version": "2.0",
            "input_value": input_value,
            "reference_url": input_value,
            "duration": int(duration),
            "max_clips": int(max_clips),
            "caption_style": caption_style,
            "caption_settings": caption_settings,
            "editing_settings": editing_settings,
        }

        url = f"https://api.github.com/repos/{REPO}/contents/jobs/{job_id}.json"
        content = base64.b64encode(
            json.dumps(job, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        payload = {
            "message": f"queue V2 job {job_id}",
            "content": content,
        }

        try:
            response = requests.put(
                url,
                headers=github_headers(),
                json=payload,
                timeout=30,
            )
            if response.status_code == 409:
                last_error = RuntimeError(
                    f"GitHub returned 409 Conflict while queuing {job_id}; "
                    f"retry {attempt}/5. Response: {response.text[:500]}"
                )
                continue
            response.raise_for_status()
        except requests.RequestException as error:
            response_text = ""
            if getattr(error, "response", None) is not None:
                response_text = error.response.text[:500]
            if getattr(error, "response", None) is not None and error.response.status_code == 409:
                last_error = error
                continue
            raise RuntimeError(
                f"Could not queue V2 job ({type(error).__name__}): "
                f"{response_text or str(error)}"
            ) from error

        # Persist the local copy only after GitHub confirms the job exists.
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        local_path = JOBS_DIR / f"{job_id}.json"
        local_path.write_text(
            json.dumps(job, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return job_id, local_path

    raise RuntimeError(
        "GitHub kept returning 409 Conflict after 5 attempts. "
        "No local queued job was written. " + str(last_error)
    )


# ============================================================
# PHONE / PHOTOS
# ============================================================

def import_to_photos(video_path):
    """
    Copies the final video into Android shared storage and
    asks Android media scanner to index it for Google Photos.
    """

    source = Path(video_path)

    if not source.exists():
        raise FileNotFoundError(source)

    PHONE_MOVIES.mkdir(
        parents=True,
        exist_ok=True,
    )

    PHONE_DCIM.mkdir(
        parents=True,
        exist_ok=True,
    )

    movie_target = PHONE_MOVIES / source.name
    dcim_target = PHONE_DCIM / source.name

    shutil.copy2(
        source,
        movie_target,
    )

    shutil.copy2(
        source,
        dcim_target,
    )

    scan_targets = [
        str(movie_target),
        str(dcim_target),
    ]

    for target in scan_targets:
        try:
            subprocess.run(
                ["termux-media-scan", target],
                timeout=15,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    return dcim_target


# ============================================================
# FIND COMPLETED VIDEOS
# ============================================================

def completed_videos():
    paths = []

    search_dirs = [
        PHONE_MOVIES,
        PHONE_DCIM,
        BASE / "output" / "jobs",
        BASE / "repo" / "output",
    ]

    seen = set()

    for directory in search_dirs:
        if not directory.exists():
            continue

        for pattern in ("*.mp4", "*.MP4"):
            for path in directory.rglob(pattern):
                try:
                    resolved = str(path.resolve())

                    if resolved in seen:
                        continue

                    if path.stat().st_size <= 0:
                        continue

                    seen.add(resolved)
                    paths.append(path)

                except Exception:
                    pass

    paths.sort(
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    return paths


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>🎬 Auto Faceless Studio V2</h1>
        <p>
            AI-assisted clip intelligence → editing → captions →
            final vertical video
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("⚡ V2 Control")

    if st.button(
        "🔄 Refresh Dashboard",
        use_container_width=True,
    ):
        st.rerun()

    st.divider()

    st.caption("V2 Pipeline")
    st.code(
        "YouTube\n"
        "↓\n"
        "GitHub Job\n"
        "↓\n"
        "Worker\n"
        "↓\n"
        "Downloader\n"
        "↓\n"
        "Analysis\n"
        "↓\n"
        "Clip Intelligence\n"
        "↓\n"
        "Video Processing\n"
        "↓\n"
        "Final MP4",
        language="text",
    )


# ============================================================
# CREATE JOB
# ============================================================

st.header("🚀 Create V2 Video")

source_value = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=...",
)

col1, col2, col3 = st.columns(3)

with col1:
    duration = st.number_input(
        "Output Duration",
        min_value=10,
        max_value=180,
        value=30,
        step=5,
        help="Target duration of the final video.",
    )

with col2:
    max_clips = st.number_input(
        "Max Clips",
        min_value=1,
        max_value=20,
        value=10,
        step=1,
    )

with col3:
    caption_style = st.selectbox(
        "Caption Style",
        [
            "Bold Viral",
            "Clean",
            "Minimal",
        ],
    )


# ============================================================
# CAPTIONS
# ============================================================

with st.expander("📝 Caption Settings", expanded=True):

    caption_enabled = st.checkbox(
        "Enable Captions",
        value=True,
    )

    cap_col1, cap_col2 = st.columns(2)
    with cap_col1:
        caption_font_size = st.slider(
            "Caption Font Size",
            min_value=32,
            max_value=82,
            value=58,
            step=2,
        )
        caption_position = st.selectbox(
            "Caption Position",
            ["lower-third", "bottom", "center", "top"],
            index=0,
        )
    with cap_col2:
        caption_stroke = st.checkbox("Black Text Outline", value=True)
        caption_shadow = st.checkbox("Text Shadow", value=True)
        caption_box = st.checkbox("Caption Background Box", value=False)

    caption_settings = {
        "enabled": caption_enabled,
        "font": "DejaVu Sans",
        "font_size": int(caption_font_size),
        "position": caption_position,
        "text_color": "white",
        "highlight_color": "yellow",
        "stroke": caption_stroke,
        "stroke_width": 3,
        "shadow": caption_shadow,
        "background_box": caption_box,
        "box": caption_box,
        "words_per_line": 3,
        "max_lines": 1,
    }


# ============================================================
# EDITING
# ============================================================

with st.expander("🎞️ Editing Settings", expanded=True):

    c1, c2, c3 = st.columns(3)

    with c1:
        dynamic_zoom = st.checkbox(
            "Dynamic Zoom",
            value=True,
        )

        remove_silence = st.checkbox(
            "Remove Silence",
            value=True,
        )

    with c2:
        normalize_audio = st.checkbox(
            "Normalize Audio",
            value=True,
        )

        reaction_selection = st.checkbox(
            "Reaction / Payoff Selection",
            value=True,
        )

    with c3:
        contextual_broll = st.checkbox(
            "Contextual B-roll",
            value=False,
        )

        visual_change_rhythm = st.checkbox(
            "Visual Change Rhythm",
            value=True,
        )

    editing_settings = {
        "dynamic_zoom": dynamic_zoom,
        "remove_silence": remove_silence,
        "normalize_audio": normalize_audio,
        "contextual_broll": contextual_broll,
        "reaction_selection": reaction_selection,
        "visual_change_rhythm": visual_change_rhythm,
    }


# ============================================================
# QUEUE
# ============================================================

if st.button(
    "🚀 CREATE V2 JOB",
    type="primary",
    use_container_width=True,
):

    if not source_value.strip():
        st.error("YouTube URL required.")
    else:
        try:
            with st.spinner("Creating V2 job..."):

                job_id, local_path = create_v2_job(
                    input_value=source_value.strip(),
                    duration=duration,
                    max_clips=max_clips,
                    caption_style=caption_style,
                    caption_settings=caption_settings,
                    editing_settings=editing_settings,
                )

            st.success("✅ V2 job queued.")

            st.code(
                job_id,
                language="text",
            )

            st.info(
                "Worker will automatically pick this job."
            )

        except Exception as error:
            st.error(
                f"Failed to create V2 job: {error}"
            )


# ============================================================
# LIVE JOB MONITOR + COMPLETION POPUP + DOWNLOAD
# ============================================================

def _resolve_job_video(job):
    """Resolve this job's exact MP4 without accidentally showing another job's video."""
    result_path = str(job.get("result_path") or "").strip()
    if result_path:
        candidate = Path(result_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        # The worker may store the MP4 path directly rather than a JSON manifest.
        if candidate.is_file() and candidate.stat().st_size > 0 and candidate.suffix.lower() == ".mp4":
            return candidate
        if candidate.is_file():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                found = []

                def walk(value, preferred=False):
                    if isinstance(value, dict):
                        for key, item in value.items():
                            key_preferred = any(
                                token in str(key).lower()
                                for token in ("output_path", "final_video", "video_path", "rendered_path")
                            )
                            walk(item, preferred or key_preferred)
                    elif isinstance(value, list):
                        for item in value:
                            walk(item, preferred)
                    elif isinstance(value, str) and value.lower().endswith(".mp4"):
                        path = Path(value).expanduser()
                        if not path.is_absolute():
                            path = Path.cwd() / path
                        if path.is_file() and path.stat().st_size > 0:
                            found.append((preferred, path))

                walk(payload)
                if found:
                    found.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)
                    return found[0][1]
            except Exception:
                pass

    videos = completed_videos()
    if not videos:
        return None

    # Rendered filenames use the YouTube video ID, not the GitHub job ID.
    source_url = str(job.get("input_value") or job.get("reference_url") or "")
    video_id = ""
    for marker in ("youtu.be/", "shorts/", "embed/", "watch?v="):
        if marker in source_url:
            video_id = source_url.split(marker, 1)[1].split("?", 1)[0].split("&", 1)[0].split("#", 1)[0].strip("/")
            if video_id:
                break

    if video_id:
        matching = [video for video in videos if video_id in video.name]
        if matching:
            return max(matching, key=lambda path: path.stat().st_mtime)

    job_id = str(job.get("job_id") or "")
    matching = [video for video in videos if job_id and job_id in video.name]
    if matching:
        return max(matching, key=lambda path: path.stat().st_mtime)

    return None


def _render_video_card(video, prefix="video"):
    st.markdown(f"**{video.name}**")
    size_mb = video.stat().st_size / (1024 * 1024)
    st.caption(f"{size_mb:.1f} MB • {video.parent}")
    with open(video, "rb") as file:
        video_bytes = file.read()
    st.video(video_bytes)
    st.download_button(
        label="⬇️ DOWNLOAD VIDEO",
        data=video_bytes,
        file_name=video.name,
        mime="video/mp4",
        use_container_width=True,
        key=f"{prefix}_download_{video}",
    )
    if st.button(
        "📱 Send to Google Photos / Android Media",
        key=f"{prefix}_photos_{video}",
        use_container_width=True,
    ):
        try:
            target = import_to_photos(video)
            st.success(f"Saved to Android DCIM: {target.name}")
            st.info("Android media scan request sent.")
        except Exception as error:
            st.error(f"Phone media copy failed: {error}")


if hasattr(st, "dialog"):
    @st.dialog("✅ Your V2 video is ready", width="large")
    def _show_video_ready(video_path):
        video = Path(video_path)
        if not video.is_file() or video.stat().st_size <= 0:
            st.warning("Job completed, but the MP4 is not accessible in this app session yet.")
            st.caption("Use Refresh Dashboard or wait for the next automatic refresh.")
            return
        st.success("Render complete. Your video is ready to preview and download.")
        _render_video_card(video, prefix="popup")
else:
    def _show_video_ready(video_path):
        st.success(f"Your V2 video is ready: {Path(video_path).name}")


def _render_live_dashboard():
    st.divider()
    st.header("📊 V2 Jobs")
    st.caption("Live status refreshes automatically while this dashboard is open.")

    try:
        jobs = github_jobs()
    except Exception as error:
        jobs = []
        st.warning(f"Could not load GitHub jobs: {error}")

    if not jobs:
        st.info("No V2 jobs found yet.")
    else:
        for job in jobs[:5]:
            status = str(job.get("status", "unknown")).lower()
            job_id = str(job.get("job_id", "unknown"))
            icon = {
                "completed": "✅",
                "running": "🟡",
                "processing": "🟡",
                "downloading": "🔵",
                "failed": "❌",
                "queued": "⏳",
            }.get(status, "⚪")
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"### {icon} `{job_id}`")
                    st.caption(f"Status: **{status.upper()}**")
                    if job.get("input_value"):
                        st.caption(str(job["input_value"]))
                    if job.get("error"):
                        st.error(str(job["error"]))
                    if status == "completed":
                        result_video = _resolve_job_video(job)
                        if result_video:
                            with open(result_video, "rb") as handle:
                                data = handle.read()
                            st.download_button(
                                "⬇️ DOWNLOAD THIS JOB",
                                data=data,
                                file_name=result_video.name,
                                mime="video/mp4",
                                key=f"job_download_{job_id}",
                                use_container_width=True,
                            )
                        else:
                            st.warning("Job says completed, but its MP4 could not be located yet.")
                with right:
                    st.metric("Duration", f'{job.get("duration", 0)}s')

            if status == "completed":
                notified = st.session_state.setdefault("v2_notified_completed", [])
                if job_id not in notified:
                    video = _resolve_job_video(job)
                    # Mark before opening the dialog so its own rerun cannot
                    # repeatedly reopen the same completion popup.
                    notified.append(job_id)
                    st.session_state["v2_notified_completed"] = notified[-100:]
                    if video:
                        _show_video_ready(str(video))

    st.divider()
    st.header("🎥 Final Videos")
    videos = completed_videos()
    if not videos:
        st.info("No completed videos found yet. When V2 finishes, the MP4 will appear here automatically.")
    else:
        for video in videos[:10]:
            try:
                with st.container(border=True):
                    _render_video_card(video, prefix="gallery")
            except Exception as error:
                st.error(f"Could not load {video.name}: {error}")


if hasattr(st, "fragment"):
    @st.fragment(run_every="8s")
    def _live_dashboard_fragment():
        _render_live_dashboard()

    _live_dashboard_fragment()
else:
    st.info("Automatic refresh is unavailable in this Streamlit version. Tap Refresh Dashboard to check job completion.")
    _render_live_dashboard()


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption("Auto Faceless Studio V2 • Automatic job monitor • Final MP4 preview/download • Android media export")
