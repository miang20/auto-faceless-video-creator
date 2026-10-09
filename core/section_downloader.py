from pathlib import Path
from typing import Iterable
import re
import yt_dlp
from yt_dlp.utils import download_range_func


SECTION_DIR = Path("downloads/sections")
SECTION_DIR.mkdir(parents=True, exist_ok=True)


def _safe(value: float) -> str:
    return f"{float(value):.3f}".replace(".", "_")


def download_section(
    url: str,
    start: float,
    end: float,
    video_id: str | None = None,
) -> str:

    start = max(0.0, float(start))
    end = max(start + 0.5, float(end))

    if not video_id:
        with yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
        }) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get("id", "source")

    filename = (
        f"{video_id}__{_safe(start)}__{_safe(end)}.mp4"
    )

    output = SECTION_DIR / filename

    if output.exists() and output.stat().st_size > 0:
        return str(output)

    options = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(
            SECTION_DIR / f"{video_id}__{_safe(start)}__{_safe(end)}.%(ext)s"
        ),
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "download_ranges": download_range_func(
            None,
            [(start, end)],
        ),
        "force_keyframes_at_cuts": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    if not output.exists():
        candidates = sorted(
            SECTION_DIR.glob(
                f"{video_id}__{_safe(start)}__{_safe(end)}.*"
            )
        )

        mp4s = [
            p for p in candidates
            if p.suffix.lower() == ".mp4"
        ]

        if mp4s:
            output = mp4s[0]

    if not output.exists():
        raise FileNotFoundError(
            f"Section download failed: {output}"
        )

    return str(output)


def download_sections(
    url: str,
    sections: Iterable[dict],
) -> list[str]:

    results = []

    for section in sections:
        start = float(section["start"])
        end = float(section["end"])

        results.append(
            download_section(
                url=url,
                start=start,
                end=end,
                video_id=section.get("video_id"),
            )
        )

    return results
