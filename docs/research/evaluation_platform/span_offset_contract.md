# Span offset and text-integrity contract

## Canonical convention

All research spans use Unicode code-point indices into one immutable canonical
transcript turn. The start is inclusive and the end is exclusive:

```text
selected_text == turn.text[start_offset:end_offset]
```

Python string indexing already follows Unicode code points, so this convention
preserves the established Item 1 validation behavior. It does not use UTF-8
bytes, UTF-16 code units, grapheme clusters, rendered pixels, DOM nodes, or a
normalized copy of the text. No NFC/NFD conversion, whitespace collapse, or
line-ending rewrite occurs during selection verification.

Combining marks therefore occupy their own code-point positions. A reviewer
may select a base letter without its combining mark at the storage level,
although the UI should preserve natural native selection and show the exact
preview. Discontinuous spans are outside Item 2B.

## Browser conversion

JavaScript string and DOM range offsets count UTF-16 code units. Before an API
request, the frontend converts a UTF-16 offset by counting code points in the
prefix:

```text
codePointOffset = Array.from(text.slice(0, utf16Offset)).length
```

The inverse conversion sums each code point's JavaScript string length. The
conversion utility rejects positions that split a surrogate pair, negative or
out-of-range positions, and ranges that do not map to one transcript turn.

Transcript rendering may segment text to display overlaps. Selection mapping
therefore combines DOM boundary offsets with each text node's canonical
code-point start, rather than calculating against visible labels, badges, or
other mutable UI text.

## Server verification

Every new or adjusted span request supplies:

- expected annotation-set revision;
- immutable transcript hash;
- start and end turn identifiers;
- canonical speaker role;
- code-point start and exclusive end;
- selected text;
- label, dimension, and supported attributes.

The server reloads the saved run and rejects the request unless:

1. the set belongs to the reviewer and is editable;
2. the expected revision equals the locked set revision;
3. the submitted transcript hash equals both the set and run hash;
4. both turn identifiers are equal and identify one snapshot turn;
5. the speaker equals that turn's canonical role;
6. `0 <= start < end <= len(turn.text)`;
7. the canonical substring exactly equals submitted selected text;
8. the substring is not empty or whitespace-only;
9. the policy permits span authoring or boundary adjustment;
10. label, dimension, attributes, and overlap behavior satisfy the policy.

For a model boundary correction, the selected turn must also equal the
original model span's turn. Human-added boundary revisions retain the same
stable annotation identity.

## Integrity and adversarial cases

Tests cover ASCII, accented precomposed characters, curly quotes, emoji and
surrogate pairs, combining sequences, multiline turns, repeated identical
substrings, start/end boundaries, stale hashes, cross-turn ranges, zero-length
ranges, whitespace-only ranges, out-of-bounds positions, role mismatch, and
selected-text mismatch.

Repeated text is resolved only by the submitted offsets; the server never uses
`find` or chooses the first matching substring.

