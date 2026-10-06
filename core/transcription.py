from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# =========================================================
# CONFIG
# =========================================================

DEFAULT_LANGUAGE = "en"
DEFAULT_MODEL = "small"

DEFAULT_OUTPUT_DIR = Path(
    "output/transcripts"
)


# =========================================================
# VALIDATION
# =========================================================

def ensure_command(
    command_name: str,
) -> None:
    """
    Make sure an external command exists.
    """

    if shutil.which(command_name) is None:

        raise RuntimeError(
            f"Required command not found: "
            f"{command_name}"
        )


def validate_audio_video(
    media_path: str | Path,
) -> Path:
    """
    Validate media input.
    """

    path = Path(
        media_path
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Media file not found: {path}"
        )

    if not path.is_file():

        raise ValueError(
            f"Media path is not a file: {path}"
        )

    return path


# =========================================================
# OUTPUT
# =========================================================

def create_output_directory(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Create transcript output directory.
    """

    directory = Path(
        output_dir
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# =========================================================
# AUDIO EXTRACTION
# =========================================================

def extract_audio(
    media_path: str | Path,
    output_path: Optional[str | Path] = None,
) -> str:
    """
    Extract mono 16 kHz WAV audio using FFmpeg.

    This format is suitable for local Whisper-style
    speech recognition.
    """

    ensure_command(
        "ffmpeg"
    )

    source = validate_audio_video(
        media_path
    )

    if output_path is None:

        output_dir = create_output_directory()

        output_path = (
            output_dir
            / f"{source.stem}.wav"
        )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
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
            "Audio extraction failed: "
            + error
        ) from exc

    if not output.exists():

        raise RuntimeError(
            "FFmpeg completed but audio "
            "file was not created."
        )

    return str(output)


# =========================================================
# WHISPER EXECUTABLE DISCOVERY
# =========================================================

def find_whisper_command(
    whisper_command: Optional[str] = None,
) -> str:
    """
    Find a Whisper executable.

    Supported possibilities include:
        whisper-cli
        whisper
        main

    A custom command can also be supplied.
    """

    if whisper_command:

        resolved = shutil.which(
            whisper_command
        )

        if resolved:

            return resolved

        if Path(
            whisper_command
        ).exists():

            return whisper_command

    candidates = [
        "whisper-cli",
        "whisper",
        "main",
    ]

    for candidate in candidates:

        resolved = shutil.which(
            candidate
        )

        if resolved:

            return resolved

    raise RuntimeError(
        "Whisper executable was not found. "
        "Provide whisper_command explicitly."
    )


# =========================================================
# TIMESTAMP HELPERS
# =========================================================

def timestamp_to_seconds(
    timestamp: str,
) -> float:
    """
    Convert HH:MM:SS, MM:SS or seconds to seconds.
    """

    if not timestamp:
        return 0.0

    timestamp = timestamp.strip()

    try:

        parts = timestamp.split(":")

        if len(parts) == 3:

            return (
                float(parts[0]) * 3600
                + float(parts[1]) * 60
                + float(parts[2])
            )

        if len(parts) == 2:

            return (
                float(parts[0]) * 60
                + float(parts[1])
            )

        return float(timestamp)

    except (
        ValueError,
        TypeError,
    ):

        return 0.0


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
# WHISPER EXECUTION
# =========================================================

def run_whisper(
    audio_path: str | Path,
    output_dir: str | Path,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
) -> dict:
    """
    Run a local Whisper-compatible executable.

    The function expects Whisper to produce TXT and SRT
    output files in the specified directory.
    """

    audio = validate_audio_video(
        audio_path
    )

    whisper = find_whisper_command(
        whisper_command
    )

    output = create_output_directory(
        output_dir
    )

    command = [
        whisper,
        "-f",
        str(audio),
    ]

    if model_path:

        command.extend(
            [
                "-m",
                str(model_path),
            ]
        )

    if language:

        command.extend(
            [
                "-l",
                language,
            ]
        )

    # Request timestamped SRT output where supported.
    command.extend(
        [
            "-osrt",
            "-otxt",
            "-of",
            str(
                output
                / audio.stem
            ),
        ]
    )

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

    except subprocess.CalledProcessError as exc:

        error = (
            exc.stderr
            or exc.stdout
            or "Unknown Whisper error."
        )

        raise RuntimeError(
            "Whisper transcription failed: "
            + error
        ) from exc

    return {
        "audio_path": str(audio),
        "output_dir": str(output),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# =========================================================
# SRT PARSER
# =========================================================

def parse_srt_timestamp(
    timestamp: str,
) -> float:
    """
    Parse SRT timestamp:

    00:01:23,450
    """

    timestamp = timestamp.strip()

    timestamp = timestamp.replace(
        ",",
        ".",
    )

    return timestamp_to_seconds(
        timestamp
    )


def parse_srt(
    srt_path: str | Path,
) -> list[dict]:
    """
    Parse an SRT file into timestamped segments.
    """

    path = Path(
        srt_path
    )

    if not path.exists():

        raise FileNotFoundError(
            f"SRT file not found: {path}"
        )

    content = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    blocks = content.replace(
        "\r\n",
        "\n",
    ).split(
        "\n\n"
    )

    segments = []

    for block in blocks:

        lines = [
            line.strip()
            for line in block.split(
                "\n"
            )
            if line.strip()
        ]

        if len(lines) < 2:
            continue

        timestamp_line_index = None

        for index, line in enumerate(
            lines
        ):

            if "-->" in line:

                timestamp_line_index = index
                break

        if timestamp_line_index is None:
            continue

        timestamp_line = lines[
            timestamp_line_index
        ]

        try:

            start_text, end_text = (
                timestamp_line.split(
                    "-->",
                    1,
                )
            )

            start = parse_srt_timestamp(
                start_text.strip()
            )

            end = parse_srt_timestamp(
                end_text.strip()
            )

        except (
            ValueError,
            TypeError,
        ):

            continue

        text_lines = lines[
            timestamp_line_index + 1:
        ]

        text = " ".join(
            text_lines
        ).strip()

        if not text:
            continue

        segments.append(
            {
                "start": round(
                    start,
                    3,
                ),
                "end": round(
                    end,
                    3,
                ),
                "duration": round(
                    max(
                        0.0,
                        end - start,
                    ),
                    3,
                ),
                "start_timestamp": format_timestamp(
                    start
                ),
                "end_timestamp": format_timestamp(
                    end
                ),
                "text": text,
            }
        )

    return segments


# =========================================================
# TRANSCRIPT CLEANING
# =========================================================

def clean_transcript_segments(
    segments: list[dict],
) -> list[dict]:
    """
    Remove invalid/empty segments and normalize structure.
    """

    cleaned = []

    for segment in segments:

        text = str(
            segment.get(
                "text",
                "",
            )
        ).strip()

        if not text:
            continue

        start = float(
            segment.get(
                "start",
                0.0,
            )
        )

        end = float(
            segment.get(
                "end",
                start,
            )
        )

        if end <= start:
            continue

        cleaned.append(
            {
                "start": round(
                    max(
                        0.0,
                        start,
                    ),
                    3,
                ),
                "end": round(
                    end,
                    3,
                ),
                "duration": round(
                    end - start,
                    3,
                ),
                "start_timestamp": format_timestamp(
                    start
                ),
                "end_timestamp": format_timestamp(
                    end
                ),
                "text": text,
            }
        )

    return cleaned


# =========================================================
# MERGE SHORT SEGMENTS
# =========================================================

def merge_transcript_segments(
    segments: list[dict],
    max_gap: float = 0.8,
    max_duration: float = 12.0,
) -> list[dict]:
    """
    Merge nearby transcript segments.

    This creates more useful context windows for the
    clip analysis engine.
    """

    if not segments:
        return []

    segments = clean_transcript_segments(
        segments
    )

    merged = []

    current = dict(
        segments[0]
    )

    for next_segment in segments[1:]:

        current_end = float(
            current["end"]
        )

        next_start = float(
            next_segment["start"]
        )

        next_end = float(
            next_segment["end"]
        )

        proposed_duration = (
            next_end
            - float(current["start"])
        )

        gap = (
            next_start
            - current_end
        )

        if (
            gap <= max_gap
            and proposed_duration
            <= max_duration
        ):

            current["end"] = next_end

            current["duration"] = (
                next_end
                - float(current["start"])
            )

            current["end_timestamp"] = (
                format_timestamp(
                    next_end
                )
            )

            current["text"] = (
                current["text"]
                + " "
                + next_segment["text"]
            ).strip()

        else:

            merged.append(
                current
            )

            current = dict(
                next_segment
            )

    merged.append(
        current
    )

    for segment in merged:

        segment["duration"] = round(
            segment["duration"],
            3,
        )

    return merged


# =========================================================
# FULL TRANSCRIPTION PIPELINE
# =========================================================

def transcribe_media(
    media_path: str | Path,
    whisper_command: Optional[str] = None,
    model_path: Optional[str] = None,
    language: str = DEFAULT_LANGUAGE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    keep_audio: bool = False,
) -> dict:
    """
    Complete local transcription pipeline:

        media
          ↓
        audio extraction
          ↓
        Whisper
          ↓
        SRT parsing
          ↓
        cleaned segments
          ↓
        merged context segments
    """

    source = validate_audio_video(
        media_path
    )

    output = create_output_directory(
        output_dir
    )

    audio_path = (
        output
        / f"{source.stem}.wav"
    )

    extract_audio(
        media_path=source,
        output_path=audio_path,
    )

    whisper_result = run_whisper(
        audio_path=audio_path,
        output_dir=output,
        whisper_command=whisper_command,
        model_path=model_path,
        language=language,
    )

    srt_path = (
        output
        / f"{audio_path.stem}.srt"
    )

    if not srt_path.exists():

        raise RuntimeError(
            "Whisper completed but the expected "
            f"SRT file was not found: {srt_path}"
        )

    raw_segments = parse_srt(
        srt_path
    )

    cleaned_segments = (
        clean_transcript_segments(
            raw_segments
        )
    )

    merged_segments = (
        merge_transcript_segments(
            cleaned_segments
        )
    )

    if not keep_audio:

        try:
            audio_path.unlink()

        except OSError:
            pass

    return {
        "version": "1.0",
        "source": str(source),
        "language": language,
        "audio_path": (
            str(audio_path)
            if keep_audio
            else None
        ),
        "srt_path": str(
            srt_path
        ),
        "segment_count": len(
            merged_segments
        ),
        "segments": merged_segments,
        "whisper": {
            "output_dir": whisper_result[
                "output_dir"
            ],
        },
    }


# =========================================================
# SAVE TRANSCRIPT
# =========================================================

def save_transcript(
    transcript: dict,
    output_path: str | Path,
) -> str:
    """
    Save transcript data as JSON.
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
            transcript,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return str(output)


# =========================================================
# CONVERT TO CLIP ANALYZER FORMAT
# =========================================================

def transcript_to_clip_segments(
    transcript: dict,
) -> list[dict]:
    """
    Convert transcription output directly into the
    structure expected by clip_analyzer.py.
    """

    segments = transcript.get(
        "segments",
        [],
    )

    result = []

    for segment in segments:

        result.append(
            {
                "start": segment.get(
                    "start",
                    0.0,
                ),
                "end": segment.get(
                    "end",
                    0.0,
                ),
                "text": segment.get(
                    "text",
                    "",
                ),
            }
        )

    return result
