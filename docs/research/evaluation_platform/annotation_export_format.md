# Annotation export format

## Common rules

Annotation exports use export schema version `1.0`; embedded annotation records
use contract version `1.1`. Every profile names the
run UUID, Item 1 envelope schema, transcript hash/projection version, evaluator,
framework/rubric, adapter, model/provider, annotation policy, guideline,
reviewer pseudonym, annotation-set revision/status, and export timestamp.

Sanitized export is the default. It excludes email, authentication and
Supabase identifiers, credentials, raw provider prompts/responses, hidden
reasoning, raw database session IDs, and transcript text. Reviewer IDs are
deterministically pseudonymized for the deployment. Transcript hashes and
narrative content remain sensitive research data.

## Full review package

Profile `full_review` contains:

- immutable saved-run metadata and complete authoritative Item 1 envelope;
- annotation-set metadata and captured prediction inventory;
- all decision revisions and lifecycle transitions;
- effective decisions;
- derived resolved annotation projection;
- every human-span, relation, and coverage revision;
- active reference projection and structured validation eligibility;
- policy/guideline versions and scientific limitations;
- transcript snapshot only when separately and explicitly requested.

When transcript inclusion is requested, the payload sets
`raw_transcript_included=true` and includes a sensitive-data warning. The
default is false. Email-like strings remain redacted even with this opt-in.

## Resolved annotation projection

Profile `resolved_projection` contains confirmed and typed-corrected model
predictions, active human additions, active valid relations, coverage,
framework/policy/guideline versions, and model/correction/addition provenance.
Rejected, retired, invalid, and superseded objects are absent. The legacy
`resolved_projection` key remains as a compatibility alias.

Every resolved export includes:

The limitation states that Item 2B extends the human-reviewed prediction set
but is not a complete or adjudicated gold standard. Metric eligibility, not
the existence of an export, governs validation claims.

## Audit history

Profile `audit_history` contains every model-decision, human-span, relation,
coverage, and lifecycle revision:
prediction ID, original prediction/source snapshot, reviewer pseudonym,
decision, typed correction, bounded note/reason, timestamp, revision, and
superseded reference. Rejections remain present even though they are absent
from the resolved projection.

## Schema evolution

Additive optional fields use the `1.1` annotation contract. Changed resolution
rules, discontinuous spans, or adjudication require explicit schema/policy
version changes. Consumers must reject unsupported versions rather than
reinterpret them.
