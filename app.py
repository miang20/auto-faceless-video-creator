import uuid
import json
import urllib.request

import streamlit as st

from core.jobs import create_job
from core.github_jobs import create_github_job


# =========================
# PAGE CONFIG
# =========================

st.set_page_config(
    page_title="Auto Faceless Video Creator",
    page_icon="🎬",
    layout="wide",
)


# =========================
# HELPERS
# =========================

REPO_OWNER = "miang20"
REPO_NAME = "auto-faceless-video-creator"


def get_github_jobs(token: str):
    """Read recent job JSON files from GitHub."""

    url = (
        f"https://api.github.com/repos/"
        f"{REPO_OWNER}/{REPO_NAME}/contents/jobs"
    )

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        jobs = []

        for item in data:
            if not item.get("name", "").endswith(".json"):
                continue

            try:
                file_url = item["download_url"]

                file_request = urllib.request.Request(
                    file_url,
                    method="GET",
                )

                with urllib.request.urlopen(
                    file_request, timeout=15
                ) as file_response:
                    job_data = json.loads(
                        file_response.read().decode("utf-8")
                    )

                jobs.append(job_data)

            except Exception:
                continue

        jobs.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )

        return jobs

    except Exception:
        return []


# =========================
# HEADER
# =========================

st.title("🎬 Auto Faceless Video Creator")
st.caption("V2 Control Center • GitHub Queue • Termux Worker")

st.divider()


# =========================
# SYSTEM STATUS
# =========================

st.subheader("🟢 System Status")

status1, status2, status3, status4 = st.columns(4)

with status1:
    st.success("GitHub\nConnected")

with status2:
    st.success("Job Queue\nReady")

with status3:
    st.success("Termux Worker\nReady")

with status4:
    st.success("Download Engine\nReady")


st.divider()


# =========================
# CREATE JOB
# =========================

st.subheader("🚀 Create New Video Job")

input_mode = st.selectbox(
    "What do you want to create?",
    [
        "YouTube Video URL",
        "Topic",
        "Idea",
        "Keyword",
    ],
)


# =========================
# INPUT
# =========================

if input_mode == "YouTube Video URL":

    input_value = st.text_input(
        "YouTube Video URL",
        placeholder="https://www.youtube.com/watch?v=...",
    )

else:

    input_value = st.text_input(
        input_mode,
        placeholder=f"Enter your {input_mode.lower()}...",
    )


reference_url = st.text_input(
    "Reference URL (Optional)",
    placeholder="Paste a YouTube video/channel/reference URL...",
)


# =========================
# CREATE BUTTON
# =========================

if st.button(
    "🚀 CREATE VIDEO JOB",
    type="primary",
    use_container_width=True,
):

    if not input_value.strip():

        st.warning(
            f"Please enter a {input_mode.lower()}."
        )

    elif input_mode == "YouTube Video URL":

        try:
            job_id = uuid.uuid4().hex

            job = create_job(
                job_id=job_id,
                job_type="download",
                input_value=input_value.strip(),
                reference_url=(
                    reference_url.strip()
                    if reference_url.strip()
                    else None
                ),
            )

            github_token = st.secrets["GITHUB_TOKEN"]

            job_path = create_github_job(
                token=github_token,
                job=job.to_dict(),
            )

            st.success(
                "✅ Job successfully sent to GitHub queue."
            )

            st.write("Job ID")
            st.code(job_id)

            st.write("Queue")
            st.code(job_path)

            st.info(
                "Termux worker will pick up this queued job."
            )

        except Exception as e:

            st.error(
                "❌ Failed to create job."
            )

            st.exception(e)

    else:

        st.info(
            f"🧠 {input_mode} input received. "
            "Research Engine will process this type in the next V2 stage."
        )


st.divider()


# =========================
# RECENT JOBS
# =========================

st.subheader("📋 Recent Jobs")

if st.button("🔄 Refresh Jobs"):

    try:

        github_token = st.secrets["GITHUB_TOKEN"]

        jobs = get_github_jobs(github_token)

        if not jobs:

            st.info("No jobs found.")

        else:

            for job in jobs[:10]:

                job_id = job.get(
                    "job_id",
                    "Unknown"
                )

                status = job.get(
                    "status",
                    "unknown"
                )

                job_type = job.get(
                    "job_type",
                    "unknown"
                )

                input_value = job.get(
                    "input_value",
                    ""
                )

                reference_url = job.get(
                    "reference_url",
                    ""
                )

                created_at = job.get(
                    "created_at",
                    ""
                )

                with st.container(border=True):

                    col1, col2, col3 = st.columns(
                        [3, 1, 2]
                    )

                    with col1:

                        st.write(
                            f"**{job_id}**"
                        )

                        st.caption(
                            input_value
                        )

                        if reference_url:

                            st.caption(
                                f"Reference: {reference_url}"
                            )

                    with col2:

                        status_upper = status.upper()

                        if status_upper == "COMPLETED":

                            st.success(
                                status_upper
                            )

                        elif status_upper == "FAILED":

                            st.error(
                                status_upper
                            )

                        elif status_upper in (
                            "DOWNLOADING",
                            "PROCESSING",
                        ):

                            st.warning(
                                status_upper
                            )

                        else:

                            st.info(
                                status_upper
                            )

                    with col3:

                        st.caption(
                            f"Type: {job_type}"
                        )

                        st.caption(
                            created_at
                        )

    except Exception as e:

        st.error(
            "Could not load jobs."
        )

        st.exception(e)

else:

    st.info(
        "Press **Refresh Jobs** to view the latest queue."
    )


st.divider()


# =========================
# FOOTER
# =========================

st.caption(
    "Auto Faceless Video Creator V2 • "
    "Streamlit → GitHub → Termux Worker"
                )
