from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Any


@dataclass
class Job:
    job_id: str
    job_type: str
    input_value: str
    reference_url: Optional[str] = None

    # Pro V2 generation settings
    duration: int = 30
    caption_style: str = "Bold Viral"
    caption_settings: Optional[dict] = None
    editing_settings: Optional[dict] = None

    # Existing job state
    status: str = "queued"
    result_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""

    def __post_init__(self):
        if self.caption_settings is None:
            self.caption_settings = {
                "font": "DejaVu Sans",
                "font_size": 64,
                "position": "bottom",
                "text_color": "#FFFFFF",
                "highlight_color": "#FFFF00",
                "stroke": True,
                "stroke_width": 3,
                "shadow": True,
                "background_box": False,
                "words_per_line": 4,
                "max_lines": 2,
                "emphasize_keywords": True,
            }

        if self.editing_settings is None:
            self.editing_settings = {
                "make_vertical": True,
                "dynamic_crop": True,
                "punch_in": True,
                "remove_dead_space": True,
                "normalize_audio": True,
                "use_reactions": True,
                "use_broll": True,
                "target_duration": self.duration,
            }

    def to_dict(self) -> dict:
        return asdict(self)


def create_job(
    job_id: str,
    job_type: str,
    input_value: str,
    reference_url: Optional[str] = None,
    duration: int = 30,
    caption_style: str = "Bold Viral",
    caption_settings: Optional[dict] = None,
    editing_settings: Optional[dict] = None,
) -> Job:
    """
    Create a Pro V2 job.

    Existing callers remain compatible because all new
    settings have safe defaults.
    """

    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 30

    duration = max(5, min(duration, 180))

    if not caption_style:
        caption_style = "Bold Viral"

    default_caption_settings = {
        "font": "DejaVu Sans",
        "font_size": 64,
        "position": "bottom",
        "text_color": "#FFFFFF",
        "highlight_color": "#FFFF00",
        "stroke": True,
        "stroke_width": 3,
        "shadow": True,
        "background_box": False,
        "words_per_line": 4,
        "max_lines": 2,
        "emphasize_keywords": True,
    }

    if caption_settings:
        default_caption_settings.update(caption_settings)

    default_editing_settings = {
        "make_vertical": True,
        "dynamic_crop": True,
        "punch_in": True,
        "remove_dead_space": True,
        "normalize_audio": True,
        "use_reactions": True,
        "use_broll": True,
        "target_duration": duration,
    }

    if editing_settings:
        default_editing_settings.update(editing_settings)

    return Job(
        job_id=job_id,
        job_type=job_type,
        input_value=input_value,
        reference_url=reference_url,
        duration=duration,
        caption_style=caption_style,
        caption_settings=default_caption_settings,
        editing_settings=default_editing_settings,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
