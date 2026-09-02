# Privacy, security, and ethics

## Access and purpose boundary

Research evaluation routes reuse the existing administrator authorization
dependency. Item 1 introduces no researcher role and grants no new access to a
session. Only completed sessions can be evaluated. The workflow is read-only
with respect to learner feedback, session state, turns, metrics, and plugin
selection.

This technical access control does not replace institutional approval,
participant consent, data-governance review, or an appropriate legal basis for
research. Administrators remain responsible for using only authorized data and
approved evaluators.

## Data minimization

- Envelopes identify the transcript by canonical SHA-256, not database session,
  user, email, or external identity.
- Native source paths reject private identifier/credential terms.
- The interactive response includes authorized turn text only so the selected
  session can be inspected and annotations verified.
- Export profiles set `raw_transcript_included=false` and redact raw transcript,
  quoted span/evidence, and patient-text fields by default.
- Multi-table CSV emits offsets, turn numbers, labels, IDs, and provenance but
  leaves quoted transcript text empty.
- No request or response contains provider credentials.

A transcript hash is pseudonymous, not anonymous. Low-entropy or known text
may be susceptible to guessing, and narrative findings may retain sensitive
clinical meaning even after direct text redaction. Treat every artifact as
sensitive research data.

## Execution safety

The registry is explicit and code-reviewed. There is no filesystem discovery,
request-driven import, arbitrary plugin upload, package installation, dynamic
researcher code execution, or request-supplied remote endpoint.

Offline baseline execution is the default. Live execution requires both:

1. explicit per-request `allow_live=true`; and
2. server policy `RESEARCH_ALLOW_LIVE_EVALUATIONS=true`.

The experimental ACE-CT-inspired rubric also requires its separate server-side
experimental authorization. Refusal occurs before provider construction. Live
providers and models are restricted to the registration's allowlist.

The service limits canonical transcript content to 1,000,000 characters and a
validated response to 5,000,000 UTF-8 bytes. Domain schemas reject extra fields,
non-finite numeric values, unsafe identifiers/source paths, invalid spans,
invalid evidence turns, and mismatched native discriminators. The frontend
renders transcript text as React text nodes and defensively ignores malformed
spans; it never inserts evaluator text as HTML.

## Error and log hygiene

Evaluator, provider, native-adapter, and projection failures are caught at the
per-evaluator boundary. Public envelopes contain an allowlisted category and a
generic message. They do not contain exception text, stack traces, prompts,
credentials, provider response bodies, or hidden reasoning. Logs record the
evaluator identifier and failure stage without logging transcript content.

Successful sibling evaluators remain available when one evaluator fails. This
is operational failure isolation, not evidence that a failed result is safe to
impute.

## Export handling

Exports are generated on demand and are not persisted by Item 1. The endpoint
validates the submitted envelope schema and session transcript hash before
serialization; it never re-executes a model. JSON is the authoritative lossless
structure at the declared profile. CSV is a normalized analysis convenience
and must not be represented as lossless.

Recommended handling:

- store exports in access-controlled encrypted research storage;
- keep an inventory and retention/deletion schedule;
- do not place exports in the Git repository, issue tracker, chat, or public
  object storage;
- preserve schema/framework/evaluator/adapter versions with derived analyses;
- review narrative fields for residual sensitive content before sharing;
- verify institutional policy before sending transcript data to a live provider.

## Scientific and ethical labeling

APEX empathy output is an **AFCE-aligned, rule-based operationalization of
selected constructs**, not a complete or validated AFCE reproduction.

The ACE-CT-inspired evaluator is experimental, unvalidated, non-official, and
not a reproduction of the confidential manuscript's trained models. Its
compatibility projection is an engineering bridge and is not
framework-equivalent. These statements are part of descriptors, envelopes,
native views, warnings, and documentation so they travel with results.

Scores must not be used as clinical decisions, trainee discipline, or claims of
human communication competence without independent validation, appropriate
human review, and governance. Missing audio, video, timing, and overlap can make
transcript-only constructs partially or wholly unassessable.

## Threats not solved by Item 1

- semantic re-identification from rare transcript content;
- malicious or compromised approved providers;
- bias or construct invalidity in evaluator logic;
- model/version drift at remote services;
- unauthorized downstream copying after an export;
- membership inference or reconstruction attacks against future trained models;
- human-review disagreement and adjudication, which belong to Item 2;
- empirical accuracy/agreement validation, which belongs to Item 3.
