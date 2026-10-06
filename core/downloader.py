from pathlib import Path
import yt_dlp


DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def download_video(url: str) -> str:
    """
    Download one video from a permitted/public source
    and return the downloaded file path.
    """

    output_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")

    options = {
        "format": "best[ext=mp4]/best",
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

    return str(downloaded_path)
