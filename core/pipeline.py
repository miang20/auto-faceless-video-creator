"""
Pro V2 Pipeline

Coordinates:
research -> source analysis -> download -> transcription ->
clip analysis -> story generation -> final rendering

The existing downloader/transcription infrastructure remains untouched.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from .clip_analyzer import (
    DEFAULT_TOP_CLIPS,
    DEFAULT_CLIP_DURATION,
    build_clip_analysis_report,
)
from .downloader import download_video
from .research import research_topic
from .script_generator import build_script_report
from .source_analyzer import (
    analyze_sources,
    build_analysis_report,
)
from .transcription import transcribe_video
from .video_processor import (
    build_video_report,
    process_video,
)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_dir(path: str) -> None:
    os.makedirs(
        path,
        exist_ok=True,
    )


def _save_json(
    data: Dict[str, Any],
    path: str,
) -> str:

    _ensure_dir(
        os.path.dirname(
            os.path.abspath(path)
        )
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            data,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return path


def _normalize_segments(
    transcript: Any,
) -> List[Dict[str, Any]]:

    if transcript is None:
        return []

    if isinstance(
        transcript,
        dict,
    ):

        for key in (
            "segments",
            "transcript",
            "results",
            "items",
        ):
            if isinstance(
                transcript.get(key),
                list,
            ):
                transcript = transcript[key]
                break

    if not isinstance(
        transcript,
        list,
    ):
        return []

    return [
        item
        for item in transcript
        if isinstance(
            item,
            dict,
        )
    ]


def _extract_research_sources(
    research: Any,
) -> List[Dict[str, Any]]:

    if not isinstance(
        research,
        dict,
    ):
        return []

    for key in (
        "sources",
        "results",
        "videos",
        "items",
    ):
        value = research.get(key)

        if isinstance(
            value,
            list,
        ):
            return [
                item
                for item in value
                if isinstance(
                    item,
                    dict,
                )
            ]

    return []


def _pick_primary_source(
    sources: Sequence[Dict[str, Any]],
    reference_url: str = "",
) -> Optional[Dict[str, Any]]:

    if not sources:
        return None

    reference_url = str(
        reference_url or ""
    ).strip()

    if reference_url:

        for source in sources:

            url = str(
                source.get("url")
                or source.get("video_url")
                or source.get("webpage_url")
                or ""
            ).strip()

            if url == reference_url:
                return source

    return max(
        sources,
        key=lambda item: _safe_float(
            item.get(
                "score",
                item.get(
                    "quality_score",
                    item.get(
                        "source_score",
                        0.0,
                    ),
                ),
            )
        ),
    )


def _download_result_path(
    result: Any,
) -> str:

    if isinstance(
        result,
        str,
    ):
        return result

    if not isinstance(
        result,
        dict,
    ):
        return ""

    for key in (
        "path",
        "file_path",
        "video_path",
        "output_path",
        "downloaded_path",
        "filename",
    ):
        value = result.get(key)

        if value:
            return str(value)

    return ""


def _transcript_from_result(
    result: Any,
) -> List[Dict[str, Any]]:

    if isinstance(
        result,
        list,
    ):
        return _normalize_segments(
            result
        )

    if isinstance(
        result,
        dict,
    ):

        for key in (
            "segments",
            "transcript",
            "results",
            "items",
        ):
            value = result.get(key)

            if isinstance(
                value,
                list,
            ):
                return _normalize_segments(
                    value
                )

    return []


def _call_download(
    url: str,
    output_dir: str,
    **kwargs: Any,
) -> Any:

    """
    Keep compatibility with different downloader signatures.

    The first call uses the standard URL/output directory contract.
    """

    try:
        return download_video(
            url,
            output_dir,
            **kwargs,
        )
    except TypeError:

        try:
            return download_video(
                url,
                output_dir,
            )
        except TypeError:
            return download_video(
                url
            )


def _call_transcription(
    video_path: str,
    **kwargs: Any,
) -> Any:

    try:
        return transcribe_video(
            video_path,
            **kwargs,
        )
    except TypeError:
        return transcribe_video(
            video_path
        )


def run_research_stage(
    topic: str,
    reference_url: str = "",
    research_dir: str = "research",
    max_sources: int = 12,
) -> Dict[str, Any]:

    _ensure_dir(
        research_dir
    )

    try:
        result = research_topic(
            topic=topic,
            reference_url=reference_url,
            max_sources=max_sources,
        )
    except TypeError:

        try:
            result = research_topic(
                topic,
                reference_url,
                max_sources,
            )
        except TypeError:
            result = research_topic(
                topic
            )

    if isinstance(
        result,
        list,
    ):
        result = {
            "topic": topic,
            "reference_url": reference_url,
            "sources": result,
        }

    if not isinstance(
        result,
        dict,
    ):
        result = {
            "topic": topic,
            "reference_url": reference_url,
            "sources": [],
        }

    _save_json(
        result,
        os.path.join(
            research_dir,
            "research.json",
        ),
    )

    return result


def run_source_analysis_stage(
    research: Dict[str, Any],
    topic: str = "",
    analysis_dir: str = "analysis",
    max_sources: int = 10,
) -> Dict[str, Any]:

    _ensure_dir(
        analysis_dir
    )

    sources = _extract_research_sources(
        research
    )

    try:
        result = analyze_sources(
            sources,
            topic=topic,
            max_sources=max_sources,
        )
    except TypeError:

        try:
            result = analyze_sources(
                sources,
                topic,
            )
        except TypeError:
            result = analyze_sources(
                sources
            )

    if isinstance(
        result,
        list,
    ):
        result = {
            "topic": topic,
            "sources": result,
        }

    if not isinstance(
        result,
        dict,
    ):
        result = {
            "topic": topic,
            "sources": sources,
            "analyzed_sources": [],
        }

    report = build_analysis_report(
        result
    )

    if not isinstance(
        report,
        dict,
    ):
        report = result

    _save_json(
        report,
        os.path.join(
            analysis_dir,
            "source_analysis.json",
        ),
    )

    return report


def run_download_stage(
    source: Dict[str, Any],
    output_dir: str,
) -> str:

    _ensure_dir(
        output_dir
    )

    url = str(
        source.get("url")
        or source.get("video_url")
        or source.get("webpage_url")
        or ""
    ).strip()

    if not url:
        raise ValueError(
            "Selected source does not contain a usable URL."
        )

    result = _call_download(
        url,
        output_dir,
    )

    video_path = _download_result_path(
        result
    )

    if not video_path:
        raise RuntimeError(
            "Downloader completed but no video path was returned."
        )

    if not os.path.isabs(
        video_path
    ):
        candidate = os.path.join(
            output_dir,
            video_path,
        )

        if os.path.exists(
            candidate
        ):
            video_path = candidate

    if not os.path.exists(
        video_path
    ):
        raise FileNotFoundError(
            f"Downloaded video was not found: {video_path}"
        )

    return video_path


def run_transcription_stage(
    video_path: str,
    transcription_dir: str,
) -> List[Dict[str, Any]]:

    _ensure_dir(
        transcription_dir
    )

    result = _call_transcription(
        video_path
    )

    segments = _transcript_from_result(
        result
    )

    transcript_path = os.path.join(
        transcription_dir,
        "transcript.json",
    )

    _save_json(
        {
            "video_path": video_path,
            "segments": segments,
        },
        transcript_path,
    )

    return segments


def run_clip_analysis_stage(
    video_path: str,
    transcript_segments: Sequence[Dict[str, Any]],
    analysis_dir: str,
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
    target_duration: float = DEFAULT_CLIP_DURATION,
) -> Dict[str, Any]:

    _ensure_dir(
        analysis_dir
    )

    result = build_clip_analysis_report(
        video_path=video_path,
        transcript_segments=transcript_segments,
        duration=duration,
        max_clips=max_clips,
        target_duration=target_duration,
    )

    _save_json(
        result,
        os.path.join(
            analysis_dir,
            "clip_analysis.json",
        ),
    )

    return result


def run_script_stage(
    clip_analysis: Dict[str, Any],
    topic: str,
    target_duration: float,
    caption_style: str,
    caption_settings: Optional[Dict[str, Any]],
    editing_settings: Optional[Dict[str, Any]],
    output_dir: str,
) -> Dict[str, Any]:

    _ensure_dir(
        output_dir
    )

    result = build_script_report(
        clip_analysis=clip_analysis,
        target_duration=target_duration,
        topic=topic,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    _save_json(
        result,
        os.path.join(
            output_dir,
            "script.json",
        ),
    )

    return result


def run_render_stage(
    video_path: str,
    script_report: Dict[str, Any],
    output_path: str,
    target_duration: float,
    caption_style: str,
    caption_settings: Optional[Dict[str, Any]],
    editing_settings: Optional[Dict[str, Any]],
) -> str:

    script = (
        script_report.get(
            "script",
            script_report,
        )
        if isinstance(
            script_report,
            dict,
        )
        else {}
    )

    return process_video(
        input_path=video_path,
        output_path=output_path,
        script=script,
        target_duration=target_duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )


def run_video_pipeline(
    video_path: str,
    topic: str = "",
    output_dir: str = "output",
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
    target_duration: float = DEFAULT_CLIP_DURATION,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    """
    Process an already-downloaded video.

    This is the main path used by the existing worker.
    """

    _ensure_dir(
        output_dir
    )

    if not os.path.exists(
        video_path
    ):
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    transcription_dir = os.path.join(
        output_dir,
        "transcription",
    )

    analysis_dir = os.path.join(
        output_dir,
        "analysis",
    )

    script_dir = os.path.join(
        output_dir,
        "script",
    )

    transcript_segments = (
        run_transcription_stage(
            video_path,
            transcription_dir,
        )
    )

    clip_analysis = (
        run_clip_analysis_stage(
            video_path=video_path,
            transcript_segments=transcript_segments,
            analysis_dir=analysis_dir,
            duration=duration,
            max_clips=max_clips,
            target_duration=target_duration,
        )
    )

    script_report = run_script_stage(
        clip_analysis=clip_analysis,
        topic=topic,
        target_duration=target_duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
        output_dir=script_dir,
    )

    final_output = os.path.join(
        output_dir,
        "final_short.mp4",
    )

    render_path = run_render_stage(
        video_path=video_path,
        script_report=script_report,
        output_path=final_output,
        target_duration=target_duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    video_report = build_video_report(
        render_path,
        script_report.get(
            "script",
            {},
        ),
    )

    _save_json(
        video_report,
        os.path.join(
            output_dir,
            "video_report.json",
        ),
    )

    return {
        "success": True,
        "video_path": video_path,
        "transcript": {
            "segments": transcript_segments,
            "count": len(
                transcript_segments
            ),
        },
        "clip_analysis": clip_analysis,
        "script": script_report,
        "output_path": render_path,
        "video_report": video_report,
    }


def execute_video_pipeline(
    video_path: str,
    topic: str = "",
    output_dir: str = "output",
    duration: Optional[float] = None,
    max_clips: int = DEFAULT_TOP_CLIPS,
    target_duration: float = DEFAULT_CLIP_DURATION,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return run_video_pipeline(
        video_path=video_path,
        topic=topic,
        output_dir=output_dir,
        duration=duration,
        max_clips=max_clips,
        target_duration=target_duration,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )


def run_topic_pipeline(
    topic: str,
    reference_url: str = "",
    output_dir: str = "output",
    research_dir: str = "research",
    analysis_dir: str = "analysis",
    download_dir: str = "downloads",
    target_duration: float = DEFAULT_CLIP_DURATION,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
    max_sources: int = 10,
    max_clips: int = DEFAULT_TOP_CLIPS,
) -> Dict[str, Any]:

    """
    Full Pro V2 topic workflow.

    Research multiple sources first, select the strongest source, then feed
    that source through the existing proven processing pipeline.
    """

    research = run_research_stage(
        topic=topic,
        reference_url=reference_url,
        research_dir=research_dir,
        max_sources=max_sources,
    )

    source_analysis = run_source_analysis_stage(
        research=research,
        topic=topic,
        analysis_dir=analysis_dir,
        max_sources=max_sources,
    )

    sources = _extract_research_sources(
        source_analysis
    )

    if not sources:
        sources = _extract_research_sources(
            research
        )

    primary_source = _pick_primary_source(
        sources,
        reference_url=reference_url,
    )

    if not primary_source:
        raise RuntimeError(
            "Research completed but no usable video source was found."
        )

    downloaded_video = run_download_stage(
        source=primary_source,
        output_dir=download_dir,
    )

    processing_output = os.path.join(
        output_dir,
        "video",
    )

    result = run_video_pipeline(
        video_path=downloaded_video,
        topic=topic,
        output_dir=processing_output,
        target_duration=target_duration,
        max_clips=max_clips,
        caption_style=caption_style,
        caption_settings=caption_settings,
        editing_settings=editing_settings,
    )

    result["research"] = research
    result["source_analysis"] = source_analysis
    result["selected_source"] = primary_source

    _save_json(
        {
            "topic": topic,
            "reference_url": reference_url,
            "selected_source": primary_source,
            "output_path": result.get(
                "output_path"
            ),
        },
        os.path.join(
            output_dir,
            "pipeline_result.json",
        ),
    )

    return result


def execute_topic_pipeline(
    topic: str,
    reference_url: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:

    return run_topic_pipeline(
        topic=topic,
        reference_url=reference_url,
        **kwargs,
    )


def process_reference_video(
    video_path: str,
    topic: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:

    return run_video_pipeline(
        video_path=video_path,
        topic=topic,
        **kwargs,
    )
