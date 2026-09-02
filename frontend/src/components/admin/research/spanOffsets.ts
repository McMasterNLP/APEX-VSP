import type { CanonicalSpanSelection, ResearchTranscriptTurn } from '@/types/researchEvaluation'

export function utf16OffsetToCodePoint(text: string, utf16Offset: number): number {
  if (!Number.isInteger(utf16Offset) || utf16Offset < 0 || utf16Offset > text.length) {
    throw new Error('Selection offset is outside the transcript text.')
  }
  const previous = text.charCodeAt(utf16Offset - 1)
  const current = text.charCodeAt(utf16Offset)
  if (previous >= 0xd800 && previous <= 0xdbff && current >= 0xdc00 && current <= 0xdfff) {
    throw new Error('Selection cannot split a Unicode character.')
  }
  return Array.from(text.slice(0, utf16Offset)).length
}

export function codePointOffsetToUtf16(text: string, codePointOffset: number): number {
  const points = Array.from(text)
  if (!Number.isInteger(codePointOffset) || codePointOffset < 0 || codePointOffset > points.length) {
    throw new Error('Canonical offset is outside the transcript text.')
  }
  return points.slice(0, codePointOffset).join('').length
}

export function domPointToUtf16Offset(root: Node, node: Node, offset: number): number {
  const range = document.createRange()
  range.selectNodeContents(root)
  try {
    range.setEnd(node, offset)
  } catch {
    throw new Error('Selection is not contained by one transcript turn.')
  }
  return range.toString().length
}

export function canonicalSelectionFromRange(
  range: Range,
  turnElement: HTMLElement,
  turn: ResearchTranscriptTurn,
  transcriptHash: string
): CanonicalSpanSelection {
  if (!turnElement.contains(range.startContainer) || !turnElement.contains(range.endContainer)) {
    throw new Error('Select text within a single transcript turn.')
  }
  const startUtf16 = domPointToUtf16Offset(turnElement, range.startContainer, range.startOffset)
  const endUtf16 = domPointToUtf16Offset(turnElement, range.endContainer, range.endOffset)
  const start = utf16OffsetToCodePoint(turn.text, Math.min(startUtf16, endUtf16))
  const end = utf16OffsetToCodePoint(turn.text, Math.max(startUtf16, endUtf16))
  const selectedText = Array.from(turn.text).slice(start, end).join('')
  if (end <= start || !selectedText.trim()) throw new Error('Select non-whitespace transcript text.')
  return {
    transcript_hash: transcriptHash,
    start_turn_number: turn.turn_number,
    end_turn_number: turn.turn_number,
    speaker: turn.role,
    start_offset: start,
    end_offset: end,
    selected_text: selectedText,
  }
}
