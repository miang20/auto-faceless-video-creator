from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Iterable


def clean_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def extract_keywords(text: str) -> list[str]:
    words = re.findall(
        r"[a-zA-Z0-9']+",
        str(text or "").lower(),
    )

    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "have",
        "has",
        "was",
        "were",
        "are",
        "you",
        "your",
        "they",
        "their",
        "into",
        "about",
        "what",
        "when",
        "where",
        "which",
        "will",
        "just",
        "than",
        "then",
        "them",
        "there",
        "here",
    }

    result = []

    for word in words:
        if len(word) < 3:
            continue

        if word in stop_words:
            continue

        if word not in result:
            result.append(word)

    return result


def _parse_count(value: str) -> int:
    text = clean_text(value).lower()

    match = re.search(
        r"([\d,.]+)\s*([km]?)",
        text,
    )

    if not match:
        return 0

    try:
        number = float(
            match.group(1).replace(
                ",",
                "",
            )
        )
    except ValueError:
        return 0

    suffix = match.group(2)

    if suffix == "m":
        number *= 1_000_000
    elif suffix == "k":
        number *= 1_000

    return int(number)


def _parse_duration_seconds(
    value: str,
) -> int:
    text = clean_text(value)

    if not text:
        return 0

    parts = text.split(":")

    try:
        numbers = [
            int(part)
            for part in parts
        ]
    except ValueError:
        return 0

    if len(numbers) == 2:
        return (
            numbers[0] * 60
            + numbers[1]
        )

    if len(numbers) == 3:
        return (
            numbers[0] * 3600
            + numbers[1] * 60
            + numbers[2]
        )

    return 0


def get_youtube_metadata(
    video_url: str,
) -> dict:
    """
    Fetch lightweight public YouTube metadata.

    No YouTube API key is required.
    """

    result = {
        "url": video_url,
        "title": "",
        "description": "",
        "channel": "",
        "view_count": 0,
        "length_seconds": 0,
    }

    if not video_url:
        return result

    request = urllib.request.Request(
        video_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:
            html = response.read().decode(
                "utf-8",
                errors="replace",
            )
    except Exception as exc:
        result["metadata_error"] = str(exc)
        return result

    def find_json_value(
        patterns: Iterable[str],
    ) -> str:
        for pattern in patterns:
            match = re.search(
                pattern,
                html,
                flags=re.DOTALL,
            )

            if match:
                return clean_text(
                    match.group(1)
                )

        return ""

    result["title"] = find_json_value([
        r'"title":"([^"]+)"',
        r'<title>(.*?)</title>',
    ])

    result["description"] = find_json_value([
        r'"shortDescription":"(.*?)"',
    ])

    result["channel"] = find_json_value([
        r'"ownerChannelName":"([^"]+)"',
        r'"author":"([^"]+)"',
    ])

    view_count_text = find_json_value([
        r'"viewCount":"(\d+)"',
    ])

    result["view_count"] = _parse_count(
        view_count_text
    )

    length_text = find_json_value([
        r'"lengthSeconds":"(\d+)"',
    ])

    if length_text.isdigit():
        result["length_seconds"] = int(
            length_text
        )

    return result


def _topic_relevance(
    title: str,
    description: str,
    topic: str,
) -> float:
    topic_words = set(
        extract_keywords(topic)
    )

    if not topic_words:
        return 0.0

    source_words = set(
        extract_keywords(
            f"{title} {description}"
        )
    )

    overlap = topic_words.intersection(
        source_words
    )

    return min(
        100.0,
        (
            len(overlap)
            / max(
                len(topic_words),
                1,
            )
        )
        * 100.0,
    )


def _visual_value(
    title: str,
    description: str,
) -> float:
    """
    Estimate whether a source is likely to contain
    useful visual footage.
    """

    text = (
        f"{title} {description}"
    ).lower()

    strong_visual_terms = [
        "caught on camera",
        "live",
        "reaction",
        "fight",
        "collision",
        "crash",
        "celebration",
        "ejection",
        "goal",
        "knockout",
        "save",
        "fails",
        "failure",
        "incident",
        "moment",
        "viral",
        "highlights",
        "breaking",
        "crowd",
        "interview",
        "behind the scenes",
        "alternate angle",
        "full moment",
        "aftermath",
    ]

    matches = sum(
        1
        for term in strong_visual_terms
        if term in text
    )

    return min(
        100.0,
        matches * 12.0,
    )


def _context_value(
    title: str,
    description: str,
) -> float:
    text = (
        f"{title} {description}"
    ).lower()

    context_terms = [
        "why",
        "explained",
        "what happened",
        "before",
        "after",
        "aftermath",
        "reaction",
        "interview",
        "full",
        "details",
        "behind",
        "context",
    ]

    matches = sum(
        1
        for term in context_terms
        if term in text
    )

    return min(
        100.0,
        matches * 12.5,
    )


def _freshness_signal(
    title: str,
    description: str,
) -> float:
    text = (
        f"{title} {description}"
    ).lower()

    fresh_terms = [
        "today",
        "tonight",
        "latest",
        "breaking",
        "new",
        "just happened",
        "2026",
        "2025",
    ]

    matches = sum(
        1
        for term in fresh_terms
        if term in text
    )

    return min(
        100.0,
        matches * 15.0,
    )


def score_source_quality(
    source: dict,
    topic: str,
) -> float:
    """
    Calculate a broader source-quality score.

    Signals:
    - topic relevance
    - visual usefulness
    - contextual usefulness
    - freshness
    - engagement
    - reasonable duration
    """

    title = clean_text(
        source.get(
            "title",
            "",
        )
    )

    description = clean_text(
        source.get(
            "description",
            "",
        )
    )

    relevance = _topic_relevance(
        title=title,
        description=description,
        topic=topic,
    )

    visual = _visual_value(
        title=title,
        description=description,
    )

    context = _context_value(
        title=title,
        description=description,
    )

    freshness = _freshness_signal(
        title=title,
        description=description,
    )

    view_count = source.get(
        "view_count",
        0,
    )

    if isinstance(
        view_count,
        str,
    ):
        view_count = _parse_count(
            view_count
        )

    view_count = int(
        view_count or 0
    )

    if view_count >= 10_000_000:
        engagement = 100.0
    elif view_count >= 1_000_000:
        engagement = 85.0
    elif view_count >= 100_000:
        engagement = 65.0
    elif view_count >= 10_000:
        engagement = 40.0
    else:
        engagement = 20.0

    duration = source.get(
        "length_seconds",
        0,
    )

    if isinstance(
        duration,
        str,
    ):
        duration = _parse_duration_seconds(
            duration
        )

    duration = int(
        duration or 0
    )

    # Extremely short sources may have limited context.
    # Extremely long sources can still be valuable, so this
    # signal stays intentionally moderate.
    if 20 <= duration <= 900:
        duration_value = 100.0
    elif duration > 0:
        duration_value = 60.0
    else:
        duration_value = 40.0

    score = (
        relevance * 0.35
        + visual * 0.20
        + context * 0.15
        + freshness * 0.10
        + engagement * 0.10
        + duration_value * 0.10
    )

    return round(
        min(
            100.0,
            max(
                0.0,
                score,
            ),
        ),
        2,
    )


def _source_identity(
    source: dict,
) -> str:
    video_id = source.get(
        "video_id"
    )

    if video_id:
        return str(video_id)

    url = source.get(
        "url",
        "",
    )

    return clean_text(url).lower()


def _deduplicate_sources(
    sources: list[dict],
) -> list[dict]:
    result = []
    seen = set()

    for source in sources:
        identity = _source_identity(
            source
        )

        if not identity:
            continue

        if identity in seen:
            continue

        seen.add(identity)
        result.append(source)

    return result


def _build_diversity_score(
    source: dict,
    selected: list[dict],
) -> float:
    """
    Reward sources from different channels and with different
    discovery queries.
    """

    channel = clean_text(
        source.get(
            "channel",
            "",
        )
    ).lower()

    query = clean_text(
        source.get(
            "search_query",
            "",
        )
    ).lower()

    selected_channels = {
        clean_text(
            item.get(
                "channel",
                "",
            )
        ).lower()
        for item in selected
    }

    selected_queries = {
        clean_text(
            item.get(
                "search_query",
                "",
            )
        ).lower()
        for item in selected
    }

    score = 0.0

    if channel and channel not in selected_channels:
        score += 60.0

    if query and query not in selected_queries:
        score += 40.0

    return score


def analyze_sources(
    sources: list[dict],
    topic: str,
    enrich_metadata: bool = True,
) -> list[dict]:
    """
    Analyze, score and rank discovered sources.
    """

    sources = _deduplicate_sources(
        sources
    )

    analyzed = []

    for source in sources:
        item = dict(source)

        url = item.get(
            "url",
            "",
        )

        if (
            enrich_metadata
            and url
        ):
            metadata = get_youtube_metadata(
                url
            )

            for key, value in metadata.items():
                if (
                    key not in item
                    or not item.get(key)
                ):
                    item[key] = value

        item["keywords"] = extract_keywords(
            f"{item.get('title', '')} "
            f"{item.get('description', '')}"
        )

        item["topic_relevance"] = round(
            _topic_relevance(
                title=item.get(
                    "title",
                    "",
                ),
                description=item.get(
                    "description",
                    "",
                ),
                topic=topic,
            ),
            2,
        )

        item["visual_value"] = round(
            _visual_value(
                title=item.get(
                    "title",
                    "",
                ),
                description=item.get(
                    "description",
                    "",
                ),
            ),
            2,
        )

        item["context_value"] = round(
            _context_value(
                title=item.get(
                    "title",
                    "",
                ),
                description=item.get(
                    "description",
                    "",
                ),
            ),
            2,
        )

        item["freshness_signal"] = round(
            _freshness_signal(
                title=item.get(
                    "title",
                    "",
                ),
                description=item.get(
                    "description",
                    "",
                ),
            ),
            2,
        )

        item["quality_score"] = (
            score_source_quality(
                source=item,
                topic=topic,
            )
        )

        analyzed.append(item)

    analyzed.sort(
        key=lambda item: item.get(
            "quality_score",
            0,
        ),
        reverse=True,
    )

    # Apply a diversity bonus without allowing weak sources
    # to overtake clearly superior sources.
    selected = []

    for item in analyzed:
        diversity = _build_diversity_score(
            source=item,
            selected=selected,
        )

        item["diversity_signal"] = diversity

        adjusted = (
            item.get(
                "quality_score",
                0,
            )
            + diversity * 0.10
        )

        item["final_score"] = round(
            min(
                100.0,
                adjusted,
            ),
            2,
        )

        selected.append(item)

    selected.sort(
        key=lambda item: item.get(
            "final_score",
            0,
        ),
        reverse=True,
    )

    return selected


def build_analysis_report(
    topic: str,
    sources: list[dict],
    reference_url: str | None = None,
) -> dict:
    """
    Build a complete source-analysis report.
    """

    analyzed_sources = analyze_sources(
        sources=sources,
        topic=topic,
        enrich_metadata=True,
    )

    report = {
        "success": True,
        "topic": topic,
        "reference_url": reference_url,
        "source_count": len(
            analyzed_sources
        ),
        "sources": analyzed_sources,
        "summary": {
            "top_source": (
                analyzed_sources[0]
                if analyzed_sources
                else None
            ),
            "average_quality": round(
                (
                    sum(
                        item.get(
                            "quality_score",
                            0,
                        )
                        for item in analyzed_sources
                    )
                    / max(
                        len(
                            analyzed_sources
                        ),
                        1,
                    )
                ),
                2,
            ),
        },
    }

    return report


def save_analysis(
    report: dict,
    output_path: str | Path,
) -> str:
    """
    Save source analysis report as JSON.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(output_path)
