# Annotation export format

## Common rules

Annotation exports are JSON with schema version `1.0`. Every profile names the
run UUID, Item 1 envelope schema, transcript hash/projection version, evaluator,
framework/rubric, adapter, model/provider, annotation policy, guideline,
reviewer pseudonym, annotation-set revision/status, and export timestamp.

Sanitized export is the default. It excludes email, authentication and
Supabase identifiers, credentials, raw provider prompts/responses, hidden
reasoning, unnecessary database IDs, and transcript text. Reviewer IDs are
deterministically pseudonymized for the deployment. Transcript hashes and
narrative content remain sensitive research data.

## Full review package

Profile `full_review` contains:

- immutable saved-run metadata and complete authoritative Item 1 envelope;
- annotation-set metadata and captured prediction inventory;
- all decision revisions and lifecycle transitions;
- effective decisions;
- derived resolved annotation projection;
- policy/guideline versions and scientific limitations;
- transcript snapshot only when separately and explicitly requested.

When transcript inclusion is requested, the payload sets
`raw_transcript_included=true` and includes a sensitive-data warning. The
default is false.

## Resolved annotation projection

Profile `resolved_projection` contains confirmed and typed-corrected model
predictions, source prediction IDs/references, framework and guideline
versions, and resolution provenance. Rejected objects are absent. Informational
metrics are not represented as reviewed decisions.

Every resolved export includes:

> Item 2A creates a human-reviewed prediction set, not a complete gold-standard
> dataset; human-added false negatives are unsupported.

## Audit history

Profile `audit_history` contains every decision revision and lifecycle event:
prediction ID, original prediction/source snapshot, reviewer pseudonym,
decision, typed correction, bounded note/reason, timestamp, revision, and
superseded reference. Rejections remain present even though they are absent
from the resolved projection.

## Schema evolution

Additive optional fields may use a compatible minor revision. New correction
types, changed resolution rules, human-added predictions, span-boundary edits,
or adjudication require explicit schema/policy version changes. Consumers must
reject unsupported versions rather than reinterpret them.
