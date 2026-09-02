import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  ResearchTranscriptTurn,
  SpanAnnotation,
  TurnLabel,
} from '@/types/researchEvaluation'

interface TranscriptAnnotationViewProps {
  turns: ResearchTranscriptTurn[]
  spans: SpanAnnotation[]
  turnLabels: TurnLabel[]
  focusedTurn: number | null
}

interface TextSegment {
  start: number
  end: number
  text: string
  annotations: SpanAnnotation[]
}

function validSpansForTurn(turn: ResearchTranscriptTurn, spans: SpanAnnotation[]) {
  return spans.filter(
    (span) =>
      span.turn_number === turn.turn_number &&
      Number.isInteger(span.start_offset) &&
      Number.isInteger(span.end_offset) &&
      span.start_offset >= 0 &&
      span.end_offset > span.start_offset &&
      span.end_offset <= turn.text.length &&
      turn.text.slice(span.start_offset, span.end_offset) === span.quoted_text
  )
}

function segmentTurnText(
  turn: ResearchTranscriptTurn,
  spans: SpanAnnotation[]
): TextSegment[] {
  const boundaries = new Set([0, turn.text.length])
  for (const span of spans) {
    boundaries.add(span.start_offset)
    boundaries.add(span.end_offset)
  }
  const ordered = [...boundaries].sort((a, b) => a - b)
  return ordered.slice(0, -1).map((start, index) => {
    const end = ordered[index + 1]
    return {
      start,
      end,
      text: turn.text.slice(start, end),
      annotations: spans.filter(
        (span) => span.start_offset < end && span.end_offset > start
      ),
    }
  })
}

export function TranscriptAnnotationView({
  turns,
  spans,
  turnLabels,
  focusedTurn,
}: TranscriptAnnotationViewProps) {
  const [selected, setSelected] = useState<SpanAnnotation | null>(null)
  const turnRefs = useRef(new Map<number, HTMLDivElement>())

  useEffect(() => {
    if (focusedTurn === null) return
    const element = turnRefs.current.get(focusedTurn)
    element?.focus()
    element?.scrollIntoView?.({ block: 'nearest' })
  }, [focusedTurn])

  const { validByTurn, invalidCount } = useMemo(() => {
    const valid = new Map<number, SpanAnnotation[]>()
    let count = 0
    for (const turn of turns) {
      const matching = spans.filter((span) => span.turn_number === turn.turn_number)
      const validForTurn = validSpansForTurn(turn, matching)
      valid.set(turn.turn_number, validForTurn)
      count += matching.length - validForTurn.length
    }
    count += spans.filter((span) => !turns.some((turn) => turn.turn_number === span.turn_number)).length
    return { validByTurn: valid, invalidCount: count }
  }, [spans, turns])

  const labelsByTurn = useMemo(() => {
    const map = new Map<number, TurnLabel[]>()
    for (const label of turnLabels) {
      map.set(label.turn_number, [...(map.get(label.turn_number) ?? []), label])
    }
    return map
  }, [turnLabels])

  if (turns.length === 0) {
    return <p className="text-sm text-gray-600">No transcript turns are available.</p>
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">
        Annotation labels are written in text; color is supplementary. Select highlighted text for details.
      </p>
      {invalidCount > 0 && (
        <p role="status" className="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-950">
          {invalidCount} invalid span {invalidCount === 1 ? 'was' : 'were'} ignored defensively.
        </p>
      )}
      <div className="max-h-96 space-y-3 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-3">
        {turns.map((turn) => {
          const validSpans = validByTurn.get(turn.turn_number) ?? []
          const segments = segmentTurnText(turn, validSpans)
          const labels = labelsByTurn.get(turn.turn_number) ?? []
          return (
            <div
              key={turn.turn_number}
              ref={(element) => {
                if (element) turnRefs.current.set(turn.turn_number, element)
                else turnRefs.current.delete(turn.turn_number)
              }}
              tabIndex={-1}
              data-turn-number={turn.turn_number}
              className="rounded-md border border-transparent p-2 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
            >
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                <span className="font-semibold text-gray-800">
                  Turn {turn.turn_number} · {turn.role}
                </span>
                {labels.map((label) => (
                  <span
                    key={label.prediction_id}
                    className="rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-sky-950"
                  >
                    {label.label}: {label.subtype ?? label.dimension ?? 'labeled'}
                  </span>
                ))}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-7 text-gray-950">
                {segments.map((segment) => {
                  if (segment.annotations.length === 0) {
                    return <span key={`${segment.start}-${segment.end}`}>{segment.text}</span>
                  }
                  const annotationLabels = segment.annotations.map(
                    (annotation) =>
                      `${annotation.label}${annotation.subtype ? ` (${annotation.subtype})` : ''}`
                  )
                  return (
                    <button
                      key={`${segment.start}-${segment.end}`}
                      type="button"
                      onClick={() => setSelected(segment.annotations[0])}
                      aria-label={`${annotationLabels.join(', ')}: ${segment.text}`}
                      className="mx-0.5 rounded-sm border-b-2 border-indigo-600 bg-indigo-100 px-0.5 text-left text-gray-950 outline-none focus:ring-2 focus:ring-indigo-600"
                    >
                      {segment.text}
                      {segment.annotations.length > 1 && (
                        <sup className="ml-0.5 font-bold" aria-label={`${segment.annotations.length} overlapping annotations`}>
                          {segment.annotations.length}
                        </sup>
                      )}
                    </button>
                  )
                })}
              </p>
            </div>
          )
        })}
      </div>
      {spans.length === 0 && (
        <p className="text-sm text-gray-600">No span annotations were produced.</p>
      )}
      {selected && (
        <div className="rounded-md border border-indigo-200 bg-indigo-50 p-3 text-sm" aria-live="polite">
          <p className="font-medium text-indigo-950">Selected annotation: {selected.label}</p>
          <dl className="mt-1 grid gap-x-3 gap-y-1 sm:grid-cols-[max-content_1fr]">
            <dt className="font-medium">Turn</dt><dd>{selected.turn_number}</dd>
            <dt className="font-medium">Text</dt><dd>“{selected.quoted_text}”</dd>
            <dt className="font-medium">Dimension</dt><dd>{selected.dimension ?? '—'}</dd>
            <dt className="font-medium">Subtype</dt><dd>{selected.subtype ?? '—'}</dd>
            <dt className="font-medium">Confidence</dt>
            <dd>{selected.confidence == null ? 'Not supplied' : selected.confidence.toFixed(2)}</dd>
            <dt className="font-medium">Native source</dt><dd className="break-all font-mono text-xs">{selected.source_reference.native_path}</dd>
          </dl>
        </div>
      )}
    </div>
  )
}
