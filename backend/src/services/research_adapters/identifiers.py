"""Content-addressed identifiers for research runs and projected objects."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel

IdentifierPrefix = Literal[
    "run", "span", "turn", "relation", "rating", "metric", "finding", "limitation"
]
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,299}$")


def canonical_result_digest(native_result: BaseModel | dict[str, Any]) -> str:
    """Hash a validated native result using canonical JSON serialization."""

    payload = (
        native_result.model_dump(mode="json")
        if isinstance(native_result, BaseModel)
        else native_result
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def stable_research_identifier(
    prefix: IdentifierPrefix,
    *,
    transcript_hash: str,
    evaluator_identifier: str,
    framework_identifier: str,
    native_identifier: str,
    adapter_version: str,
    projection_type: str,
    object_location: str,
    native_result_digest: str,
) -> str:
    """Return a deterministic non-reversible 160-bit research identifier.

    Array position may be one component of ``object_location`` but is never the
    sole input. Transcript content is represented only by its existing hash.
    """

    if not re.fullmatch(r"[0-9a-f]{64}", transcript_hash):
        raise ValueError("transcript_hash must be a lowercase SHA-256 digest.")
    if not re.fullmatch(r"[0-9a-f]{64}", native_result_digest):
        raise ValueError("native_result_digest must be a lowercase SHA-256 digest.")
    components = (
        evaluator_identifier,
        framework_identifier,
        native_identifier,
        adapter_version,
        projection_type,
        object_location,
    )
    if any(not _SAFE_COMPONENT.fullmatch(component) for component in components):
        raise ValueError("Identifier components must use bounded safe characters.")

    material = {
        "adapter_version": adapter_version,
        "evaluator_identifier": evaluator_identifier,
        "framework_identifier": framework_identifier,
        "native_identifier": native_identifier,
        "native_result_digest": native_result_digest,
        "object_location": object_location,
        "projection_type": projection_type,
        "transcript_hash": transcript_hash,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:40]
    return f"{prefix}_{digest}"
