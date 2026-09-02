# ADR 0010: Use Unicode code-point half-open span offsets

- Status: accepted
- Date: 2026-09-02

## Context

Python uses Unicode code-point indexing while browser selection positions use
UTF-16 code units. Emoji, combining marks, and other non-BMP text make direct
copying unsafe.

## Decision

Preserve the established backend convention: contiguous single-turn Unicode
code-point offsets with inclusive start and exclusive end. Add strict, tested
UTF-16/code-point conversion utilities in the frontend. Verify hash, turn,
role, bounds, non-whitespace content, and exact canonical substring on every
server write.

## Consequences

Offsets are independent of UTF-8 encoding and DOM segmentation. Grapheme
clusters may contain multiple offsets and discontinuous spans remain future
work. Clients must never send unconverted DOM offsets.

