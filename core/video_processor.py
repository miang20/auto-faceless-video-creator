"""
Pro V2 Video Processor

Takes a generated story/edit blueprint and renders a vertical 9:16 video.

Important:
- No narration is generated.
- Source audio/dialogue is preserved.
- FFmpeg remains the rendering engine.
- Missing optional features gracefully fall back instead of breaking the job.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_OUTPUT_WIDTH = 1080
DEFAULT_OUTPUT_HEIGHT = 1920
DEFAULT_FPS = 30
DEFAULT_CRF = 20


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    return max(
        minimum,
        min(maximum, value),
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _run_command(
    command: Sequence[str],
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:

    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg was not found. Please ensure FFmpeg is installed "
            "and available in PATH."
        )


def _probe_duration(video_path: str) -> float:
    if not os.path.exists(video_path):
        return 0.0

    try:
        result = _run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            timeout=15,
        )

        if result.returncode != 0:
            return 0.0

        return max(
            0.0,
            _safe_float(result.stdout.strip()),
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return 0.0


def _probe_dimensions(
    video_path: str,
) -> Tuple[int, int]:

    try:
        result = _run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=s=x:p=0",
                video_path,
            ],
            timeout=15,
        )

        if result.returncode != 0:
            return 0, 0

        raw = result.stdout.strip()

        if "x" not in raw:
            return 0, 0

        width, height = raw.split("x", 1)

        return (
            _safe_int(width),
            _safe_int(height),
        )

    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ):
        return 0, 0


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(
        os.path.abspath(path)
    )

    if parent:
        os.makedirs(
            parent,
            exist_ok=True,
        )


def _normalize_clip(
    clip: Dict[str, Any],
) -> Dict[str, Any]:

    start = max(
        0.0,
        _safe_float(
            clip.get(
                "source_start",
                clip.get(
                    "start",
                    clip.get("start_time", 0.0),
                ),
            )
        ),
    )

    end = _safe_float(
        clip.get(
            "source_end",
            clip.get(
                "end",
                clip.get("end_time", 0.0),
            ),
        )
    )

    duration = _safe_float(
        clip.get("source_duration")
        or clip.get("duration")
    )

    if end <= start:
        if duration > 0:
            end = start + duration
        else:
            end = start + 3.0

    return {
        "path": str(clip.get("path") or clip.get("local_path") or clip.get("file_path") or ""),
        "start": start,
        "end": max(
            start + 0.1,
            end,
        ),
        "duration": max(
            0.1,
            end - start,
        ),
        "role": str(
            clip.get(
                "role",
                clip.get(
                    "story_role",
                    "SETUP",
                ),
            )
        ).upper(),
        "score": _safe_float(
            clip.get("score")
        ),
        "text": _clean_text(
            clip.get("text")
        ),
    }


def _extract_timeline(
    script: Dict[str, Any],
) -> List[Dict[str, Any]]:

    if not isinstance(script, dict):
        return []

    timeline = script.get("timeline")

    if not isinstance(timeline, list):
        return []

    result = []

    for item in timeline:
        if isinstance(item, dict):
            normalized = _normalize_clip(item)

            if normalized["duration"] > 0:
                result.append(normalized)

    return result


def _escape_drawtext(text: str) -> str:
    """
    Escape text for FFmpeg drawtext filter syntax.
    """

    text = str(text)

    replacements = [
        ("\\", r"\\\\"),
        (":", r"\:"),
        ("'", r"\'"),
        ("%", r"\%"),
        # Escape filtergraph separators too: punctuation must not split a
        # drawtext expression and leave it without its required text option.
        (",", r"\,"),
        (";", r"\;"),
        ("[", r"\["),
        ("]", r"\]"),
    ]

    for old, new in replacements:
        text = text.replace(
            old,
            new,
        )

    return text


def _find_font_file(
    requested_font: str = "",
) -> Optional[str]:

    candidates = []

    requested_font = _clean_text(
        requested_font
    )

    if requested_font:
        candidates.extend(
            [
                requested_font,
                f"/system/fonts/{requested_font}.ttf",
                f"/usr/share/fonts/truetype/dejavu/{requested_font}.ttf",
            ]
        )

    candidates.extend(
        [
            "/system/fonts/Roboto-Bold.ttf",
            "/system/fonts/Roboto-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def _caption_position(
    position: str,
) -> Tuple[str, str]:

    position = (
        _clean_text(position)
        .lower()
    )

    if position in {
        "top",
        "top center",
        "upper",
    }:
        return (
            "(w-text_w)/2",
            "h*0.14",
        )

    if position in {
        "bottom",
        "bottom center",
        "lower",
        "lower-third",
        "lower third",
        "viral",
        "center",
    }:
        return (
            "(w-text_w)/2",
            "h*0.64",
        )

    return (
        "(w-text_w)/2",
        "h*0.64",
    )


def _ffmpeg_caption_color(value: Any, fallback: str) -> str:
    color = _clean_text(value) or fallback
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
        return "0x" + color.lstrip("#")
    return color


def _dynamic_caption_filters(
    text: str,
    duration: float,
    caption_settings: Dict[str, Any],
) -> List[str]:
    """Create timed 1-3 word captions with a yellow active-word overlay."""
    if not text or caption_settings.get("enabled", True) is False:
        return []

    words = _clean_text(text).split()
    if not words:
        return []

    font_size = max(24, min(110, _safe_int(caption_settings.get("font_size", 58), 58)))
    style = _clean_text(caption_settings.get("style", "Bold Viral")).lower()
    if style == "impact":
        font_size = max(font_size, 64)

    stroke = bool(caption_settings.get("stroke", True))
    shadow = bool(caption_settings.get("shadow", True))
    box = bool(caption_settings.get("box", caption_settings.get("background_box", False)))
    if style == "clean":
        stroke = False
        shadow = False

    normal_color = _ffmpeg_caption_color(caption_settings.get("text_color", "white"), "white")
    active_color = _ffmpeg_caption_color(caption_settings.get("highlight_color", "yellow"), "yellow")
    font = _find_font_file(caption_settings.get("font", ""))
    font_option = f"fontfile='{_escape_drawtext(font)}'" if font else "font='DejaVu Sans'"
    _, y = _caption_position(caption_settings.get("position", "lower-third"))
    duration = max(0.1, _safe_float(duration, 0.1))
    word_step = duration / len(words)
    filters: List[str] = []

    def drawtext(label: str, color: str, x_expr: str, start: float, end: float) -> str:
        parts = [
            "drawtext",
            font_option,
            f"text='{_escape_drawtext(label)}'",
            f"fontsize={font_size}",
            f"fontcolor={color}",
            f"x={x_expr}",
            f"y={y}",
        ]
        if stroke:
            parts.extend(["borderw=3", "bordercolor=black"])
        if shadow:
            parts.extend(["shadowx=2", "shadowy=2", "shadowcolor=black@0.65"])
        if box:
            parts.extend(["box=1", "boxcolor=black@0.55", "boxborderw=10"])
        parts.append(f"enable='between(t\\,{start:.3f}\\,{end:.3f})'")
        return "=".join(parts[:1]) + "=" + ":".join(parts[1:])

    # Group up to three words together. A yellow overlay advances word by word.
    for group_start in range(0, len(words), 3):
        group = words[group_start:group_start + 3]
        first_index = group_start
        last_index = group_start + len(group)
        group_start_time = first_index * word_step
        group_end_time = min(duration, last_index * word_step)
        phrase = " ".join(group)

        # Approximate text width so the active word overlays its place in the phrase.
        phrase_width = sum(max(1, len(word)) * font_size * 0.54 for word in group)
        phrase_width += max(0, len(group) - 1) * font_size * 0.32
        phrase_x = f"(w-{phrase_width:.1f})/2"
        filters.append(drawtext(phrase, normal_color, phrase_x, group_start_time, group_end_time))

        prefix_width = 0.0
        for offset, word in enumerate(group):
            word_index = group_start + offset
            word_start = word_index * word_step
            word_end = min(duration, (word_index + 1) * word_step)
            word_x = f"(w-{phrase_width:.1f})/2+{prefix_width:.1f}"
            filters.append(drawtext(word, active_color, word_x, word_start, word_end))
            prefix_width += max(1, len(word)) * font_size * 0.54 + font_size * 0.32

    return filters


def _caption_filter(
    caption_settings: Dict[str, Any],
) -> Optional[str]:

    if not caption_settings:
        return None

    if caption_settings.get(
        "enabled",
        True,
    ) is False:
        return None

    style = _clean_text(
        caption_settings.get(
            "style",
            "Bold Viral",
        )
    ).lower()

    font_size = _safe_int(
        caption_settings.get(
            "font_size",
            54,
        ),
        54,
    )

    font_size = max(
        24,
        min(
            110,
            font_size,
        ),
    )

    position = caption_settings.get(
        "position",
        "center",
    )

    x, y = _caption_position(
        position
    )

    text_color = _clean_text(
        caption_settings.get(
            "text_color",
            "white",
        )
    ) or "white"

    highlight_color = _clean_text(
        caption_settings.get(
            "highlight_color",
            "yellow",
        )
    ) or "yellow"

    stroke_enabled = bool(
        caption_settings.get(
            "stroke",
            True,
        )
    )

    shadow_enabled = bool(
        caption_settings.get(
            "shadow",
            True,
        )
    )

    box_enabled = bool(
        caption_settings.get(
            "box",
            False,
        )
    )

    font = _find_font_file(
        caption_settings.get(
            "font",
            "",
        )
    )

    if font:
        font_option = (
            f"fontfile='{_escape_drawtext(font)}'"
        )
    else:
        font_option = "font='DejaVu Sans'"

    if style == "minimal bottom":
        x, y = _caption_position(
            "bottom"
        )

    elif style == "clean":
        stroke_enabled = False
        shadow_enabled = False

    elif style == "impact":
        font_size = max(
            font_size,
            64,
        )

    elif style == "karaoke":
        text_color = highlight_color

    elif style == "mrbeast-style inspired":
        stroke_enabled = True
        shadow_enabled = True
        box_enabled = False

    parts = [
        "drawtext",
        font_option,
        f"fontsize={font_size}",
        f"fontcolor={text_color}",
        f"x={x}",
        f"y={y}",
    ]

    if stroke_enabled:
        parts.extend(
            [
                "borderw=3",
                "bordercolor=black",
            ]
        )

    if shadow_enabled:
        parts.extend(
            [
                "shadowx=2",
                "shadowy=2",
                "shadowcolor=black@0.65",
            ]
        )

    if box_enabled:
        parts.extend(
            [
                "box=1",
                "boxcolor=black@0.55",
                "boxborderw=12",
            ]
        )

    return parts[0] + "=" + ":".join(parts[1:])


def _vertical_crop_filter(
    width: int,
    height: int,
    output_width: int,
    output_height: int,
) -> str:

    if width <= 0 or height <= 0:
        return (
            f"scale={output_width}:{output_height}"
            ":force_original_aspect_ratio=increase,"
            f"crop={output_width}:{output_height}"
        )

    source_ratio = width / height
    target_ratio = output_width / output_height

    if source_ratio > target_ratio:
        # Source is wider. Crop left/right.
        return (
            f"scale=-2:{output_height},"
            f"crop={output_width}:{output_height}"
        )

    return (
        f"scale={output_width}:-2,"
        f"crop={output_width}:{output_height}"
    )


def _zoom_filter(
    duration: float,
    enabled: bool = True,
) -> str:

    if not enabled:
        return "scale=iw:ih"

    duration = max(
        0.5,
        duration,
    )

    # Very subtle continuous punch-in.
    # It avoids aggressive shaking and keeps the original frame stable.
    return (
        "zoompan="
        "z='min(zoom+0.0008,1.08)':"
        f"d='1':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        "s=1080x1920"
    )


def _build_video_filter(
    width: int,
    height: int,
    output_width: int,
    output_height: int,
    duration: float,
    editing_settings: Dict[str, Any],
    caption_settings: Optional[Dict[str, Any]] = None,
    caption_text: str = "",
) -> str:

    filters = []

    filters.append(
        _vertical_crop_filter(
            width,
            height,
            output_width,
            output_height,
        )
    )

    dynamic_zoom = bool(
        editing_settings.get(
            "dynamic_zoom",
            True,
        )
    )

    punch_in = bool(
        editing_settings.get(
            "punch_in",
            True,
        )
    )

    if dynamic_zoom and punch_in:
        # Actual slow punch-in; output stays 1080x1920 at a fixed 30 fps.
        filters.append(
            "zoompan=z='min(zoom+0.0008,1.08)':d=1:"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            "s=1080x1920:fps=30"
        )

    if caption_settings and caption_text:
        filters.extend(
            _dynamic_caption_filters(
                caption_text,
                duration,
                caption_settings,
            )
        )

    return ",".join(filters)


def _detect_internal_silence(
    input_path: str,
    start: float,
    duration: float,
) -> List[Tuple[float, float]]:
    """Find internal quiet gaps so matching video frames and audio can both be removed."""
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.3f}",
        "-t", f"{duration:.3f}", "-i", input_path, "-vn",
        "-af", "silencedetect=noise=-42dB:d=0.35",
        "-f", "null", "-",
    ]
    try:
        result = _run_command(command, timeout=45)
    except (OSError, subprocess.SubprocessError):
        return []

    log = (result.stderr or "") + "\n" + (result.stdout or "")
    starts = re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", log)
    ends = re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", log)
    intervals: List[Tuple[float, float]] = []
    for raw_start, raw_end in zip(starts, ends):
        silence_start, silence_end = float(raw_start), float(raw_end)
        # Keep only internal gaps. Trimming at clip edges can cut meaningful
        # ambience or make dialogue feel abruptly clipped.
        if (
            silence_end - silence_start >= 0.35
            and silence_start >= 0.08
            and silence_end <= duration - 0.08
        ):
            intervals.append((silence_start, silence_end))
    return intervals


def _render_single_segment(
    input_path: str,
    output_path: str,
    clip: Dict[str, Any],
    output_width: int,
    output_height: int,
    fps: int,
    editing_settings: Dict[str, Any],
    caption_settings: Optional[Dict[str, Any]],
) -> str:

    segment_input_path = str(clip.get("path") or input_path)
    if not os.path.isfile(segment_input_path):
        raise FileNotFoundError(f"Clip source file not found: {segment_input_path}")
    width, height = _probe_dimensions(segment_input_path)
    start = _safe_float(clip.get("start"))

    duration = _safe_float(
        clip.get("duration")
    )

    duration = max(
        0.1,
        duration,
    )

    remove_silence = bool(editing_settings.get("remove_silence", False))
    silences = _detect_internal_silence(segment_input_path, start, duration) if remove_silence else []
    effective_duration = max(0.1, duration - sum(end - begin for begin, end in silences))

    video_filter = _build_video_filter(
        width,
        height,
        output_width,
        output_height,
        effective_duration,
        editing_settings,
        caption_settings,
        caption_text=_clean_text(clip.get("text", "")),
    )

    command = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}",
        "-i", segment_input_path, "-t", f"{duration:.3f}",
    ]

    if silences:
        silence_expression = "+".join(
            f"between(t\\,{begin:.3f}\\,{end:.3f})"
            for begin, end in silences
        )
        video_select = f"select='not({silence_expression})',setpts=N/(FRAME_RATE*TB)"
        audio_select = f"aselect='not({silence_expression})',asetpts=N/SR/TB"
        audio_chain = audio_select
        if bool(editing_settings.get("audio_normalize", editing_settings.get("normalize_audio", True))):
            audio_chain += ",loudnorm=I=-14:TP=-1.5:LRA=11"
        command.extend([
            "-filter_complex",
            f"[0:v:0]{video_select},{video_filter}[v];[0:a:0]{audio_chain}[a]",
            "-map", "[v]", "-map", "[a]",
        ])
    else:
        command.extend([
            "-vf", video_filter,
            "-map", "0:v:0", "-map", "0:a?",
        ])

    command.extend([
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", str(_safe_int(editing_settings.get("crf", DEFAULT_CRF), DEFAULT_CRF)),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
    ])

    if not silences and bool(editing_settings.get("audio_normalize", editing_settings.get("normalize_audio", True))):
        command.extend(["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"])

    command.extend(
        [
            "-movflags",
            "+faststart",
            output_path,
        ]
    )

    result = _run_command(
        command,
        timeout=900,
    )

    if result.returncode != 0:
        stderr_text = result.stderr or ""
        # FFmpeg versions differ in how they report malformed drawtext
        # expressions. Do not depend on one exact error string: if captions
        # were enabled and the filter graph reports a drawtext failure, retry
        # this segment once with captions disabled. Other render failures still
        # fail normally and retain the original FFmpeg diagnostic.
        caption_filter_failure = (
            caption_settings
            and caption_settings.get("enabled", True) is not False
            and (
                "drawtext" in stderr_text.lower()
                or "Either text, a valid file, a timecode or text source must be provided" in stderr_text
            )
        )
        if caption_filter_failure:
            # Keep the job renderable if an individual caption trips FFmpeg's
            # drawtext parser. Retry this segment with captions disabled only;
            # preserve the selected clip, crop/zoom, audio, and all other edits.
            print(
                "[V2 RENDER] Caption parser rejected text; retrying this "
                "segment without captions."
            )
            safe_captions = dict(caption_settings or {})
            safe_captions["enabled"] = False
            return _render_single_segment(
                input_path=input_path,
                output_path=output_path,
                clip=clip,
                output_width=output_width,
                output_height=output_height,
                fps=fps,
                editing_settings=editing_settings,
                caption_settings=safe_captions,
            )
        raise RuntimeError(
            "FFmpeg failed while rendering segment:\n"
            + stderr_text[-4000:]
        )

    return output_path


def _write_concat_file(
    paths: Sequence[str],
    concat_path: str,
) -> None:

    with open(
        concat_path,
        "w",
        encoding="utf-8",
    ) as handle:

        for path in paths:
            safe_path = os.path.abspath(
                path
            ).replace(
                "'",
                "'\\''",
            )

            handle.write(
                f"file '{safe_path}'\n"
            )


def _concat_segments(
    segment_paths: Sequence[str],
    output_path: str,
    editing_settings: Dict[str, Any],
) -> str:

    if not segment_paths:
        raise ValueError(
            "No rendered segments were available."
        )

    if len(segment_paths) == 1:
        shutil.copy2(
            segment_paths[0],
            output_path,
        )
        return output_path

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
    ) as handle:
        concat_path = handle.name

    try:
        _write_concat_file(
            segment_paths,
            concat_path,
        )

        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_path,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(
                _safe_int(
                    editing_settings.get(
                        "crf",
                        DEFAULT_CRF,
                    ),
                    DEFAULT_CRF,
                )
            ),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            output_path,
        ]

        result = _run_command(
            command,
            timeout=1200,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg failed while concatenating segments:\n"
                + result.stderr[-4000:]
            )

    finally:
        try:
            os.remove(
                concat_path
            )
        except OSError:
            pass

    return output_path


def _trim_to_target_duration(
    input_path: str,
    output_path: str,
    target_duration: float,
) -> str:

    target_duration = max(
        0.1,
        target_duration,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-t",
        f"{target_duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(DEFAULT_CRF),
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]

    result = _run_command(
        command,
        timeout=900,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed while applying target duration:\n"
            + result.stderr[-4000:]
        )

    return output_path


def process_video(
    input_path: str,
    output_path: str,
    script: Optional[Dict[str, Any]] = None,
    clip_analysis: Optional[Dict[str, Any]] = None,
    target_duration: Optional[float] = None,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[Dict[str, Any]] = None,
    editing_settings: Optional[Dict[str, Any]] = None,
    output_width: int = DEFAULT_OUTPUT_WIDTH,
    output_height: int = DEFAULT_OUTPUT_HEIGHT,
    fps: int = DEFAULT_FPS,
) -> str:

    _require_ffmpeg()

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Input video not found: {input_path}"
        )

    _ensure_parent(
        output_path
    )

    script = dict(
        script or {}
    )

    editing = dict(
        editing_settings
        or script.get("editing")
        or {}
    )

    captions = dict(
        caption_settings
        or script.get("caption")
        or {}
    )

    if "style" not in captions:
        captions["style"] = (
            caption_style
            or "Bold Viral"
        )

    timeline = _extract_timeline(
        script
    )

    if not timeline and isinstance(
        clip_analysis,
        dict,
    ):

        raw_clips = clip_analysis.get(
            "clips"
        )

        if not isinstance(
            raw_clips,
            list,
        ):
            raw_clips = (
                clip_analysis
                .get("analysis", {})
                .get("clips", [])
            )

        if isinstance(
            raw_clips,
            list,
        ):
            timeline = [
                _normalize_clip(
                    clip
                )
                for clip in raw_clips
                if isinstance(
                    clip,
                    dict,
                )
            ]

    if not timeline:
        raise ValueError(
            "No usable clip timeline was found."
        )

    requested_duration = (
        _safe_float(
            target_duration
        )
        if target_duration is not None
        else _safe_float(
            script.get(
                "target_duration",
                0.0,
            )
        )
    )

    temp_dir = tempfile.mkdtemp(
        prefix="pro_v2_render_"
    )

    segment_paths: List[str] = []

    try:

        for index, clip in enumerate(
            timeline
        ):

            segment_path = os.path.join(
                temp_dir,
                f"segment_{index:03d}.mp4",
            )

            _render_single_segment(
                input_path=input_path,
                output_path=segment_path,
                clip=clip,
                output_width=output_width,
                output_height=output_height,
                fps=fps,
                editing_settings=editing,
                caption_settings=captions,
            )

            segment_paths.append(
                segment_path
            )

        combined_path = os.path.join(
            temp_dir,
            "combined.mp4",
        )

        _concat_segments(
            segment_paths,
            combined_path,
            editing,
        )

        if requested_duration > 0:

            actual_duration = _probe_duration(
                combined_path
            )

            # Only trim when the story is materially longer than requested.
            # We never pad a short video with meaningless content.
            if actual_duration > requested_duration + 0.25:

                trimmed_path = os.path.join(
                    temp_dir,
                    "trimmed.mp4",
                )

                _trim_to_target_duration(
                    combined_path,
                    trimmed_path,
                    requested_duration,
                )

                shutil.copy2(
                    trimmed_path,
                    output_path,
                )

            else:
                shutil.copy2(
                    combined_path,
                    output_path,
                )

        else:
            shutil.copy2(
                combined_path,
                output_path,
            )

        return output_path

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )


def render_video(
    input_path: str,
    output_path: str,
    script: Dict[str, Any],
    **kwargs: Any,
) -> str:

    return process_video(
        input_path=input_path,
        output_path=output_path,
        script=script,
        **kwargs,
    )


def process_video_file(
    input_path: str,
    output_path: str,
    script: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:

    return process_video(
        input_path=input_path,
        output_path=output_path,
        script=script,
        **kwargs,
    )


def build_video_report(
    output_path: str,
    script: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    duration = _probe_duration(
        output_path
    )

    width, height = _probe_dimensions(
        output_path
    )

    return {
        "output_path": output_path,
        "duration": round(
            duration,
            3,
        ),
        "width": width,
        "height": height,
        "aspect_ratio": (
            "9:16"
            if height > width
            else "other"
        ),
        "exists": os.path.exists(
            output_path
        ),
        "script": script or {},
    }


def save_video_report(
    report: Dict[str, Any],
    output_path: str,
) -> str:

    _ensure_parent(
        output_path
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            report,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return output_path
