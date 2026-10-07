from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from core.research import research_topic
from core.source_analyzer import build_analysis_report
from core.transcription import (
    transcribe_media,
    transcript_to_clip_segments,
)
from core.clip_analyzer import build_clip_analysis_report
from core.video_processor import process_video
from core.script_generator import (
    generate_script,
    build_visual_editing_plan,
)


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

    sources = research.get(
        "sources",
        [],
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
) -> dict:

    script = generate_script(
        topic=topic,
        research=research,
        reference_url=reference_url,
    )

    script["visual_editing_plan"] = (
        build_visual_editing_plan(
            script
        )
    )

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

    analysis = clip_analysis.get(
        "analysis",
        {},
    )

    clips = analysis.get(
        "clips",
        [],
    )

    return process_video(
        video_path=video_path,
        clips=clips,
        output_dir=output_dir,
        make_vertical=make_vertical,
        duration=duration,
        caption_style=caption_style,
        caption_settings=caption_settings or {},
        editing_settings=editing_settings or {},
    )


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

    # -----------------------------------------------------
    # 7. FINAL VIDEO
    # -----------------------------------------------------

    processing = run_video_processing(
        video_path=video_path,
        clip_analysis=clip_analysis,
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
