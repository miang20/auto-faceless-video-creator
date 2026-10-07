import urllib.request
import json

import streamlit as st
import uuid

from core.config import (
    GITHUB_OWNER,
    GITHUB_REPO,
    DEFAULT_RESEARCH_LIMIT,
    DEFAULT_MAX_CLIPS,
    DEFAULT_LANGUAGE,
    DEFAULT_MAKE_VERTICAL,
    DEFAULT_KEEP_AUDIO,
)

from core.github_jobs import create_github_job
from core.jobs import create_job
from core.validator import validate_video_url, validate_reference_url


st.set_page_config(
    page_title="Auto Faceless Video Creator",
    page_icon="🎬",
    layout="wide",
)


def get_github_token():
    token = st.secrets.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is missing from Streamlit secrets."
        )

    return token


def get_github_jobs(token):
    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/jobs"
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            items = json.loads(
                response.read().decode("utf-8")
            )

        jobs = []

        for item in items:
            if not item.get("name", "").endswith(".json"):
                continue

            download_url = item.get("download_url")

            if not download_url:
                continue

            try:
                with urllib.request.urlopen(
                    download_url,
                    timeout=15,
                ) as response:
                    jobs.append(
                        json.loads(
                            response.read().decode("utf-8")
                        )
                    )
            except Exception:
                continue

        jobs.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )

        return jobs

    except Exception:
        return []


st.title("🎬 Auto Faceless Video Creator")

st.caption(
    "Pro V2 Control Center • Research • Story • Dynamic Editing • 9:16"
)

st.divider()

st.subheader("🟢 System Status")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.success("GitHub Connected")

with c2:
    st.success("Job Queue Ready")

with c3:
    st.success("V2 Pipeline Ready")

with c4:
    st.success("Termux Worker Ready")

st.divider()

st.subheader("🚀 Create New Video")

input_value = st.text_input(
    "YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=...",
)

reference_url = st.text_input(
    "Reference URL (Optional)",
    placeholder="Optional YouTube reference...",
)

st.subheader("⚙️ V2 Settings")

c1, c2, c3 = st.columns(3)

with c1:
    duration = st.selectbox(
        "Video Duration",
        [10, 15, 20, 30, 45, 60],
        index=3,
        format_func=lambda x: f"{x} seconds",
    )

with c2:
    caption_style = st.selectbox(
        "Caption Style",
        [
            "Bold Viral",
            "Karaoke",
            "Clean",
            "Impact",
            "Minimal Bottom",
        ],
    )

with c3:
    max_clips = st.number_input(
        "Maximum Clips",
        min_value=1,
        max_value=100,
        value=DEFAULT_MAX_CLIPS,
        step=1,
    )

c1, c2, c3 = st.columns(3)

with c1:
    language = st.selectbox(
        "Language",
        ["en"],
        index=0,
    )

with c2:
    make_vertical = st.checkbox(
        "9:16 Vertical",
        value=DEFAULT_MAKE_VERTICAL,
    )

with c3:
    keep_audio = st.checkbox(
        "Keep Audio Files",
        value=DEFAULT_KEEP_AUDIO,
    )

with st.expander("🎨 Caption Controls"):

    caption_size = st.slider(
        "Caption Size",
        20,
        120,
        60,
    )

    words_per_line = st.slider(
        "Words Per Line",
        1,
        8,
        4,
    )

    keyword_emphasis = st.checkbox(
        "Keyword Emphasis",
        value=True,
    )

    caption_settings = {
        "font_size": caption_size,
        "words_per_line": words_per_line,
        "keyword_emphasis": keyword_emphasis,
    }

with st.expander("🎬 Editing Controls"):

    dynamic_zoom = st.checkbox(
        "Dynamic Zoom / Punch In",
        value=True,
    )

    remove_silence = st.checkbox(
        "Remove Dead Space",
        value=True,
    )

    normalize_audio = st.checkbox(
        "Normalize Audio",
        value=True,
    )

    editing_settings = {
        "dynamic_zoom": dynamic_zoom,
        "remove_silence": remove_silence,
        "normalize_audio": normalize_audio,
    }


if st.button(
    "🚀 CREATE V2 VIDEO",
    type="primary",
    use_container_width=True,
):

    if not input_value.strip():
        st.warning("Please enter a YouTube video URL.")
        st.stop()

    try:
        video_url = validate_video_url(
            input_value.strip()
        )

        reference = validate_reference_url(
            reference_url.strip()
            if reference_url.strip()
            else None
        )

        token = get_github_token()

        job = create_job(
            job_id=str(uuid.uuid4()),
            job_type="video",
            input_value=video_url,
            reference_url=reference,
            duration=int(duration),
            caption_style=caption_style,
            caption_settings=caption_settings,
            editing_settings=editing_settings,
        )

        with st.spinner(
            "Adding V2 job to GitHub queue..."
        ):
            job_data = job.to_dict() if hasattr(job, "to_dict") else job
            job_path = create_github_job(
                token=token,
                job=job_data,
            )

        st.success(
            "✅ V2 video job successfully queued."
        )

        st.code(
            job.job_id
            if hasattr(job, "job_id")
            else job.get("job_id")
        )

        st.info(
            "Termux worker will download the source, "
            "run the V2 pipeline, and save the final video."
        )

    except Exception as exc:
        st.error(
            "❌ Failed to create V2 job."
        )
        st.exception(exc)


st.divider()

st.subheader("📋 Recent Jobs")

if st.button(
    "🔄 Refresh Jobs",
    use_container_width=True,
):

    try:
        token = get_github_token()
        jobs = get_github_jobs(token)

        if not jobs:
            st.info("No jobs found.")
        else:

            for job in jobs[:10]:

                status = (
                    job.get("status", "unknown")
                    .upper()
                )

                with st.container(border=True):

                    st.write(
                        f"**{job.get('job_id', 'Unknown')}**"
                    )

                    if status == "COMPLETED":
                        st.success(status)

                    elif status == "FAILED":
                        st.error(status)

                    elif status in {
                        "RUNNING",
                        "DOWNLOADING",
                        "PROCESSING",
                    }:
                        st.warning(status)

                    else:
                        st.info(status)

                    if job.get("result_path"):
                        st.code(
                            str(job["result_path"])
                        )

                    if job.get("error"):
                        st.error(
                            str(job["error"])
                        )

    except Exception as exc:
        st.error(
            f"Could not load jobs: {exc}"
        )
