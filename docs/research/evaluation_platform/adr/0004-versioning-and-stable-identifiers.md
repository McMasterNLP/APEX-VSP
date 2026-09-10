# ADR 0004: Versioned schemas and stable identifiers

- Status: accepted
- Date: 2026-09-01

## Context

Results must be traceable across UI, exports, future annotations, and future
validation runs without relying on database IDs or unstable array positions.

## Decision

The envelope, native variant, adapter, framework/rubric, and transcript
projection are independently versioned. Run and projected-object identifiers
are deterministic SHA-256-derived identifiers over bounded canonical metadata:
transcript hash, evaluator/native-result digest, framework/native identifier,
adapter version, projection type, and stable object location/content key.

Only a truncated hexadecimal digest with a non-sensitive type prefix is
exposed. Plaintext transcript content is never embedded in the identifier.
Source references use allowlisted native type, native identifier, safe field
path, and adapter version.

## Consequences

The same transcript, native result, and adapter version produce the same IDs.
Changing meaningful output or adapter mapping changes IDs. Truncating SHA-256
to 160 bits gives negligible collision risk for the expected corpus; consumers
must still treat IDs as identifiers, not cryptographic authenticity proofs.

## Rejected alternatives

- Random UUIDs: rejected because repeated deterministic projections would not
  align.
- Array index alone: rejected because it is not semantically stable.
- Raw text in IDs: rejected because identifiers can be logged and exported.
- Database primary keys: rejected because they expose unnecessary internal
  identifiers and do not describe projection provenance.
