import streamlit as st
from core.downloader import download_video


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
