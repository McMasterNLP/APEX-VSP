import { useEffect, useMemo, useState } from 'react'
import type {
  AnnotationPolicyDescriptor,
  DecisionRevisionRecord,
  DimensionRating,
  DimensionRatingCorrection,
  ReviewablePrediction,
  SpanAnnotation,
  SpanCorrection,
  TurnLabel,
  TurnLabelCorrection,
  TypedCorrection,
} from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface ReviewControlsProps {
  prediction: ReviewablePrediction
  policy: AnnotationPolicyDescriptor
  transcriptTurnNumbers: number[]
  currentDecision: DecisionRevisionRecord | null
  disabled: boolean
  onSave: (
    decision: 'confirmed' | 'rejected' | 'corrected' | 'insufficient_evidence',
    correction: TypedCorrection | null,
    reviewerNote: string
  ) => Promise<void>
}

export function ReviewControls({
  prediction,
  policy,
  transcriptTurnNumbers,
  currentDecision,
  disabled,
  onSave,
}: ReviewControlsProps) {
  const [note, setNote] = useState(currentDecision?.reviewer_note ?? '')
  const [correcting, setCorrecting] = useState(false)

  useEffect(() => {
    setNote(currentDecision?.reviewer_note ?? '')
    // Collapse the correction form whenever the prediction changes, or once this prediction's
    // decision itself changes (a successful save gets a fresh decision_uuid) — so "Correct"
    // doesn't stay open after the item it belonged to has moved on.
    setCorrecting(false)
  }, [prediction.prediction_id, currentDecision?.decision_uuid, currentDecision?.reviewer_note])

  const save = (
    decision: 'confirmed' | 'rejected' | 'corrected' | 'insufficient_evidence',
    correction: TypedCorrection | null = null
  ) => onSave(decision, correction, note)

  const supportsLabelCorrection =
    (prediction.projection_type === 'span_annotation' || prediction.projection_type === 'turn_label') &&
    (prediction.allowed_operations.change_label || prediction.allowed_operations.change_dimension)
  const supportsRatingCorrection =
    prediction.projection_type === 'dimension_rating' && prediction.allowed_operations.change_rating
  const supportsCorrect = supportsLabelCorrection || supportsRatingCorrection
  const supportsInsufficientEvidence =
    prediction.projection_type === 'dimension_rating' && prediction.allowed_operations.mark_insufficient_evidence

  const markInsufficientEvidence = () => {
    const original = prediction.original_prediction as DimensionRating
    save('insufficient_evidence', {
      correction_type: 'dimension_rating',
      corrected_assessability: original.assessability,
      corrected_evidence_turns: original.evidence_turns,
      corrected_score: null,
      corrected_score_status: 'insufficient_evidence',
    })
  }

  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-gray-800">
        Reviewer note (optional, 1,000 characters maximum)
        <Textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={1000}
          disabled={disabled}
          aria-label="Reviewer note"
          className="mt-1"
        />
      </label>

      {/*
        Confirm, Reject, Correct (and, for ratings, Mark insufficient evidence) are presented as
        equal-weight peer decisions in one row, rather than Confirm/Reject as prominent buttons
        with correction buried in an always-open form below. Correct can't be a single click —
        it needs a label/score picked first — so it toggles the form open instead of saving
        directly; every other button here is a genuine one-click decision.
      */}
      <div className="flex flex-wrap gap-2" aria-label="Prediction decision controls">
        {prediction.allowed_operations.confirm && (
          <Button type="button" size="sm" disabled={disabled} onClick={() => void save('confirmed')}>
            Confirm prediction
          </Button>
        )}
        {prediction.allowed_operations.reject && (
          <Button type="button" size="sm" variant="destructive" disabled={disabled} onClick={() => void save('rejected')}>
            Reject prediction
          </Button>
        )}
        {supportsCorrect && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-indigo-300 text-indigo-900 hover:bg-indigo-50"
            aria-expanded={correcting}
            disabled={disabled}
            onClick={() => setCorrecting((current) => !current)}
          >
            {correcting ? 'Cancel correction' : 'Correct prediction'}
          </Button>
        )}
        {supportsInsufficientEvidence && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-amber-300 text-amber-900 hover:bg-amber-50"
            disabled={disabled}
            onClick={() => void markInsufficientEvidence()}
          >
            Mark insufficient evidence
          </Button>
        )}
      </div>

      {/*
        Confirm/Reject stay available for every prediction type, but correction is only
        meaningful for span/turn-label/dimension-rating predictions (see supportsCorrect
        above) — relations, global metrics, findings, and limitations have no correction
        UI at all. Without this caption that reads as a missing button rather than a
        deliberate scope boundary, so call it out explicitly instead of leaving it blank.
      */}
      {!supportsCorrect && !supportsInsufficientEvidence && (
        <p className="text-xs text-gray-500">
          This prediction type doesn&apos;t support correction — confirm or reject only.
        </p>
      )}

      {correcting && supportsLabelCorrection && (
        <LabelCorrectionControls
          prediction={prediction}
          policy={policy}
          disabled={disabled}
          onSave={(correction) => { void save('corrected', correction); setCorrecting(false) }}
          onCancel={() => setCorrecting(false)}
        />
      )}

      {correcting && supportsRatingCorrection && (
        <RatingCorrectionControls
          prediction={prediction}
          policy={policy}
          transcriptTurnNumbers={transcriptTurnNumbers}
          disabled={disabled}
          onCorrect={(correction) => { void save('corrected', correction); setCorrecting(false) }}
          onCancel={() => setCorrecting(false)}
        />
      )}
    </div>
  )
}

function LabelCorrectionControls({
  prediction,
  policy,
  disabled,
  onSave,
  onCancel,
}: {
  prediction: ReviewablePrediction
  policy: AnnotationPolicyDescriptor
  disabled: boolean
  onSave: (correction: SpanCorrection | TurnLabelCorrection) => void
  onCancel: () => void
}) {
  const original = prediction.original_prediction as SpanAnnotation | TurnLabel
  const labelPolicy = policy.label_policies.find(
    (item) => item.projection_type === prediction.projection_type
  )
  const [label, setLabel] = useState(original.label)
  const [dimension, setDimension] = useState(original.dimension ?? '')

  useEffect(() => {
    setLabel(original.label)
    setDimension(original.dimension ?? '')
  }, [prediction.prediction_id, original.label, original.dimension])

  if (!labelPolicy) return null
  const isSpan = prediction.projection_type === 'span_annotation'
  const dimensionRequired = isSpan && label === 'empathic_opportunity'
  const canSave =
    (label !== original.label || (dimension || null) !== (original.dimension ?? null)) &&
    (!dimensionRequired || dimension.length > 0)

  const changeLabel = (value: string) => {
    setLabel(value)
    if (isSpan && value !== 'empathic_opportunity') setDimension('')
  }

  const correction = (): SpanCorrection | TurnLabelCorrection =>
    isSpan
      ? {
          correction_type: 'span_annotation',
          corrected_label: label,
          corrected_dimension: dimension || null,
          corrected_start_char: null,
          corrected_end_char: null,
          corrected_text: null,
        }
      : {
          correction_type: 'turn_label',
          corrected_label: label,
          corrected_dimension: dimension || null,
        }

  return (
    <fieldset className="space-y-2 rounded-md border border-gray-200 p-3" disabled={disabled}>
      <legend className="px-1 text-sm font-semibold">Typed label correction</legend>
      {prediction.allowed_operations.change_label && (
        <label className="block text-sm">
          Corrected label
          <select aria-label="Corrected label" value={label} onChange={(event) => changeLabel(event.target.value)} className="mt-1 block w-full rounded border border-gray-300 bg-white px-2 py-1.5">
            {labelPolicy.allowed_labels.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
      )}
      {prediction.allowed_operations.change_dimension && (
        <label className="block text-sm">
          Corrected dimension
          <select aria-label="Corrected dimension" value={dimension} onChange={(event) => setDimension(event.target.value)} className="mt-1 block w-full rounded border border-gray-300 bg-white px-2 py-1.5">
            {labelPolicy.allow_null_dimension && !dimensionRequired && <option value="">No dimension</option>}
            {labelPolicy.allowed_dimensions.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" disabled={disabled || !canSave} onClick={() => onSave(correction())}>
          Save label correction
        </Button>
        <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <p className="text-xs text-gray-600">Span boundaries cannot be changed in Item 2A.</p>
    </fieldset>
  )
}

function RatingCorrectionControls({
  prediction,
  policy,
  transcriptTurnNumbers,
  disabled,
  onCorrect,
  onCancel,
}: {
  prediction: ReviewablePrediction
  policy: AnnotationPolicyDescriptor
  transcriptTurnNumbers: number[]
  disabled: boolean
  onCorrect: (correction: DimensionRatingCorrection) => void
  onCancel: () => void
}) {
  const original = prediction.original_prediction as DimensionRating
  const scale = policy.rating_scales.find(
    (item) => item.dimension_identifier === original.dimension_identifier
  )
  const [score, setScore] = useState(String(original.score ?? ''))
  const [evidence, setEvidence] = useState<number[]>(original.evidence_turns)
  const [assessability, setAssessability] = useState(original.assessability)

  useEffect(() => {
    setScore(String(original.score ?? ''))
    setEvidence(original.evidence_turns)
    setAssessability(original.assessability)
  }, [prediction.prediction_id, original])

  const evidenceSet = useMemo(() => new Set(evidence), [evidence])
  if (!scale) return null
  const toggleEvidence = (turn: number) => {
    setEvidence((current) =>
      current.includes(turn)
        ? current.filter((item) => item !== turn)
        : [...current, turn].sort((a, b) => a - b)
    )
  }
  const base = {
    correction_type: 'dimension_rating' as const,
    corrected_assessability: assessability,
    corrected_evidence_turns: evidence,
  }

  return (
    <fieldset className="space-y-3 rounded-md border border-gray-200 p-3" disabled={disabled}>
      <legend className="px-1 text-sm font-semibold">Typed rating correction</legend>
      {prediction.allowed_operations.change_rating && (
        <label className="block text-sm">
          Corrected score
          <select aria-label="Corrected score" value={score} onChange={(event) => setScore(event.target.value)} className="mt-1 block w-full rounded border border-gray-300 bg-white px-2 py-1.5">
            {scale.allowed_scores.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      )}
      {prediction.allowed_operations.change_assessability && scale.allow_assessability_correction && (
        <label className="block text-sm">
          Corrected assessability
          <select aria-label="Corrected assessability" value={assessability} onChange={(event) => setAssessability(event.target.value as DimensionRating['assessability'])} className="mt-1 block w-full rounded border border-gray-300 bg-white px-2 py-1.5">
            {scale.allowed_assessability.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
      )}
      {prediction.allowed_operations.change_evidence && (
        <div>
          <p className="text-sm font-medium">Evidence turns</p>
          <div className="mt-1 flex max-h-32 flex-wrap gap-2 overflow-y-auto" aria-label="Corrected evidence turns">
            {transcriptTurnNumbers.map((turn) => (
              <label key={turn} className="flex items-center gap-1 rounded border border-gray-300 px-2 py-1 text-xs">
                <input type="checkbox" checked={evidenceSet.has(turn)} onChange={() => toggleEvidence(turn)} />
                Turn {turn}
              </label>
            ))}
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {prediction.allowed_operations.change_rating && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled || score === ''}
            onClick={() => onCorrect({
              ...base,
              corrected_score: Number(score),
              corrected_score_status: 'available',
            })}
          >
            Save rating correction
          </Button>
        )}
        <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </fieldset>
  )
}
