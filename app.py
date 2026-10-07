from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import streamlit as st

from core.config import (
    DEFAULT_KEEP_AUDIO,
    DEFAULT_LANGUAGE,
    DEFAULT_MAKE_VERTICAL,
    DEFAULT_MAX_CLIPS,
    DEFAULT_RESEARCH_LIMIT,
    GITHUB_OWNER,
    GITHUB_REPO,
    JOB_OUTPUT_DIR,
)

from core.github_jobs import create_github_job

from core.orchestrator import (
    create_orchestrator_job,
    execute_topic_job,
)

from core.validator import (
    validate_reference_url,
    validate_video_url,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Auto Faceless Video Creator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

APP_TITLE = "Auto Faceless Video Creator"
APP_VERSION = "V2"

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".m4v",
}

CAPTION_PRESETS = {
    "Clean White": {
        "description": "Clean, readable white captions.",
        "style": "clean_white",
    },
    "Bold Viral": {
        "description": "Large high-impact captions for short-form content.",
        "style": "bold_viral",
    },
    "Word Highlight": {
        "description": "Word-by-word emphasis style.",
        "style": "word_highlight",
    },
    "Big Center": {
        "description": "Large centered captions.",
        "style": "big_center",
    },
    "Bottom Subtitles": {
        "description": "Traditional bottom subtitle layout.",
        "style": "bottom_subtitles",
    },
}


# ============================================================
# GITHUB HELPERS
# ============================================================

def get_github_token() -> str:
    """
    Read GitHub token from Streamlit secrets.

    Supports:
        GITHUB_TOKEN
    """
    try:
        token = st.secrets.get("GITHUB_TOKEN")
    except Exception:
        token = None

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is missing from Streamlit secrets."
        )

    return str(token).strip()


def github_request(
    url: str,
    token: str,
    method: str = "GET",
    data: bytes | None = None,
    timeout: int = 30,
) -> Any:
    """
    Generic GitHub API request helper.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if data is not None:
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        body = response.read().decode("utf-8")

    if not body:
        return {}

    return json.loads(body)


@st.cache_data(ttl=10, show_spinner=False)
def get_github_jobs_cached(
    owner: str,
    repo: str,
    token: str,
) -> list[dict]:
    """
    Fetch recent jobs from GitHub.

    Short cache prevents unnecessary API requests while
    still keeping the queue reasonably fresh.
    """
    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/jobs"
    )

    try:
        data = github_request(
            url=url,
            token=token,
            method="GET",
            timeout=30,
        )
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    jobs: list[dict] = []

    for item in data:
        if not isinstance(item, dict):
            continue

        name = item.get("name", "")

        if not str(name).endswith(".json"):
            continue

        download_url = item.get("download_url")

        if not download_url:
            continue

        try:
            job_data = github_request(
                url=download_url,
                token=token,
                method="GET",
                timeout=15,
            )

            if isinstance(job_data, dict):
                jobs.append(job_data)

        except Exception:
            continue

    jobs.sort(
        key=lambda job: job.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    return jobs


def get_github_jobs(token: str) -> list[dict]:
    """
    Public wrapper around cached GitHub job loading.
    """
    return get_github_jobs_cached(
        GITHUB_OWNER,
        GITHUB_REPO,
        token,
    )


def clear_job_cache() -> None:
    """
    Clear cached GitHub jobs.
    """
    get_github_jobs_cached.clear()


# ============================================================
# STATUS HELPERS
# ============================================================

def normalize_status(status: str | None) -> str:
    return str(status or "unknown").strip().lower()


def display_job_status(
    status: str | None,
    compact: bool = False,
) -> None:
    """
    Render consistent job status.
    """
    normalized = normalize_status(status)

    labels = {
        "queued": "QUEUED",
        "downloading": "DOWNLOADING",
        "processing": "PROCESSING",
        "completed": "COMPLETED",
        "failed": "FAILED",
        "unknown": "UNKNOWN",
    }

    label = labels.get(
        normalized,
        normalized.upper(),
    )

    if normalized == "completed":
        st.success(
            f"✅ {label}",
            icon="✅",
        )

    elif normalized == "failed":
        st.error(
            f"❌ {label}",
            icon="❌",
        )

    elif normalized in {
        "downloading",
        "processing",
    }:
        st.warning(
            f"⏳ {label}",
            icon="⏳",
        )

    else:
        st.info(
            f"📌 {label}",
            icon="📌",
        )


def status_emoji(status: str | None) -> str:
    normalized = normalize_status(status)

    return {
        "queued": "🟡",
        "downloading": "🔵",
        "processing": "🟠",
        "completed": "🟢",
        "failed": "🔴",
    }.get(
        normalized,
        "⚪",
    )


# ============================================================
# INPUT HELPERS
# ============================================================

def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def format_file_size(path: Path) -> str:
    """
    Human-readable file size.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return "Unknown size"

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    size_float = float(size)

    for unit in units:
        if size_float < 1024:
            return f"{size_float:.1f} {unit}"

        size_float /= 1024

    return f"{size_float:.1f} PB"


def is_video_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower()
        in SUPPORTED_VIDEO_EXTENSIONS
    )


# ============================================================
# LOCAL ARTIFACT HELPERS
# ============================================================

def get_possible_job_directories(
    job_id: str,
) -> list[Path]:
    """
    Return possible locations for generated artifacts.

    Supports both the current flat output structure and
    future per-job output directories.
    """
    candidates = [
        JOB_OUTPUT_DIR,
        JOB_OUTPUT_DIR / job_id,
        Path("output") / "jobs",
        Path("output") / "jobs" / job_id,
        Path("output") / "clips",
    ]

    unique: list[Path] = []
    seen: set[str] = set()

    for path in candidates:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)

        if key in seen:
            continue

        seen.add(key)
        unique.append(path)

    return unique


def find_job_videos(
    job_id: str,
) -> list[Path]:
    """
    Find locally available generated video artifacts.
    """
    found: list[Path] = []
    seen: set[str] = set()

    for directory in get_possible_job_directories(
        job_id
    ):
        if not directory.exists():
            continue

        try:
            files = directory.rglob("*")
        except Exception:
            continue

        for path in files:
            if not is_video_file(path):
                continue

            filename = path.name.lower()

            # Prefer generated clips rather than source downloads.
            looks_relevant = (
                job_id.lower() in filename
                or "clip_" in filename
                or "vertical" in filename
                or directory.name in {
                    "clips",
                    job_id,
                }
            )

            if not looks_relevant:
                continue

            try:
                key = str(path.resolve())
            except Exception:
                key = str(path)

            if key in seen:
                continue

            seen.add(key)
            found.append(path)

    found.sort(
        key=lambda path: path.stat().st_mtime
        if path.exists()
        else 0,
        reverse=True,
    )

    return found


def find_job_result_file(
    job: dict,
) -> Path | None:
    """
    Locate local result JSON if it exists.
    """
    result_path = safe_text(
        job.get("result_path")
    )

    if result_path:
        path = Path(result_path)

        if path.exists() and path.is_file():
            return path

    job_id = safe_text(
        job.get("job_id")
    )

    if not job_id:
        return None

    candidates = [
        JOB_OUTPUT_DIR / f"{job_id}_result.json",
        JOB_OUTPUT_DIR / job_id / f"{job_id}_result.json",
    ]

    for path in candidates:
        if path.exists() and path.is_file():
            return path

    return None


def load_local_result(
    job: dict,
) -> dict | None:
    """
    Load local pipeline result JSON.
    """
    result_file = find_job_result_file(job)

    if not result_file:
        return None

    try:
        with result_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, dict) else None

    except Exception:
        return None


def extract_artifacts_from_result(
    result: dict | None,
) -> dict:
    if not isinstance(result, dict):
        return {}

    artifacts = result.get(
        "artifacts",
        {},
    )

    return artifacts if isinstance(
        artifacts,
        dict,
    ) else {}


# ============================================================
# VIDEO PREVIEW
# ============================================================

def render_video_artifact(
    path: Path,
    index: int,
    total: int,
) -> None:
    """
    Render one local generated video.
    """
    st.markdown(
        f"### Clip {index}"
    )

    meta_col1, meta_col2 = st.columns(2)

    with meta_col1:
        st.caption(
            f"📄 {path.name}"
        )

    with meta_col2:
        st.caption(
            f"💾 {format_file_size(path)}"
        )

    try:
        with path.open(
            "rb"
        ) as video_file:
            video_bytes = video_file.read()

        st.video(
            video_bytes,
            format="video/mp4",
        )

        st.download_button(
            label="⬇️ Download Clip",
            data=video_bytes,
            file_name=path.name,
            mime="video/mp4",
            key=f"download_{index}_{path.name}",
            use_container_width=True,
        )

    except Exception as exc:
        st.error(
            f"Could not preview {path.name}: {exc}"
        )


def render_generated_outputs(
    job: dict,
) -> None:
    """
    Show generated clips when they exist on the
    current Streamlit runtime.
    """
    job_id = safe_text(
        job.get("job_id")
    )

    if not job_id:
        return

    videos = find_job_videos(
        job_id
    )

    st.subheader(
        "🎞️ Generated Videos"
    )

    if not videos:
        st.info(
            "Job completed, but generated video files "
            "are not available on this Streamlit runtime yet."
        )

        st.caption(
            "The current Termux worker stores generated "
            "videos on the Termux machine. A future artifact "
            "sync layer will make them remotely available "
            "inside this app."
        )

        return

    st.success(
        f"Found {len(videos)} generated video artifact(s)."
    )

    for index, path in enumerate(
        videos,
        start=1,
    ):
        render_video_artifact(
            path=path,
            index=index,
            total=len(videos),
        )

        if index != len(videos):
            st.divider()


# ============================================================
# CAPTION UI
# ============================================================

def render_caption_panel(
    job: dict,
) -> None:
    """
    Caption-style selection UI.

    This stage stores the user's desired style in session
    state. Actual FFmpeg caption rendering is intentionally
    kept separate for the final-render phase.
    """
    st.subheader(
        "✍️ Caption Style"
    )

    selected_name = st.selectbox(
        "Choose caption style",
        list(CAPTION_PRESETS.keys()),
        index=1,
        key=f"caption_style_{job.get('job_id', 'unknown')}",
    )

    selected = CAPTION_PRESETS[
        selected_name
    ]

    st.info(
        selected["description"]
    )

    st.session_state[
        "selected_caption_style"
    ] = selected["style"]

    st.session_state[
        "selected_caption_style_name"
    ] = selected_name

    st.caption(
        "Caption rendering is the next production stage. "
        "The selected preset is ready for the final-render system."
    )


# ============================================================
# JOB CARD
# ============================================================

def render_job_card(
    job: dict,
    show_output: bool = False,
) -> None:
    job_id = safe_text(
        job.get("job_id")
    ) or "Unknown"

    status = safe_text(
        job.get("status")
    ) or "unknown"

    job_type = safe_text(
        job.get("job_type")
    ) or "unknown"

    input_value = safe_text(
        job.get("input_value")
    )

    reference_url = safe_text(
        job.get("reference_url")
    )

    created_at = safe_text(
        job.get("created_at")
    )

    result_path = safe_text(
        job.get("result_path")
    )

    error = safe_text(
        job.get("error")
    )

    with st.container(
        border=True
    ):
        top_left, top_right = st.columns(
            [4, 1]
        )

        with top_left:
            st.markdown(
                f"### {status_emoji(status)} {job_id}"
            )

            if input_value:
                st.write(
                    input_value
                )

        with top_right:
            display_job_status(
                status,
                compact=True,
            )

        meta1, meta2, meta3 = st.columns(3)

        with meta1:
            st.caption(
                f"Type: {job_type}"
            )

        with meta2:
            if created_at:
                st.caption(
                    f"Created: {created_at}"
                )

        with meta3:
            if result_path:
                st.caption(
                    f"Result: {result_path}"
                )

        if reference_url:
            st.caption(
                f"Reference: {reference_url}"
            )

        if error:
            st.error(
                error
            )

        if (
            show_output
            and normalize_status(status)
            == "completed"
        ):
            st.divider()

            render_generated_outputs(
                job
            )

            render_caption_panel(
                job
            )


# ============================================================
# TOPIC RESULT UI
# ============================================================

def render_topic_result(
    result: dict,
) -> None:
    """
    Render topic research + analysis + script result.
    """
    if not result.get("success"):
        st.error(
            "❌ Topic pipeline failed."
        )

        error = safe_text(
            result.get("error")
        )

        if error:
            st.error(
                error
            )

        return

    research = result.get(
        "research",
        {},
    )

    source_analysis = result.get(
        "source_analysis",
        {},
    )

    script = result.get(
        "script",
        {},
    )

    artifacts = result.get(
        "artifacts",
        {},
    )

    sources = research.get(
        "sources",
        []
    )

    analyzed_sources = source_analysis.get(
        "sources",
        []
    )

    sections = script.get(
        "sections",
        []
    )

    st.success(
        "✅ Research + analysis + production plan completed."
    )

    metric1, metric2, metric3 = st.columns(3)

    with metric1:
        st.metric(
            "Sources Found",
            len(sources),
        )

    with metric2:
        st.metric(
            "Sources Analyzed",
            len(analyzed_sources),
        )

    with metric3:
        st.metric(
            "Script Sections",
            len(sections),
        )

    # --------------------------------------------------------
    # RESEARCH SOURCES
    # --------------------------------------------------------

    if sources:
        st.subheader(
            "🎥 Research Sources"
        )

        for index, source in enumerate(
            sources,
            start=1,
        ):
            if not isinstance(
                source,
                dict,
            ):
                continue

            title = safe_text(
                source.get("title")
            ) or "Untitled"

            video_url = safe_text(
                source.get("url")
            )

            video_id = safe_text(
                source.get("video_id")
            )

            channel = safe_text(
                source.get("channel")
            )

            with st.container(
                border=True
            ):
                st.markdown(
                    f"**{index}. {title}**"
                )

                details = []

                if channel:
                    details.append(
                        f"Channel: {channel}"
                    )

                if video_id:
                    details.append(
                        f"Video ID: {video_id}"
                    )

                if details:
                    st.caption(
                        " • ".join(details)
                    )

                if video_url:
                    st.link_button(
                        "▶️ Open YouTube Video",
                        video_url,
                    )

    # --------------------------------------------------------
    # SOURCE ANALYSIS
    # --------------------------------------------------------

    if analyzed_sources:
        st.subheader(
            "📊 Source Analysis"
        )

        for index, source in enumerate(
            analyzed_sources[:20],
            start=1,
        ):
            if not isinstance(
                source,
                dict,
            ):
                continue

            title = safe_text(
                source.get("title")
            ) or "Untitled"

            score = source.get(
                "final_score",
                source.get(
                    "score",
                    0,
                ),
            )

            with st.container(
                border=True
            ):
                col1, col2 = st.columns(
                    [4, 1]
                )

                with col1:
                    st.write(
                        f"**#{index} {title}**"
                    )

                with col2:
                    st.metric(
                        "Score",
                        score,
                    )

    # --------------------------------------------------------
    # PRODUCTION PLAN
    # --------------------------------------------------------

    if script:
        st.subheader(
            "📝 Production Plan"
        )

        hook = safe_text(
            script.get("hook")
        )

        if hook:
            st.markdown(
                "**🔥 Hook**"
            )

            st.info(
                hook
            )

        if sections:
            st.markdown(
                "**Story Structure**"
            )

            for index, section in enumerate(
                sections,
                start=1,
            ):
                if isinstance(
                    section,
                    dict,
                ):
                    title = safe_text(
                        section.get("title")
                    ) or f"Section {index}"

                    text = safe_text(
                        section.get(
                            "text",
                            section.get(
                                "content",
                                "",
                            ),
                        )
                    )

                    st.markdown(
                        f"**{index}. {title}**"
                    )

                    if text:
                        st.write(
                            text
                        )

                else:
                    st.write(
                        f"{index}. {section}"
                    )

    # --------------------------------------------------------
    # ARTIFACTS
    # --------------------------------------------------------

    if artifacts:
        with st.expander(
            "📁 Pipeline Artifacts"
        ):
            for name, path in artifacts.items():
                if not path:
                    continue

                st.markdown(
                    f"**{name}**"
                )

                st.code(
                    str(path)
                )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎬 Auto Faceless Video Creator"
)

st.caption(
    "V2 Control Center • "
    "YouTube → Queue → Termux Worker → "
    "Analysis → Clips → Captions → Final Render"
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header(
        "⚙️ Control Center"
    )

    st.markdown(
        f"**Version:** {APP_VERSION}"
    )

    st.markdown(
        f"**Repository:** `{GITHUB_OWNER}/{GITHUB_REPO}`"
    )

    st.divider()

    st.subheader(
        "System"
    )

    try:
        github_token = get_github_token()
        github_ready = bool(
            github_token
        )
    except Exception:
        github_token = None
        github_ready = False

    if github_ready:
        st.success(
            "GitHub Connected"
        )
    else:
        st.error(
            "GitHub Token Missing"
        )

    st.success(
        "Job Queue Ready"
    )

    st.success(
        "Research Engine Ready"
    )

    st.success(
        "Pipeline Ready"
    )

    st.divider()

    st.caption(
        "Worker mode:"
    )

    st.info(
        "ONE JOB MODE"
    )

    st.caption(
        "Termux worker processes one eligible "
        "queued video job and then stops."
    )


# ============================================================
# SYSTEM STATUS
# ============================================================

st.subheader(
    "🟢 System Status"
)

status1, status2, status3, status4 = st.columns(4)

with status1:
    if github_ready:
        st.success(
            "GitHub\nConnected"
        )
    else:
        st.error(
            "GitHub\nNot Connected"
        )

with status2:
    st.success(
        "Job Queue\nReady"
    )

with status3:
    st.success(
        "Research\nReady"
    )

with status4:
    st.success(
        "Pipeline\nReady"
    )

st.divider()


# ============================================================
# CREATE JOB
# ============================================================

st.subheader(
    "🚀 Create New Video"
)

input_mode = st.selectbox(
    "Input Type",
    [
        "YouTube Video URL",
        "Topic",
        "Idea",
        "Keyword",
    ],
)


# ============================================================
# INPUT
# ============================================================

if input_mode == "YouTube Video URL":
    input_value = st.text_input(
        "YouTube Video URL",
        placeholder=(
            "https://www.youtube.com/watch?v=..."
        ),
        key="video_url_input",
    )

else:
    input_value = st.text_input(
        input_mode,
        placeholder=(
            f"Enter your "
            f"{input_mode.lower()}..."
        ),
        key="topic_input",
    )


reference_url = st.text_input(
    "Reference URL (Optional)",
    placeholder=(
        "YouTube video, channel, article, or reference URL..."
    ),
    key="reference_url_input",
)


# ============================================================
# PIPELINE SETTINGS
# ============================================================

with st.expander(
    "⚙️ Pipeline Settings",
    expanded=False,
):
    col1, col2, col3 = st.columns(3)

    with col1:
        research_limit = st.number_input(
            "Research Sources",
            min_value=1,
            max_value=50,
            value=int(
                DEFAULT_RESEARCH_LIMIT
            ),
            step=1,
        )

    with col2:
        max_clips = st.number_input(
            "Maximum Clips",
            min_value=1,
            max_value=100,
            value=int(
                DEFAULT_MAX_CLIPS
            ),
            step=1,
        )

    with col3:
        language = st.selectbox(
            "Language",
            ["en"],
            index=0,
        )

    make_vertical = st.checkbox(
        "Create vertical clips (9:16)",
        value=DEFAULT_MAKE_VERTICAL,
    )

    keep_audio = st.checkbox(
        "Keep extracted audio files",
        value=DEFAULT_KEEP_AUDIO,
    )


# ============================================================
# CREATE BUTTON
# ============================================================

if input_mode == "YouTube Video URL":
    button_label = "🚀 CREATE VIDEO JOB"
else:
    button_label = "🔎 RESEARCH & ANALYZE"


if st.button(
    button_label,
    type="primary",
    use_container_width=True,
):
    if not safe_text(input_value):
        st.warning(
            f"Please enter a {input_mode.lower()}."
        )

        st.stop()

    # ========================================================
    # VIDEO URL WORKFLOW
    # ========================================================

    if input_mode == "YouTube Video URL":
        try:
            video_url = validate_video_url(
                input_value
            )

            reference = validate_reference_url(
                reference_url
            )

            github_token = get_github_token()

            with st.spinner(
                "Creating GitHub video job..."
            ):
                job = create_orchestrator_job(
                    job_type="video",
                    input_value=video_url,
                    reference_url=reference,
                )

                job_path = create_github_job(
                    token=github_token,
                    job=job,
                )

            clear_job_cache()

            st.success(
                "✅ Video job added to GitHub queue."
            )

            metric1, metric2 = st.columns(2)

            with metric1:
                st.metric(
                    "Job ID",
                    job["job_id"],
                )

            with metric2:
                st.metric(
                    "Status",
                    "QUEUED",
                )

            st.write(
                "Queue Path"
            )

            st.code(
                job_path
            )

            st.info(
                "Termux worker will pick up this queued job."
            )

            st.markdown(
                "### Next"
            )

            st.write(
                "Run the ONE-JOB worker in Termux. "
                "After processing, return here and refresh Jobs."
            )

        except Exception as exc:
            st.error(
                "❌ Failed to create video job."
            )

            st.exception(
                exc
            )

    # ========================================================
    # TOPIC WORKFLOW
    # ========================================================

    else:
        try:
            clean_reference = (
                reference_url.strip()
                if reference_url.strip()
                else None
            )

            with st.spinner(
                "🔎 Researching topic, analyzing sources "
                "and generating production plan..."
            ):
                result = execute_topic_job(
                    topic=input_value.strip(),
                    reference_url=clean_reference,
                    research_limit=int(
                        research_limit
                    ),
                )

            render_topic_result(
                result
            )

        except Exception as exc:
            st.error(
                "❌ Research / analysis failed."
            )

            st.exception(
                exc
            )


# ============================================================
# JOB QUEUE
# ============================================================

st.divider()

st.subheader(
    "📋 Recent Jobs"
)

queue_col1, queue_col2 = st.columns(
    [1, 4]
)

with queue_col1:
    refresh_jobs = st.button(
        "🔄 Refresh Jobs",
        use_container_width=True,
    )

with queue_col2:
    st.caption(
        "Refresh after the Termux worker finishes a job."
    )


# ============================================================
# LOAD JOBS
# ============================================================

if refresh_jobs:
    clear_job_cache()


try:
    if not github_ready:
        st.warning(
            "GitHub jobs cannot be loaded until GITHUB_TOKEN "
            "is configured in Streamlit secrets."
        )

    else:
        jobs = get_github_jobs(
            github_token
        )

        if not jobs:
            st.info(
                "No jobs found."
            )

        else:
            # ------------------------------------------------
            # Queue metrics
            # ------------------------------------------------

            queued_count = sum(
                1
                for job in jobs
                if normalize_status(
                    job.get("status")
                )
                == "queued"
            )

            processing_count = sum(
                1
                for job in jobs
                if normalize_status(
                    job.get("status")
                )
                in {
                    "downloading",
                    "processing",
                }
            )

            completed_count = sum(
                1
                for job in jobs
                if normalize_status(
                    job.get("status")
                )
                == "completed"
            )

            failed_count = sum(
                1
                for job in jobs
                if normalize_status(
                    job.get("status")
                )
                == "failed"
            )

            m1, m2, m3, m4 = st.columns(4)

            with m1:
                st.metric(
                    "Queued",
                    queued_count,
                )

            with m2:
                st.metric(
                    "Processing",
                    processing_count,
                )

            with m3:
                st.metric(
                    "Completed",
                    completed_count,
                )

            with m4:
                st.metric(
                    "Failed",
                    failed_count,
                )

            st.divider()

            # ------------------------------------------------
            # Job selector
            # ------------------------------------------------

            job_labels = []

            for job in jobs[:25]:
                job_id = safe_text(
                    job.get("job_id")
                ) or "Unknown"

                status = safe_text(
                    job.get("status")
                ) or "unknown"

                job_labels.append(
                    f"{status_emoji(status)} {job_id} • "
                    f"{status.upper()}"
                )

            selected_label = st.selectbox(
                "Select Job",
                job_labels,
                key="selected_job",
            )

            selected_index = job_labels.index(
                selected_label
            )

            selected_job = jobs[
                selected_index
            ]

            # ------------------------------------------------
            # Selected job
            # ------------------------------------------------

            render_job_card(
                selected_job,
                show_output=(
                    normalize_status(
                        selected_job.get("status")
                    )
                    == "completed"
                ),
            )

            # ------------------------------------------------
            # Other recent jobs
            # ------------------------------------------------

            remaining_jobs = [
                job
                for job in jobs[:10]
                if job is not selected_job
            ]

            if remaining_jobs:
                st.divider()

                with st.expander(
                    "📜 Other Recent Jobs"
                ):
                    for job in remaining_jobs:
                        render_job_card(
                            job,
                            show_output=False,
                        )


except Exception as exc:
    st.error(
        "❌ Could not load GitHub jobs."
    )

    st.exception(
        exc
    )


# ============================================================
# CURRENT CAPTION SELECTION
# ============================================================

if (
    "selected_caption_style_name"
    in st.session_state
):
    st.divider()

    st.subheader(
        "🎨 Current Caption Selection"
    )

    selected_name = st.session_state[
        "selected_caption_style_name"
    ]

    selected_style = st.session_state.get(
        "selected_caption_style",
        "",
    )

    st.success(
        f"Selected: {selected_name}"
    )

    st.caption(
        f"Render style: `{selected_style}`"
    )


# ============================================================
# ARCHITECTURE STATUS
# ============================================================

st.divider()

with st.expander(
    "🏗️ V2 Pipeline Status",
    expanded=False,
):
    pipeline_rows = [
        ("Input / URL Validation", "READY"),
        ("GitHub Job Queue", "READY"),
        ("Termux Downloader", "WORKING"),
        ("Whisper Transcription", "WORKING"),
        ("Clip Analysis", "WORKING"),
        ("FFmpeg Clip Processing", "WORKING"),
        ("Vertical 9:16 Output", "WORKING"),
        ("Research Engine", "READY"),
        ("Source Analysis", "READY"),
        ("Script Planning", "READY"),
        ("Caption Presets UI", "READY"),
        ("Final Caption Render", "NEXT"),
        ("Remote Artifact Sync", "NEXT"),
        ("Gallery Download", "NEXT"),
    ]

    for component, status in pipeline_rows:
        col1, col2 = st.columns(
            [4, 1]
        )

        with col1:
            st.write(
                component
            )

        with col2:
            if status in {
                "READY",
                "WORKING",
            }:
                st.success(
                    status
                )
            else:
                st.info(
                    status
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Auto Faceless Video Creator V2 • "
    "Input → Validation → GitHub Queue → "
    "Termux → Download → Whisper → Clip Analysis → "
    "FFmpeg → Vertical Clips → Captions → Final Render"
)
