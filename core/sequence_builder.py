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


def build_sequence(profile, clip_analysis, target_duration=60):
    target_duration = max(10, min(int(target_duration), 600))

    candidates = list(
        clip_analysis.get("candidates",
        clip_analysis.get("top_candidates", []))
    )

    candidates = [
        x for x in candidates
        if x.get("start") is not None
        and x.get("end") is not None
        and _duration(x) >= 2.0
    ]

    candidates.sort(key=_score, reverse=True)

    sequence = []
    used = set()
    total = 0.0

    # Prefer one strong candidate per beat first.
    beat_ids = []
    for candidate in candidates:
        beat = candidate.get("beat_id")
        if beat and beat not in beat_ids:
            beat_ids.append(beat)

    for beat_id in beat_ids:
        for candidate in candidates:
            if candidate.get("beat_id") != beat_id:
                continue

            key = _key(candidate)
            duration = _duration(candidate)

            if key in used:
                continue

            if total + duration > target_duration and sequence:
                continue

            sequence.append({
                "order": len(sequence) + 1,
                "beat_id": candidate.get("beat_id"),
                "source_video_id": candidate.get("source_video_id"),
                "source_url": candidate.get("source_url"),
                "source_title": candidate.get("source_title", ""),
                "local_path": candidate.get("local_path"),
                "start": candidate.get("start"),
                "end": candidate.get("end"),
                "duration": round(duration, 3),
                "score": _score(candidate),
                "semantic_score": candidate.get("semantic_score", 0),
                "source_score": candidate.get("source_score", 0),
                "role": (
                    "hook"
                    if len(sequence) == 0
                    else "peak"
                    if len(sequence) == 1
                    else "main"
                ),
            })

            used.add(key)
            total += duration
            break

    # Fill remaining duration with best unused candidates.
    for candidate in candidates:
        if total >= target_duration * 0.85:
            break

        key = _key(candidate)
        duration = _duration(candidate)

        if key in used:
            continue

        if total + duration > target_duration:
            continue

        sequence.append({
            "order": len(sequence) + 1,
            "beat_id": candidate.get("beat_id"),
            "source_video_id": candidate.get("source_video_id"),
            "source_url": candidate.get("source_url"),
            "source_title": candidate.get("source_title", ""),
            "local_path": candidate.get("local_path"),
            "start": candidate.get("start"),
            "end": candidate.get("end"),
            "duration": round(duration, 3),
            "score": _score(candidate),
            "semantic_score": candidate.get("semantic_score", 0),
            "source_score": candidate.get("source_score", 0),
            "role": "main",
        })

        used.add(key)
        total += duration

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
            "dynamic_crops": True,
            "captions": True,
            "sound_effects": True,
            "music_layer": True,
            "beat_sync": True,
            "smart_reframing": True,
            "source_diversification": True,
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
