import { describe, expect, it } from 'vitest'
import { codePointOffsetToUtf16, utf16OffsetToCodePoint } from './spanOffsets'

describe('canonical Unicode span offsets', () => {
  it.each([
    ['plain text', 5],
    ['café', 4],
    ['“hello”', 7],
    ['A😀B', 2],
    ['e\u0301motion', 2],
    ['line one\nline two', 9],
  ])('round trips code-point offsets for %s', (text, offset) => {
    const bounded = Math.min(offset, Array.from(text).length)
    expect(utf16OffsetToCodePoint(text, codePointOffsetToUtf16(text, bounded))).toBe(bounded)
  })

  it('accounts for browser surrogate pairs', () => {
    expect(codePointOffsetToUtf16('A😀B', 2)).toBe(3)
    expect(utf16OffsetToCodePoint('A😀B', 3)).toBe(2)
    expect(() => utf16OffsetToCodePoint('A😀B', 2)).toThrow(/split/i)
  })
})
