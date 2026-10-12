"""Reference-video intelligence for Pro V2.

Extracts metadata, chapters, and topic signals from a supplied reference URL.
It deliberately does not alter the frozen core downloader.
"""
from __future__ import annotations

import re
from typing import Any


_STOPWORDS = {
    "about", "after", "again", "against", "also", "and", "are", "because",
    "been", "before", "being", "between", "but", "can", "could", "did",
    "does", "doing", "for", "from", "had", "has", "have", "into", "its",
    "just", "more", "most", "not", "our", "out", "over", "said", "same",
    "she", "should", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through",
    "too", "under", "very", "was", "were", "what", "when", "where", "which",
    "while", "who", "will", "with", "would", "you", "your", "video",
}


def _keywords(*values: Any, limit: int = 35) -> list[str]:
    text = " ".join(str(value or "") for value in values)
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text.lower())
    result = []
    for word in words:
        word = word.strip("'-")
        if len(word) < 3 or word in _STOPWORDS or word in result:
            continue
        result.append(word)
        if len(result) >= limit:
            break
    return result


def analyze_reference(reference_url: str | None, topic: str = "") -> dict:
    """Return a JSON-safe reference profile; degrade cleanly if lookup fails."""
    if not reference_url or not str(reference_url).strip():
        return {
            "success": False, "status": "not_provided", "url": None,
            "title": "", "duration": 0.0, "chapters": [],
            "peak_moments": [], "keywords": _keywords(topic),
        }
    try:
        import yt_dlp
        options = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": False, "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(str(reference_url).strip(), download=False)
        info = info if isinstance(info, dict) else {}
        title = str(info.get("title") or "").strip()
        description = str(info.get("description") or "")
        duration = max(0.0, float(info.get("duration") or 0.0))
        raw_chapters = info.get("chapters") or []
        chapters = []
        peaks = []
        for index, chapter in enumerate(raw_chapters):
            if not isinstance(chapter, dict):
                continue
            try:
                start = max(0.0, float(chapter.get("start_time", 0) or 0))
                end = min(duration or float("inf"), float(chapter.get("end_time", 0) or 0))
            except (TypeError, ValueError):
                continue
            chapter_title = str(chapter.get("title") or "").strip()
            if not chapter_title or end <= start:
                continue
            item = {
                "index": index + 1, "text": chapter_title,
                "start": round(start, 3), "end": round(end, 3),
                "duration": round(end - start, 3), "role": "REFERENCE_CHAPTER",
            }
            chapters.append(item)
            peaks.append(dict(item))
        tags = info.get("tags") or []
        categories = info.get("categories") or []
        keywords = _keywords(
            topic, title, description[:5000], " ".join(map(str, tags)),
            " ".join(map(str, categories)),
            " ".join(chapter.get("text", "") for chapter in chapters),
        )
        return {
            "success": True, "status": "analyzed",
            "url": str(reference_url).strip(), "id": str(info.get("id") or ""),
            "title": title, "description": description[:5000],
            "duration": round(duration, 3), "chapters": chapters,
            "peak_moments": peaks, "keywords": keywords,
            "tags": [str(x) for x in tags[:40]],
            "categories": [str(x) for x in categories[:15]],
            "view_count": info.get("view_count"),
            "uploader": str(info.get("uploader") or ""),
        }
    except Exception as exc:
        return {
            "success": False, "status": "lookup_failed",
            "url": str(reference_url).strip(), "title": "",
            "duration": 0.0, "chapters": [], "peak_moments": [],
            "keywords": _keywords(topic),
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
        }


def plan_source_sections(source: dict, max_sections: int = 3,
                         section_seconds: float = 8.0) -> list[tuple[float, float]]:
    """Sample a source across its full duration, rather than only its opening 30s."""
    source = source if isinstance(source, dict) else {}
    try:
        max_sections = max(1, min(6, int(max_sections)))
    except (TypeError, ValueError):
        max_sections = 3
    try:
        section_seconds = max(3.0, min(12.0, float(section_seconds)))
    except (TypeError, ValueError):
        section_seconds = 8.0

    duration = 0.0
    for key in ("duration", "duration_seconds", "length"):
        try:
            duration = float(source.get(key) or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration > 0:
            break
    if duration <= 0 and source.get("url"):
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True, "skip_download": True,
                "noplaylist": True,
            }) as ydl:
                info = ydl.extract_info(source["url"], download=False)
            duration = float((info or {}).get("duration") or 0)
        except Exception:
            duration = 0.0

    if duration <= 0:
        # Conservative fallback only when metadata is unavailable.
        return [(0.0, section_seconds)]

    window = min(section_seconds, duration)
    if duration <= window + 0.5:
        return [(0.0, round(duration, 3))]

    count = min(max_sections, max(1, int(duration // max(window, 1.0))))
    if count == 1:
        starts = [max(0.0, (duration - window) / 2.0)]
    else:
        latest_start = max(0.0, duration - window)
        starts = [latest_start * i / (count - 1) for i in range(count)]

    sections = []
    for start in starts:
        start = max(0.0, min(start, duration - 0.5))
        end = min(duration, start + window)
        if end - start >= 0.5 and not any(
            abs(start - old_start) < 1.0 for old_start, _ in sections
        ):
            sections.append((round(start, 3), round(end, 3)))
    return sections
