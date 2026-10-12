from __future__ import annotations

import json
from pathlib import Path


VERSION = "4.0"


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
    """Build a relevance-first timeline while honoring clip and duration budgets."""
    target_duration = max(1, min(int(target_duration), 600))
    try:
        max_clips = max(1, min(100, int(max_clips)))
    except (TypeError, ValueError):
        max_clips = 10
    settings = dict(editing_settings or {})
    reaction_enabled = bool(settings.get("reaction_selection", settings.get("use_reactions", True)))
    contextual_broll = bool(settings.get("contextual_broll", settings.get("use_broll", True)))
    visual_rhythm = bool(settings.get("visual_change_rhythm", True))
    topic = str((profile or {}).get("content", {}).get("topic", "") or "")
    if isinstance(clip_analysis, list):
        candidates = clip_analysis
    else:
        candidates = list((clip_analysis or {}).get("candidates", (clip_analysis or {}).get("top_candidates", [])) or [])

    valid = []
    for original in candidates:
        if not isinstance(original, dict) or original.get("start") is None or original.get("end") is None:
            continue
        try:
            start, end = float(original["start"]), float(original["end"])
        except (TypeError, ValueError):
            continue
        duration = _duration(original)
        if end <= start or duration < 1.0 or not original.get("local_path"):
            continue

        score = _score(original)
        semantic = float(original.get("semantic_score", 0) or 0)
        beat_text = str(original.get("beat_text") or original.get("requested_beat_text") or topic or "")
        candidate_text = str(
            original.get("transcript") or original.get("visual_description")
            or original.get("text") or original.get("source_title") or ""
        )
        lexical_match = _similarity(candidate_text, beat_text)
        has_beat_contract = bool(original.get("beat_id") and original.get("beat_text"))
        # Older candidate reports did not emit semantic_score. Permit those only
        # when they carry an explicit story-beat contract and a strong rank score.
        legacy_beat_evidence = has_beat_contract and score >= 0.65
        if semantic < 0.12 and lexical_match < 0.10 and not legacy_beat_evidence:
            continue
        if score < 0.12 and semantic < 0.18 and lexical_match < 0.15:
            continue
        item = dict(original)
        item["_lexical_match"] = round(lexical_match, 3)
        valid.append(item)

    if not valid:
        return {
            "version": VERSION, "success": False,
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
        available = _duration(candidate)
        remaining = target_duration - total
        if key in used_keys or available <= 0 or remaining <= 0.05:
            return False
        source_id = str(candidate.get("source_video_id") or "")
        text = str(candidate.get("beat_text", candidate.get("text", "")) or "")
        for chosen in sequence:
            if _similarity(text, chosen.get("text", "")) >= 0.82 and text:
                return False
            if source_id and source_id == chosen.get("source_video_id"):
                a, b = float(candidate.get("start", 0)), float(candidate.get("end", 0))
                x, y = float(chosen.get("start", 0)), float(chosen.get("end", 0))
                overlap = max(0.0, min(b, y) - max(a, x))
                if overlap / max(0.1, min(b-a, y-x)) >= 0.5:
                    return False

        # Trim the final selected section to the remaining target budget instead
        # of dropping it and returning an unnecessarily short sequence.
        chosen_duration = min(available, remaining)
        local_start = float(candidate.get("local_start", 0) or 0)
        local_end_value = candidate.get("local_end")
        local_end = local_start + chosen_duration if local_end_value is None else min(float(local_end_value), local_start + chosen_duration)
        chosen_duration = max(0.0, local_end - local_start)
        if chosen_duration < 0.75:
            return False

        reaction = float(candidate.get("reaction_score", 0) or 0)
        if not sequence:
            role = "hook"
        elif reaction_enabled and reaction >= 0.25:
            role = "reaction"
        elif len(sequence) == max_clips - 1 or chosen_duration >= remaining - 0.05:
            role = "payoff"
        elif contextual_broll and (len(sequence) + 1) % 3 == 0:
            role = "broll"
        elif len(sequence) == 1:
            role = "setup"
        else:
            role = "main"

        item_start = float(candidate.get("start", 0))
        item_end = float(candidate.get("end", 0))
        source_span = max(0.0, item_end - item_start)
        if source_span > chosen_duration:
            if role in {"PAYOFF", "ENDING"}:
                item_start = item_end - chosen_duration
            else:
                item_end = item_start + chosen_duration
        sequence.append({
            "order": len(sequence) + 1,
            "beat_id": candidate.get("beat_id"),
            "source_video_id": candidate.get("source_video_id"),
            "source_url": candidate.get("source_url"),
            "source_title": candidate.get("source_title", ""),
            "local_path": candidate.get("local_path"),
            "local_start": local_start,
            "local_end": local_end,
            "start": item_start,
            "end": item_end,
            "duration": round(chosen_duration, 3),
            "score": _score(candidate),
            "semantic_score": candidate.get("semantic_score", 0),
            "source_score": candidate.get("source_score", 0),
            "reaction_score": reaction,
            "text": text,
            "role": role,
        })
        used_keys.add(key)
        total += chosen_duration
        return True

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
        selected_sources = {z.get("source_video_id") for z in sequence[-2:]}
        options.sort(key=lambda x: (
            _score(x) + (0.035 if visual_rhythm and x.get("source_video_id") not in selected_sources else 0),
            float(x.get("semantic_score", 0) or 0)
        ), reverse=True)
        if not any(append_candidate(item) for item in options):
            break

    # max_clips=1 is an explicit request for a single clip, not a requirement
    # that one clip fill the entire requested runtime.
    minimum_clips = min(2, max_clips)
    passed = bool(sequence) and len(sequence) >= minimum_clips and (
        total >= target_duration * 0.90 or max_clips == 1
    )
    return {
        "version": VERSION,
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
            "minimum_duration_ratio": 0.90,
            "minimum_clips": minimum_clips,
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
        raise SystemExit("Usage: python sequence_builder.py profile candidates target output")
    with open(sys.argv[1], encoding="utf-8") as f:
        profile = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        candidates = json.load(f)
    result = build_sequence(profile, candidates, int(sys.argv[3]))
    save_sequence(result, sys.argv[4])
    print(json.dumps({
        "success": result["success"], "version": result["version"],
        "clips": result["clip_count"], "duration": result["estimated_duration"],
    }, indent=2))
