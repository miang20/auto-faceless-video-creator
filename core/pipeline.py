from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from core.research import research_topic
from core.source_analyzer import build_analysis_report
from core.transcription import (
    transcribe_media,
    transcript_to_clip_segments,
)
from core.clip_analyzer import build_clip_analysis_report
from core.video_processor import process_video
from core.script_generator import build_script
from core.pro_editing import build_hook_overlay
from core.reference_intelligence import analyze_reference, plan_source_sections


PIPELINE_VERSION = "2.0"

DEFAULT_OUTPUT_DIR = Path("output/jobs")


def create_pipeline_id() -> str:
    return uuid.uuid4().hex


def create_output_directory(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:

    directory = Path(output_dir)

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def save_json(
    data: dict,
    output_path: str | Path,
) -> str:

    output = Path(output_path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return str(output)


def _build_peak_moments(raw_beats) -> list[dict]:
    """Normalize story beat timestamps for external source matching.

    Script-generator beats use source_start/source_end while clip-analysis
    beats commonly use start/end. Accept both contracts so the external
    sequence stage does not silently skip every generated story beat.
    """
    moments = []
    for index, item in enumerate(raw_beats or []):
        if not isinstance(item, dict):
            continue
        start = item.get("start", item.get("start_time", item.get("source_start")))
        end = item.get("end", item.get("end_time", item.get("source_end")))
        if start is None or end is None:
            continue
        try:
            start, end = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        moments.append({
            "index": index + 1,
            "text": str(item.get("text") or item.get("caption") or item.get("beat_text") or ""),
            "start": start,
            "end": end,
        })
    return moments


# =========================================================
# RESEARCH
# =========================================================

def _apply_visual_change_rhythm(
    timeline: list[dict],
    enabled: bool = True,
    max_segment_seconds: float = 4.0,
) -> list[dict]:
    """Split long selected windows into short, evenly sized visual beats."""
    items = [dict(item) for item in (timeline or []) if isinstance(item, dict)]
    if not enabled:
        return items
    try:
        maximum = max(2.0, min(5.0, float(max_segment_seconds)))
    except (TypeError, ValueError):
        maximum = 4.0
    result = []
    for item in items:
        try:
            start, end = float(item["start"]), float(item["end"])
        except (KeyError, TypeError, ValueError):
            result.append(item)
            continue
        length = end - start
        if length <= maximum + 0.01:
            result.append(item)
            continue
        count = max(2, int(math.ceil(length / maximum)))
        part_length = length / count
        for index in range(count):
            part_start = start + index * part_length
            part_end = end if index == count - 1 else start + (index + 1) * part_length
            part = dict(item)
            part["start"] = round(part_start, 4)
            part["end"] = round(part_end, 4)
            part["duration"] = max(0.1, part_end - part_start)
            result.append(part)
    return result


def run_research(
    topic: str,
    reference_url: Optional[str] = None,
    limit: int = 10,
) -> dict:

    return research_topic(
        topic=topic,
        reference_url=reference_url,
        limit=limit,
    )


# =========================================================
# SOURCE ANALYSIS
# =========================================================

def run_source_analysis(
    topic: str,
    research: dict,
    reference_url: Optional[str] = None,
) -> dict:

    sources = (
        research.get("sources", [])
        if isinstance(research, dict)
        else research if isinstance(research, list) else []
    )

    return build_analysis_report(
        topic=topic,
        sources=sources,
        reference_url=reference_url,
    )


# =========================================================
# SCRIPT
# =========================================================

def run_script_generation(
    topic: str,
    research: dict,
    reference_url: Optional[str] = None,
    clip_analysis: Optional[dict] = None,
    target_duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """Build a real story/edit blueprint from analyzed clips."""
    if isinstance(clip_analysis, dict):
        script = build_script(
            clip_analysis=clip_analysis,
            target_duration=target_duration,
            topic=topic or "",
            caption_style=caption_style,
            caption_settings=caption_settings,
            editing_settings=editing_settings,
        )
    else:
        sources = research.get("sources", []) if isinstance(research, dict) else []
        script = {
            "topic": topic or "",
            "reference_url": reference_url,
            "context_sources": sources if isinstance(sources, list) else [],
            "target_duration": target_duration,
            "format": "9:16",
            "narration": False,
            "timeline": [],
            "story_structure": [],
            "editing": dict(editing_settings or {}),
        }
    if isinstance(research, dict):
        script["context_sources"] = research.get("sources", []) or []
        script["source_analysis_summary"] = {
            "source_count": research.get("source_count", len(script["context_sources"])),
            "summary": research.get("summary", {}),
        }
    script["visual_editing_plan"] = dict(script.get("editing", {}))
    return script


# =========================================================
# TRANSCRIPTION
# =========================================================

def run_transcription(
    video_path: str | Path,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = "en",
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    keep_audio: bool = False,
) -> dict:

    return transcribe_media(
        media_path=video_path,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
        output_dir=output_dir,
        keep_audio=keep_audio,
    )


# =========================================================
# CLIP ANALYSIS
# =========================================================

def run_clip_analysis(
    video_path: str | Path,
    transcript: Optional[dict] = None,
    duration: Optional[float] = None,
    max_clips: int = 10,
) -> dict:

    transcript_segments = []

    if transcript:
        transcript_segments = (
            transcript_to_clip_segments(
                transcript
            )
        )

    return build_clip_analysis_report(
        video_path=str(video_path),
        transcript_segments=transcript_segments,
        duration=duration,
        max_clips=max_clips,
    )


# =========================================================
# VIDEO PROCESSING
# =========================================================

def run_video_processing(
    video_path: str | Path,
    clip_analysis: dict,
    output_dir: str | Path,
    make_vertical: bool = True,
    duration: Optional[int] = None,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:
    """Render selected clips using the renderer's actual API."""
    source_path = str(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"final_{Path(source_path).stem}.mp4"
    raw_clips = []
    if isinstance(clip_analysis, dict):
        for key in ("sequence", "clips"):
            value = clip_analysis.get(key)
            if isinstance(value, list) and value:
                raw_clips = value
                break
        if not raw_clips:
            analysis = clip_analysis.get("analysis", {})
            if isinstance(analysis, dict):
                raw_clips = analysis.get("clips", []) or []
    timeline, ranges_by_path = [], {}
    for clip in raw_clips:
        if not isinstance(clip, dict):
            continue
        local_section = clip.get("local_path")
        clip_path = str(local_section or clip.get("path") or clip.get("file_path") or clip.get("file") or source_path)
        if local_section:
            start = clip.get("local_start", 0)
            end = clip.get("local_end")
            if end is None:
                end = clip.get("duration")
            if end is None:
                try:
                    end = float(clip.get("end", clip.get("end_time"))) - float(clip.get("start", clip.get("start_time", 0)))
                except (TypeError, ValueError):
                    continue
        else:
            start = clip.get("start", clip.get("start_time", 0))
            end = clip.get("end", clip.get("end_time"))
        try:
            start, end = max(0.0, float(start)), float(end)
        except (TypeError, ValueError):
            continue
        if end <= start or not Path(clip_path).is_file():
            continue
        # Reordered edits may legitimately jump backward in source time. Reject
        # only genuinely overlapping source windows, not every earlier timestamp.
        prior_ranges = ranges_by_path.setdefault(clip_path, [])
        if any(start < prior_end - 0.02 and end > prior_start + 0.02
               for prior_start, prior_end in prior_ranges):
            continue
        timeline.append({
            "path": clip_path, "start": start, "end": end,
            "duration": end - start,
            "text": str(clip.get("text") or clip.get("caption") or clip.get("caption_text") or clip.get("beat_text") or clip.get("transcript") or ""),
            "role": str(clip.get("role", clip.get("story_role", "")) or "").upper(),
            "score": clip.get("score", clip.get("final_score", 0)),
            "hook_score": clip.get("hook_score", 0),
            "reaction_score": clip.get("reaction_score", 0),
            "visual_score": clip.get("visual_score", clip.get("motion_score", 0)),
            "audio_score": clip.get("audio_score", 0),
        })
        prior_ranges.append((start, end))

    # Put a footage-supported hook first. The chosen UI style changes which
    # measurable signal wins; it never manufactures a scene or a claim.
    hook_style = str((editing_settings or {}).get("hook_style", "Auto / Best for this footage")).lower()
    if len(timeline) > 1:
        def hook_rank(item):
            def number(key):
                try:
                    return max(0.0, min(1.0, float(item.get(key, 0) or 0)))
                except (TypeError, ValueError):
                    return 0.0
            text = str(item.get("text") or "").lower()
            hook = number("hook_score")
            visual = number("visual_score")
            reaction = number("reaction_score")
            audio = number("audio_score")
            overall = number("score")
            if "emotional human reaction" in hook_style:
                style_score = reaction * 0.48 + audio * 0.18 + visual * 0.14 + hook * 0.10 + overall * 0.10
            elif "immediate danger" in hook_style or "tension" in hook_style:
                tension_words = ("danger", "fall", "hit", "crash", "fight", "almost", "near", "scream", "hurt", "run")
                text_signal = 0.12 if any(word in text for word in tension_words) else 0.0
                style_score = hook * 0.32 + visual * 0.28 + audio * 0.16 + overall * 0.12 + text_signal + reaction * 0.12
            elif "curiosity gap" in hook_style or "question" in hook_style:
                curiosity_words = ("why", "how", "what", "wait", "until", "secret", "then", "because", "?")
                text_signal = 0.14 if any(word in text for word in curiosity_words) else 0.0
                style_score = hook * 0.30 + overall * 0.22 + visual * 0.16 + audio * 0.12 + reaction * 0.06 + text_signal
            elif "pov" in hook_style or "first-person" in hook_style:
                pov_words = ("you", "your", "imagine", "when you", "if you")
                text_signal = 0.14 if any(word in text for word in pov_words) else 0.0
                style_score = visual * 0.26 + hook * 0.24 + reaction * 0.16 + overall * 0.14 + audio * 0.06 + text_signal
            elif "payoff preview" in hook_style or "countdown" in hook_style or "unexpected" in hook_style:
                style_score = hook * 0.34 + visual * 0.28 + reaction * 0.16 + audio * 0.10 + overall * 0.12
            elif "cinematic" in hook_style or "suspense" in hook_style:
                style_score = visual * 0.30 + audio * 0.22 + hook * 0.22 + overall * 0.16 + reaction * 0.10
            else:
                style_score = hook * 0.34 + visual * 0.22 + overall * 0.20 + audio * 0.12 + reaction * 0.12
            if item.get("role") == "HOOK":
                style_score += 0.06
            return style_score

        best_hook_index = max(range(len(timeline)), key=lambda index: hook_rank(timeline[index]))
        best_hook = timeline.pop(best_hook_index)
        best_hook["role"] = "HOOK"
        timeline.insert(0, best_hook)

    # Preserve semantic selections before rhythm splitting so short cuts cannot
    # disguise a single unedited source moment.
    original_timeline = [dict(item) for item in timeline]
    selected_clip_count = len(original_timeline)

    # Keep visual changes in a 2-5 second window unless the selected moment is shorter.
    timeline = _apply_visual_change_rhythm(
        timeline,
        enabled=bool((editing_settings or {}).get("visual_change_rhythm", True)),
        max_segment_seconds=(editing_settings or {}).get("max_visual_segment_seconds", 4.0),
    )

    print(f"[VIDEO PROCESSOR] Selected clips: {selected_clip_count}; render segments: {len(timeline)}")
    print(f"[VIDEO PROCESSOR] Distinct source files: {len({x['path'] for x in timeline})}")
    if not timeline:
        raise ValueError("No usable clips found: candidate paths/timestamps were invalid.")
    from core.video_processor import process_video, _probe_duration
    requested = max(0.0, float(duration or 0))
    try:
        source_duration = float(_probe_duration(source_path))
    except Exception:
        source_duration = 0.0

    selected_duration = sum(max(0.0, float(item.get("end", 0)) - float(item.get("start", 0))) for item in timeline)
    minimum_usable = min(requested * 0.65, source_duration * 0.80) if requested and source_duration else 0.0

    # A one-clip timeline covering almost the whole source is a pass-through edit,
    # not a ready-to-upload result. If the chosen sequence is too short or is
    # effectively the entire source, rebuild it from independent local clip candidates.
    same_source_timeline = all(
        Path(str(item.get("path") or source_path)).expanduser().resolve()
        == Path(source_path).expanduser().resolve()
        for item in original_timeline
    )
    source_pass_through = (
        same_source_timeline
        and (
            len(original_timeline) < 2
            or (
                source_duration > 0
                and selected_duration >= source_duration * 0.85
            )
        )
    )
    needs_fallback = source_pass_through or (
        source_duration > 0 and selected_duration < minimum_usable
    )

    if needs_fallback:
        raw_fallback = (
            clip_analysis.get("clips", [])
            if isinstance(clip_analysis, dict) else []
        )
        fallback_candidates = []
        for item in raw_fallback:
            if not isinstance(item, dict):
                continue
            try:
                start = max(0.0, float(item.get("start", item.get("start_time", 0))))
                end_value = item.get("end", item.get("end_time"))
                if end_value is None:
                    end_value = start + float(item.get("duration", 0))
                end = min(source_duration, float(end_value))
            except (TypeError, ValueError):
                continue
            if end <= start or end - start < 1.0:
                continue
            if any(
                start < prior_end - 0.02 and end > prior_start + 0.02
                for prior_start, prior_end in [
                    (float(x["start"]), float(x["end"])) for x in fallback_candidates
                ]
            ):
                continue
            fallback_candidates.append({
                "path": source_path,
                "start": start,
                "end": end,
                "duration": end - start,
                "text": str(item.get("text") or item.get("transcript") or item.get("caption") or ""),
                "role": str(item.get("story_role") or item.get("role") or "MAIN"),
                "score": float(item.get("score", item.get("final_score", 0)) or 0),
            })

        # Prefer the highest-scoring moments, then restore source chronology.
        fallback_candidates.sort(key=lambda item: float(item.get("score", 0)), reverse=True)
        fallback_timeline = []
        fallback_total = 0.0
        # Keep the fallback meaningfully shorter than the source and within the
        # requested duration. Trim the final selected moment if it only partly fits.
        source_budget = source_duration * 0.85 if source_duration > 0 else float("inf")
        target_budget = requested * 1.20 if requested > 0 else float("inf")
        total_budget = min(source_budget, target_budget)
        for candidate in fallback_candidates:
            if len(fallback_timeline) >= 12 or fallback_total >= total_budget:
                break
            remaining = total_budget - fallback_total
            if remaining < 1.0:
                break
            item = dict(candidate)
            if float(item["duration"]) > remaining:
                item["end"] = float(item["start"]) + remaining
                item["duration"] = remaining
            if item["duration"] < 1.0:
                continue
            fallback_timeline.append(item)
            fallback_total += float(item["duration"])
        fallback_timeline.sort(key=lambda item: float(item["start"]))

        fallback_semantic_count = len(fallback_timeline)
        if fallback_timeline:
            fallback_timeline = _apply_visual_change_rhythm(
                fallback_timeline,
                enabled=bool((editing_settings or {}).get("visual_change_rhythm", True)),
                max_segment_seconds=(editing_settings or {}).get("max_visual_segment_seconds", 4.0),
            )
            fallback_total = sum(
                max(0.0, float(item["end"]) - float(item["start"]))
                for item in fallback_timeline
            )
        if (
            fallback_semantic_count < 2
            or (minimum_usable > 0 and fallback_total < minimum_usable)
            or (source_duration > 0 and fallback_total >= source_duration * 0.90)
        ):
            raise RuntimeError(
                "V2 edit validation blocked pass-through output: the selected story is too short "
                "or lacks at least two independent source moments. No unedited source will be "
                "copied as the final video. Check transcription/clip-analysis artifacts."
            )

        timeline = fallback_timeline
        selected_clip_count = fallback_semantic_count
        print(
            f"[V2 RENDER] Rebuilt timeline from {selected_clip_count} independent local moments "
            f"({fallback_total:.2f}s); pass-through source output blocked."
        )

    # Put a grounded on-screen hook over the first actual rendered shot.
    if timeline:
        first = timeline[0]
        if not str(first.get("hook_text") or "").strip():
            first["hook_text"] = build_hook_overlay(
                str(editing_settings.get("hook_style") or "Auto / Best for this footage"),
                str(editing_settings.get("topic") or Path(source_path).stem),
                str(first.get("text") or ""),
            )

    # Discover and download context-matched B-roll automatically; gracefully fall back.
    broll_report = {"enabled": False, "inserted": 0, "status": "disabled"}
    if bool(editing_settings.get("contextual_broll", editing_settings.get("use_broll", False))):
        try:
            from core.contextual_broll import insert_contextual_broll
            timeline, broll_report = insert_contextual_broll(
                timeline=timeline, topic=str(editing_settings.get("topic") or Path(source_path).stem),
                target_duration=int(duration or 30),
                max_broll=int(editing_settings.get("max_broll_clips", 2) or 2),
            )
            print("[V2 BROLL] %s: inserted=%s" % (broll_report.get("status"), broll_report.get("inserted", 0)))
        except Exception as broll_error:
            broll_report = {"enabled": True, "inserted": 0, "status": "fallback", "warnings": [str(broll_error)[:240]]}
            print("[V2 BROLL] Non-fatal fallback:", str(broll_error)[:180])

    captions_enabled = (
        isinstance(caption_settings, dict)
        and caption_settings.get("enabled", True) is not False
    )
    if captions_enabled and not any(str(item.get("text", "")).strip() for item in timeline):
        raise RuntimeError(
            "Caption validation failed: captions are enabled, but the final selected timeline "
            "contains no transcript text. Refusing to publish a captionless final."
        )

    editing = dict(editing_settings or {})
    output_format = str(editing.get("output_format", "")).strip().lower()
    use_vertical = bool(editing.get("make_vertical", make_vertical))
    if output_format in {"landscape", "long-form", "long_form", "16:9"}:
        output_width, output_height = 1920, 1080
        use_vertical = False
    elif output_format in {"vertical", "shorts", "9:16"}:
        output_width, output_height = 1080, 1920
        use_vertical = True
    else:
        output_width, output_height = (1080, 1920) if use_vertical else (1920, 1080)
    editing["make_vertical"] = use_vertical
    editing["output_format"] = "vertical" if use_vertical else "landscape"
    editing.setdefault("audio_normalize", editing.get("normalize_audio", True))
    # Embedded narration cannot be reliably separated from music/dialogue by
    # volume filters. Only mute the complete source track on explicit user choice.
    editing["source_audio_mode"] = str(
        editing.get("source_audio_mode")
        or ("mute_source" if "mute source audio" in str(editing.get("voiceover_mode", "")).lower() else "keep_source")
    ).strip().lower()
    captions = dict(caption_settings or {})
    captions.setdefault("enabled", True)
    captions.setdefault("style", caption_style or "Bold Viral")
    rendered_path = process_video(
        input_path=source_path, output_path=str(output_path),
        script={"timeline": timeline, "target_duration": duration or 30},
        target_duration=duration, caption_style=caption_style,
        caption_settings=captions, editing_settings=editing,
        output_width=output_width, output_height=output_height,
    )
    rendered_path = str(rendered_path or output_path)
    if not Path(rendered_path).is_file() or Path(rendered_path).stat().st_size <= 0:
        raise RuntimeError(f"Renderer returned without a valid MP4: {rendered_path}")
    actual_duration = float(_probe_duration(rendered_path))
    # The renderer must not mark a materially short timeline as successful.
    # Compare against the requested duration, capped by actual source duration.
    expected_floor = min(requested, source_duration) * 0.90 if requested and source_duration else 0.0
    if expected_floor > 0 and actual_duration < expected_floor:
        raise RuntimeError(
            f"Final render failed duration QC ({actual_duration:.2f}s; expected at least "
            f"{expected_floor:.2f}s for a {requested:.2f}s target). "
            "Refusing to mark this job completed; inspect clip selection and timeline assembly."
        )
    return {
        "success": True, "output_path": rendered_path,
        "final_video": rendered_path, "result_path": rendered_path,
        "size_bytes": Path(rendered_path).stat().st_size,
        "selected_clips": selected_clip_count,
        "render_segments": len(timeline),
        "distinct_source_files": len({x["path"] for x in timeline}),
        "broll": broll_report,
        "hook_overlay": str(timeline[0].get("hook_text") or "") if timeline else "",
    }



# =========================================================
# COMPLETE VIDEO PIPELINE
# =========================================================

def run_video_pipeline(
    video_path: str | Path,
    topic: Optional[str] = None,
    reference_url: Optional[str] = None,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = "en",
    max_clips: int = 10,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    make_vertical: bool = True,
    keep_audio: bool = False,

    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:

    # The UI submits the reference URL as input_value. Resolve its title so
    # research searches use a human-readable topic instead of a URL string.
    topic_text = str(topic or "").strip()
    parsed_topic = urlparse(topic_text) if topic_text else None
    if parsed_topic and parsed_topic.scheme in {"http", "https"} and parsed_topic.hostname:
        host = parsed_topic.hostname.lower().rstrip(".")
        if host == "youtu.be" or host.endswith("youtube.com"):
            reference_url = reference_url or topic_text
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
                    info = ydl.extract_info(reference_url, download=False)
                resolved_title = str(info.get("title") or "").strip()
                topic = resolved_title or Path(video_path).stem
            except Exception as metadata_error:
                print("[V2 RESEARCH] Reference title lookup failed:", str(metadata_error)[:180])
                topic = Path(video_path).stem
        else:
            topic = topic_text
    elif topic_text:
        topic = topic_text

    pipeline_id = create_pipeline_id()

    output = create_output_directory(
        output_dir
    )

    video_path = str(video_path)

    caption_settings = dict(caption_settings or {})
    editing_settings = dict(editing_settings or {})
    editing_settings.setdefault("topic", str(topic or Path(video_path).stem))

    # -----------------------------------------------------
    # 0. REFERENCE INTELLIGENCE
    # -----------------------------------------------------
    # Analyze the user-supplied reference once and persist the evidence used by
    # research/sequence selection. This does not change core/downloader.py.
    reference_profile = analyze_reference(reference_url, topic or "")
    reference_profile_path = save_json(
        reference_profile,
        output / f"{pipeline_id}_reference_profile.json",
    )
    reference_keywords = reference_profile.get("keywords", [])
    if reference_keywords:
        editing_settings["reference_keywords"] = reference_keywords
    if reference_profile.get("success"):
        editing_settings["reference_title"] = reference_profile.get("title", "")
        editing_settings["reference_duration"] = reference_profile.get("duration", 0)
        editing_settings["reference_chapters"] = reference_profile.get("chapters", [])


    # -----------------------------------------------------
    # 1. RESEARCH
    # -----------------------------------------------------

    research = {}

    if topic:
        try:
            research = run_research(
                topic=topic,
                reference_url=reference_url,
                limit=10,
            )
        except Exception as error:
            research = {
                "error": str(error),
                "sources": [],
            }

    research_path = save_json(
        research,
        output / f"{pipeline_id}_research.json",
    )

    # -----------------------------------------------------
    # 2. SOURCE ANALYSIS
    # -----------------------------------------------------

    source_analysis = {}

    if research:
        try:
            source_analysis = run_source_analysis(
                topic=topic or "",
                research=research,
                reference_url=reference_url,
            )
        except Exception as error:
            source_analysis = {
                "error": str(error),
                "sources": [],
            }

    source_analysis_path = save_json(
        source_analysis,
        output / f"{pipeline_id}_source_analysis.json",
    )

    # -----------------------------------------------------
    # 3. STORY / SCRIPT
    # -----------------------------------------------------

    script = {}

    if source_analysis:
        try:
            script = run_script_generation(
                topic=topic or "",
                research=source_analysis,
                reference_url=reference_url,
            )
        except Exception as error:
            script = {
                "error": str(error),
            }

    script_path = save_json(
        script,
        output / f"{pipeline_id}_script.json",
    )

    # -----------------------------------------------------
    # 4. TRANSCRIPTION
    # -----------------------------------------------------

    transcript_dir = output / "transcription"

    transcript = run_transcription(
        video_path=video_path,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
        output_dir=transcript_dir,
        keep_audio=keep_audio,
    )

    transcript_path = save_json(
        transcript,
        output / f"{pipeline_id}_transcript.json",
    )

    # -----------------------------------------------------
    # 5. SOURCE DURATION
    # -----------------------------------------------------

    source_duration = None

    segments = transcript.get(
        "segments",
        [],
    )

    if segments:
        try:
            source_duration = max(
                float(segment.get("end", 0))
                for segment in segments
            )
        except Exception:
            source_duration = None

    # -----------------------------------------------------
    # 6. CLIP INTELLIGENCE
    # -----------------------------------------------------

    clip_analysis = run_clip_analysis(
        video_path=video_path,
        transcript=transcript,
        duration=source_duration,
        max_clips=max_clips,
    )

    clip_analysis_path = save_json(
        clip_analysis,
        output / f"{pipeline_id}_clip_analysis.json",
    )

    # Build the actual story blueprint only after clip analysis exists.
    # The old call passed unsupported kwargs to generate_script and only saved
    # an error object instead of a usable timeline.
    try:
        script = run_script_generation(
            topic=topic or "",
            research=source_analysis,
            reference_url=reference_url,
            clip_analysis=clip_analysis,
            target_duration=duration or 30,
            caption_style=caption_style,
            caption_settings=caption_settings,
            editing_settings=editing_settings,
        )
    except Exception as script_error:
        print("[V2 STORY] Blueprint generation failed:", str(script_error)[:240])
        script = {
            "topic": topic or "",
            "timeline": [],
            "story_structure": [],
            "error": str(script_error),
        }
    script_path = save_json(script, output / f"{pipeline_id}_script.json")

    # -----------------------------------------------------

    # Use the generated story blueprint even when external-source discovery
    # is unavailable. This keeps HOOK/SETUP/ESCALATION/REACTION/PAYOFF order
    # connected to the actual renderer instead of saving an unused script.
    render_analysis = clip_analysis
    story_timeline = []
    for item in script.get("timeline", []):
        if not isinstance(item, dict):
            continue
        start = item.get("source_start", item.get("start", item.get("start_time")))
        end = item.get("source_end", item.get("end", item.get("end_time")))
        try:
            start, end = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        source_duration = end - start
        budget = item.get("target_screen_duration")
        try:
            budget = float(budget) if budget is not None else source_duration
        except (TypeError, ValueError):
            budget = source_duration
        budget = max(0.1, min(source_duration, budget))
        role = str(item.get("role") or item.get("story_role") or "MAIN").upper()
        # Trim within each chosen beat instead of proportionally mutating source
        # timestamps. For payoff/ending, retain the tail of the source window.
        if source_duration > budget + 0.01 and role in {"PAYOFF", "ENDING"}:
            start = end - budget
        else:
            end = start + budget
        story_timeline.append({
            "start": start,
            "end": end,
            "duration": end - start,
            "text": str(item.get("text") or ""),
            "role": role,
            "score": item.get("score", 0),
        })
    if story_timeline:
        # Keep the script generator's narrative order. Clip analysis already
        # selects non-overlapping source windows; never sort back to source order
        # or scale timestamps independently, both of which break the edit.
        render_analysis = {
            "sequence": story_timeline,
            "clips": clip_analysis.get("clips", []) if isinstance(clip_analysis, dict) else [],
            "story_blueprint": script,
        }

    # V2_SEQUENCE_INTEGRATION
    # Connect research sources -> section downloads -> candidate scoring.
    # Preserve the story-ordered local-source fallback if discovery fails.
    try:
        from core.section_downloader import download_section
        from core.clip_finder import find_clip_candidates
        from core.sequence_builder import build_sequence

        analyzed_sources = (
            source_analysis.get("sources", [])
            if isinstance(source_analysis, dict) else []
        )
        raw_sources = analyzed_sources or (
            research.get("sources", [])
            if isinstance(research, dict)
            else research if isinstance(research, list) else []
        )
        sources = [
            item for item in raw_sources
            if isinstance(item, dict)
            and item.get("url")
            and item.get("video_id")
        ][:3]
        raw_beats = script.get("timeline") or clip_analysis.get("clips", [])
        profile = {
            "content": {
                "topic": topic or "",
                "keywords": list(dict.fromkeys(
                    [
                        word.strip(".,!?;:")
                        for word in (topic or "").split()
                        if len(word.strip(".,!?;:")) > 2
                    ]
                    + [
                        str(keyword).strip(".,!?;:")
                        for keyword in reference_keywords
                        if len(str(keyword).strip(".,!?;:")) > 2
                    ]
                    + [
                        str(keyword).strip(".,!?;:")
                        for source in sources
                        for keyword in (source.get("keywords", []) or [])
                        if len(str(keyword).strip(".,!?;:")) > 2
                    ]
                )),
            },
            "peak_moments": (
                _build_peak_moments(raw_beats)
                + [
                    {"index": 1000 + i, "text": str(chapter.get("text") or ""),
                     "role": "REFERENCE_CHAPTER"}
                    for i, chapter in enumerate(reference_profile.get("chapters", []))
                    if isinstance(chapter, dict) and str(chapter.get("text") or "").strip()
                ]
            ),
        }

        downloaded = 0
        # Sample three short windows from each of the top research sources.
        # Failed/too-short sources are skipped; the frozen core downloader
        # and the existing pipeline fallback remain unchanged.
        for item in sources:
            for start, end in plan_source_sections(item, max_sections=3, section_seconds=8.0):
                try:
                    result_path = download_section(
                        url=item["url"],
                        start=start,
                        end=end,
                        video_id=str(item["video_id"]),
                    )
                    if result_path and Path(result_path).is_file():
                        downloaded += 1
                except Exception as download_error:
                    print(
                        "[V2 SEQUENCE] Section skipped:",
                        item.get("video_id"),
                        start, end, str(download_error)[:160],
                    )

        print(f"[V2 SEQUENCE] Sections downloaded: {downloaded}")

        if downloaded and profile["peak_moments"]:
            discovery = {"sources": sources}
            candidate_report = find_clip_candidates(discovery, profile)
            sequence_report = build_sequence(
                profile,
                candidate_report,
                target_duration=duration or 30,
                editing_settings=editing_settings,
                max_clips=max_clips,
            )

            if sequence_report.get("success") and sequence_report.get("sequence"):
                selected_sequence = sequence_report["sequence"]
                render_analysis = {
                    "sequence": selected_sequence,
                    # Keep the independently analyzed local-source candidates
                    # available if external-source selection is too short or invalid.
                    "clips": clip_analysis.get("clips", []),
                    "sequence_report": sequence_report,
                    "candidate_report": candidate_report,
                }
                # The exact selected sequence becomes the story blueprint that
                # is handed to the renderer; roles and edit plan are persisted.
                script["timeline"] = selected_sequence
                script["selected_sequence"] = selected_sequence
                script["story_structure"] = [
                    str(item.get("role", "MAIN")).upper()
                    for item in selected_sequence
                ]
                script["visual_editing_plan"] = {
                    **dict(script.get("editing", {})),
                    **dict(sequence_report.get("editing_plan", {})),
                }
                clip_analysis["story_blueprint"] = {
                    "timeline": selected_sequence,
                    "story_structure": script["story_structure"],
                    "visual_editing_plan": script["visual_editing_plan"],
                }
                clip_analysis["sequence_report"] = sequence_report
                clip_analysis["candidate_report_summary"] = {
                    "candidate_count": candidate_report.get("candidate_count", 0),
                    "sections_analyzed": candidate_report.get("sections_analyzed", 0),
                    "beats_analyzed": candidate_report.get("beats_analyzed", 0),
                }
                save_json(script, script_path)
                save_json(clip_analysis, output / f"{pipeline_id}_clip_analysis.json")
                print(
                    "[V2 SEQUENCE] Selected:",
                    sequence_report.get("clip_count", 0),
                    "clips; estimated duration:",
                    sequence_report.get("estimated_duration", 0),
                )
            else:
                # External discovery is optional. Keep the already analyzed local
                # story timeline; never erase it merely because research footage
                # failed its quality gate.
                reason = sequence_report.get("reason", "No valid coherent external sequence")
                print("[V2 SEQUENCE] External quality gate failed; preserving local story fallback:", reason)
                render_analysis["sequence_report"] = sequence_report
                render_analysis["candidate_report"] = candidate_report
                render_analysis["quality_gate_failed"] = True
                render_analysis["quality_gate_reason"] = reason
                clip_analysis["sequence_report"] = sequence_report
        else:
            # No external sections/beats is not a reason to blank a valid local
            # edit blueprint prepared above.
            print("[V2 SEQUENCE] Insufficient external sections/beats; preserving local story fallback.")
            render_analysis["quality_gate_failed"] = True
            render_analysis["quality_gate_reason"] = "Insufficient source sections or story beats"

    except Exception as integration_error:
        # Keep the story-timeline fallback already prepared above. Reverting
        # to raw clip_analysis here discards the generated story and often
        # leaves only two long, nearly-original segments.
        print(
            "[V2 SEQUENCE] Integration fallback:",
            repr(integration_error)[:300],
        )

    # 7. FINAL VIDEO
    # -----------------------------------------------------

    processing = run_video_processing(
        video_path=video_path,
        clip_analysis=render_analysis,
        output_dir=output,
        make_vertical=make_vertical,
        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    output_path = (
        processing.get("output_path")
        or processing.get("final_video")
        or processing.get("result_path")
    )

    sequence_report = clip_analysis.get("sequence_report", {}) if isinstance(clip_analysis, dict) else {}
    stage_status = {
        "research": "complete" if bool(research) else "no_sources",
        "source_analysis": "complete" if isinstance(source_analysis, dict) and source_analysis.get("source_count", 0) else "no_sources",
        "clip_analysis": "complete" if isinstance(clip_analysis, dict) and clip_analysis.get("clips") else "no_clips",
        "story_blueprint": "complete" if bool(script.get("timeline")) else "fallback",
        "external_sequence": "complete" if isinstance(sequence_report, dict) and sequence_report.get("success") else "local_story_fallback",
        "render": "complete" if processing.get("success") else "failed",
    }

    result = {
        "success": bool(
            processing.get(
                "success",
                False,
            )
        ),
        "stage_status": stage_status,
        "feature_audit": {
            "captions_requested": bool(caption_settings.get("enabled", True)),
            "dynamic_zoom_requested": bool(editing_settings.get("dynamic_zoom", True)),
            "silence_removal_requested": bool(editing_settings.get("remove_silence", False)),
            "audio_normalization_requested": bool(editing_settings.get("normalize_audio", editing_settings.get("audio_normalize", True))),
            "reaction_selection_requested": bool(editing_settings.get("reaction_selection", True)),
            "contextual_broll_requested": bool(editing_settings.get("contextual_broll", False)),
            "visual_change_rhythm_requested": bool(editing_settings.get("visual_change_rhythm", True)),
            "smart_subject_tracking": "face-aware crop when OpenCV and face detections are available; otherwise centered crop fallback",
            "sequence_clip_count": sequence_report.get("clip_count", 0) if isinstance(sequence_report, dict) else 0,
        },
        "pipeline_id": pipeline_id,
        "version": PIPELINE_VERSION,

        "source_video": video_path,
        "topic": topic,
        "reference_url": reference_url,

        "duration": duration,

        "caption_style": caption_style,
        "caption_settings": caption_settings,
        "editing_settings": editing_settings,

        "output_path": output_path,

        "research": research,
        "source_analysis": source_analysis,
        "script": script,
        "transcript": transcript,
        "clip_analysis": clip_analysis,
        "processing": processing,

        "artifacts": {
            "research": research_path,
            "source_analysis": source_analysis_path,
            "script": script_path,
            "transcript": transcript_path,
            "clip_analysis": clip_analysis_path,
            "reference_profile": reference_profile_path,
        },
    }

    result_path = (
        output
        / f"{pipeline_id}_result.json"
    )

    save_json(
        result,
        result_path,
    )

    result["result_file"] = str(
        result_path
    )

    return result


def summarize_pipeline(
    result: dict,
) -> dict:

    return {
        "success": result.get(
            "success",
            False,
        ),
        "pipeline_id": result.get(
            "pipeline_id"
        ),
        "version": result.get(
            "version"
        ),
        "output_path": result.get(
            "output_path"
        ),
        "duration": result.get(
            "duration"
        ),
    }


def execute_video_pipeline(
    video_path: str | Path,
    topic: Optional[str] = None,
    reference_url: Optional[str] = None,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = "en",
    max_clips: int = 10,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    make_vertical: bool = True,
    keep_audio: bool = False,

    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> dict:

    return run_video_pipeline(
        video_path=video_path,
        topic=topic,
        reference_url=reference_url,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
        max_clips=max_clips,
        output_dir=output_dir,
        make_vertical=make_vertical,
        keep_audio=keep_audio,

        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )


def save_pipeline_result(
    result: dict,
    output_path: str | Path,
) -> str:

    return save_json(
        result,
        output_path,
    )

# ============================================================
# TOPIC PIPELINE COMPATIBILITY
# ============================================================

def run_topic_pipeline(
    topic: str,
    reference_url: Optional[str] = None,
    research_limit: int = 10,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    pipeline_id = create_pipeline_id()
    output = create_output_directory(output_dir)

    research = run_research(
        topic=topic,
        reference_url=reference_url,
        limit=research_limit,
    )
    research_path = save_json(
        research,
        output / f"{pipeline_id}_research.json",
    )

    source_analysis = run_source_analysis(
        topic=topic,
        research=research,
        reference_url=reference_url,
    )
    source_analysis_path = save_json(
        source_analysis,
        output / f"{pipeline_id}_source_analysis.json",
    )

    script = run_script_generation(
        topic=topic,
        research=source_analysis,
        reference_url=reference_url,
    )
    script_path = save_json(
        script,
        output / f"{pipeline_id}_script.json",
    )

    return {
        "success": True,
        "pipeline_id": pipeline_id,
        "version": PIPELINE_VERSION,
        "topic": topic,
        "reference_url": reference_url,
        "research": research,
        "source_analysis": source_analysis,
        "script": script,
        "artifacts": {
            "research": research_path,
            "source_analysis": source_analysis_path,
            "script": script_path,
        },
    }
