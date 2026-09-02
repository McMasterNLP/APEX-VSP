import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  CanonicalSpanSelection,
  ResearchTranscriptTurn,
  DecisionRevisionRecord,
  SpanAnnotation,
  TurnLabel,
} from '@/types/researchEvaluation'
import { canonicalSelectionFromRange, codePointOffsetToUtf16 } from './spanOffsets'

interface TranscriptAnnotationViewProps {
  turns: ResearchTranscriptTurn[]
  spans: SpanAnnotation[]
  turnLabels: TurnLabel[]
  focusedTurn: number | null
  effectiveDecisions?: DecisionRevisionRecord[]
  selectedPredictionId?: string | null
  annotationMode?: boolean
  transcriptHash?: string
  onSelection?: (selection: CanonicalSpanSelection) => void
  onInvalidSelection?: (message: string) => void
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
      span.end_offset <= Array.from(turn.text).length &&
      turn.text.slice(codePointOffsetToUtf16(turn.text, span.start_offset), codePointOffsetToUtf16(turn.text, span.end_offset)) === span.quoted_text
  )
}

function segmentTurnText(
  turn: ResearchTranscriptTurn,
  spans: SpanAnnotation[]
): TextSegment[] {
  const boundaries = new Set([0, Array.from(turn.text).length])
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
      text: turn.text.slice(codePointOffsetToUtf16(turn.text, start), codePointOffsetToUtf16(turn.text, end)),
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
  effectiveDecisions = [],
  selectedPredictionId = null,
  annotationMode = false,
  transcriptHash,
  onSelection,
  onInvalidSelection,
}: TranscriptAnnotationViewProps) {
  const [selected, setSelected] = useState<SpanAnnotation | null>(null)
  const [overlapChoices, setOverlapChoices] = useState<SpanAnnotation[]>([])
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
  const decisionByPrediction = useMemo(
    () => new Map(effectiveDecisions.map((decision) => [decision.prediction_id, decision.decision])),
    [effectiveDecisions]
  )

  const captureSelection = () => {
    if (!annotationMode || !transcriptHash || !onSelection) return
    const browserSelection = window.getSelection()
    if (!browserSelection || browserSelection.rangeCount === 0 || browserSelection.isCollapsed) return
    const range = browserSelection.getRangeAt(0)
    const startElement = (range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement) as HTMLElement | null
    const endElement = (range.endContainer.nodeType === Node.ELEMENT_NODE ? range.endContainer : range.endContainer.parentElement) as HTMLElement | null
    const startTurnText = startElement?.closest<HTMLElement>('[data-turn-text]')
    const endTurnText = endElement?.closest<HTMLElement>('[data-turn-text]')
    if (!startTurnText || startTurnText !== endTurnText) {
      onInvalidSelection?.('Select text within a single transcript turn.')
      return
    }
    const turnNumber = Number(startTurnText.dataset.turnText)
    const turn = turns.find((item) => item.turn_number === turnNumber)
    if (!turn) return
    try {
      onSelection(canonicalSelectionFromRange(range, startTurnText, turn, transcriptHash))
    } catch (error) {
      onInvalidSelection?.(error instanceof Error ? error.message : 'The selection is invalid.')
    }
  }

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
      <div onMouseUp={captureSelection} onKeyUp={(event) => { if (event.shiftKey) captureSelection() }} className="max-h-96 space-y-3 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-3">
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
                    {label.label}: {label.subtype ?? label.dimension ?? 'labeled'} · {decisionByPrediction.get(label.prediction_id)?.replaceAll('_', ' ') ?? 'unreviewed'}
                  </span>
                ))}
              </div>
              <p data-turn-text={turn.turn_number} className="whitespace-pre-wrap text-sm leading-7 text-gray-950">
                {segments.map((segment) => {
                  if (segment.annotations.length === 0) {
                    return <span key={`${segment.start}-${segment.end}`}>{segment.text}</span>
                  }
                  const annotationLabels = segment.annotations.map(
                    (annotation) =>
                      `${annotation.label}${annotation.subtype ? ` (${annotation.subtype})` : ''}`
                  )
                  const primary = segment.annotations[0]
                  const decisionState = decisionByPrediction.get(primary.prediction_id) ?? 'unreviewed'
                  const selectedState = segment.annotations.some(
                    (annotation) => annotation.prediction_id === selectedPredictionId
                  )
                  const humanState = primary.provenance?.method === 'human_annotation'
                  return (
                    <button
                      key={`${segment.start}-${segment.end}`}
                      type="button"
                      onClick={() => {
                        if (segment.annotations.length > 1) setOverlapChoices(segment.annotations)
                        else setSelected(primary)
                      }}
                      aria-label={`${annotationLabels.join(', ')}: ${segment.text}; ${primary.provenance?.method === 'human_annotation' ? 'human added' : 'model prediction'}; human decision ${decisionState}`}
                      data-review-state={decisionState}
                      className={`mx-0.5 rounded-sm border-b-2 px-0.5 text-left text-gray-950 outline-none focus:ring-2 focus:ring-indigo-600 ${selectedState ? 'border-indigo-800 bg-indigo-200 ring-1 ring-indigo-700' : humanState ? 'border-emerald-700 bg-emerald-100 underline decoration-dotted' : 'border-indigo-600 bg-indigo-100'}`}
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
          <p className="text-xs font-medium">Source: {selected.provenance?.method === 'human_annotation' ? 'Human added' : selected.provenance?.method === 'human_correction' ? 'Human correction of model prediction' : 'Model prediction'}</p>
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
      {overlapChoices.length > 1 && (
        <div className="rounded-md border border-violet-300 bg-violet-50 p-3" role="dialog" aria-label="Overlapping annotations">
          <p className="text-sm font-semibold">Choose an overlapping annotation</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {overlapChoices.map((item) => <button key={item.prediction_id} type="button" className="rounded border border-violet-500 bg-white px-2 py-1 text-sm focus:ring-2 focus:ring-violet-700" onClick={() => { setSelected(item); setOverlapChoices([]) }}>{item.label} · {item.provenance?.method === 'human_annotation' ? 'human' : 'model'}</button>)}
          </div>
        </div>
      )}
    </div>
  )
}
