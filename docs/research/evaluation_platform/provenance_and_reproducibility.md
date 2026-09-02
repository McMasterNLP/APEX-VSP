# Provenance and reproducibility

## What a result records

Every envelope records the schema, evaluator, framework/rubric, adapter,
execution mode, provider/model when applicable, generated timestamp, runtime,
status/failure category, canonical transcript hash, and declared hash
algorithms. A projection object additionally records a stable object ID and a
source reference into the authoritative native result.

Provider and model are null for offline execution. They are explicit for live
execution. A model identifier is useful provenance, but it does not guarantee
that a remote provider is deterministic or that a mutable alias refers to the
same weights later.

## Canonical transcript identity

APEX canonicalizes the persisted turns using `apex-canonical-v1`, with the
source convention `user=clinician;assistant=patient`, then computes SHA-256.
The envelope carries the digest, turn count, projection version, and role
convention—not a database session or user identifier.

Export requests reload the authorized completed session and reject envelopes
whose transcript digest differs. Raw transcript text is available in the
authorized interactive response so annotations can be rendered, but envelope
identity declares `raw_transcript_included=false`; export profiles redact
transcript-derived strings by default.

## Stable identifiers

Run and projection identifiers are SHA-256 content addresses truncated to 160
bits and prefixed by object type. Their canonical material includes:

- transcript SHA-256;
- evaluator and framework identifiers;
- native discriminator;
- adapter version;
- projection type and bounded native/object location;
- SHA-256 of the canonical, validated native result.

Array position may contribute to an object location but is never the sole
identity source. The digest input uses sorted-key, compact UTF-8 JSON. The same
canonical transcript, evaluator/framework, adapter version, native result, and
object mapping produce the same IDs. Changing meaningful content or adapter
version changes the IDs.

Timestamps and measured runtime are deliberately excluded from stable IDs.
Consequently, two executions may share a run ID while recording different
generation times and runtimes. For live evaluators, even identical inputs may
produce a different native result and therefore a different run ID.

## Reproducing an offline baseline result

Record the repository commit, Python/runtime dependency lock, configuration,
and sanitized envelope. Then:

1. restore the same canonical transcript and commit;
2. select `baseline` with `allow_live=false`;
3. confirm evaluator/framework/adapter versions and transcript hash;
4. compare the native result, projection, and stable identifiers;
5. treat timestamp and runtime as observational fields, not equality fields.

The baseline path is rule-based and does not require a provider call. This
makes it the strongest reproducibility reference in Item 1.

## Reproducing a live result

In addition to the above, record provider, exact model identifier when the
provider exposes one, request configuration, server policy, and execution
date. Remote service behavior, alias updates, sampling, and service-side changes
can prevent byte-for-byte reproduction. The envelope supports traceability; it
does not overstate determinism.

Prompts, credentials, raw provider responses, and internal reasoning are not
returned in the research envelope. When a provider call fails, the envelope
contains an allowlisted category and public message, not a raw exception.

## Comparison rules

- Compare output only inside the same framework/version unless a documented
  projection explicitly states otherwise.
- Read every metric's `source_label` and `comparability_statement`.
- Do not compare APEX compatibility values as if they were native ACE-CT scores.
- Interpret insufficient evidence and not-assessable as states, not numeric
  zero.
- Preserve the complete native result when re-projecting with a later adapter.

## Versioning expectations

Breaking wire changes require a new envelope/projection version. A changed
mapping requires an adapter version change. A changed rubric or construct
definition requires a framework/rubric version change. A model change requires
evaluator and model provenance review. Older native results should remain
readable through their declared discriminator and version; consumers must not
silently reinterpret them as a newer contract.
