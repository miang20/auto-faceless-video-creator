import uuid

import streamlit as st

from core.jobs import create_job
from core.github_jobs import create_github_job


st.set_page_config(
    page_title="Auto Faceless Video Creator",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Auto Faceless Video Creator")
st.caption("V2 — Termux Worker Connected")

st.divider()

st.subheader("🎥 Create Video Download Job")

url = st.text_input(
    "Paste a YouTube video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)

if st.button("Send to Termux Worker", type="primary"):
    if not url.strip():
        st.warning("Please enter a YouTube URL.")

    else:
        try:
            job_id = uuid.uuid4().hex

            job = create_job(
                job_id=job_id,
                job_type="download",
                input_value=url.strip(),
            )

            github_token = st.secrets["GITHUB_TOKEN"]

            job_path = create_github_job(
                token=github_token,
                job=job.to_dict(),
            )

            st.success("Job sent to Termux worker!")

            st.write("Job ID:")
            st.code(job_id)

            st.write("GitHub job:")
            st.code(job_path)

            st.info(
                "Termux worker can now pick up this queued job."
            )

        except Exception as e:
            st.error("Failed to create job.")
            st.exception(e)
