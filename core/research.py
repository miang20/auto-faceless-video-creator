import json
import urllib.parse
import urllib.request
import urllib.error


YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query="


def search_youtube(query: str, limit: int = 10) -> list:
    """
    Search YouTube for a topic/keyword and return basic video results.
    """

    query = query.strip()

    if not query:
        return []

    search_url = (
        YOUTUBE_SEARCH_URL
        + urllib.parse.quote_plus(query)
    )

    request = urllib.request.Request(
        search_url,
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

    try:
        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:

            html = response.read().decode(
                "utf-8",
                errors="ignore",
            )

    except (
        urllib.error.URLError,
        TimeoutError,
    ):
        return []

    results = []

    marker = "ytInitialData"

    start = html.find(marker)

    if start == -1:
        return results

    json_start = html.find(
        "{",
        start,
    )

    if json_start == -1:
        return results

    try:

        decoder = json.JSONDecoder()

        data, _ = decoder.raw_decode(
            html[json_start:]
        )

    except json.JSONDecodeError:
        return results

    def walk(value):

        if len(results) >= limit:
            return

        if isinstance(value, dict):

            renderer = value.get(
                "videoRenderer"
            )

            if renderer:

                video_id = renderer.get(
                    "videoId"
                )

                title_runs = (
                    renderer.get("title", {})
                    .get("runs", [])
                )

                title = "".join(
                    run.get("text", "")
                    for run in title_runs
                )

                if video_id and title:

                    results.append(
                        {
                            "video_id": video_id,
                            "title": title,
                            "url": (
                                "https://www.youtube.com/watch?v="
                                + video_id
                            ),
                        }
                    )

                    if len(results) >= limit:
                        return

            for child in value.values():
                walk(child)

                if len(results) >= limit:
                    return

        elif isinstance(value, list):

            for child in value:
                walk(child)

                if len(results) >= limit:
                    return

    walk(data)

    return results


def research_topic(
    topic: str,
    reference_url: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Research a topic and collect relevant YouTube sources.
    """

    topic = topic.strip()

    if not topic:
        raise ValueError(
            "Research topic cannot be empty."
        )

    search_queries = [
        topic,
        f"{topic} latest",
        f"{topic} viral",
    ]

    sources = []

    for query in search_queries:

        results = search_youtube(
            query=query,
            limit=limit,
        )

        for result in results:

            video_id = result.get(
                "video_id"
            )

            if not video_id:
                continue

            if any(
                item.get("video_id") == video_id
                for item in sources
            ):
                continue

            sources.append(result)

            if len(sources) >= limit:
                break

        if len(sources) >= limit:
            break

    return {
        "topic": topic,
        "reference_url": reference_url,
        "sources": sources,
    }


def save_research(
    research: dict,
    output_path: str,
) -> str:

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            research,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path
