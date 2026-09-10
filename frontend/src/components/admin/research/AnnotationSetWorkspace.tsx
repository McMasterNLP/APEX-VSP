import { useEffect, useMemo, useState } from 'react'
import type { AxiosError } from 'axios'
import {
  fetchResearchAnnotationSet,
  getResearchApiMessage,
  saveResearchReviewDecision,
} from '@/api/research.api'
import type {
  AnnotationSetRecord,
  DecisionRevisionRecord,
  EvaluationRunRecord,
  ResearchRevisionConflict,
  ReviewablePrediction,
  TypedCorrection,
} from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'
import { TranscriptAnnotationView } from './TranscriptAnnotationView'
import { PredictionReviewCard } from './PredictionReviewCard'
import { AnnotationSetActions } from './AnnotationSetActions'
import { ReviewProgress } from './ReviewProgress'

function evidenceTurns(
  prediction: ReviewablePrediction,
  run: EvaluationRunRecord
): number[] {
  const original = prediction.original_prediction
  if (original.projection_type === 'span_annotation' || original.projection_type === 'turn_label') {
    return [original.turn_number]
  }
  if (original.projection_type === 'dimension_rating' || original.projection_type === 'finding') {
    return original.evidence_turns
  }
  if (original.projection_type === 'relation') {
    const spanById = new Map(
      run.envelope.projection.spans.map((span) => [span.prediction_id, span.turn_number])
    )
    return [
      spanById.get(original.source_annotation_id),
      spanById.get(original.target_annotation_id),
    ].filter((turn): turn is number => turn !== undefined)
  }
  return []
}

function revisionConflict(error: unknown): ResearchRevisionConflict | null {
  const payload = (error as AxiosError<{ message?: ResearchRevisionConflict }>).response?.data
    ?.message
  return payload?.category === 'revision_conflict' ? payload : null
}

export function AnnotationSetWorkspace({
  run,
  annotationSet,
  onChange,
}: {
  run: EvaluationRunRecord
  annotationSet: AnnotationSetRecord
  onChange: (next: AnnotationSetRecord) => void
}) {
  const [index, setIndex] = useState(0)
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<ResearchRevisionConflict | null>(null)
  const inventory = annotationSet.eligible_predictions
  const prediction = inventory[index] ?? null

  useEffect(() => {
    if (index >= inventory.length) setIndex(Math.max(0, inventory.length - 1))
  }, [index, inventory.length])

  const effectiveByPrediction = useMemo(
    () => new Map(annotationSet.effective_decisions.map((item) => [item.prediction_id, item])),
    [annotationSet.effective_decisions]
  )
  const currentDecision: DecisionRevisionRecord | null = prediction
    ? effectiveByPrediction.get(prediction.prediction_id) ?? null
    : null
  const focusedTurns = prediction ? evidenceTurns(prediction, run) : []

  const save = async (
    decision: 'confirmed' | 'rejected' | 'corrected' | 'insufficient_evidence',
    correction: TypedCorrection | null,
    reviewerNote: string
  ) => {
    if (!prediction) return
    setSaving(true)
    setError(null)
    setConflict(null)
    try {
      const next = await saveResearchReviewDecision(
        annotationSet.annotation_set_uuid,
        prediction.prediction_id,
        {
          expected_set_revision: annotationSet.revision,
          expected_decision_revision: currentDecision?.revision_number ?? null,
          decision,
          correction,
          reviewer_note: reviewerNote || null,
        }
      )
      onChange(next)
    } catch (caught) {
      const conflictPayload = revisionConflict(caught)
      if (conflictPayload) {
        setConflict(conflictPayload)
        setError('Another review change exists. Refresh before saving this decision.')
      } else {
        setError(getResearchApiMessage(caught, 'The review decision could not be saved.'))
      }
    } finally {
      setSaving(false)
    }
  }

  const refresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      onChange(await fetchResearchAnnotationSet(annotationSet.annotation_set_uuid))
      setConflict(null)
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'The annotation set could not be refreshed.'))
    } finally {
      setRefreshing(false)
    }
  }

  const onQueueKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return
    if (event.key === 'ArrowRight' && index < inventory.length - 1) {
      event.preventDefault()
      setIndex((current) => current + 1)
    }
    if (event.key === 'ArrowLeft' && index > 0) {
      event.preventDefault()
      setIndex((current) => current - 1)
    }
  }

  return (
    <section aria-labelledby="annotation-workspace-heading" className="space-y-4 rounded-lg border-2 border-indigo-200 p-4">
      <div>
        <h5 id="annotation-workspace-heading" className="font-semibold text-gray-950">Human annotation workspace</h5>
        <p className="text-sm text-gray-700">Model predictions remain immutable. Human decisions are stored as separate revisions.</p>
      </div>
      {!annotationSet.transcript_matches_current && (
        <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm font-medium text-amber-950">
          Transcript mismatch: this review remains tied to the immutable saved snapshot.
        </p>
      )}
      <ReviewProgress progress={annotationSet.progress} />
      <AnnotationSetActions annotationSet={annotationSet} onChange={onChange} />
      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span>{error}</span>
          {conflict && <Button type="button" size="sm" variant="outline" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? 'Refreshing…' : 'Refresh newer review data'}</Button>}
        </div>
      )}
      {prediction ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)]">
          <div>
            <TranscriptAnnotationView
              turns={run.transcript_snapshot}
              spans={run.envelope.projection.spans}
              turnLabels={run.envelope.projection.turn_labels}
              focusedTurn={focusedTurns[0] ?? null}
              effectiveDecisions={annotationSet.effective_decisions}
              selectedPredictionId={prediction.prediction_id}
            />
          </div>
          <section tabIndex={0} onKeyDown={onQueueKeyDown} aria-label="Prediction review queue" className="space-y-3 rounded-md outline-none focus:ring-2 focus:ring-indigo-600">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">Item {index + 1} of {inventory.length}</p>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" disabled={index === 0 || saving} onClick={() => setIndex((current) => current - 1)}>Previous</Button>
                <Button type="button" size="sm" variant="outline" disabled={index === inventory.length - 1 || saving} onClick={() => setIndex((current) => current + 1)}>Next</Button>
              </div>
            </div>
            <PredictionReviewCard
              key={prediction.prediction_id}
              prediction={prediction}
              policy={annotationSet.annotation_policy}
              transcriptTurnNumbers={run.transcript_snapshot.map((turn) => turn.turn_number)}
              currentDecision={currentDecision}
              disabled={saving || annotationSet.locked}
              onSave={save}
            />
          </section>
        </div>
      ) : (
        <p className="text-sm text-gray-600">No predictions are eligible for review.</p>
      )}
    </section>
  )
}
