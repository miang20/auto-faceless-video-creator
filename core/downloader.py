from pathlib import Path
import yt_dlp


DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def download_video(url: str) -> str:
    """
    Download one public video and return the downloaded file path.
    """

    output_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")

    options = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

        downloaded_path = Path(
            ydl.prepare_filename(info)
        )

        if downloaded_path.suffix.lower() != ".mp4":
            possible_mp4 = downloaded_path.with_suffix(".mp4")
            if possible_mp4.exists():
                downloaded_path = possible_mp4

    return str(downloaded_path)
