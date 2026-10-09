import json
import re
from pathlib import Path

VERSION = "2.3"


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def overlap(a, b):
    if not a or not b:
        return 0.0
    return min(len(a & b) / max(len(b), 1), 1.0)


def semantic_score(text, beat_text, keywords):
    t = tokens(text)
    b = tokens(beat_text)
    k = tokens(" ".join(map(str, keywords)))
    return round(overlap(t, b) * 0.7 + overlap(t, k) * 0.3, 3)


def source_score(source, keywords):
    return round(
        overlap(
            tokens(source.get("title", "")),
            tokens(" ".join(map(str, keywords))),
        ),
        3,
    )


def decode_timestamp(value):
    """
    Convert filename timestamp format to seconds.

    Examples:
        87_600  -> 87.600
        92_400  -> 92.400
        261_001 -> 261.001
        1294_614 -> 1294.614
    """
    value = str(value)

    if "_" in value:
        whole, decimal = value.rsplit("_", 1)

        if whole.isdigit() and decimal.isdigit():
            return float(f"{whole}.{decimal}")

    return float(value)


def parse_section(path):
    """Parse current and legacy section filenames."""
    path = Path(path)
    name = path.stem

    m = re.match(r"^(.+?)__(\d+_\d+)__(\d+_\d+)$", name)
    if m:
        video_id = m.group(1)
        start = decode_timestamp(m.group(2))
        end = decode_timestamp(m.group(3))
    else:
        m = re.match(r"^(.+?)_(\d+)_(\d+)_(\d+)_(\d+)$", name)
        if not m:
            return None
        video_id = m.group(1)
        start = decode_timestamp(f"{m.group(2)}_{m.group(3)}")
        end = decode_timestamp(f"{m.group(4)}_{m.group(5)}")

    if end <= start:
        return None

    return {
        "video_id": video_id,
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(end - start, 3),
        "path": str(path),
    }


def duration_score(d):
    if 3 <= d <= 7:
        return 1.0
    if 2 <= d < 3:
        return 0.75
    if 7 < d <= 8:
        return 0.8
    return 0.5


def make_beats(profile):
    peaks = profile.get("peak_moments", [])

    if peaks:
        return [
            {
                "id": f"peak_{x.get('index', i + 1)}",
                "text": x.get("text", ""),
                "start": x.get("start"),
                "end": x.get("end"),
            }
            for i, x in enumerate(peaks)
        ]

    structure = profile.get("structure", [])

    return [
        {
            "id": f"segment_{i}",
            "text": x.get("text", ""),
            "start": x.get("start"),
            "end": x.get("end"),
        }
        for i, x in enumerate(structure)
    ]


def find_clip_candidates(discovery, profile):
    keywords = profile.get("content", {}).get("keywords", [])
    topic = profile.get("content", {}).get("topic", "")

    beats = make_beats(profile)
    section_dir = Path(__file__).resolve().parent.parent / "downloads" / "sections"

    sections = []

    for p in sorted(section_dir.glob("*.mp4")):
        x = parse_section(p)

        if x:
            sections.append(x)

    source_map = {
        x.get("video_id"): x
        for x in discovery.get("sources", [])
    }

    results = []

    for beat in beats:
        beat_text = f"{topic} {beat.get('text', '')}"

        for section in sections:
            source = source_map.get(
                section["video_id"],
                {},
            )

            src = source_score(
                source,
                keywords,
            )

            sem = semantic_score(
                source.get("title", ""),
                beat_text,
                keywords,
            )

            ds = duration_score(
                section["duration"]
            )

            timing = 0.0

            if beat.get("start") is not None:
                distance = abs(
                    section["start"]
                    - float(beat["start"])
                )

                timing = max(
                    0.0,
                    1.0 - min(distance / 60.0, 1.0),
                )

            final = round(
                sem * 0.45
                + src * 0.20
                + ds * 0.10
                + timing * 0.25,
                3,
            )

            results.append({
                "beat_id": beat["id"],
                "beat_text": beat_text,
                "source_video_id": section["video_id"],
                "source_url": source.get("url"),
                "source_title": source.get("title", ""),
                "local_path": section["path"],
                "start": section["start"],
                "end": section["end"],
                "duration": section["duration"],
                "semantic_score": sem,
                "source_score": src,
                "duration_score": ds,
                "timing_score": round(timing, 3),
                "final_score": final,
                "status": "candidate",
            })

    results.sort(
        key=lambda x: x["final_score"],
        reverse=True,
    )

    return {
        "version": VERSION,
        "candidate_count": len(results),
        "beats_analyzed": len(beats),
        "sections_analyzed": len(sections),
        "candidates": results,
        "scoring": {
            "semantic": 0.45,
            "source": 0.20,
            "duration": 0.10,
            "timing": 0.25,
        },
        "next_stage": "download_and_verify_selected_clips",
    }


def save(data, path):
    Path(path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: python clip_finder.py discovery profile output"
        )

    with open(
        sys.argv[1],
        encoding="utf-8",
    ) as f:
        discovery = json.load(f)

    with open(
        sys.argv[2],
        encoding="utf-8",
    ) as f:
        profile = json.load(f)

    result = find_clip_candidates(
        discovery,
        profile,
    )

    save(
        result,
        sys.argv[3],
    )

    print(
        json.dumps(
            {
                "success": True,
                "version": VERSION,
                "beats": result["beats_analyzed"],
                "sections": result["sections_analyzed"],
                "candidates": result["candidate_count"],
            },
            indent=2,
        )
    )
