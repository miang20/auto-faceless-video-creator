"""Psychology-led, footage-grounded on-screen hook utilities."""
from __future__ import annotations
import re
from typing import Any

HOOK_STYLES = [
    "Auto / Best for this footage",
    "POV — Put the viewer in the situation",
    "Immediate danger or tension",
    "Curiosity gap — What happens next?",
    "Unexpected moment first",
    "Emotional human reaction",
    "Direct question to the viewer",
    "Countdown to the payoff",
    "Payoff preview, then context",
    "Suspense / slow reveal",
    "Challenge / impossible situation",
    "Cinematic cold open",
    "Relatable first-person scenario",
]

def build_hook_overlay(style: str, topic: str, clip_text: str) -> str:
    """Create a short overlay without inventing unseen events or fake stakes."""
    style = str(style or "").lower()
    topic = re.sub(r"\s+", " ", str(topic or "")).strip()
    text = re.sub(r"\s+", " ", str(clip_text or "")).strip()
    # Prefer an actual short spoken line when available; it is the most grounded hook.
    if text:
        words = text.split()
        quote = " ".join(words[:8]).strip(" ,.!?;:")
        if quote and len(quote) <= 52 and ("pov" not in style and "cinematic" not in style):
            if "curiosity" in style or "question" in style:
                return "WAIT FOR IT…"
            if "emotional" in style:
                return "WATCH THEIR REACTION"
            if "countdown" in style:
                return "HERE IT COMES"
            if "unexpected" in style or "payoff preview" in style:
                return "DID YOU CATCH THAT?"
    if "pov" in style or "first-person" in style or "relatable" in style:
        return "POV: YOU'RE RIGHT THERE"
    if "danger" in style or "tension" in style:
        return "THIS GETS INTENSE"
    if "curiosity" in style or "question" in style:
        return "WAIT… HOW DID THAT HAPPEN?"
    if "emotional" in style:
        return "WATCH THE REACTION"
    if "countdown" in style:
        return "WATCH WHAT HAPPENS NEXT"
    if "payoff preview" in style or "unexpected" in style:
        return "DID YOU SEE THAT COMING?"
    if "suspense" in style or "slow reveal" in style:
        return "LOOK CLOSELY…"
    if "challenge" in style or "impossible" in style:
        return "WOULD YOU TRY THIS?"
    if "cinematic" in style:
        return "ONE MOMENT CHANGES EVERYTHING"
    if topic:
        short_topic = " ".join(topic.split()[:5]).upper()
        if len(short_topic) <= 38:
            return short_topic
    return "WATCH THIS MOMENT"

def build_retention_plan(timeline: list[dict], target_duration: float = 30.0) -> dict:
    """Return an actionable retention blueprint tied to real selected moments."""
    beats = []
    for index, item in enumerate(timeline or []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "MAIN").upper()
        duration = item.get("target_screen_duration", item.get("duration", 0))
        try:
            duration = max(0.5, min(8.0, float(duration or 0)))
        except (TypeError, ValueError):
            duration = 3.0
        if index == 0 or role == "HOOK":
            purpose = "Pattern interrupt and immediate situation framing"
        elif role == "SETUP":
            purpose = "Minimum context; remove explanation that does not change understanding"
        elif role in {"ESCALATION", "MAIN"}:
            purpose = "Add new information, tension, or visual evidence; avoid repeating the prior beat"
        elif role == "REACTION":
            purpose = "Human response as emotional proof; preserve authentic source audio"
        elif role == "PAYOFF":
            purpose = "Close the open loop; show the complete real outcome"
        elif role == "ENDING":
            purpose = "End on the strongest consequence or natural visual loop"
        else:
            purpose = "Support the current beat without replacing the story"
        beats.append({
            "sequence": len(beats) + 1,
            "role": role,
            "duration_budget_seconds": round(duration, 2),
            "retention_purpose": purpose,
            "source_text": re.sub(r"\\s+", " ", str(item.get("text") or "")).strip()[:180],
        })
    return {
        "model": "hook-context-escalation-open-loop-payoff",
        "target_duration_seconds": round(max(0.0, float(target_duration or 0)), 2),
        "beats": beats,
        "rules": [
            "Every beat must add new information, tension, reaction, or payoff.",
            "Open loops must be resolved by the actual footage, never fabricated.",
            "Preserve cause-and-effect order except for a brief, clearly contextualized payoff preview.",
            "Keep original dialogue and natural audio when they carry the story.",
            "Use a visual or audio change when attention would otherwise drift; do not cut mechanically.",
            "Do not promise an outcome the selected footage does not show.",
        ],
        "quality_checks": [
            "Hook is understandable without an intro.",
            "Setup is shorter than the payoff whenever the footage allows.",
            "No duplicated moment or repeated caption-only beat.",
            "Final outcome is visible before the ending.",
        ],
    }
