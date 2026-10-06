import json
import re
import urllib.parse
import urllib.request
import urllib.error
from typing import Optional


YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v="


# =========================================================
# TEXT HELPERS
# =========================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for comparison and scoring.
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


def extract_keywords(text: str) -> list:
    """
    Extract useful searchable words from text.
    """

    normalized = normalize_text(text)

    words = normalized.split()

    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
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
        for word in words
        if len(word) >= 3
        and word not in stop_words
    ]


# =========================================================
# YOUTUBE METADATA
# =========================================================

def get_youtube_metadata(
    video_url: str,
) -> dict:
    """
    Attempt to extract basic public YouTube metadata.

    This function is intentionally lightweight.
    Actual downloading remains handled by the existing
    frozen downloader layer.
    """

    if not video_url:
        return {}

    try:

        parsed = urllib.parse.urlparse(
            video_url
        )

        if not parsed.netloc:
            return {}

        request = urllib.request.Request(
            video_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                )
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:

            html = response.read().decode(
                "utf-8",
                errors="ignore",
            )

    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
    ):
        return {}

    metadata = {}

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    title_match = re.search(
        r'<meta\s+name="title"\s+content="([^"]*)"',
        html,
        re.IGNORECASE,
    )

    if not title_match:

        title_match = re.search(
            r'<title>(.*?)</title>',
            html,
            re.IGNORECASE | re.DOTALL,
        )

    if title_match:

        metadata["title"] = (
            title_match.group(1)
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .strip()
        )

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    description_match = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        html,
        re.IGNORECASE,
    )

    if description_match:

        metadata["description"] = (
            description_match.group(1)
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .strip()
        )

    # -----------------------------------------------------
    # CHANNEL
    # -----------------------------------------------------

    channel_match = re.search(
        r'"ownerChannelName":"(.*?)"',
        html,
    )

    if channel_match:

        metadata["channel_name"] = (
            channel_match.group(1)
            .replace("\\u0026", "&")
        )

    # -----------------------------------------------------
    # VIEW COUNT
    # -----------------------------------------------------

    view_match = re.search(
        r'"viewCount":"(\d+)"',
        html,
    )

    if view_match:

        try:
            metadata["view_count"] = int(
                view_match.group(1)
            )
        except ValueError:
            pass

    # -----------------------------------------------------
    # LENGTH
    # -----------------------------------------------------

    length_match = re.search(
        r'"lengthSeconds":"(\d+)"',
        html,
    )

    if length_match:

        try:

            metadata["duration_seconds"] = int(
                length_match.group(1)
            )

        except ValueError:
            pass

    return metadata


# =========================================================
# SOURCE QUALITY
# =========================================================

def score_source_quality(
    source: dict,
    topic: str,
) -> dict:
    """
    Score a source for relevance and potential usefulness.
    """

    title = source.get(
        "title",
        "",
    )

    description = source.get(
        "description",
        "",
    )

    combined_text = normalize_text(
        f"{title} {description}"
    )

    topic_keywords = extract_keywords(
        topic
    )

    relevance_score = 0
    quality_score = 0

    # -----------------------------------------------------
    # TOPIC RELEVANCE
    # -----------------------------------------------------

    normalized_topic = normalize_text(
        topic
    )

    normalized_title = normalize_text(
        title
    )

    if normalized_topic and (
        normalized_topic in normalized_title
    ):
        relevance_score += 40

    for keyword in topic_keywords:

        if keyword in normalized_title:
            relevance_score += 10

        elif keyword in combined_text:
            relevance_score += 3

    # -----------------------------------------------------
    # USEFUL CONTENT SIGNALS
    # -----------------------------------------------------

    strong_keywords = {
        "viral": 8,
        "crazy": 8,
        "insane": 8,
        "unbelievable": 8,
        "shocking": 8,
        "unexpected": 7,
        "caught": 7,
        "moments": 6,
        "highlights": 6,
        "compilation": 5,
        "rare": 5,
        "amazing": 5,
        "wild": 5,
        "best": 4,
        "top": 4,
    }

    for keyword, points in strong_keywords.items():

        if keyword in normalized_title:
            quality_score += points

    # -----------------------------------------------------
    # VIEW SIGNAL
    # -----------------------------------------------------

    view_count = source.get(
        "view_count",
        0,
    )

    if isinstance(view_count, int):

        if view_count >= 10_000_000:
            quality_score += 20

        elif view_count >= 1_000_000:
            quality_score += 15

        elif view_count >= 100_000:
            quality_score += 10

        elif view_count >= 10_000:
            quality_score += 5

    # -----------------------------------------------------
    # DURATION SIGNAL
    # -----------------------------------------------------

    duration = source.get(
        "duration_seconds",
        0,
    )

    if isinstance(duration, int):

        if 30 <= duration <= 1800:
            quality_score += 5

    final_score = (
        relevance_score
        + quality_score
    )

    result = dict(source)

    result["relevance_score"] = relevance_score
    result["quality_score"] = quality_score
    result["final_score"] = final_score

    return result


# =========================================================
# DUPLICATE FILTER
# =========================================================

def remove_duplicate_sources(
    sources: list,
) -> list:
    """
    Remove duplicate sources using video ID and URL.
    """

    unique = []
    seen_ids = set()
    seen_urls = set()

    for source in sources:

        video_id = source.get(
            "video_id"
        )

        url = source.get(
            "url"
        )

        if video_id and video_id in seen_ids:
            continue

        if url and url in seen_urls:
            continue

        if video_id:
            seen_ids.add(video_id)

        if url:
            seen_urls.add(url)

        unique.append(source)

    return unique


# =========================================================
# SOURCE ANALYSIS
# =========================================================

def analyze_sources(
    sources: list,
    topic: str,
    enrich_metadata: bool = True,
) -> list:
    """
    Analyze, enrich, score and rank research sources.
    """

    if not sources:
        return []

    unique_sources = remove_duplicate_sources(
        sources
    )

    analyzed = []

    for source in unique_sources:

        item = dict(source)

        video_url = item.get(
            "url",
            "",
        )

        # -------------------------------------------------
        # METADATA ENRICHMENT
        # -------------------------------------------------

        if enrich_metadata and video_url:

            metadata = get_youtube_metadata(
                video_url
            )

            for key, value in metadata.items():

                if value is not None:

                    item[key] = value

        # -------------------------------------------------
        # SCORE
        # -------------------------------------------------

        scored = score_source_quality(
            source=item,
            topic=topic,
        )

        analyzed.append(
            scored
        )

    # -----------------------------------------------------
    # FINAL RANKING
    # -----------------------------------------------------

    analyzed.sort(
        key=lambda item: (
            item.get(
                "final_score",
                0,
            ),
            item.get(
                "view_count",
                0,
            ),
        ),
        reverse=True,
    )

    # -----------------------------------------------------
    # RANK NUMBER
    # -----------------------------------------------------

    for index, item in enumerate(
        analyzed,
        start=1,
    ):

        item["rank"] = index

    return analyzed


# =========================================================
# BUILD ANALYSIS REPORT
# =========================================================

def build_analysis_report(
    topic: str,
    sources: list,
    reference_url: Optional[str] = None,
) -> dict:
    """
    Build a clean analysis-ready structure.
    """

    analyzed_sources = analyze_sources(
        sources=sources,
        topic=topic,
        enrich_metadata=True,
    )

    return {
        "topic": topic,
        "reference_url": reference_url,
        "source_count": len(
            analyzed_sources
        ),
        "sources": analyzed_sources,
    }


# =========================================================
# SAVE ANALYSIS
# =========================================================

def save_analysis(
    analysis: dict,
    output_path: str,
) -> str:
    """
    Save analysis data as JSON.
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
