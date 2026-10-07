from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# =========================================================
# CONFIG
# =========================================================

DEFAULT_OUTPUT_DIR = Path("output/clips")

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".m4v",
}


# =========================================================
# VALIDATION
# =========================================================

def ensure_ffmpeg() -> None:
    """
    Make sure FFmpeg is available.
    """

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg was not found on this system."
        )


def validate_video_path(
    video_path: str | Path,
) -> Path:
    """
    Validate an input video path.
    """

    path = Path(video_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Video not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Video path is not a file: {path}"
        )

    if (
        path.suffix.lower()
        not in VIDEO_EXTENSIONS
    ):
        raise ValueError(
            f"Unsupported video format: {path.suffix}"
        )

    return path


# =========================================================
# TIMESTAMP HELPERS
# =========================================================

def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def format_timestamp(
    seconds: float,
) -> str:
    """
    Convert seconds to HH:MM:SS.mmm.
    """

    seconds = max(
        0.0,
        float(seconds),
    )

    hours = int(
        seconds // 3600
    )

    minutes = int(
        (seconds % 3600) // 60
    )

    remaining = (
        seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{remaining:06.3f}"
    )


# =========================================================
# VIDEO INFORMATION
# =========================================================

def get_video_info(
    video_path: str | Path,
) -> dict:
    """
    Get basic video metadata through FFprobe.
    """

    ensure_ffmpeg()

    path = validate_video_path(
        video_path
    )

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        (
            "format=duration,size,"
            "format_name"
        ),
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

    except subprocess.CalledProcessError as exc:

        raise RuntimeError(
            "FFprobe failed while reading video information."
        ) from exc

    try:

        data = json.loads(
            result.stdout
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "FFprobe returned invalid JSON."
        ) from exc

    format_data = data.get(
        "format",
        {},
    )

    duration = float(
        format_data.get(
            "duration",
            0.0,
        )
        or 0.0
    )

    size = int(
        format_data.get(
            "size",
            0,
        )
        or 0
    )

    video_stream = None

    for stream in data.get(
        "streams",
        [],
    ):

        if stream.get(
            "codec_type"
        ) == "video":

            video_stream = stream
            break

    width = 0
    height = 0
    fps = 0.0
    codec = None

    if video_stream:

        width = int(
            video_stream.get(
                "width",
                0,
            )
            or 0
        )

        height = int(
            video_stream.get(
                "height",
                0,
            )
            or 0
        )

        codec = video_stream.get(
            "codec_name"
        )

        fps_value = video_stream.get(
            "r_frame_rate",
            "0/1",
        )

        try:

            numerator, denominator = (
                fps_value.split("/")
            )

            denominator = float(
                denominator
            )

            if denominator:
                fps = (
                    float(numerator)
                    / denominator
                )

        except (
            ValueError,
            ZeroDivisionError,
        ):
            fps = 0.0

    return {
        "path": str(path),
        "filename": path.name,
        "format": format_data.get(
            "format_name"
        ),
        "duration": duration,
        "duration_timestamp": format_timestamp(
            duration
        ),
        "size_bytes": size,
        "width": width,
        "height": height,
        "fps": round(
            fps,
            3,
        ),
        "codec": codec,
    }


# =========================================================
# OUTPUT PATH
# =========================================================

def create_output_directory(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Create and return output directory.
    """

    directory = Path(
        output_dir
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def build_clip_path(
    output_dir: str | Path,
    clip_number: int,
    extension: str = ".mp4",
) -> Path:
    """
    Build a deterministic output filename.
    """

    directory = create_output_directory(
        output_dir
    )

    extension = extension.lower()

    if not extension.startswith("."):
        extension = "." + extension

    return (
        directory
        / f"clip_{clip_number:03d}{extension}"
    )


# =========================================================
# SINGLE CLIP EXTRACTION
# =========================================================

def extract_clip(
    video_path: str | Path,
    start: float,
    end: float,
    output_path: str | Path,
    re_encode: bool = True,
) -> str:
    """
    Extract one clip from a source video.

    Re-encoding is the default because it gives reliable
    frame-accurate cuts and predictable output.
    """

    ensure_ffmpeg()

    source = validate_video_path(
        video_path
    )

    start = max(
        0.0,
        float(start),
    )

    end = max(
        start,
        float(end),
    )

    if end <= start:
        raise ValueError(
            "Clip end must be greater than clip start."
        )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    duration = end - start

    if re_encode:

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(duration),
            "-map",
            "0:v:0?",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output),
        ]

    else:

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(duration),
            "-c",
            "copy",
            str(output),
        ]

    try:

        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

    except subprocess.CalledProcessError as exc:

        error = (
            exc.stderr
            or "Unknown FFmpeg error."
        )

        raise RuntimeError(
            f"FFmpeg clip extraction failed: {error}"
        ) from exc

    if not output.exists():
        raise RuntimeError(
            f"FFmpeg finished but output was not created: "
            f"{output}"
        )

    return str(output)


# =========================================================
# CLIP BATCH PROCESSING
# =========================================================

def process_clip_candidates(
    video_path: str | Path,
    clips: list[dict],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    re_encode: bool = True,
) -> list[dict]:
    """
    Convert analyzed clip candidates into actual video files.
    """

    source = validate_video_path(
        video_path
    )

    directory = create_output_directory(
        output_dir
    )

    results = []

    for index, clip in enumerate(
        clips,
        start=1,
    ):

        start = float(
            clip.get(
                "start",
                0.0,
            )
        )

        end = float(
            clip.get(
                "end",
                0.0,
            )
        )

        if end <= start:
            continue

        output_path = build_clip_path(
            output_dir=directory,
            clip_number=index,
        )

        extracted_path = extract_clip(
            video_path=source,
            start=start,
            end=end,
            output_path=output_path,
            re_encode=re_encode,
        )

        result = dict(clip)

        result["clip_number"] = index
        result["source_video"] = str(
            source
        )
        result["output_path"] = extracted_path
        result["processed"] = True

        results.append(
            result
        )

    return results


# =========================================================
# VERTICAL VIDEO SUPPORT
# =========================================================

def convert_to_vertical(
    input_path: str | Path,
    output_path: str | Path,
    width: int = 1080,
    height: int = 1920,
) -> str:
    """
    Convert a clip to 9:16 vertical format.

    The source is scaled to fit while preserving aspect ratio,
    with padding where necessary.
    """

    ensure_ffmpeg()

    source = validate_video_path(
        input_path
    )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    filter_graph = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:"
        f"(ow-iw)/2:(oh-ih)/2"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        filter_graph,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]

    try:

        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

    except subprocess.CalledProcessError as exc:

        raise RuntimeError(
            "Failed to convert video to vertical format."
        ) from exc

    if not output.exists():
        raise RuntimeError(
            f"Vertical output was not created: {output}"
        )

    return str(output)


# =========================================================
# CONCATENATION
# =========================================================

def concatenate_clips(
    clip_paths: list[str | Path],
    output_path: str | Path,
) -> str:
    """
    Concatenate processed clips into one video.

    All clips should have compatible video/audio formats.
    """

    ensure_ffmpeg()

    if not clip_paths:
        raise ValueError(
            "No clips were supplied for concatenation."
        )

    valid_paths = []

    for clip_path in clip_paths:

        path = validate_video_path(
            clip_path
        )

        valid_paths.append(
            path
        )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Use a temporary concat file next to the output.
    concat_file = (
        output.parent
        / f".{output.stem}_concat.txt"
    )

    try:

        with concat_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            for path in valid_paths:

                safe_path = (
                    str(path.resolve())
                    .replace(
                        "'",
                        "'\\''",
                    )
                )

                file.write(
                    f"file '{safe_path}'\n"
                )

        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]

        try:

            subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )

        except subprocess.CalledProcessError as exc:

            raise RuntimeError(
                "Failed to concatenate clips."
            ) from exc

    finally:

        if concat_file.exists():
            concat_file.unlink()

    if not output.exists():
        raise RuntimeError(
            f"Concatenated video was not created: {output}"
        )

    return str(output)


# =========================================================
# PROCESSING PIPELINE
# =========================================================

def process_video(
    video_path: str | Path,
    clips: Optional[list[dict]] = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    make_vertical: bool = False,
) -> dict:
    """
    Main video processing entry point.

    Input:
        Source video + analyzed clip candidates.

    Output:
        Metadata + generated clip files.
    """

    source = validate_video_path(
        video_path
    )

    video_info = get_video_info(
        source
    )

    clips = clips or []

    processed_clips = process_clip_candidates(
        video_path=source,
        clips=clips,
        output_dir=output_dir,
    )

    if make_vertical:

        vertical_clips = []

        for item in processed_clips:

            source_clip = Path(
                item["output_path"]
            )

            vertical_path = (
                source_clip.parent
                / f"{source_clip.stem}_vertical.mp4"
            )

            converted = convert_to_vertical(
                input_path=source_clip,
                output_path=vertical_path,
            )

            updated = dict(item)

            updated["original_output_path"] = (
                updated["output_path"]
            )

            updated["output_path"] = converted
            updated["vertical"] = True

            vertical_clips.append(
                updated
            )

        processed_clips = vertical_clips

    return {
        "version": "1.0",
        "source": video_info,
        "clip_count": len(
            processed_clips
        ),
        "clips": processed_clips,
    }


# =========================================================
# SAVE PROCESSING REPORT
# =========================================================

def save_processing_report(
    report: dict,
    output_path: str | Path,
) -> str:
    """
    Save processing results as JSON.
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
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(output)
