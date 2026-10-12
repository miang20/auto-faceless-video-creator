"""Automatic, context-aware supplementary footage discovery for Pro V2.

B-roll is optional enhancement, never a requirement for a successful edit.
Search/download failures are recorded and safely fall back to the main footage.
Use only footage the operator has permission to reuse; yt-dlp cannot determine
copyright or license status reliably.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.section_downloader import download_section


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", str(value or "").lower()))


def _relevance(title: str, query: str) -> float:
    a, b = _tokens(title), _tokens(query)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(b))


def _search(query: str, excluded_ids: set[str]) -> dict[str, Any] | None:
    try:
        import yt_dlp
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": True,
            "socket_timeout": 12,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info("ytsearch8:" + query, download=False)
        entries = result.get("entries", []) if isinstance(result, dict) else []
        candidates = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("id") or "")
            title = str(item.get("title") or "")
            url = str(item.get("url") or "")
            duration = float(item.get("duration") or 0)
            if not video_id or video_id in excluded_ids or duration < 8:
                continue
            if not url.startswith("http"):
                url = "https://www.youtube.com/watch?v=" + video_id
            score = _relevance(title, query)
            if score >= 0.12:
                candidates.append((score, title, url, video_id, duration))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        score, title, url, video_id, duration = candidates[0]
        return {"title": title, "url": url, "video_id": video_id, "duration": duration, "relevance": score}
    except Exception as exc:
        print("[V2 BROLL] Search skipped:", str(exc)[:180])
        return None


def insert_contextual_broll(
    timeline: list[dict],
    topic: str = "",
    target_duration: int = 30,
    max_broll: int = 2,
) -> tuple[list[dict], dict]:
    """Search relevant cutaways and insert at story transitions, without replacing payoff."""
    source = [dict(x) for x in (timeline or []) if isinstance(x, dict)]
    report = {"enabled": True, "inserted": 0, "searched": 0, "items": [], "warnings": []}
    if len(source) < 3 or max_broll <= 0:
        report["warnings"].append("Not enough distinct story beats for a useful cutaway.")
        return source, report

    # Choose transitions after setup/escalation beats, not the opening hook or final payoff.
    eligible = []
    for index in range(1, len(source) - 1):
        item = source[index]
        role = str(item.get("role") or "").upper()
        text = str(item.get("text") or "").strip()
        if role in {"PAYOFF", "ENDING"}:
            continue
        if len(_tokens(text + " " + topic)) >= 2:
            eligible.append((index, item, text))
    if not eligible:
        eligible = [(i, x, str(x.get("text") or "")) for i, x in enumerate(source[1:-1], 1)]

    selected = []
    for index, item, text in eligible:
        query = " ".join([topic, text, "real world footage"]).strip()
        if len(_tokens(query)) < 3:
            continue
        selected.append((index, item, query))
        if len(selected) >= min(max_broll, 2):
            break

    excluded = set()
    output = []
    insertion_map = {idx: (item, query) for idx, item, query in selected}
    section_dir = Path(__file__).resolve().parent.parent / "downloads" / "sections"
    for index, item in enumerate(source):
        output.append(item)
        request = insertion_map.get(index)
        if not request:
            continue
        _, query = request
        report["searched"] += 1
        found = _search(query, excluded)
        if not found:
            report["warnings"].append("No relevant supplementary source found for one beat.")
            continue
        excluded.add(found["video_id"])
        try:
            # A short cutaway near the middle avoids opening title cards and end screens.
            start = min(max(1.0, found["duration"] * 0.35), max(1.0, found["duration"] - 4.0))
            end = min(found["duration"] - 0.5, start + 3.0)
            if end - start < 1.5:
                raise ValueError("Candidate is too short for a clean cutaway.")
            path = download_section(found["url"], start, end, found["video_id"])
            if not Path(path).is_file() or Path(path).stat().st_size <= 0:
                raise FileNotFoundError("Downloaded B-roll file is empty.")
            output.append({
                "path": str(path), "start": 0.0, "end": end - start,
                "duration": end - start, "text": "", "role": "BROLL",
                "score": found["relevance"], "hook_score": 0.0,
                "reaction_score": 0.0, "visual_score": 0.0, "audio_score": 0.0,
                "broll_source_title": found["title"], "broll_source_url": found["url"],
            })
            report["inserted"] += 1
            report["items"].append({"title": found["title"], "url": found["url"], "path": path, "query": query})
        except Exception as exc:
            report["warnings"].append("B-roll download failed: " + str(exc)[:180])
            print("[V2 BROLL] Download skipped:", str(exc)[:180])

    report["status"] = "inserted" if report["inserted"] else "fallback"
    return output, report
