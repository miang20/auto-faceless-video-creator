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
