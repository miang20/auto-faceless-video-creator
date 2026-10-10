from __future__ import annotations

import json
from pathlib import Path


VERSION = "3.0"


def _score(candidate):
    return float(
        candidate.get(
            "final_score",
            candidate.get("score", 0),
        )
        or 0
    )


def _duration(candidate):
    return float(candidate.get("duration", 0) or 0)


def _key(candidate):
    return (
        candidate.get("source_video_id"),
        round(float(candidate.get("start", 0)), 3),
        round(float(candidate.get("end", 0)), 3),
    )


def build_sequence(profile, clip_analysis, target_duration=60, editing_settings=None):
    target_duration = max(10, min(int(target_duration), 600))
    settings = dict(editing_settings or {})
    reaction_enabled = bool(settings.get("reaction_selection", settings.get("use_reactions", True)))
    contextual_broll = bool(settings.get("contextual_broll", settings.get("use_broll", True)))
    visual_rhythm = bool(settings.get("visual_change_rhythm", True))

    candidates = list(
        clip_analysis.get("candidates", clip_analysis.get("top_candidates", []))
    )
    candidates = [
        x for x in candidates
        if x.get("start") is not None
        and x.get("end") is not None
        and _duration(x) >= 1.0
    ]

    def rank(candidate, recent_sources):
        value = _score(candidate)
        if reaction_enabled:
            value += float(candidate.get("reaction_score", 0) or 0) * 0.12
        source_id = candidate.get("source_video_id")
        if visual_rhythm and source_id and source_id not in recent_sources:
            value += 0.12
        if contextual_broll and source_id and source_id not in {
            item.get("source_video_id") for item in sequence
        }:
            value += 0.06
        return value

    candidates.sort(key=_score, reverse=True)
    sequence = []
    used = set()
    total = 0.0

    def append_candidate(candidate):
        nonlocal total
        key = _key(candidate)
        duration = _duration(candidate)
        if key in used or duration <= 0:
            return False
        if total + duration > target_duration and sequence:
            return False

        source_id = candidate.get("source_video_id")
        recent_sources = {
            item.get("source_video_id") for item in sequence[-2:]
        }
        different_recent = bool(source_id and source_id not in recent_sources)
        reaction_score = float(candidate.get("reaction_score", 0) or 0)

        if not sequence:
            role = "hook"
        elif reaction_enabled and reaction_score >= 0.25:
            role = "reaction"
        elif contextual_broll and (len(sequence) + 1) % 3 == 0 and different_recent:
            role = "broll"
        elif len(sequence) == 1:
            role = "peak"
        else:
            role = "main"

        sequence.append({
            "order": len(sequence) + 1,
            "beat_id": candidate.get("beat_id"),
            "source_video_id": source_id,
            "source_url": candidate.get("source_url"),
            "source_title": candidate.get("source_title", ""),
            "local_path": candidate.get("local_path"),
            "local_start": candidate.get("local_start", 0),
            "local_end": candidate.get("local_end"),
            "start": candidate.get("start"),
            "end": candidate.get("end"),
            "duration": round(duration, 3),
            "score": _score(candidate),
            "semantic_score": candidate.get("semantic_score", 0),
            "source_score": candidate.get("source_score", 0),
            "reaction_score": reaction_score,
            "text": candidate.get("beat_text", ""),
            "role": role,
        })
        used.add(key)
        total += duration
        return True

    beat_ids = []
    for candidate in candidates:
        beat = candidate.get("beat_id")
        if beat and beat not in beat_ids:
            beat_ids.append(beat)

    # Choose the strongest candidate for each beat, with modest bonuses for
    # source variety and detected reaction language when those features are on.
    for beat_id in beat_ids:
        if total >= target_duration * 0.9:
            break
        options = [
            item for item in candidates
            if item.get("beat_id") == beat_id and _key(item) not in used
        ]
        options.sort(
            key=lambda item: rank(
                item,
                {x.get("source_video_id") for x in sequence[-2:]},
            ),
            reverse=True,
        )
        for candidate in options:
            if append_candidate(candidate):
                break

    # Fill any remaining time with the best unused sections while maintaining
    # a visual source-change rhythm where viable.
    while total < target_duration * 0.85:
        options = [item for item in candidates if _key(item) not in used]
        if not options:
            break
        options.sort(
            key=lambda item: rank(
                item,
                {x.get("source_video_id") for x in sequence[-2:]},
            ),
            reverse=True,
        )
        appended = False
        for candidate in options:
            if append_candidate(candidate):
                appended = True
                break
        if not appended:
            break

    return {
        "version": VERSION,
        "success": bool(sequence),
        "reason": None if sequence else "No usable clip candidates",
        "target_duration": target_duration,
        "estimated_duration": round(total, 3),
        "clip_count": len(sequence),
        "sequence": sequence,
        "editing_plan": {
            "vertical": True,
            "fast_cuts": True,
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
