from __future__ import annotations

import json
import math
import re
from typing import Any, Optional


# =========================================================
# CONFIGURATION
# =========================================================

MIN_CLIP_DURATION = 3.0
MAX_CLIP_DURATION = 60.0

DEFAULT_CLIP_DURATION = 15.0
DEFAULT_TOP_CLIPS = 10


# =========================================================
# TEXT HELPERS
# =========================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for scoring and comparison.
    """

    if not text:
        return ""

    text = text.lower().strip()

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def tokenize(text: str) -> list[str]:
    """
    Convert text into useful words.
    """

    normalized = normalize_text(text)

    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "there",
        "their",
        "they",
        "you",
        "your",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "into",
        "about",
        "what",
        "when",
        "where",
        "which",
        "who",
        "how",
        "why",
        "can",
        "could",
        "would",
        "should",
        "will",
        "been",
        "being",
        "but",
        "not",
        "all",
        "just",
        "than",
        "then",
        "too",
        "very",
        "its",
        "it's",
        "his",
        "her",
        "our",
        "their",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "at",
        "is",
        "it",
    }

    return [
        word
        for word in normalized.split()
        if len(word) >= 3
        and word not in stop_words
    ]


# =========================================================
# TIME HELPERS
# =========================================================

def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Keep a numeric value inside a range.
    """

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def format_timestamp(
    seconds: float,
) -> str:
    """
    Convert seconds into HH:MM:SS.mmm format.
    """

    seconds = max(
        0.0,
        float(seconds),
    )

    hours = int(
        seconds // 3600
    )

    minutes = int(
        (seconds % 3600) // 60
    )

    remaining = (
        seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{remaining:06.3f}"
    )


def timestamp_to_seconds(
    timestamp: str,
) -> float:
    """
    Convert HH:MM:SS, MM:SS or SS into seconds.
    """

    if not timestamp:
        return 0.0

    timestamp = timestamp.strip()

    try:

        parts = timestamp.split(":")

        if len(parts) == 3:

            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])

            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

        if len(parts) == 2:

            minutes = float(parts[0])
            seconds = float(parts[1])

            return (
                minutes * 60
                + seconds
            )

        return float(timestamp)

    except (
        ValueError,
        TypeError,
    ):
        return 0.0


# =========================================================
# TRANSCRIPT ANALYSIS
# =========================================================

def calculate_text_energy(
    text: str,
) -> float:
    """
    Estimate how information-dense / interesting
    a transcript segment is.

    This is a heuristic score, not an AI judgment.
    """

    if not text:
        return 0.0

    words = tokenize(text)

    if not words:
        return 0.0

    score = 0.0

    exciting_words = {
        "crazy",
        "insane",
        "unbelievable",
        "shocking",
        "amazing",
        "wow",
        "wait",
        "what",
        "look",
        "no",
        "never",
        "never",
        "huge",
        "massive",
        "dangerous",
        "wild",
        "unexpected",
        "caught",
        "breaking",
        "fight",
        "fighting",
        "crash",
        "destroyed",
        "exploded",
        "explosion",
        "injured",
        "save",
        "saved",
        "fails",
        "failure",
        "winning",
        "winner",
        "lost",
        "lose",
        "secret",
        "rare",
        "crazy",
        "insane",
    }

    for word in words:

        if word in exciting_words:
            score += 8

    # Longer informative segments receive a
    # small information-density bonus.
    word_count = len(words)

    score += min(
        20.0,
        word_count * 0.15,
    )

    # Questions/exclamations often indicate
    # conversational peaks.
    score += text.count("!") * 2
    score += text.count("?") * 2

    return score


def analyze_transcript_segment(
    text: str,
    start: float,
    end: float,
) -> dict:
    """
    Analyze one transcript segment.
    """

    start = max(
        0.0,
        float(start),
    )

    end = max(
        start,
        float(end),
    )

    duration = end - start

    energy = calculate_text_energy(
        text
    )

    return {
        "start": start,
        "end": end,
        "duration": duration,
        "start_timestamp": format_timestamp(
            start
        ),
        "end_timestamp": format_timestamp(
            end
        ),
        "text": text.strip(),
        "text_energy": round(
            energy,
            2,
        ),
    }


# =========================================================
# CANDIDATE CLIP CREATION
# =========================================================

def create_clip_candidate(
    start: float,
    end: float,
    reason: str = "",
    score: float = 0.0,
    text: str = "",
) -> dict:
    """
    Create a standardized clip candidate.
    """

    start = max(
        0.0,
        float(start),
    )

    end = max(
        start,
        float(end),
    )

    duration = end - start

    return {
        "start": round(
            start,
            3,
        ),
        "end": round(
            end,
            3,
        ),
        "duration": round(
            duration,
            3,
        ),
        "start_timestamp": format_timestamp(
            start
        ),
        "end_timestamp": format_timestamp(
            end
        ),
        "score": round(
            float(score),
            2,
        ),
        "reason": reason,
        "text": text.strip(),
    }


# =========================================================
# HEURISTIC MOMENT DETECTION
# =========================================================

def detect_text_peaks(
    transcript_segments: list[dict],
    clip_duration: float = DEFAULT_CLIP_DURATION,
) -> list[dict]:
    """
    Detect potentially interesting moments from transcript
    energy.

    This provides a baseline until stronger audio/visual
    analysis is connected.
    """

    if not transcript_segments:
        return []

    candidates = []

    for segment in transcript_segments:

        start = float(
            segment.get(
                "start",
                0.0,
            )
        )

        end = float(
            segment.get(
                "end",
                start,
            )
        )

        text = segment.get(
            "text",
            "",
        )

        energy = calculate_text_energy(
            text
        )

        if energy <= 0:
            continue

        duration = end - start

        target_duration = clamp(
            clip_duration,
            MIN_CLIP_DURATION,
            MAX_CLIP_DURATION,
        )

        # Center the clip around the detected
        # interesting segment.
        center = (
            start + end
        ) / 2

        candidate_start = max(
            0.0,
            center - target_duration / 2,
        )

        candidate_end = (
            candidate_start
            + target_duration
        )

        candidates.append(
            create_clip_candidate(
                start=candidate_start,
                end=candidate_end,
                reason="transcript_peak",
                score=energy,
                text=text,
            )
        )

    return candidates


# =========================================================
# VISUAL / AUDIO SIGNAL SUPPORT
# =========================================================

def score_signal(
    signal: Optional[float],
    maximum: float = 1.0,
) -> float:
    """
    Normalize an external signal to 0-100.

    Future FFmpeg / audio / visual analysis can feed
    normalized values here.
    """

    if signal is None:
        return 0.0

    try:

        value = float(signal)

    except (
        ValueError,
        TypeError,
    ):

        return 0.0

    if maximum <= 0:
        return 0.0

    normalized = value / maximum

    normalized = clamp(
        normalized,
        0.0,
        1.0,
    )

    return normalized * 100.0


def calculate_clip_score(
    transcript_score: float = 0.0,
    audio_score: float = 0.0,
    visual_score: float = 0.0,
    motion_score: float = 0.0,
    context_score: float = 0.0,
) -> float:
    """
    Combine multiple analysis signals into one score.

    Weights are intentionally centralized so the scoring
    model can be upgraded later without changing the
    rest of the pipeline.
    """

    score = (
        transcript_score * 0.30
        + audio_score * 0.15
        + visual_score * 0.25
        + motion_score * 0.15
        + context_score * 0.15
    )

    return round(
        clamp(
            score,
            0.0,
            100.0,
        ),
        2,
    )


# =========================================================
# CANDIDATE FILTERING
# =========================================================

def clips_overlap(
    first: dict,
    second: dict,
) -> bool:
    """
    Check whether two clip candidates overlap.
    """

    first_start = float(
        first.get(
            "start",
            0.0,
        )
    )

    first_end = float(
        first.get(
            "end",
            0.0,
        )
    )

    second_start = float(
        second.get(
            "start",
            0.0,
        )
    )

    second_end = float(
        second.get(
            "end",
            0.0,
        )
    )

    return (
        first_start < second_end
        and second_start < first_end
    )


def filter_clip_candidates(
    candidates: list[dict],
    min_score: float = 0.0,
    max_clips: int = DEFAULT_TOP_CLIPS,
) -> list[dict]:
    """
    Remove invalid/weak/duplicate-overlapping candidates
    and keep the strongest clips.
    """

    valid = []

    for candidate in candidates:

        start = float(
            candidate.get(
                "start",
                0.0,
            )
        )

        end = float(
            candidate.get(
                "end",
                0.0,
            )
        )

        duration = end - start

        score = float(
            candidate.get(
                "score",
                0.0,
            )
        )

        if duration < MIN_CLIP_DURATION:
            continue

        if duration > MAX_CLIP_DURATION:
            continue

        if score < min_score:
            continue

        valid.append(
            dict(candidate)
        )

    valid.sort(
        key=lambda item: item.get(
            "score",
            0.0,
        ),
        reverse=True,
    )

    selected = []

    for candidate in valid:

        if any(
            clips_overlap(
                candidate,
                existing,
            )
            for existing in selected
        ):
            continue

        selected.append(
            candidate
        )

        if len(selected) >= max_clips:
            break

    for index, candidate in enumerate(
        selected,
        start=1,
    ):

        candidate["rank"] = index

    return selected


# =========================================================
# TRANSCRIPT-BASED ANALYSIS
# =========================================================

def analyze_transcript(
    transcript_segments: list[dict],
    clip_duration: float = DEFAULT_CLIP_DURATION,
    max_clips: int = DEFAULT_TOP_CLIPS,
) -> list[dict]:
    """
    Full baseline transcript analysis pipeline.
    """

    candidates = detect_text_peaks(
        transcript_segments=transcript_segments,
        clip_duration=clip_duration,
    )

    return filter_clip_candidates(
        candidates=candidates,
        min_score=0.0,
        max_clips=max_clips,
    )


# =========================================================
# VIDEO ANALYSIS RESULT
# =========================================================

def analyze_video(
    video_path: str,
    transcript_segments: Optional[list[dict]] = None,
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
) -> dict:
    """
    Create an analysis-ready result for a video.

    Actual FFmpeg/media decoding is deliberately kept
    outside this module. The existing downloader remains
    untouched.

    Later stages can supply:
        - transcript segments
        - audio peaks
        - visual scores
        - motion scores
        - scene changes
    """

    if not video_path:
        raise ValueError(
            "video_path cannot be empty."
        )

    transcript_segments = (
        transcript_segments or []
    )

    candidates = analyze_transcript(
        transcript_segments=transcript_segments,
        max_clips=max_clips,
    )

    if duration is not None:

        duration = max(
            0.0,
            float(duration),
        )

        # Keep candidates inside actual video duration.
        cleaned = []

        for candidate in candidates:

            start = min(
                candidate["start"],
                duration,
            )

            end = min(
                candidate["end"],
                duration,
            )

            if end <= start:
                continue

            updated = dict(candidate)

            updated["start"] = round(
                start,
                3,
            )

            updated["end"] = round(
                end,
                3,
            )

            updated["duration"] = round(
                end - start,
                3,
            )

            updated["start_timestamp"] = format_timestamp(
                start
            )

            updated["end_timestamp"] = format_timestamp(
                end
            )

            cleaned.append(
                updated
            )

        candidates = cleaned

    return {
        "video_path": video_path,
        "duration": duration,
        "clip_count": len(candidates),
        "clips": candidates,
    }


# =========================================================
# ANALYSIS REPORT
# =========================================================

def build_clip_analysis_report(
    video_path: str,
    transcript_segments: Optional[list[dict]] = None,
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
) -> dict:
    """
    Build a clean JSON-ready analysis report.
    """

    analysis = analyze_video(
        video_path=video_path,
        transcript_segments=transcript_segments,
        duration=duration,
        max_clips=max_clips,
    )

    return {
        "version": "1.0",
        "video": {
            "path": video_path,
            "duration": duration,
        },
        "analysis": analysis,
    }


# =========================================================
# SAVE ANALYSIS
# =========================================================

def save_clip_analysis(
    analysis: dict,
    output_path: str,
) -> str:
    """
    Save clip analysis to JSON.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            analysis,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path
