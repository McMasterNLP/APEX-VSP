"""Original prompt builder for experimental ACE-CT-inspired transcript evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from schemas.ace_ct import ACECTRubricSpec, ACECTTranscript
from services.ace_ct_transcript import serialize_ace_ct_transcript

PROMPT_VERSION = "ace-ct-inspired-prompt-v1"
DIMENSION_SCHEMA_START = "BEGIN ORDERED DIMENSION SCHEMA"
DIMENSION_SCHEMA_END = "END ORDERED DIMENSION SCHEMA"
TRANSCRIPT_START = "BEGIN INTERLEAVED TRANSCRIPT"
TRANSCRIPT_END = "END INTERLEAVED TRANSCRIPT"


@dataclass(frozen=True)
class ACECTPromptMessage:
    """One immutable provider-neutral chat message."""

    role: Literal["system", "user"]
    content: str


@dataclass(frozen=True)
class ACECTPrompt:
    """Exactly two messages ready for an adapter's context and prompt fields."""

    messages: tuple[ACECTPromptMessage, ACECTPromptMessage]
    prompt_version: str = PROMPT_VERSION

    @property
    def system_message(self) -> str:
        return self.messages[0].content

    @property
    def user_message(self) -> str:
        return self.messages[1].content


def _system_message() -> str:
    return """You evaluate communication behavior in an interleaved clinician-patient transcript using an experimental ACE-CT-inspired rubric.

Boundaries:
- This is transcript-only evaluation. Audio, video, tone, gesture, overlap, pause duration, and delivery timing may be absent.
- Evaluate only the supplied communication behaviors. Do not evaluate diagnosis, treatment, medical correctness, clinical competence, or patient outcomes.
- Keep the supplied Clinician and Patient roles fixed. Do not reinterpret or exchange them.
- Honor each dimension's assessability and modality limits. Use a null score only under the stated insufficient-evidence policy; never substitute a neutral score.
- Cite evidence only by turn number. Every cited number must exist in the supplied transcript. Do not invent evidence and do not quote transcript text.
- Return exactly eleven dimension results in the supplied order and exactly four domain scores in respond, listen, speak, general order.
- Return strict JSON only: no markdown fences, preamble, commentary, or extra keys.
- Keep each reasoning field at most 500 characters and each improvement recommendation at most 400 characters.
- Do not provide chain-of-thought or hidden reasoning. The reasoning field must be only a concise evidence-based rationale.
- This is an experimental, unvalidated implementation and is not an official model reproduction."""


def _dimension_schema(rubric: ACECTRubricSpec) -> str:
    lines = [DIMENSION_SCHEMA_START]
    for index, dimension in enumerate(rubric.dimensions, start=1):
        limitations = " ".join(dimension.modality_limitations)
        lines.append(
            f"{index}. id={dimension.identifier.value}; domain={dimension.domain.value}; "
            f"assessability={dimension.assessability.value}; description={dimension.description}; "
            f"modality_limits={limitations}"
        )
    lines.append(DIMENSION_SCHEMA_END)
    return "\n".join(lines)


def _score_scale(rubric: ACECTRubricSpec) -> str:
    anchors = rubric.dimensions[0].score_anchors
    return "\n".join(f"{anchor.score}: {anchor.description}" for anchor in anchors)


def _json_contract(rubric: ACECTRubricSpec) -> str:
    return f"""Return one JSON object with this exact key structure and no additional keys:
{{
  "framework_name": "ACE-CT-inspired",
  "implementation_type": "experimental_transcript_rubric",
  "validation_status": "experimental_unvalidated",
  "publication_reproduction": false,
  "rubric_version": "{rubric.rubric_version}",
  "approval_status": "{rubric.approval_status.value}",
  "dimension_results": [
    {{
      "dimension_id": "<id from the ordered dimension schema>",
      "domain": "<matching domain>",
      "score": "<integer 1-5 or null>",
      "insufficient_evidence": "<boolean; true exactly when score is null>",
      "assessability": "<matching assessability>",
      "confidence": "<finite number from 0 through 1>",
      "evidence_turn_numbers": ["<positive unique turn numbers in ascending order>"],
      "reasoning": "<concise rationale without transcript quotation>",
      "improvement_recommendation": "<concise recommendation>",
      "modality_limitation_notes": ["<applicable transcript-only limits>"]
    }}
  ],
  "domain_scores": [
    {{
      "domain": "<respond, listen, speak, or general>",
      "mean_score": "<mean of non-null member scores or null>",
      "scored_dimension_count": "<integer count>",
      "insufficient_evidence_count": "<integer count>"
    }}
  ],
  "score_sources": {{
    "dimension_scores": "experimental_llm_transcript_rubric",
    "domain_scores": "arithmetic_mean_of_non_null_dimensions",
    "compatibility_scores": "not_computed_in_model_response"
  }},
  "limitations": {{
    "transcript_only": true,
    "missing_modalities": ["audio", "video", "timing", "overlap"],
    "notes": ["<one or more concise limitations>"],
    "official_model_reproduction": false
  }}
}}

Use JSON numbers, booleans, and null values, not quoted placeholders or quoted numeric values. Produce all eleven dimension objects and all four domain objects."""


def build_ace_ct_prompt(
    transcript: ACECTTranscript,
    rubric: ACECTRubricSpec,
) -> ACECTPrompt:
    """Build two provider-neutral messages without identity or configuration data."""

    user_message = "\n\n".join(
        (
            f"Prompt version: {PROMPT_VERSION}",
            f"Rubric version: {rubric.rubric_version}",
            f"Rubric approval status: {rubric.approval_status.value}",
            (
                "Evaluation modality: transcript only. Missing signals include audio, video, "
                "tone, gesture, overlap, pause duration, and timing."
            ),
            _dimension_schema(rubric),
            "Provisional score scale:\n" + _score_scale(rubric),
            (
                "Insufficient evidence: return score=null and insufficient_evidence=true when "
                "there is no relevant opportunity, the transcript is incomplete, decisive "
                "evidence requires a missing modality, or scoring would require invented context."
            ),
            _json_contract(rubric),
            f"{TRANSCRIPT_START}\n{serialize_ace_ct_transcript(transcript)}\n{TRANSCRIPT_END}",
        )
    )
    return ACECTPrompt(
        messages=(
            ACECTPromptMessage(role="system", content=_system_message()),
            ACECTPromptMessage(role="user", content=user_message),
        )
    )
