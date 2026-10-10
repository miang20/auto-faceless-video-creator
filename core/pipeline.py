from __future__ import annotations

import json
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


# =========================================================
# RESEARCH
# =========================================================

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
    timeline, last_end_by_path = [], {}
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
        if start < last_end_by_path.get(clip_path, -1.0):
            continue
        timeline.append({
            "path": clip_path, "start": start, "end": end,
            "duration": end - start,
            "text": str(clip.get("text") or clip.get("caption") or clip.get("caption_text") or clip.get("beat_text") or clip.get("transcript") or ""),
            "role": clip.get("role", clip.get("story_role", "")),
            "score": clip.get("score", clip.get("final_score", 0)),
        })
        last_end_by_path[clip_path] = end
    print(f"[VIDEO PROCESSOR] Selected clips: {len(timeline)}")
    print(f"[VIDEO PROCESSOR] Distinct source files: {len({x['path'] for x in timeline})}")
    if not timeline:
        raise ValueError("No usable clips found: candidate paths/timestamps were invalid.")
    from core.video_processor import process_video
    editing = dict(editing_settings or {})
    editing.setdefault("make_vertical", make_vertical)
    editing.setdefault("audio_normalize", editing.get("normalize_audio", True))
    captions = dict(caption_settings or {})
    captions.setdefault("enabled", True)
    captions.setdefault("style", caption_style or "Bold Viral")
    rendered_path = process_video(
        input_path=source_path, output_path=str(output_path),
        script={"timeline": timeline, "target_duration": duration or 30},
        target_duration=duration, caption_style=caption_style,
        caption_settings=captions, editing_settings=editing,
    )
    rendered_path = str(rendered_path or output_path)
    if not Path(rendered_path).is_file() or Path(rendered_path).stat().st_size <= 0:
        raise RuntimeError(f"Renderer returned without a valid MP4: {rendered_path}")
    return {
        "success": True, "output_path": rendered_path,
        "final_video": rendered_path, "result_path": rendered_path,
        "size_bytes": Path(rendered_path).stat().st_size,
        "selected_clips": len(timeline),
        "distinct_source_files": len({x["path"] for x in timeline}),
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

    caption_settings = caption_settings or {}
    editing_settings = editing_settings or {}

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

    # V2_SEQUENCE_INTEGRATION
    # Connect research sources -> section downloads -> candidate scoring
    # -> sequence builder. Preserve the original clip-analysis fallback.
    render_analysis = clip_analysis

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
                        for source in sources
                        for keyword in (source.get("keywords", []) or [])
                        if len(str(keyword).strip(".,!?;:")) > 2
                    ]
                )),
            },
            "peak_moments": [
                {
                    "index": index + 1,
                    "text": str(item.get("text") or item.get("caption") or ""),
                    "start": item.get("start", item.get("start_time", item.get("source_start"))),
                    "end": item.get("end", item.get("end_time", item.get("source_end"))),
                }
                for index, item in enumerate(raw_beats)
                if isinstance(item, dict)
                and item.get("start", item.get("start_time")) is not None
                and item.get("end", item.get("end_time")) is not None
            ],
        }

        downloaded = 0
        # Sample three short windows from each of the top research sources.
        # Failed/too-short sources are skipped; the frozen core downloader
        # and the existing pipeline fallback remain unchanged.
        for item in sources:
            for start, end in ((0, 10), (10, 20), (20, 30)):
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
            )

            if sequence_report.get("success") and sequence_report.get("sequence"):
                selected_sequence = sequence_report["sequence"]
                render_analysis = {
                    "sequence": selected_sequence,
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
                print("[V2 SEQUENCE] No usable sequence; using original clips.")
        else:
            print("[V2 SEQUENCE] Insufficient sections/beats; using original clips.")

    except Exception as integration_error:
        render_analysis = clip_analysis
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

    result = {
        "success": bool(
            processing.get(
                "success",
                False,
            )
        ),
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
