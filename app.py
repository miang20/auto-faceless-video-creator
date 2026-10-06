import uuid

import streamlit as st

from core.downloader import download_video
from core.jobs import create_job
from core.github_jobs import create_github_job


st.set_page_config(
    page_title="Auto Faceless Video Creator",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 Auto Faceless Video Creator")
st.caption("V2 — Development Build")

st.divider()

st.subheader("🎥 Test Video Downloader")

url = st.text_input(
    "Paste a YouTube video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)

if st.button("Download Video", type="primary"):
    if not url.strip():
        st.warning("Please enter a YouTube URL.")
    else:
        with st.spinner("Downloading video..."):
            try:
                video_path = download_video(url.strip())

                st.success("Video downloaded successfully!")
                st.code(video_path)

            except Exception as e:
                st.error("Download failed.")
                st.exception(e)


st.divider()

st.subheader("🧪 GitHub Worker Connection Test")

if st.button("Create Test Job"):
    try:
        job_id = uuid.uuid4().hex

        job = create_job(
            job_id=job_id,
            job_type="test",
            input_value="connection-test",
        )

        github_token = st.secrets["GITHUB_TOKEN"]

        job_path = create_github_job(
            token=github_token,
            job=job.to_dict(),
        )

        st.success("GitHub test job created successfully!")
        st.code(job_path)

    except Exception as e:
        st.error("GitHub test failed.")
        st.exception(e)
