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
from core.clip_analyzer import (
    build_clip_analysis_report,
)
from core.video_processor import (
    process_video,
)
from core.script_generator import (
    generate_script,
    build_visual_editing_plan,
)


# =========================================================
# CONFIG
# =========================================================

PIPELINE_VERSION = "1.0"

DEFAULT_OUTPUT_DIR = Path(
    "output/pipeline"
)


# =========================================================
# HELPERS
# =========================================================

def create_pipeline_id() -> str:
    """
    Create a unique pipeline execution ID.
    """

    return uuid.uuid4().hex


def create_output_directory(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Create the pipeline output directory.
    """

    directory = Path(
        output_dir
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def save_json(
    data: dict,
    output_path: str | Path,
) -> str:
    """
    Save any pipeline result as JSON.
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
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(output)


# =========================================================
# STEP 1 — RESEARCH
# =========================================================

def run_research(
    topic: str,
    reference_url: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Research a topic and collect candidate sources.
    """

    return research_topic(
        topic=topic,
        reference_url=reference_url,
        limit=limit,
    )


# =========================================================
# STEP 2 — SOURCE ANALYSIS
# =========================================================

def run_source_analysis(
    topic: str,
    research: dict,
    reference_url: Optional[str] = None,
) -> dict:
    """
    Analyze and rank discovered sources.
    """

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
# STEP 3 — SCRIPT GENERATION
# =========================================================

def run_script_generation(
    topic: str,
    research: dict,
    reference_url: Optional[str] = None,
) -> dict:
    """
    Generate structured script and visual editing plan.
    """

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
# STEP 4 — TRANSCRIPTION
# =========================================================

def run_transcription(
    video_path: str | Path,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = "en",
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    keep_audio: bool = False,
) -> dict:
    """
    Transcribe a downloaded/source video locally.
    """

    return transcribe_media(
        media_path=video_path,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
        output_dir=output_dir,
        keep_audio=keep_audio,
    )


# =========================================================
# STEP 5 — CLIP ANALYSIS
# =========================================================

def run_clip_analysis(
    video_path: str | Path,
    transcript: Optional[dict] = None,
    duration: Optional[float] = None,
    max_clips: int = 10,
) -> dict:
    """
    Analyze transcript peaks and produce clip candidates.
    """

    transcript_segments = []

    if transcript:

        transcript_segments = (
            transcript_to_clip_segments(
                transcript
            )
        )

    return build_clip_analysis_report(
        video_path=str(
            video_path
        ),
        transcript_segments=(
            transcript_segments
        ),
        duration=duration,
        max_clips=max_clips,
    )


# =========================================================
# STEP 6 — VIDEO PROCESSING
# =========================================================

def run_video_processing(
    video_path: str | Path,
    clip_analysis: dict,
    output_dir: str | Path,
    make_vertical: bool = True,
) -> dict:
    """
    Turn analyzed clip candidates into actual video files.
    """

    clips = clip_analysis.get(
        "analysis",
        {},
    ).get(
        "clips",
        [],
    )

    return process_video(
        video_path=video_path,
        clips=clips,
        output_dir=output_dir,
        make_vertical=make_vertical,
    )


# =========================================================
# FULL TOPIC PIPELINE
# =========================================================

def run_topic_pipeline(
    topic: str,
    reference_url: Optional[str] = None,
    research_limit: int = 10,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    """
    Run the research → source analysis → script pipeline.

    This stage does not download or process videos yet.
    """

    pipeline_id = create_pipeline_id()

    output = create_output_directory(
        output_dir
    )

    research = run_research(
        topic=topic,
        reference_url=reference_url,
        limit=research_limit,
    )

    research_path = save_json(
        research,
        output
        / f"{pipeline_id}_research.json",
    )

    source_analysis = run_source_analysis(
        topic=topic,
        research=research,
        reference_url=reference_url,
    )

    source_analysis_path = save_json(
        source_analysis,
        output
        / f"{pipeline_id}_source_analysis.json",
    )

    script = run_script_generation(
        topic=topic,
        research=source_analysis,
        reference_url=reference_url,
    )

    script_path = save_json(
        script,
        output
        / f"{pipeline_id}_script.json",
    )

    return {
        "pipeline_id": pipeline_id,
        "version": PIPELINE_VERSION,
        "mode": "topic",
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


# =========================================================
# FULL VIDEO PIPELINE
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
) -> dict:
    """
    Run the complete available video-processing pipeline:

        Video
          ↓
        Transcription
          ↓
        Clip Analysis
          ↓
        Video Processing
          ↓
        Final Clips

    If a topic is supplied, script generation is also included.
    """

    pipeline_id = create_pipeline_id()

    output = create_output_directory(
        output_dir
    )

    video_path = str(
        video_path
    )

    # -----------------------------------------------------
    # TRANSCRIPTION
    # -----------------------------------------------------

    transcript_dir = (
        output
        / "transcription"
    )

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
        output
        / f"{pipeline_id}_transcript.json",
    )

    # -----------------------------------------------------
    # VIDEO DURATION
    # -----------------------------------------------------

    duration = None

    segments = transcript.get(
        "segments",
        [],
    )

    if segments:

        try:

            duration = max(
                float(
                    segment.get(
                        "end",
                        0.0,
                    )
                )
                for segment in segments
            )

        except (
            ValueError,
            TypeError,
        ):

            duration = None

    # -----------------------------------------------------
    # CLIP ANALYSIS
    # -----------------------------------------------------

    clip_analysis = run_clip_analysis(
        video_path=video_path,
        transcript=transcript,
        duration=duration,
        max_clips=max_clips,
    )

    clip_analysis_path = save_json(
        clip_analysis,
        output
        / f"{pipeline_id}_clip_analysis.json",
    )

    # -----------------------------------------------------
    # VIDEO PROCESSING
    # -----------------------------------------------------

    clips_output_dir = (
        output
        / "clips"
    )

    processing = run_video_processing(
        video_path=video_path,
        clip_analysis=clip_analysis,
        output_dir=clips_output_dir,
        make_vertical=make_vertical,
    )

    processing_path = save_json(
        processing,
        output
        / f"{pipeline_id}_processing.json",
    )

    # -----------------------------------------------------
    # OPTIONAL SCRIPT
    # -----------------------------------------------------

    script = None
    script_path = None

    if topic:

        research = run_research(
            topic=topic,
            reference_url=reference_url,
            limit=10,
        )

        source_analysis = run_source_analysis(
            topic=topic,
            research=research,
            reference_url=reference_url,
        )

        script = run_script_generation(
            topic=topic,
            research=source_analysis,
            reference_url=reference_url,
        )

        script_path = save_json(
            script,
            output
            / f"{pipeline_id}_script.json",
        )

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    return {
        "pipeline_id": pipeline_id,
        "version": PIPELINE_VERSION,
        "mode": "video",
        "video_path": video_path,
        "topic": topic,
        "reference_url": reference_url,
        "transcription": transcript,
        "clip_analysis": clip_analysis,
        "processing": processing,
        "script": script,
        "artifacts": {
            "transcript": transcript_path,
            "clip_analysis": clip_analysis_path,
            "processing": processing_path,
            "script": script_path,
        },
    }


# =========================================================
# PIPELINE STATUS
# =========================================================

def summarize_pipeline(
    result: dict,
) -> dict:
    """
    Create a compact status summary for the UI.
    """

    transcription = result.get(
        "transcription",
        {},
    )

    clip_analysis = result.get(
        "clip_analysis",
        {},
    )

    analysis = clip_analysis.get(
        "analysis",
        {},
    )

    processing = result.get(
        "processing",
        {},
    )

    return {
        "pipeline_id": result.get(
            "pipeline_id"
        ),
        "mode": result.get(
            "mode"
        ),
        "status": "completed",
        "source_video": result.get(
            "video_path"
        ),
        "transcript_segments": (
            transcription.get(
                "segment_count",
                0,
            )
        ),
        "clip_candidates": (
            analysis.get(
                "clip_count",
                0,
            )
        ),
        "processed_clips": (
            processing.get(
                "clip_count",
                0,
            )
        ),
        "script_generated": (
            result.get(
                "script"
            )
            is not None
        ),
    }


# =========================================================
# SAFE PIPELINE RUNNER
# =========================================================

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
) -> dict:
    """
    Execute the video pipeline and return a structured
    success/failure response.

    This wrapper is intended for Streamlit, GitHub jobs,
    workers, and future automation.
    """

    try:

        result = run_video_pipeline(
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
        )

        result["success"] = True

        result["summary"] = (
            summarize_pipeline(
                result
            )
        )

        return result

    except Exception as exc:

        return {
            "success": False,
            "status": "failed",
            "error": str(exc),
            "video_path": str(
                video_path
            ),
            "topic": topic,
            "reference_url": reference_url,
        }


# =========================================================
# SAVE FINAL PIPELINE RESULT
# =========================================================

def save_pipeline_result(
    result: dict,
    output_path: str | Path,
) -> str:
    """
    Save complete pipeline execution result.
    """

    return save_json(
        result,
        output_path,
    )
