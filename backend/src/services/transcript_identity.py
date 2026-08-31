"""Canonical transcript serialization shared by evaluator comparison paths."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from domain.models.evaluator_comparison import CanonicalTranscriptTurn


def _turn_value(turn: Any, field: str) -> Any:
    if isinstance(turn, dict):
        return turn.get(field)
    return getattr(turn, field)


def canonicalize_transcript(turns: Iterable[Any]) -> list[CanonicalTranscriptTurn]:
    """Return the minimal transcript in stable turn-number order."""

    canonical = [
        CanonicalTranscriptTurn(
            turn_number=int(_turn_value(turn, "turn_number")),
            role=str(_turn_value(turn, "role")),
            text=str(_turn_value(turn, "text") or ""),
        )
        for turn in turns
    ]
    return sorted(canonical, key=lambda turn: turn.turn_number)


def serialize_canonical_transcript(turns: Iterable[Any]) -> bytes:
    """Serialize canonical turns as deterministic, compact UTF-8 JSON."""

    payload = [turn.model_dump(mode="json") for turn in canonicalize_transcript(turns)]
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def hash_transcript(turns: Iterable[Any]) -> str:
    """Return a SHA-256 hex digest, including the explicit empty transcript ``[]``."""

    return hashlib.sha256(serialize_canonical_transcript(turns)).hexdigest()
