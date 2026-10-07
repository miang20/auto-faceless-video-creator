"""
Pro V2 Script Generator

Builds a structured, no-narration short-form story from analyzed clips.

The generator does NOT create voiceover narration.
It creates an editing blueprint:
HOOK -> SETUP -> ESCALATION -> REACTION -> PAYOFF -> ENDING

The actual source audio/dialogue remains the primary storytelling layer.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_TARGET_DURATION = 15.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    return max(minimum, min(maximum, value))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _clip_role(clip: Dict[str, Any]) -> str:
    return str(
        clip.get("story_role")
        or clip.get("role")
        or "SETUP"
    ).upper()


def _clip_score(clip: Dict[str, Any]) -> float:
    return _safe_float(
        clip.get(
            "score",
            clip.get("final_score", 0.0),
        )
    )


def _clip_text(clip: Dict[str, Any]) -> str:
    return _clean_text(
        clip.get("text")
        or clip.get("transcript")
        or clip.get("caption")
        or ""
    )


def _clip_start(clip: Dict[str, Any]) -> float:
    return _safe_float(
        clip.get(
            "start",
            clip.get("start_time", 0.0),
        )
    )


def _clip_end(clip: Dict[str, Any]) -> float:
    return _safe_float(
        clip.get(
            "end",
            clip.get("end_time", 0.0),
        )
    )


def _clip_duration(clip: Dict[str, Any]) -> float:
    duration = _safe_float(
        clip.get("duration")
    )

    if duration > 0:
        return duration

    return max(
        0.0,
        _clip_end(clip) - _clip_start(clip),
    )


def _hook_score(clip: Dict[str, Any]) -> float:
    return _safe_float(
        clip.get(
            "hook_score",
            clip.get("score", 0.0),
        )
    )


def _find_best(
    clips: Sequence[Dict[str, Any]],
    roles: Sequence[str],
) -> Optional[Dict[str, Any]]:

    matching = [
        clip
        for clip in clips
        if _clip_role(clip) in roles
    ]

    if not matching:
        return None

    return max(
        matching,
        key=lambda clip: (
            _clip_score(clip),
            _hook_score(clip),
        ),
    )


def _find_best_hook(
    clips: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:

    if not clips:
        return None

    return max(
        clips,
        key=lambda clip: (
            _hook_score(clip),
            _clip_score(clip),
        ),
    )


def _dedupe_clips(
    clips: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    result: List[Dict[str, Any]] = []
    seen = set()

    for clip in clips:

        start = round(
            _clip_start(clip),
            2,
        )

        end = round(
            _clip_end(clip),
            2,
        )

        key = (
            start,
            end,
            _clip_text(clip)[:80],
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(clip)

    return result


def _sort_chronological(
    clips: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    return sorted(
        clips,
        key=lambda clip: _clip_start(clip),
    )


def _estimate_word_count(text: str) -> int:
    return len(
        re.findall(
            r"\b[\w']+\b",
            text,
        )
    )


def _build_context_summary(
    clips: Sequence[Dict[str, Any]],
) -> str:

    texts = [
        _clip_text(clip)
        for clip in clips
        if _clip_text(clip)
    ]

    if not texts:
        return ""

    return " ".join(texts)[:1000]


def _choose_story_clips(
    clips: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not clips:
        return []

    clips = _dedupe_clips(clips)

    hook = _find_best_hook(clips)

    setup = _find_best(
        clips,
        ["SETUP"],
    )

    escalation = _find_best(
        clips,
        ["ESCALATION"],
    )

    reaction = _find_best(
        clips,
        ["REACTION"],
    )

    payoff = _find_best(
        clips,
        ["PAYOFF"],
    )

    ending = _find_best(
        clips,
        ["ENDING"],
    )

    chosen: List[Dict[str, Any]] = []

    for clip in (
        hook,
        setup,
        escalation,
        reaction,
        payoff,
        ending,
    ):
        if clip is None:
            continue

        if clip not in chosen:
            chosen.append(clip)

    # If story-role classification did not give enough structure, fill from
    # strongest remaining candidates.
    remaining = sorted(
        clips,
        key=lambda clip: _clip_score(clip),
        reverse=True,
    )

    for clip in remaining:
        if clip in chosen:
            continue

        chosen.append(clip)

        if len(chosen) >= 8:
            break

    return _sort_chronological(chosen)


def _assign_roles(
    clips: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not clips:
        return []

    ordered = _sort_chronological(clips)

    roles = [
        "HOOK",
        "SETUP",
        "ESCALATION",
        "REACTION",
        "PAYOFF",
        "ENDING",
    ]

    output = []

    for index, clip in enumerate(ordered):

        role = _clip_role(clip)

        if role not in roles:
            if index == 0:
                role = "HOOK"
            elif index == len(ordered) - 1:
                role = "PAYOFF"
            else:
                role = "ESCALATION"

        item = dict(clip)
        item["story_role"] = role
        item["sequence"] = index + 1

        output.append(item)

    return output


def _duration_budget(
    target_duration: float,
    story_length: int,
) -> List[float]:

    target_duration = max(
        5.0,
        min(
            180.0,
            _safe_float(
                target_duration,
                DEFAULT_TARGET_DURATION,
            ),
        ),
    )

    if story_length <= 1:
        return [target_duration]

    if story_length == 2:
        ratios = [
            0.42,
            0.58,
        ]

    elif story_length == 3:
        ratios = [
            0.25,
            0.30,
            0.45,
        ]

    elif story_length == 4:
        ratios = [
            0.20,
            0.22,
            0.23,
            0.35,
        ]

    elif story_length == 5:
        ratios = [
            0.15,
            0.18,
            0.20,
            0.20,
            0.27,
        ]

    else:
        ratios = [
            0.12,
            0.14,
            0.16,
            0.16,
            0.20,
            0.22,
        ]

        ratios = ratios[:story_length]

        total = sum(ratios)

        if total > 0:
            ratios = [
                value / total
                for value in ratios
            ]

    return [
        round(
            target_duration * ratio,
            2,
        )
        for ratio in ratios
    ]


def _build_edit_instruction(
    role: str,
    clip: Dict[str, Any],
) -> str:

    text = _clip_text(clip)

    if role == "HOOK":
        return (
            "Open immediately on the strongest visual/audio moment. "
            "No intro. No logo. No dead air. "
            "Use the most surprising frame first, then let the context catch up."
        )

    if role == "SETUP":
        return (
            "Give only the minimum context needed to understand what is happening. "
            "Keep the source audio/dialogue whenever it carries useful information."
        )

    if role == "ESCALATION":
        return (
            "Increase momentum. Remove pauses and repetitive beats while "
            "preserving the cause-and-effect sequence."
        )

    if role == "REACTION":
        return (
            "Prioritize the strongest visible or audible reaction. "
            "A reaction can be used as a quick punch-in or contextual cut."
        )

    if role == "PAYOFF":
        return (
            "Protect the full payoff. Do not cut away before the viewer sees "
            "the actual outcome."
        )

    if role == "ENDING":
        return (
            "End immediately after the strongest final beat. "
            "Avoid generic outro language or unnecessary branding."
        )

    return (
        "Keep only the useful action and remove dead space."
    )


def _build_caption_instruction(
    caption_style: str,
    caption_settings: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    settings = dict(
        caption_settings or {}
    )

    style = (
        _clean_text(
            caption_style
            or settings.get("style")
            or "Bold Viral"
        )
        or "Bold Viral"
    )

    return {
        "style": style,
        "enabled": settings.get(
            "enabled",
            True,
        ),
        "font": settings.get(
            "font",
            "Arial Bold",
        ),
        "font_size": settings.get(
            "font_size",
            54,
        ),
        "position": settings.get(
            "position",
            "center",
        ),
        "text_color": settings.get(
            "text_color",
            "#FFFFFF",
        ),
        "highlight_color": settings.get(
            "highlight_color",
            "#FFFF00",
        ),
        "stroke": settings.get(
            "stroke",
            True,
        ),
        "shadow": settings.get(
            "shadow",
            True,
        ),
        "box": settings.get(
            "box",
            False,
        ),
        "words_per_line": settings.get(
            "words_per_line",
            4,
        ),
        "max_lines": settings.get(
            "max_lines",
            2,
        ),
        "keyword_emphasis": settings.get(
            "keyword_emphasis",
            True,
        ),
    }


def generate_script(
    clips: Sequence[Dict[str, Any]],
    target_duration: float = DEFAULT_TARGET_DURATION,
    topic: str = "",
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    clips = list(clips or [])

    selected = _choose_story_clips(clips)

    if not selected and clips:
        selected = [
            max(
                clips,
                key=lambda clip: _clip_score(clip),
            )
        ]

    selected = _assign_roles(selected)

    budgets = _duration_budget(
        target_duration,
        len(selected),
    )

    timeline: List[Dict[str, Any]] = []

    for index, clip in enumerate(selected):

        role = _clip_role(clip)

        item = {
            "sequence": index + 1,
            "role": role,
            "source_start": round(
                _clip_start(clip),
                3,
            ),
            "source_end": round(
                _clip_end(clip),
                3,
            ),
            "source_duration": round(
                _clip_duration(clip),
                3,
            ),
            "target_screen_duration": budgets[index]
            if index < len(budgets)
            else _clip_duration(clip),
            "score": round(
                _clip_score(clip),
                4,
            ),
            "hook_score": round(
                _hook_score(clip),
                4,
            ),
            "text": _clip_text(clip),
            "edit_instruction": _build_edit_instruction(
                role,
                clip,
            ),
        }

        timeline.append(item)

    editing = dict(
        editing_settings or {}
    )

    output = {
        "topic": _clean_text(topic),
        "target_duration": round(
            max(
                5.0,
                min(
                    180.0,
                    _safe_float(
                        target_duration,
                        DEFAULT_TARGET_DURATION,
                    ),
                ),
            ),
            2,
        ),
        "format": "9:16",
        "narration": False,
        "story_structure": [
            item["role"]
            for item in timeline
        ],
        "timeline": timeline,
        "caption": _build_caption_instruction(
            caption_style,
            caption_settings,
        ),
        "editing": {
            "remove_silence": editing.get(
                "remove_silence",
                True,
            ),
            "dynamic_zoom": editing.get(
                "dynamic_zoom",
                True,
            ),
            "punch_in": editing.get(
                "punch_in",
                True,
            ),
            "audio_normalize": editing.get(
                "audio_normalize",
                True,
            ),
            "visual_change_target": editing.get(
                "visual_change_target",
                "2-4 sec average",
            ),
            "avoid_rigid_cuts": True,
        },
        "context_summary": _build_context_summary(
            selected
        ),
        "estimated_words": _estimate_word_count(
            _build_context_summary(selected)
        ),
    }

    return output


def build_script(
    clip_analysis: Dict[str, Any],
    target_duration: float = DEFAULT_TARGET_DURATION,
    topic: str = "",
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    clips = []

    if isinstance(clip_analysis, dict):

        if isinstance(
            clip_analysis.get("clips"),
            list,
        ):
            clips = clip_analysis["clips"]

        elif isinstance(
            clip_analysis.get("analysis"),
            dict,
        ):
            clips = clip_analysis["analysis"].get(
                "clips",
                [],
            )

    return generate_script(
        clips=clips,
        target_duration=target_duration,
        topic=topic,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )


def generate_story(
    clip_analysis: Dict[str, Any],
    target_duration: float = DEFAULT_TARGET_DURATION,
    topic: str = "",
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return build_script(
        clip_analysis=clip_analysis,
        target_duration=target_duration,
        topic=topic,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )


def save_script(
    script: Dict[str, Any],
    output_path: str,
) -> str:

    directory = os.path.dirname(
        output_path
    )

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
            script,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


def build_script_report(
    clip_analysis: Dict[str, Any],
    target_duration: float = DEFAULT_TARGET_DURATION,
    topic: str = "",
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    script = build_script(
        clip_analysis=clip_analysis,
        target_duration=target_duration,
        topic=topic,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    return {
        "script": script,
        "timeline": script.get(
            "timeline",
            [],
        ),
        "story_structure": script.get(
            "story_structure",
            [],
        ),
        "target_duration": script.get(
            "target_duration",
            target_duration,
        ),
        "narration": False,
    }
