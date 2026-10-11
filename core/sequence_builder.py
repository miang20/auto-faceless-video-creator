from __future__ import annotations

import json
from pathlib import Path


VERSION = "3.0"


def _score(candidate):
    try:
        return float(candidate.get("final_score", candidate.get("score", 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def _duration(candidate):
    try:
        start = float(candidate.get("local_start", 0) or 0)
        end = candidate.get("local_end")
        if end is not None:
            return max(0.0, float(end) - start)
        return max(0.0, float(candidate.get("duration", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def _key(candidate):
    return (
        str(candidate.get("source_video_id") or candidate.get("video_id") or ""),
        round(float(candidate.get("start", 0) or 0), 2),
        round(float(candidate.get("end", 0) or 0), 2),
        round(float(candidate.get("local_start", 0) or 0), 2),
    )


def _tokens(value):
    import re
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _similarity(a, b):
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def build_sequence(profile, clip_analysis, target_duration=60, editing_settings=None, max_clips=10):
    """Build a relevance-first timeline; reject weak, repeated and malformed candidates."""
    target_duration = max(10, min(int(target_duration), 600))
    try:
        max_clips = max(1, min(100, int(max_clips)))
    except (TypeError, ValueError):
        max_clips = 10
    settings = dict(editing_settings or {})
    reaction_enabled = bool(settings.get("reaction_selection", settings.get("use_reactions", True)))
    contextual_broll = bool(settings.get("contextual_broll", settings.get("use_broll", True)))
    visual_rhythm = bool(settings.get("visual_change_rhythm", True))
    topic = str((profile or {}).get("content", {}).get("topic", "") or "")

    candidates = list(clip_analysis.get("candidates", clip_analysis.get("top_candidates", [])) or [])
    valid = []
    for item in candidates:
        if not isinstance(item, dict) or item.get("start") is None or item.get("end") is None:
            continue
        try:
            start, end = float(item["start"]), float(item["end"])
        except (TypeError, ValueError):
            continue
        duration = _duration(item)
        if end <= start or duration < 1.0 or not item.get("local_path"):
            continue
        score = _score(item)
        # Avoid making a video from random candidates when semantic relevance is weak.
        semantic = float(item.get("semantic_score", 0) or 0)
        source = float(item.get("source_score", 0) or 0)
        if score < 0.18 and semantic < 0.12 and source < 0.12:
            continue
        valid.append(item)

    if not valid:
        return {
            "version": "4.0", "success": False,
            "reason": "No candidates passed relevance and timestamp quality gates",
            "target_duration": target_duration, "max_clips": max_clips,
            "estimated_duration": 0, "clip_count": 0, "sequence": [],
            "quality_gate": {"passed": False, "rejected_candidates": len(candidates)},
        }

    valid.sort(key=lambda x: (_score(x), float(x.get("semantic_score", 0) or 0)), reverse=True)
    sequence, used_keys, total = [], set(), 0.0

    def append_candidate(candidate):
        nonlocal total
        key = _key(candidate)
        duration = _duration(candidate)
        if key in used_keys or duration <= 0:
            return False
        source_id = str(candidate.get("source_video_id") or "")
        text = str(candidate.get("beat_text", candidate.get("text", "")) or "")
        # Reject near-identical beat text and same-source overlapping sections.
        for chosen in sequence:
            if _similarity(text, chosen.get("text", "")) >= 0.82 and text:
                return False
            if source_id and source_id == chosen.get("source_video_id"):
                a, b = float(candidate.get("start", 0)), float(candidate.get("end", 0))
                x, y = float(chosen.get("start", 0)), float(chosen.get("end", 0))
                overlap = max(0.0, min(b, y) - max(a, x))
                if overlap / max(0.1, min(b-a, y-x)) >= 0.5:
                    return False
        if total + duration > target_duration and sequence:
            return False
        reaction = float(candidate.get("reaction_score", 0) or 0)
        if not sequence:
            role = "hook"
        elif reaction_enabled and reaction >= 0.25:
            role = "reaction"
        elif len(sequence) == max_clips - 1:
            role = "payoff"
        elif contextual_broll and (len(sequence) + 1) % 3 == 0:
            role = "broll"
        elif len(sequence) == 1:
            role = "setup"
        else:
            role = "main"
        sequence.append({
            "order": len(sequence) + 1,
            "beat_id": candidate.get("beat_id"),
            "source_video_id": candidate.get("source_video_id"),
            "source_url": candidate.get("source_url"),
            "source_title": candidate.get("source_title", ""),
            "local_path": candidate.get("local_path"),
            "local_start": float(candidate.get("local_start", 0) or 0),
            "local_end": candidate.get("local_end"),
            "start": float(candidate.get("start", 0)),
            "end": float(candidate.get("end", 0)),
            "duration": round(duration, 3),
            "score": _score(candidate),
            "semantic_score": candidate.get("semantic_score", 0),
            "source_score": candidate.get("source_score", 0),
            "reaction_score": reaction,
            "text": text,
            "role": role,
        })
        used_keys.add(key)
        total += duration
        return True

    # Pick one strong candidate per story beat first, not many variants of the same beat.
    beat_ids = []
    for item in valid:
        beat = item.get("beat_id")
        if beat and beat not in beat_ids:
            beat_ids.append(beat)
    for beat in beat_ids:
        if len(sequence) >= max_clips or total >= target_duration * 0.92:
            break
        options = [x for x in valid if x.get("beat_id") == beat and _key(x) not in used_keys]
        options.sort(key=lambda x: (_score(x), float(x.get("semantic_score", 0) or 0)), reverse=True)
        for item in options:
            if append_candidate(item):
                break

    while total < target_duration * 0.82 and len(sequence) < max_clips:
        options = [x for x in valid if _key(x) not in used_keys]
        if not options:
            break
        # Favor source variety without allowing a weak candidate to beat a relevant one.
        options.sort(key=lambda x: (
            _score(x) + (0.035 if visual_rhythm and x.get("source_video_id") not in {z.get("source_video_id") for z in sequence[-2:]} else 0),
            float(x.get("semantic_score", 0) or 0)
        ), reverse=True)
        appended = False
        for item in options:
            if append_candidate(item):
                appended = True
                break
        if not appended:
            break

    passed = bool(sequence) and len(sequence) >= min(3, max_clips) and total >= min(target_duration * 0.55, target_duration - 1)
    return {
        "version": "4.0",
        "success": passed,
        "reason": None if passed else "Sequence failed minimum clip-count or duration quality gate",
        "target_duration": target_duration,
        "max_clips": max_clips,
        "estimated_duration": round(total, 3),
        "clip_count": len(sequence),
        "sequence": sequence,
        "quality_gate": {
            "passed": passed,
            "input_candidates": len(candidates),
            "eligible_candidates": len(valid),
            "rejected_candidates": len(candidates) - len(valid),
            "unique_clips": len(sequence),
            "minimum_duration_ratio": 0.55,
            "minimum_clips": min(3, max_clips),
        },
        "editing_plan": {
            "vertical": True, "fast_cuts": True,
            "dynamic_crops": bool(settings.get("dynamic_zoom", True)),
            "captions": bool(settings.get("captions", True)),
            "source_diversification": visual_rhythm,
            "contextual_broll": contextual_broll,
            "reaction_selection": reaction_enabled,
            "visual_change_rhythm": visual_rhythm,
        },
    }

def save_sequence(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage: python sequence_builder.py profile candidates target output"
        )

    with open(sys.argv[1], encoding="utf-8") as f:
        profile = json.load(f)

    with open(sys.argv[2], encoding="utf-8") as f:
        candidates = json.load(f)

    target = int(sys.argv[3])

    result = build_sequence(
        profile,
        candidates,
        target,
    )

    save_sequence(result, sys.argv[4])

    print(json.dumps({
        "success": result["success"],
        "version": result["version"],
        "clips": result["clip_count"],
        "duration": result["estimated_duration"],
    }, indent=2))
