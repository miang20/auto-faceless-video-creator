from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


# =========================================================
# CONFIG
# =========================================================

DEFAULT_MAX_POINTS = 8
DEFAULT_MAX_SOURCES = 10
DEFAULT_HOOK_COUNT = 5


# =========================================================
# TEXT HELPERS
# =========================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.lower().strip()
    text = re.sub(r"[^\w\s!?.,'-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        str(text),
    )

    return text.strip()


def extract_sentences(text: str) -> list[str]:
    text = clean_text(text)

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def extract_keywords(
    text: str,
    max_keywords: int = 20,
) -> list[str]:
    """
    Extract useful topic keywords.
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

    words = re.findall(
        r"\b[a-z0-9][a-z0-9'-]*\b",
        normalized,
    )

    result = []
    seen = set()

    for word in words:

        if len(word) < 3:
            continue

        if word in stop_words:
            continue

        if word in seen:
            continue

        seen.add(word)
        result.append(word)

        if len(result) >= max_keywords:
            break

    return result


# =========================================================
# SOURCE EXTRACTION
# =========================================================

def get_source_title(
    source: dict,
) -> str:
    return clean_text(
        source.get(
            "title",
            "",
        )
    )


def get_source_description(
    source: dict,
) -> str:
    return clean_text(
        source.get(
            "description",
            "",
        )
    )


def get_source_url(
    source: dict,
) -> str:
    return clean_text(
        source.get(
            "url",
            "",
        )
    )


def get_source_score(
    source: dict,
) -> float:
    for key in (
        "final_score",
        "quality_score",
        "relevance_score",
    ):

        value = source.get(
            key
        )

        try:

            if value is not None:
                return float(value)

        except (
            ValueError,
            TypeError,
        ):

            continue

    return 0.0


def rank_script_sources(
    sources: list[dict],
    max_sources: int = DEFAULT_MAX_SOURCES,
) -> list[dict]:
    """
    Select the strongest available research sources.
    """

    if not sources:
        return []

    unique = []
    seen_ids = set()
    seen_urls = set()

    for source in sources:

        video_id = source.get(
            "video_id"
        )

        url = get_source_url(
            source
        )

        if video_id and video_id in seen_ids:
            continue

        if url and url in seen_urls:
            continue

        if video_id:
            seen_ids.add(
                video_id
            )

        if url:
            seen_urls.add(
                url
            )

        unique.append(
            dict(source)
        )

    unique.sort(
        key=get_source_score,
        reverse=True,
    )

    return unique[
        :max_sources
    ]


# =========================================================
# FACT / POINT EXTRACTION
# =========================================================

def build_source_points(
    sources: list[dict],
    max_points: int = DEFAULT_MAX_POINTS,
) -> list[dict]:
    """
    Convert research sources into concise usable points.

    This is deliberately deterministic and does not invent
    facts that are not present in the supplied research.
    """

    points = []

    ranked_sources = rank_script_sources(
        sources
    )

    for source in ranked_sources:

        title = get_source_title(
            source
        )

        description = get_source_description(
            source
        )

        url = get_source_url(
            source
        )

        video_id = source.get(
            "video_id",
            "",
        )

        text = clean_text(
            f"{title}. {description}"
        )

        sentences = extract_sentences(
            text
        )

        if not sentences:
            continue

        # Prefer the title as the primary point.
        primary_text = title

        if not primary_text:
            primary_text = sentences[0]

        points.append(
            {
                "point_id": len(points) + 1,
                "text": primary_text,
                "context": sentences[:3],
                "source_url": url,
                "video_id": video_id,
                "source_title": title,
                "source_score": get_source_score(
                    source
                ),
            }
        )

        if len(points) >= max_points:
            break

    return points


# =========================================================
# HOOK GENERATION
# =========================================================

def generate_hooks(
    topic: str,
    points: list[dict],
    count: int = DEFAULT_HOOK_COUNT,
) -> list[str]:
    """
    Generate short, high-retention hook candidates.

    Hooks are templates rather than fabricated factual claims.
    """

    topic = clean_text(
        topic
    )

    first_point = ""

    if points:

        first_point = clean_text(
            points[0].get(
                "text",
                "",
            )
        )

    hooks = [
        f"This is one of the craziest things to happen with {topic}.",
        f"You won't expect what happened in {topic}.",
        f"Something went seriously wrong in {topic}.",
        f"This {topic} moment got completely out of control.",
        f"Wait until you see what happened next.",
    ]

    if first_point:

        hooks.append(
            f"At first, it looked normal — then {first_point.lower()}"
        )

    # Remove duplicates while preserving order.
    unique = []
    seen = set()

    for hook in hooks:

        hook = clean_text(
            hook
        )

        key = hook.lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(hook)

    return unique[
        :count
    ]


# =========================================================
# SCRIPT STRUCTURE
# =========================================================

def build_script_sections(
    topic: str,
    points: list[dict],
) -> list[dict]:
    """
    Build a structured short-form script.

    The output is designed to work even when narration is
    disabled: each section contains visual/editing guidance.
    """

    sections = []

    sections.append(
        {
            "section": "hook",
            "order": 1,
            "duration_target": "0-5s",
            "narration": (
                f"You won't believe what happened "
                f"with {topic}."
            ),
            "on_screen_text": (
                f"{topic.upper()} GOT WILD"
            ),
            "visual_instruction": (
                "Start immediately with the strongest "
                "available visual moment."
            ),
        }
    )

    for index, point in enumerate(
        points,
        start=1,
    ):

        point_text = clean_text(
            point.get(
                "text",
                "",
            )
        )

        source_title = clean_text(
            point.get(
                "source_title",
                "",
            )
        )

        sections.append(
            {
                "section": "main",
                "order": index + 1,
                "point_number": index,
                "duration_target": "5-12s",
                "narration": point_text,
                "on_screen_text": point_text,
                "visual_instruction": (
                    "Use the strongest matching footage "
                    "from the source."
                ),
                "source_title": source_title,
                "source_url": point.get(
                    "source_url",
                    "",
                ),
                "video_id": point.get(
                    "video_id",
                    "",
                ),
            }
        )

    sections.append(
        {
            "section": "ending",
            "order": len(sections) + 1,
            "duration_target": "2-4s",
            "narration": (
                "Which moment was the craziest?"
            ),
            "on_screen_text": (
                "WHICH ONE WAS CRAZIEST?"
            ),
            "visual_instruction": (
                "End on the strongest reaction or "
                "final payoff frame."
            ),
        }
    )

    return sections


# =========================================================
# FULL SCRIPT GENERATOR
# =========================================================

def generate_script(
    topic: str,
    research: Optional[dict] = None,
    reference_url: Optional[str] = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> dict:
    """
    Generate a complete structured video script from research.

    Input:
        topic
        research result from research.py/source_analyzer.py

    Output:
        hooks
        selected sources
        content points
        script sections
        keywords
    """

    topic = clean_text(
        topic
    )

    if not topic:

        raise ValueError(
            "Script topic cannot be empty."
        )

    research = research or {}

    sources = research.get(
        "sources",
        [],
    )

    if not isinstance(
        sources,
        list,
    ):

        sources = []

    selected_sources = rank_script_sources(
        sources=sources,
    )

    points = build_source_points(
        sources=selected_sources,
        max_points=max_points,
    )

    hooks = generate_hooks(
        topic=topic,
        points=points,
    )

    sections = build_script_sections(
        topic=topic,
        points=points,
    )

    return {
        "version": "1.0",
        "topic": topic,
        "reference_url": reference_url,
        "keywords": extract_keywords(
            topic
        ),
        "source_count": len(
            selected_sources
        ),
        "selected_sources": selected_sources,
        "point_count": len(
            points
        ),
        "points": points,
        "hooks": hooks,
        "recommended_hook": (
            hooks[0]
            if hooks
            else ""
        ),
        "sections": sections,
    }


# =========================================================
# NARRATION-FREE EDITING PLAN
# =========================================================

def build_visual_editing_plan(
    script: dict,
) -> list[dict]:
    """
    Convert the script into a narration-independent
    visual editing plan.

    This is important for the raw-footage workflow.
    """

    sections = script.get(
        "sections",
        [],
    )

    plan = []

    for section in sections:

        section_type = section.get(
            "section",
            "main",
        )

        if section_type == "hook":

            instruction = (
                "Open with the strongest visual. "
                "No intro animation. No delay."
            )

        elif section_type == "ending":

            instruction = (
                "Use the payoff/reaction and finish "
                "quickly before viewer drop-off."
            )

        else:

            instruction = (
                "Cut directly to the relevant action. "
                "Remove dead time and weak frames."
            )

        plan.append(
            {
                "order": section.get(
                    "order",
                    len(plan) + 1,
                ),
                "section": section_type,
                "visual_instruction": instruction,
                "on_screen_text": section.get(
                    "on_screen_text",
                    "",
                ),
                "source_url": section.get(
                    "source_url",
                    "",
                ),
                "video_id": section.get(
                    "video_id",
                    "",
                ),
            }
        )

    return plan


# =========================================================
# VALIDATION
# =========================================================

def validate_script(
    script: dict,
) -> dict:
    """
    Validate generated script structure.
    """

    required_keys = [
        "topic",
        "hooks",
        "points",
        "sections",
    ]

    missing = [
        key
        for key in required_keys
        if key not in script
    ]

    errors = []

    if missing:

        errors.append(
            "Missing keys: "
            + ", ".join(missing)
        )

    topic = clean_text(
        script.get(
            "topic",
            "",
        )
    )

    if not topic:

        errors.append(
            "Script topic is empty."
        )

    hooks = script.get(
        "hooks",
        [],
    )

    if not hooks:

        errors.append(
            "No hooks were generated."
        )

    sections = script.get(
        "sections",
        [],
    )

    if not sections:

        errors.append(
            "No script sections were generated."
        )

    return {
        "valid": not errors,
        "errors": errors,
    }


# =========================================================
# SAVE
# =========================================================

def save_script(
    script: dict,
    output_path: str | Path,
) -> str:
    """
    Save generated script as JSON.
    """

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            script,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(output)


# =========================================================
# HUMAN-READABLE SCRIPT
# =========================================================

def render_script_text(
    script: dict,
) -> str:
    """
    Render the structured script into readable text.
    """

    topic = script.get(
        "topic",
        "",
    )

    lines = [
        f"TOPIC: {topic}",
        "",
        "HOOK:",
        script.get(
            "recommended_hook",
            "",
        ),
        "",
        "SCRIPT:",
    ]

    for section in script.get(
        "sections",
        [],
    ):

        section_name = str(
            section.get(
                "section",
                "main",
            )
        ).upper()

        lines.append(
            f"\n[{section_name}]"
        )

        narration = clean_text(
            section.get(
                "narration",
                "",
            )
        )

        text = clean_text(
            section.get(
                "on_screen_text",
                "",
            )
        )

        visual = clean_text(
            section.get(
                "visual_instruction",
                "",
            )
        )

        if narration:

            lines.append(
                f"Narration: {narration}"
            )

        if text:

            lines.append(
                f"Text: {text}"
            )

        if visual:

            lines.append(
                f"Visual: {visual}"
            )

    return "\n".join(
        lines
    )
