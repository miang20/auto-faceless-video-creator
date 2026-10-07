from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable


YOUTUBE_SEARCH_URL = (
    "https://www.youtube.com/results?search_query={query}"
)


DISCOVERY_TERMS = (
    "viral",
    "reaction",
    "moment",
    "incident",
    "caught",
    "highlights",
    "breaking",
    "aftermath",
    "alternate angle",
    "interview",
    "behind the scenes",
    "explained",
)


def _clean_text(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _normalize_query(value: str) -> str:
    value = _clean_text(value)

    value = re.sub(
        r"[^\w\s\-]",
        " ",
        value,
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _tokenize(value: str) -> set[str]:
    words = re.findall(
        r"[a-zA-Z0-9']+",
        value.lower(),
    )

    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "what",
        "when",
        "where",
        "your",
        "have",
        "has",
        "was",
        "were",
        "are",
        "you",
        "how",
        "why",
        "who",
    }

    return {
        word
        for word in words
        if len(word) > 2
        and word not in stop_words
    }


def _build_search_queries(
    topic: str,
    reference_url: str | None = None,
) -> list[str]:
    """
    Build diverse discovery queries around the reference topic.

    The goal is NOT to repeatedly search the exact same phrase.
    We want different footage angles and contextual sources.
    """

    topic = _normalize_query(topic)

    if not topic:
        return []

    queries = [
        topic,
        f"{topic} latest",
        f"{topic} viral moment",
        f"{topic} reaction",
        f"{topic} incident",
        f"{topic} highlights",
        f"{topic} caught on camera",
        f"{topic} aftermath",
        f"{topic} alternate angle",
        f"{topic} interview",
    ]

    # A reference URL is useful as a signal that this is a
    # reference-driven workflow, but we intentionally do not
    # search the URL itself.
    if reference_url:
        queries.extend([
            f"{topic} context",
            f"{topic} full moment",
            f"{topic} before after",
        ])

    seen = set()
    result = []

    for query in queries:
        normalized = _normalize_query(query)

        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def search_youtube(
    query: str,
    limit: int = 10,
) -> list[dict]:
    """
    Search public YouTube results without requiring an API key.
    """

    query = _normalize_query(query)

    if not query:
        return []

    encoded_query = urllib.parse.quote_plus(query)

    url = YOUTUBE_SEARCH_URL.format(
        query=encoded_query,
    )

    request = urllib.request.Request(
        url,
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
    except Exception:
        return []

    match = re.search(
        r"ytInitialData\s*=\s*(\{.*?\});",
        html,
        flags=re.DOTALL,
    )

    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    results: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            renderer = node.get(
                "videoRenderer"
            )

            if isinstance(renderer, dict):
                video_id = renderer.get(
                    "videoId"
                )

                if video_id:
                    title = ""

                    title_data = renderer.get(
                        "title",
                        {},
                    )

                    if isinstance(title_data, dict):
                        runs = title_data.get(
                            "runs",
                            [],
                        )

                        if runs:
                            title = "".join(
                                str(
                                    run.get(
                                        "text",
                                        "",
                                    )
                                )
                                for run in runs
                            )

                        if not title:
                            title = str(
                                title_data.get(
                                    "simpleText",
                                    "",
                                )
                            )

                    channel = ""

                    owner = renderer.get(
                        "ownerText",
                        {},
                    )

                    if isinstance(owner, dict):
                        runs = owner.get(
                            "runs",
                            [],
                        )

                        if runs:
                            channel = "".join(
                                str(
                                    run.get(
                                        "text",
                                        "",
                                    )
                                )
                                for run in runs
                            )

                    length = ""

                    length_text = renderer.get(
                        "lengthText",
                        {},
                    )

                    if isinstance(
                        length_text,
                        dict,
                    ):
                        length = str(
                            length_text.get(
                                "simpleText",
                                "",
                            )
                        )

                    view_text = ""

                    view_data = renderer.get(
                        "viewCountText",
                        {},
                    )

                    if isinstance(
                        view_data,
                        dict,
                    ):
                        view_text = str(
                            view_data.get(
                                "simpleText",
                                "",
                            )
                        )

                    results.append({
                        "video_id": video_id,
                        "title": _clean_text(title),
                        "channel": _clean_text(channel),
                        "duration": length,
                        "views_text": _clean_text(
                            view_text
                        ),
                        "url": (
                            "https://www.youtube.com/watch?v="
                            + video_id
                        ),
                        "search_query": query,
                    })

            for value in node.values():
                walk(value)

        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)

    unique = []
    seen_ids = set()

    for item in results:
        video_id = item.get("video_id")

        if not video_id:
            continue

        if video_id in seen_ids:
            continue

        seen_ids.add(video_id)
        unique.append(item)

        if len(unique) >= limit:
            break

    return unique


def _parse_view_count(value: str) -> int:
    """
    Convert common YouTube view strings into an approximate
    integer score.
    """

    text = str(value or "").lower()
    text = text.replace(
        "views",
        "",
    ).strip()

    match = re.search(
        r"([\d,.]+)\s*([km]?)",
        text,
    )

    if not match:
        return 0

    number_text = match.group(1)
    suffix = match.group(2)

    try:
        number = float(
            number_text.replace(
                ",",
                "",
            )
        )
    except ValueError:
        return 0

    if suffix == "m":
        number *= 1_000_000
    elif suffix == "k":
        number *= 1_000

    return int(number)


def score_source(
    title: str,
    topic: str,
    views_text: str = "",
    channel: str = "",
) -> float:
    """
    Score a discovered source for relevance and usefulness.

    This is a discovery score, not a guarantee of footage quality.
    """

    title = _clean_text(title).lower()
    topic = _clean_text(topic).lower()

    topic_words = _tokenize(topic)
    title_words = _tokenize(title)

    if not topic_words:
        return 0.0

    overlap = len(
        topic_words.intersection(
            title_words
        )
    )

    relevance = (
        overlap / max(len(topic_words), 1)
    )

    score = relevance * 60.0

    for keyword in DISCOVERY_TERMS:
        if keyword in title:
            score += 4.0

    views = _parse_view_count(
        views_text
    )

    if views >= 1_000_000:
        score += 15.0
    elif views >= 100_000:
        score += 10.0
    elif views >= 10_000:
        score += 5.0

    if channel:
        score += 1.0

    return round(
        min(score, 100.0),
        2,
    )


def _source_key(source: dict) -> str:
    video_id = source.get(
        "video_id"
    )

    if video_id:
        return str(video_id)

    url = source.get(
        "url",
        "",
    )

    return str(url).strip().lower()


def _deduplicate_sources(
    sources: Iterable[dict],
) -> list[dict]:
    seen = set()
    result = []

    for source in sources:
        key = _source_key(source)

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(source)

    return result


def rank_sources(
    sources: list[dict],
    topic: str,
) -> list[dict]:
    """
    Rank sources by relevance + discovery value.
    """

    ranked = []

    for source in sources:
        item = dict(source)

        item["score"] = score_source(
            title=item.get(
                "title",
                "",
            ),
            topic=topic,
            views_text=item.get(
                "views_text",
                "",
            ),
            channel=item.get(
                "channel",
                "",
            ),
        )

        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            float(
                item.get(
                    "score",
                    0,
                )
            ),
            _parse_view_count(
                item.get(
                    "views_text",
                    "",
                )
            ),
        ),
        reverse=True,
    )

    return ranked


def select_diverse_sources(
    sources: list[dict],
    limit: int = 10,
) -> list[dict]:
    """
    Prefer different channels and different discovery queries
    so the result is not dominated by duplicates.
    """

    selected = []
    used_channels = set()
    used_queries = set()

    # First pass: maximize diversity.
    for source in sources:
        if len(selected) >= limit:
            break

        channel = _clean_text(
            source.get(
                "channel",
                "",
            )
        ).lower()

        query = _clean_text(
            source.get(
                "search_query",
                "",
            )
        ).lower()

        if (
            channel
            and channel in used_channels
        ):
            continue

        if (
            query
            and query in used_queries
        ):
            continue

        selected.append(source)

        if channel:
            used_channels.add(channel)

        if query:
            used_queries.add(query)

    # Second pass: fill remaining slots.
    if len(selected) < limit:
        selected_ids = {
            _source_key(source)
            for source in selected
        }

        for source in sources:
            if len(selected) >= limit:
                break

            key = _source_key(source)

            if key in selected_ids:
                continue

            selected.append(source)
            selected_ids.add(key)

    return selected


def research_topic(
    topic: str,
    reference_url: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Research a topic using multiple YouTube search angles.

    Returns a ranked, deduplicated and diversity-aware source list.
    """

    topic = _clean_text(topic)

    if not topic:
        return []

    limit = max(
        1,
        int(limit),
    )

    queries = _build_search_queries(
        topic=topic,
        reference_url=reference_url,
    )

    all_sources = []

    # Search a few results per query. This keeps the research
    # lightweight while still producing multiple source angles.
    per_query = max(
        3,
        min(
            8,
            limit,
        ),
    )

    for query in queries:
        results = search_youtube(
            query=query,
            limit=per_query,
        )

        all_sources.extend(results)

    unique_sources = _deduplicate_sources(
        all_sources
    )

    ranked = rank_sources(
        unique_sources,
        topic=topic,
    )

    selected = select_diverse_sources(
        ranked,
        limit=limit,
    )

    # Final ordering is by research score.
    selected.sort(
        key=lambda item: float(
            item.get(
                "score",
                0,
            )
        ),
        reverse=True,
    )

    return selected


def save_research(
    research: list[dict],
    output_path: str | Path,
) -> str:
    """
    Save research results as JSON.
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
            research,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(output_path)
