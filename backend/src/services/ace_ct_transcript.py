"""Privacy-minimal transcript projection for ACE-CT-inspired evaluation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from schemas.ace_ct import ACECTTranscript, ACECTTranscriptTurn, ACECTTranscriptWarning
from services.transcript_identity import hash_transcript

ROLE_MAPPING = {
    "user": "clinician",
    "assistant": "patient",
}
EMPTY_TURN_MARKER = "[[EMPTY TURN: NO TRANSCRIPT TEXT]]"


class ACECTTranscriptProjectionError(ValueError):
    """Raised when source turns cannot be projected without inference."""


def _value(turn: Any, field: str) -> Any:
    if isinstance(turn, Mapping):
        if field not in turn:
            raise ACECTTranscriptProjectionError(f"Turn is missing required field '{field}'.")
        return turn[field]
    try:
        return getattr(turn, field)
    except AttributeError as exc:
        raise ACECTTranscriptProjectionError(f"Turn is missing required field '{field}'.") from exc


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def project_ace_ct_transcript(turns: Iterable[Any]) -> ACECTTranscript:
    """Validate and project APEX turns without identity or content inference.

    The returned hash deliberately reuses the comparison pipeline's canonical
    source-turn hash. Text normalization affects only the projected model input.
    """

    validated: list[tuple[int, str, str]] = []
    seen_turn_numbers: set[int] = set()

    for turn in turns:
        turn_number = _value(turn, "turn_number")
        if not isinstance(turn_number, int) or isinstance(turn_number, bool) or turn_number < 1:
            raise ACECTTranscriptProjectionError("Turn numbers must be positive integers.")
        if turn_number in seen_turn_numbers:
            raise ACECTTranscriptProjectionError(
                f"Duplicate turn number {turn_number} is not permitted."
            )
        seen_turn_numbers.add(turn_number)

        role = _value(turn, "role")
        if role not in ROLE_MAPPING:
            raise ACECTTranscriptProjectionError(
                f"Unknown role for turn {turn_number}; expected 'user' or 'assistant'."
            )

        text = _value(turn, "text")
        if not isinstance(text, str):
            raise ACECTTranscriptProjectionError(f"Text for turn {turn_number} must be a string.")
        validated.append((turn_number, role, text))

    ordered = sorted(validated, key=lambda item: item[0])
    projected_turns: list[ACECTTranscriptTurn] = []
    warnings: list[ACECTTranscriptWarning] = []
    for turn_number, role, source_text in ordered:
        normalized_text = _normalize_text(source_text)
        projected_turns.append(
            ACECTTranscriptTurn(
                turn_number=turn_number,
                source_turn_number=turn_number,
                speaker=ROLE_MAPPING[role],
                text=normalized_text,
            )
        )
        if not normalized_text:
            warnings.append(
                ACECTTranscriptWarning(
                    code="empty_text_retained",
                    source_turn_number=turn_number,
                    message="Empty normalized text was retained to preserve turn ordering.",
                )
            )

    source_turns = [
        {"turn_number": number, "role": role, "text": text} for number, role, text in validated
    ]
    return ACECTTranscript(
        turns=tuple(projected_turns),
        warnings=tuple(warnings),
        transcript_hash=hash_transcript(source_turns),
    )


def serialize_ace_ct_transcript(transcript: ACECTTranscript) -> str:
    """Serialize an interleaved transcript with explicit clinical role labels."""

    blocks: list[str] = []
    for turn in transcript.turns:
        speaker = turn.speaker.capitalize()
        text = turn.text if turn.text else EMPTY_TURN_MARKER
        blocks.append(f"[Turn {turn.turn_number} | {speaker}] {text}")
    return "\n".join(blocks)
