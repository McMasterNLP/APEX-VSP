"""Typed contracts for the experimental ACE-CT-inspired evaluator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ACECTTranscriptWarning(BaseModel):
    """Non-fatal transcript projection issue tied to a source turn."""

    code: Literal["empty_text_retained"]
    source_turn_number: int = Field(strict=True, ge=1)
    message: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTTranscriptTurn(BaseModel):
    """Minimal immutable turn supplied to the rubric evaluator."""

    turn_number: int = Field(strict=True, ge=1)
    source_turn_number: int = Field(strict=True, ge=1)
    speaker: Literal["clinician", "patient"]
    text: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class ACECTTranscript(BaseModel):
    """Immutable projected transcript without identity or database metadata."""

    turns: tuple[ACECTTranscriptTurn, ...]
    warnings: tuple[ACECTTranscriptWarning, ...] = ()
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def turn_numbers(self) -> tuple[int, ...]:
        """Return source evidence coordinates in conversational order."""

        return tuple(turn.turn_number for turn in self.turns)
