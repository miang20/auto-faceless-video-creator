"""
Pro V2 Clip Analyzer

Analyzes transcript segments and produces high-value clip candidates.

Design goals:
- Strong hook detection
- Story-role detection
- Transcript intensity
- Audio/visual/motion signal support
- Scene/change awareness when metadata is available
- Target-duration awareness
- Flexible clip boundaries
- Backward-compatible output structure
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


MIN_CLIP_DURATION = 3.0
MAX_CLIP_DURATION = 60.0
DEFAULT_CLIP_DURATION = 15.0
DEFAULT_TOP_CLIPS = 10


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than",
    "to", "of", "in", "on", "at", "for", "from", "with", "by",
    "is", "it", "this", "that", "was", "were", "are", "be",
    "been", "being", "as", "into", "about", "after", "before",
    "he", "she", "they", "them", "his", "her", "their", "we",
    "you", "i", "me", "my", "our", "your", "us", "do", "did",
    "does", "have", "has", "had", "not", "no", "so", "just",
    "very", "really", "like", "well", "yeah", "okay", "ok",
}


INTENSITY_WORDS = {
    "crazy", "insane", "wild", "unbelievable", "incredible",
    "amazing", "shocking", "shocked", "wow", "what", "why",
    "how", "never", "ever", "suddenly", "actually", "literally",
    "massive", "huge", "dangerous", "scary", "terrifying",
    "ridiculous", "insane", "brutal", "destroyed", "destroy",
    "fight", "fighting", "crash", "crashed", "hit", "hits",
    "caught", "caught", "exposed", "ejected", "ejection",
    "fails", "failed", "failure", "accident", "accidental",
    "run", "running", "escape", "escaped", "break", "broke",
    "broken", "fall", "fell", "falls", "almost", "close",
    "danger", "dangerous", "warning", "wrong", "mistake",
    "mistake", "perfect", "worst", "best", "first", "last",
    "record", "rare", "rarely", "never",
}


REACTION_WORDS = {
    "wow", "oh", "whoa", "damn", "holy", "what", "no", "yes",
    "look", "wait", "bro", "dude", "crazy", "insane", "unreal",
    "shocking", "shocked", "can't", "cannot", "believe",
}


HOOK_PATTERNS = [
    r"\bwait\b",
    r"\bwhat\b",
    r"\bhow\b",
    r"\bwhy\b",
    r"\blook\b",
    r"\bwatch\b",
    r"\bno way\b",
    r"\byou won't believe\b",
    r"\bcan't believe\b",
    r"\bcannot believe\b",
    r"\bnever seen\b",
    r"\bnever happened\b",
    r"\bwhat just happened\b",
    r"\bhow did\b",
    r"\bwhy did\b",
    r"\bcaught\b",
    r"\bsuddenly\b",
    r"\bturns out\b",
    r"\buntil\b",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def clean_text(text: Any) -> str:
    if text is None:
        return ""

    text = str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    text = clean_text(text).lower()
    words = re.findall(r"[a-zA-Z0-9']+", text)

    return [
        word
        for word in words
        if word not in STOP_WORDS
    ]


def _raw_tokens(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9']+", clean_text(text).lower())


def _keyword_density(text: str) -> float:
    words = _raw_tokens(text)

    if not words:
        return 0.0

    meaningful = [w for w in words if w not in STOP_WORDS]
    return _clamp(len(meaningful) / max(len(words), 1))


def calculate_text_energy(text: str) -> float:
    """
    Estimate how information-dense and emotionally intense a transcript line is.
    """

    text = clean_text(text)

    if not text:
        return 0.0

    words = _raw_tokens(text)
    if not words:
        return 0.0

    lower = text.lower()

    intensity_hits = sum(
        1 for word in words
        if word in INTENSITY_WORDS
    )

    reaction_hits = sum(
        1 for word in words
        if word in REACTION_WORDS
    )

    exclamation_count = text.count("!")
    question_count = text.count("?")

    uppercase_words = sum(
        1 for word in re.findall(r"\b[A-Z]{2,}\b", text)
    )

    keyword_density = _keyword_density(text)

    intensity_signal = _clamp(
        intensity_hits / max(len(words) * 0.18, 1.0)
    )

    reaction_signal = _clamp(
        reaction_hits / max(len(words) * 0.15, 1.0)
    )

    punctuation_signal = _clamp(
        (exclamation_count * 0.18)
        + (question_count * 0.12)
        + (uppercase_words * 0.10)
    )

    length_signal = _clamp(
        len(words) / 25.0
    )

    score = (
        intensity_signal * 0.40
        + reaction_signal * 0.20
        + punctuation_signal * 0.15
        + keyword_density * 0.15
        + length_signal * 0.10
    )

    return round(_clamp(score), 4)


def _hook_signal(text: str) -> float:
    lower = clean_text(text).lower()

    if not lower:
        return 0.0

    pattern_hits = sum(
        1 for pattern in HOOK_PATTERNS
        if re.search(pattern, lower)
    )

    energy = calculate_text_energy(lower)

    surprise_words = sum(
        1
        for word in _raw_tokens(lower)
        if word in {
            "suddenly",
            "caught",
            "never",
            "wait",
            "what",
            "why",
            "how",
            "until",
            "actually",
            "turns",
        }
    )

    signal = (
        _clamp(pattern_hits / 2.0) * 0.50
        + energy * 0.30
        + _clamp(surprise_words / 3.0) * 0.20
    )

    return round(_clamp(signal), 4)


def _reaction_signal(text: str) -> float:
    words = _raw_tokens(text)

    if not words:
        return 0.0

    hits = sum(1 for word in words if word in REACTION_WORDS)

    return round(
        _clamp(hits / max(len(words) * 0.15, 1.0)),
        4,
    )


def _audio_signal(segment: Dict[str, Any]) -> float:
    """
    Use supplied audio metadata if available.

    We intentionally do not require audio analysis here. The processor can
    provide RMS/volume/peak information later without changing this analyzer.
    """

    for key in (
        "audio_score",
        "audio_energy",
        "volume_score",
        "rms_score",
    ):
        if key in segment:
            return round(
                _clamp(_safe_float(segment.get(key))),
                4,
            )

    rms = segment.get("rms")
    if rms is not None:
        rms_value = _safe_float(rms)

        # Common normalized RMS is 0..1.
        if 0.0 <= rms_value <= 1.0:
            return round(rms_value, 4)

        # Convert dB-ish values to a rough normalized score.
        if rms_value < 0:
            return round(
                _clamp((rms_value + 60.0) / 60.0),
                4,
            )

    return 0.0


def _visual_signal(segment: Dict[str, Any]) -> float:
    """
    Consume optional visual-analysis metadata.

    Supported fields:
    visual_score, visual_energy, motion_score, motion_energy,
    scene_change, scene_change_score.
    """

    values = []

    for key in (
        "visual_score",
        "visual_energy",
        "motion_score",
        "motion_energy",
    ):
        if key in segment:
            values.append(
                _clamp(_safe_float(segment.get(key)))
            )

    if not values:
        return 0.0

    return round(sum(values) / len(values), 4)


def _scene_change_signal(segment: Dict[str, Any]) -> float:
    for key in (
        "scene_change",
        "scene_change_score",
        "cut_score",
    ):
        if key in segment:
            value = segment.get(key)

            if isinstance(value, bool):
                return 1.0 if value else 0.0

            return round(
                _clamp(_safe_float(value)),
                4,
            )

    return 0.0


def _context_signal(
    text: str,
    previous_text: str = "",
    next_text: str = "",
) -> float:
    """
    Estimates whether the segment has enough surrounding context to be useful.
    """

    current_words = tokenize(text)

    if not current_words:
        return 0.0

    score = 0.35

    if previous_text:
        score += 0.20

    if next_text:
        score += 0.20

    if len(current_words) >= 5:
        score += 0.15

    if any(
        marker in clean_text(text).lower()
        for marker in (
            "because",
            "but",
            "then",
            "after",
            "before",
            "so",
            "when",
            "until",
            "suddenly",
        )
    ):
        score += 0.10

    return round(_clamp(score), 4)


def analyze_transcript_segment(
    segment: Dict[str, Any],
    previous_segment: Optional[Dict[str, Any]] = None,
    next_segment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    text = clean_text(
        segment.get("text")
        or segment.get("content")
        or segment.get("transcript")
        or ""
    )

    start = _safe_float(
        segment.get("start", segment.get("start_time", 0.0))
    )

    end = _safe_float(
        segment.get(
            "end",
            segment.get(
                "end_time",
                start + _safe_float(segment.get("duration"), 0.0),
            ),
        )
    )

    if end <= start:
        end = start + max(
            1.0,
            _safe_float(segment.get("duration"), 1.0),
        )

    previous_text = ""
    next_text = ""

    if previous_segment:
        previous_text = clean_text(
            previous_segment.get("text")
            or previous_segment.get("content")
            or ""
        )

    if next_segment:
        next_text = clean_text(
            next_segment.get("text")
            or next_segment.get("content")
            or ""
        )

    text_energy = calculate_text_energy(text)
    hook_score = _hook_signal(text)
    reaction_score = _reaction_signal(text)
    audio_score = _audio_signal(segment)
    visual_score = _visual_signal(segment)
    scene_change_score = _scene_change_signal(segment)
    context_score = _context_signal(
        text,
        previous_text,
        next_text,
    )

    words = _raw_tokens(text)

    speech_density = _clamp(
        len(words) / max(end - start, 0.5) / 3.0
    )

    score = (
        text_energy * 0.30
        + audio_score * 0.15
        + visual_score * 0.20
        + scene_change_score * 0.10
        + context_score * 0.10
        + hook_score * 0.15
    )

    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(max(0.0, end - start), 3),
        "text": text,
        "word_count": len(words),
        "text_energy": round(text_energy, 4),
        "hook_score": round(hook_score, 4),
        "reaction_score": round(reaction_score, 4),
        "audio_score": round(audio_score, 4),
        "visual_score": round(visual_score, 4),
        "motion_score": round(visual_score, 4),
        "scene_change_score": round(scene_change_score, 4),
        "context_score": round(context_score, 4),
        "speech_density": round(speech_density, 4),
        "score": round(_clamp(score), 4),
    }


def _story_role(
    item: Dict[str, Any],
    index: int,
    total: int,
) -> str:

    score = _safe_float(item.get("score"))
    hook = _safe_float(item.get("hook_score"))
    reaction = _safe_float(item.get("reaction_score"))
    energy = _safe_float(item.get("text_energy"))

    position = index / max(total - 1, 1)

    if index == 0 or hook >= 0.65:
        return "HOOK"

    if position < 0.28:
        return "SETUP"

    if reaction >= 0.60:
        return "REACTION"

    if position > 0.72 and score >= 0.45:
        return "PAYOFF"

    if energy >= 0.60 or score >= 0.55:
        return "ESCALATION"

    if position > 0.88:
        return "ENDING"

    return "SETUP"


def create_clip_candidate(
    segments: Sequence[Dict[str, Any]],
    start_index: int,
    end_index: int,
    target_duration: float = DEFAULT_CLIP_DURATION,
) -> Dict[str, Any]:

    selected = list(segments[start_index:end_index + 1])

    if not selected:
        return {}

    start = _safe_float(selected[0].get("start"))
    end = _safe_float(selected[-1].get("end"))

    if end <= start:
        end = start + target_duration

    duration = end - start

    texts = [
        clean_text(item.get("text", ""))
        for item in selected
        if clean_text(item.get("text", ""))
    ]

    combined_text = " ".join(texts)

    scores = [
        _safe_float(item.get("score"))
        for item in selected
    ]

    hook_scores = [
        _safe_float(item.get("hook_score"))
        for item in selected
    ]

    audio_scores = [
        _safe_float(item.get("audio_score"))
        for item in selected
    ]

    visual_scores = [
        _safe_float(item.get("visual_score"))
        for item in selected
    ]

    motion_scores = [
        _safe_float(item.get("motion_score"))
        for item in selected
    ]

    scene_scores = [
        _safe_float(item.get("scene_change_score"))
        for item in selected
    ]

    peak_score = max(scores) if scores else 0.0
    average_score = (
        sum(scores) / len(scores)
        if scores
        else 0.0
    )

    hook_score = max(hook_scores) if hook_scores else 0.0

    audio_score = (
        sum(audio_scores) / len(audio_scores)
        if audio_scores
        else 0.0
    )

    visual_score = (
        sum(visual_scores) / len(visual_scores)
        if visual_scores
        else 0.0
    )

    motion_score = (
        sum(motion_scores) / len(motion_scores)
        if motion_scores
        else 0.0
    )

    scene_score = (
        sum(scene_scores) / len(scene_scores)
        if scene_scores
        else 0.0
    )

    target_fit = _clamp(
        1.0 - abs(duration - target_duration)
        / max(target_duration, 1.0)
    )

    # Slightly favor clips that contain multiple useful signals rather than
    # clips that are only long or only text-heavy.
    multi_signal = sum(
        1
        for value in (
            hook_score,
            audio_score,
            visual_score,
            motion_score,
            scene_score,
        )
        if value >= 0.45
    )

    multi_signal_score = _clamp(
        multi_signal / 3.0
    )

    final_score = (
        peak_score * 0.25
        + average_score * 0.20
        + hook_score * 0.15
        + visual_score * 0.10
        + motion_score * 0.10
        + audio_score * 0.08
        + scene_score * 0.05
        + target_fit * 0.04
        + multi_signal_score * 0.03
    )

    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(duration, 3),
        "text": combined_text,
        "score": round(_clamp(final_score), 4),
        "peak_score": round(peak_score, 4),
        "average_score": round(average_score, 4),
        "hook_score": round(hook_score, 4),
        "audio_score": round(audio_score, 4),
        "visual_score": round(visual_score, 4),
        "motion_score": round(motion_score, 4),
        "scene_change_score": round(scene_score, 4),
        "target_fit": round(target_fit, 4),
        "multi_signal_score": round(multi_signal_score, 4),
        "start_index": start_index,
        "end_index": end_index,
    }


def detect_text_peaks(
    transcript_segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    analyzed = []

    for index, segment in enumerate(transcript_segments):

        previous_segment = (
            transcript_segments[index - 1]
            if index > 0
            else None
        )

        next_segment = (
            transcript_segments[index + 1]
            if index + 1 < len(transcript_segments)
            else None
        )

        analyzed.append(
            analyze_transcript_segment(
                segment,
                previous_segment,
                next_segment,
            )
        )

    return analyzed


def score_signal(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:

    value = _safe_float(value)

    if maximum <= minimum:
        return 0.0

    return round(
        _clamp(
            (value - minimum) / (maximum - minimum)
        ),
        4,
    )


def calculate_clip_score(
    transcript_score: float,
    audio_score: float = 0.0,
    visual_score: float = 0.0,
    motion_score: float = 0.0,
    context_score: float = 0.0,
    hook_score: float = 0.0,
    scene_change_score: float = 0.0,
) -> float:
    """
    Public scoring helper retained for backward compatibility.

    Transcript remains the strongest single signal, while hook and visual
    signals are explicitly rewarded for Pro V2.
    """

    score = (
        _safe_float(transcript_score) * 0.25
        + _safe_float(audio_score) * 0.12
        + _safe_float(visual_score) * 0.16
        + _safe_float(motion_score) * 0.12
        + _safe_float(context_score) * 0.10
        + _safe_float(hook_score) * 0.17
        + _safe_float(scene_change_score) * 0.08
    )

    return round(_clamp(score), 4)


def _overlap_ratio(
    first: Dict[str, Any],
    second: Dict[str, Any],
) -> float:

    first_start = _safe_float(first.get("start"))
    first_end = _safe_float(first.get("end"))

    second_start = _safe_float(second.get("start"))
    second_end = _safe_float(second.get("end"))

    intersection = max(
        0.0,
        min(first_end, second_end)
        - max(first_start, second_start),
    )

    first_duration = max(
        0.001,
        first_end - first_start,
    )

    second_duration = max(
        0.001,
        second_end - second_start,
    )

    return intersection / min(
        first_duration,
        second_duration,
    )


def _select_non_overlapping(
    candidates: Sequence[Dict[str, Any]],
    max_clips: int,
    overlap_threshold: float = 0.55,
) -> List[Dict[str, Any]]:

    selected: List[Dict[str, Any]] = []

    for candidate in sorted(
        candidates,
        key=lambda item: _safe_float(item.get("score")),
        reverse=True,
    ):

        if len(selected) >= max_clips:
            break

        overlaps = any(
            _overlap_ratio(candidate, existing)
            >= overlap_threshold
            for existing in selected
        )

        if overlaps:
            continue

        selected.append(candidate)

    return selected


def _build_candidates(
    analyzed_segments: Sequence[Dict[str, Any]],
    target_duration: float,
) -> List[Dict[str, Any]]:

    candidates: List[Dict[str, Any]] = []

    if not analyzed_segments:
        return candidates

    # Candidate windows of different sizes prevent the analyzer from forcing
    # every clip into the same rigid duration.
    window_sizes = [1, 2, 3, 4, 5, 6]

    for start_index in range(len(analyzed_segments)):

        for window_size in window_sizes:

            end_index = start_index + window_size - 1

            if end_index >= len(analyzed_segments):
                break

            candidate = create_clip_candidate(
                analyzed_segments,
                start_index,
                end_index,
                target_duration=target_duration,
            )

            if not candidate:
                continue

            duration = _safe_float(
                candidate.get("duration")
            )

            if duration < MIN_CLIP_DURATION:
                continue

            if duration > MAX_CLIP_DURATION:
                continue

            candidates.append(candidate)

    return candidates


def _expand_short_candidates(
    candidates: List[Dict[str, Any]],
    transcript_segments: Sequence[Dict[str, Any]],
    target_duration: float,
) -> List[Dict[str, Any]]:

    """
    Add larger windows around high-value moments.

    This is deliberately flexible. A strong moment may need 6 seconds of setup
    while another may work perfectly at 3–4 seconds.
    """

    if not transcript_segments:
        return candidates

    analyzed = detect_text_peaks(transcript_segments)

    for index, item in enumerate(analyzed):

        score = _safe_float(item.get("score"))

        if score < 0.45:
            continue

        center_start = max(
            0,
            index - 2,
        )

        center_end = min(
            len(analyzed) - 1,
            index + 2,
        )

        candidate = create_clip_candidate(
            analyzed,
            center_start,
            center_end,
            target_duration=target_duration,
        )

        if candidate:
            duration = _safe_float(
                candidate.get("duration")
            )

            if MIN_CLIP_DURATION <= duration <= MAX_CLIP_DURATION:
                candidates.append(candidate)

    return candidates


def analyze_transcript(
    transcript_segments: Sequence[Dict[str, Any]],
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
    target_duration: float = DEFAULT_CLIP_DURATION,
) -> Dict[str, Any]:

    if not transcript_segments:
        return {
            "segments": [],
            "clips": [],
            "peaks": [],
            "total_segments": 0,
        }

    target_duration = max(
        MIN_CLIP_DURATION,
        min(
            MAX_CLIP_DURATION,
            _safe_float(
                target_duration,
                DEFAULT_CLIP_DURATION,
            ),
        ),
    )

    analyzed_segments = detect_text_peaks(
        transcript_segments
    )

    for index, item in enumerate(analyzed_segments):
        item["story_role"] = _story_role(
            item,
            index,
            len(analyzed_segments),
        )

    candidates = _build_candidates(
        analyzed_segments,
        target_duration,
    )

    candidates = _expand_short_candidates(
        candidates,
        transcript_segments,
        target_duration,
    )

    selected = _select_non_overlapping(
        candidates,
        max(
            1,
            int(max_clips),
        ),
    )

    # Ensure the strongest hook is represented when one exists.
    hook_segments = sorted(
        analyzed_segments,
        key=lambda item: (
            _safe_float(item.get("hook_score")),
            _safe_float(item.get("score")),
        ),
        reverse=True,
    )

    if hook_segments:
        strongest_hook = hook_segments[0]

        hook_candidate = create_clip_candidate(
            analyzed_segments,
            max(
                0,
                analyzed_segments.index(strongest_hook) - 1,
            ),
            min(
                len(analyzed_segments) - 1,
                analyzed_segments.index(strongest_hook) + 1,
            ),
            target_duration=target_duration,
        )

        if hook_candidate:
            hook_candidate["story_role"] = "HOOK"

            existing_hook = any(
                item.get("story_role") == "HOOK"
                for item in selected
            )

            if not existing_hook:
                selected = [
                    hook_candidate,
                    *selected,
                ][:max(1, int(max_clips))]

    selected.sort(
        key=lambda item: _safe_float(item.get("start"))
    )

    # Assign story role to final clips based on their dominant segment.
    for candidate in selected:

        start_index = int(
            candidate.get("start_index", 0)
        )

        end_index = int(
            candidate.get("end_index", start_index)
        )

        roles = [
            analyzed_segments[i].get("story_role")
            for i in range(
                max(0, start_index),
                min(
                    len(analyzed_segments),
                    end_index + 1,
                ),
            )
        ]

        role = "SETUP"

        if "HOOK" in roles:
            role = "HOOK"
        elif "PAYOFF" in roles:
            role = "PAYOFF"
        elif "REACTION" in roles:
            role = "REACTION"
        elif "ESCALATION" in roles:
            role = "ESCALATION"
        elif "ENDING" in roles:
            role = "ENDING"

        candidate["story_role"] = role

    peaks = sorted(
        analyzed_segments,
        key=lambda item: _safe_float(item.get("score")),
        reverse=True,
    )[:max(5, int(max_clips))]

    return {
        "segments": analyzed_segments,
        "clips": selected,
        "peaks": peaks,
        "total_segments": len(analyzed_segments),
        "duration": duration,
        "target_duration": target_duration,
    }


def _probe_video_duration(video_path: str) -> Optional[float]:
    if not video_path or not os.path.exists(video_path):
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            return None

        value = _safe_float(result.stdout.strip())

        if value > 0:
            return value

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        pass

    return None


def _normalize_transcript(
    transcript: Any,
) -> List[Dict[str, Any]]:

    if transcript is None:
        return []

    if isinstance(transcript, dict):

        for key in (
            "segments",
            "transcript",
            "results",
            "items",
        ):
            if isinstance(transcript.get(key), list):
                transcript = transcript[key]
                break

    if not isinstance(transcript, list):
        return []

    normalized = []

    for item in transcript:

        if isinstance(item, dict):
            normalized.append(item)

    return normalized


def analyze_video(
    video_path: str,
    transcript_segments: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
    target_duration: float = DEFAULT_CLIP_DURATION,
) -> Dict[str, Any]:

    if duration is None:
        duration = _probe_video_duration(video_path)

    transcript_segments = _normalize_transcript(
        transcript_segments
    )

    analysis = analyze_transcript(
        transcript_segments,
        duration=duration,
        max_clips=max_clips,
        target_duration=target_duration,
    )

    analysis["video_path"] = video_path

    return analysis


def build_clip_analysis_report(
    video_path: str,
    transcript_segments: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
    target_duration: float = DEFAULT_CLIP_DURATION,
) -> Dict[str, Any]:

    analysis = analyze_video(
        video_path=video_path,
        transcript_segments=transcript_segments,
        duration=duration,
        max_clips=max_clips,
        target_duration=target_duration,
    )

    clips = analysis.get("clips", [])

    return {
        "video_path": video_path,
        "duration": analysis.get("duration"),
        "target_duration": analysis.get(
            "target_duration",
            target_duration,
        ),
        "total_segments": analysis.get(
            "total_segments",
            0,
        ),
        "clips": clips,
        "peaks": analysis.get("peaks", []),
        "analysis": {
            "clips": clips,
            "peaks": analysis.get("peaks", []),
            "segments": analysis.get("segments", []),
            "total_segments": analysis.get(
                "total_segments",
                0,
            ),
        },
    }


def save_clip_analysis(
    analysis: Dict[str, Any],
    output_path: str,
) -> str:

    directory = os.path.dirname(output_path)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            analysis,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return output_path
