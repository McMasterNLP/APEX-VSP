import { useEffect, useMemo, useRef, useState } from 'react'
import type { AxiosError } from 'axios'
import {
  fetchResearchAnnotationSet,
  createAuthoredRelation,
  createHumanAnnotation,
  declareAnnotationCoverage,
  getResearchApiMessage,
  saveResearchReviewDecision,
  reviseHumanAnnotation,
} from '@/api/research.api'
import type {
  AnnotationSetRecord,
  CanonicalSpanSelection,
  CoverageLevel,
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
  const [mode, setMode] = useState<'review' | 'add' | 'adjust' | 'relation'>('review')
  const [pendingSelection, setPendingSelection] = useState<CanonicalSpanSelection | null>(null)
  const [authoringLabel, setAuthoringLabel] = useState('')
  const [authoringDimension, setAuthoringDimension] = useState('')
  const [adjustHumanId, setAdjustHumanId] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [relationSource, setRelationSource] = useState('')
  const [relationTarget, setRelationTarget] = useState('')
  const [relationType, setRelationType] = useState('')
  const [coverage, setCoverage] = useState<CoverageLevel>(annotationSet.coverage_level ?? 'not_assessed')
  const modeButtonRef = useRef<HTMLButtonElement>(null)
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
  const spanPolicy = annotationSet.annotation_policy.label_policies.find((item) => item.projection_type === 'span_annotation')
  const activeHuman = annotationSet.active_human_annotations ?? []
  const resolvedSpans = annotationSet.reference_projection?.projection.spans ?? annotationSet.resolved_projection.spans
  const displayedSpans = useMemo(() => {
    const byId = new Map(run.envelope.projection.spans.map((item) => [item.prediction_id, item]))
    for (const item of resolvedSpans) byId.set(item.prediction_id, item)
    for (const decision of annotationSet.effective_decisions) if (decision.decision === 'rejected') byId.delete(decision.prediction_id)
    return [...byId.values()]
  }, [annotationSet.effective_decisions, resolvedSpans, run.envelope.projection.spans])

  const cancelSelection = () => {
    setPendingSelection(null)
    setAdjustHumanId(null)
    window.getSelection()?.removeAllRanges()
    setAnnouncement('Pending selection cancelled.')
    modeButtonRef.current?.focus()
  }

  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && pendingSelection) cancelSelection()
    }
    document.addEventListener('keydown', onEscape)
    return () => document.removeEventListener('keydown', onEscape)
  })

  const chooseMode = (next: typeof mode) => {
    if (next !== mode) setPendingSelection(null)
    setMode(next)
    setAnnouncement(`${next.replace('_', ' ')} mode active.`)
  }

  const onSpanSelection = (selection: CanonicalSpanSelection) => {
    setPendingSelection(selection)
    setAuthoringLabel(
      mode === 'adjust' && prediction?.original_prediction.projection_type === 'span_annotation'
        ? prediction.original_prediction.label
        : spanPolicy?.allowed_labels[0] ?? ''
    )
    setAuthoringDimension('')
    setAnnouncement('Selection ready. Choose a label and save, or press Escape to cancel.')
  }

  const savePendingSpan = async () => {
    if (!pendingSelection) return
    setSaving(true); setError(null)
    try {
      let next: AnnotationSetRecord
      if (mode === 'add') {
        const attributePolicy = annotationSet.annotation_policy.span_authoring?.attribute_policies.find((item) => item.required_for_labels.includes(authoringLabel))
        next = await createHumanAnnotation(annotationSet.annotation_set_uuid, {
          expected_set_revision: annotationSet.revision,
          selection: pendingSelection,
          label: authoringLabel,
          dimension: authoringDimension || null,
          attributes: attributePolicy ? [{ identifier: attributePolicy.identifier, value: attributePolicy.allowed_values[0] }] : [],
        })
      } else if (adjustHumanId) {
        const human = activeHuman.find((item) => item.annotation_id === adjustHumanId)!
        next = await reviseHumanAnnotation(annotationSet.annotation_set_uuid, adjustHumanId, {
          expected_set_revision: annotationSet.revision,
          expected_annotation_revision: human.revision_number,
          operation: 'adjust_span', selection: pendingSelection,
        })
      } else if (prediction?.original_prediction.projection_type === 'span_annotation') {
        const original = prediction.original_prediction
        next = await saveResearchReviewDecision(annotationSet.annotation_set_uuid, prediction.prediction_id, {
          expected_set_revision: annotationSet.revision,
          expected_decision_revision: currentDecision?.revision_number ?? null,
          decision: 'corrected',
          correction: {
            correction_type: 'span_annotation', corrected_label: original.label,
            corrected_dimension: original.dimension ?? null,
            corrected_start_char: pendingSelection.start_offset,
            corrected_end_char: pendingSelection.end_offset,
            corrected_text: pendingSelection.selected_text,
            transcript_hash: pendingSelection.transcript_hash,
            corrected_turn_number: pendingSelection.start_turn_number,
            corrected_speaker: pendingSelection.speaker,
          },
        })
      } else throw new Error('Choose a span annotation before adjusting boundaries.')
      onChange(next); setPendingSelection(null); setAnnouncement('Annotation revision saved.')
      modeButtonRef.current?.focus()
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'The annotation revision could not be saved.'))
    } finally { setSaving(false) }
  }

  const lifecycleHuman = async (annotationId: string, operation: 'retire' | 'restore') => {
    const history = annotationSet.human_annotation_revisions ?? []
    const current = [...history].reverse().find((item) => item.annotation_id === annotationId)
    if (!current) return
    try {
      const next = await reviseHumanAnnotation(annotationSet.annotation_set_uuid, annotationId, {
        expected_set_revision: annotationSet.revision, expected_annotation_revision: current.revision_number, operation,
      })
      onChange(next); setAnnouncement(`Human annotation ${operation === 'retire' ? 'retired' : 'restored'}.`)
    } catch (caught) { setError(getResearchApiMessage(caught, 'The lifecycle change could not be saved.')) }
  }

  const relabelHuman = async (annotationId: string, label: string) => {
    const current = activeHuman.find((item) => item.annotation_id === annotationId)
    if (!current) return
    try {
      const next = await reviseHumanAnnotation(annotationSet.annotation_set_uuid, annotationId, {
        expected_set_revision: annotationSet.revision,
        expected_annotation_revision: current.revision_number,
        operation: 'relabel', label,
        dimension: label === 'empathic_opportunity' ? current.dimension ?? spanPolicy?.allowed_dimensions[0] ?? null : null,
      })
      onChange(next); setAnnouncement('Human annotation relabeled.')
    } catch (caught) { setError(getResearchApiMessage(caught, 'The label revision could not be saved.')) }
  }

  const saveRelation = async () => {
    try {
      const next = await createAuthoredRelation(annotationSet.annotation_set_uuid, {
        expected_set_revision: annotationSet.revision, source_annotation_id: relationSource,
        target_annotation_id: relationTarget, relation_type: relationType,
      })
      onChange(next); setAnnouncement('Relation saved.')
    } catch (caught) { setError(getResearchApiMessage(caught, 'The relation could not be saved.')) }
  }

  const saveCoverage = async () => {
    try {
      const next = await declareAnnotationCoverage(annotationSet.annotation_set_uuid, annotationSet.revision, coverage)
      onChange(next); setAnnouncement('Coverage declaration saved.')
    } catch (caught) { setError(getResearchApiMessage(caught, 'Coverage could not be saved.')) }
  }

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
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Annotation modes">
        <Button ref={modeButtonRef} type="button" size="sm" variant={mode === 'review' ? 'default' : 'outline'} onClick={() => chooseMode('review')}>Review</Button>
        <Button type="button" size="sm" variant={mode === 'add' ? 'default' : 'outline'} disabled={annotationSet.locked || !annotationSet.annotation_policy.span_authoring?.supported} onClick={() => chooseMode('add')}>Add annotation</Button>
        <Button type="button" size="sm" variant={mode === 'adjust' ? 'default' : 'outline'} disabled={annotationSet.locked || !annotationSet.annotation_policy.operations.span_annotation.adjust_span} onClick={() => chooseMode('adjust')}>Adjust span</Button>
        <Button type="button" size="sm" variant={mode === 'relation' ? 'default' : 'outline'} disabled={annotationSet.locked || !(annotationSet.annotation_policy.relation_types?.length)} onClick={() => chooseMode('relation')}>Relation</Button>
      </div>
      {!annotationSet.annotation_policy.span_authoring?.supported && <p role="status" className="text-sm text-amber-800">This evaluator does not support transcript span authoring; predictions remain read-only.</p>}
      <p aria-live="polite" className="sr-only">{announcement}</p>
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
              spans={displayedSpans}
              turnLabels={run.envelope.projection.turn_labels}
              focusedTurn={focusedTurns[0] ?? null}
              effectiveDecisions={annotationSet.effective_decisions}
              selectedPredictionId={prediction.prediction_id}
              annotationMode={mode === 'add' || mode === 'adjust'}
              transcriptHash={annotationSet.transcript_hash}
              onSelection={onSpanSelection}
              onInvalidSelection={(message) => { setError(message); setAnnouncement(message) }}
            />
            {(mode === 'add' || mode === 'adjust') && <p className="mt-2 text-xs text-gray-700">Select one contiguous range in a single turn, then choose “Annotate selected text.” Escape cancels. Offsets use Unicode code points.</p>}
            {pendingSelection && (
              <section aria-label="Annotation composer" className="mt-3 space-y-3 rounded-md border border-indigo-300 bg-indigo-50 p-3">
                <p className="font-semibold">Selected text: “{pendingSelection.selected_text}”</p>
                <p className="text-xs">Turn {pendingSelection.start_turn_number} · {pendingSelection.speaker} · [{pendingSelection.start_offset}, {pendingSelection.end_offset})</p>
                {mode === 'add' && <><label className="block text-sm font-medium">Annotation type<select aria-label="Annotation type" value={authoringLabel} onChange={(event) => setAuthoringLabel(event.target.value)} className="mt-1 block w-full rounded border p-2">{spanPolicy?.allowed_labels.map((label) => <option key={label}>{label}</option>)}</select></label>{authoringLabel === 'empathic_opportunity' && <label className="block text-sm font-medium">Dimension<select aria-label="Annotation dimension" value={authoringDimension} onChange={(event) => setAuthoringDimension(event.target.value)} className="mt-1 block w-full rounded border p-2"><option value="">Choose…</option>{spanPolicy?.allowed_dimensions.map((item) => <option key={item}>{item}</option>)}</select></label>}</>}
                <p className="text-xs">{annotationSet.annotation_policy.span_authoring?.guideline_help_text}</p>
                <div className="flex gap-2"><Button type="button" size="sm" disabled={saving || !authoringLabel || (authoringLabel === 'empathic_opportunity' && !authoringDimension)} onClick={() => void savePendingSpan()}>{mode === 'add' ? 'Annotate selected text' : 'Save adjusted span'}</Button><Button type="button" size="sm" variant="outline" onClick={cancelSelection}>Cancel</Button></div>
              </section>
            )}
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
      <section aria-labelledby="human-annotations-heading" className="space-y-2 rounded-md border p-3">
        <h6 id="human-annotations-heading" className="font-semibold">Human-added annotations</h6>
        {(annotationSet.human_annotation_revisions ?? []).length === 0 && <p className="text-sm text-gray-600">None added.</p>}
        {activeHuman.map((item) => <div key={item.annotation_id} className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span><strong>{item.label}</strong> · turn {item.turn_number} [{item.start_offset}, {item.end_offset}) · revision {item.revision_number}</span><div className="flex flex-wrap gap-2"><label className="sr-only" htmlFor={`relabel-${item.annotation_id}`}>Relabel {item.label}</label><select id={`relabel-${item.annotation_id}`} aria-label={`Relabel ${item.label}`} value={item.label} onChange={(event) => void relabelHuman(item.annotation_id, event.target.value)} className="rounded border bg-white px-2">{spanPolicy?.allowed_labels.map((label) => <option key={label}>{label}</option>)}</select><Button type="button" size="sm" variant="outline" onClick={() => { setAdjustHumanId(item.annotation_id); chooseMode('adjust') }}>Adjust boundaries</Button><Button type="button" size="sm" variant="outline" onClick={() => void lifecycleHuman(item.annotation_id, 'retire')}>Retire</Button></div></div><details className="mt-2"><summary className="cursor-pointer font-medium">Revision history and provenance</summary><ul className="mt-1 list-disc pl-5">{(annotationSet.human_annotation_revisions ?? []).filter((revision) => revision.annotation_id === item.annotation_id).map((revision) => <li key={revision.revision_uuid}>{revision.operation} · revision {revision.revision_number} · {revision.guideline_identifier} v{revision.guideline_version} · {revision.reviewer_reference}</li>)}</ul></details></div>)}
        {(annotationSet.human_annotation_revisions ?? []).filter((item, index, all) => item.status === 'retired' && !all.slice(index + 1).some((candidate) => candidate.annotation_id === item.annotation_id)).map((item) => <div key={item.annotation_id} className="flex justify-between rounded border border-dashed p-2 text-sm"><span>Retired: {item.label} · revision {item.revision_number}</span><Button type="button" size="sm" variant="outline" onClick={() => void lifecycleHuman(item.annotation_id, 'restore')}>Restore</Button></div>)}
      </section>
      {mode === 'relation' && <section aria-label="Relation composer" className="grid gap-2 rounded-md border border-violet-300 p-3 sm:grid-cols-3"><label className="text-sm">Source<select aria-label="Relation source" className="block w-full rounded border p-2" value={relationSource} onChange={(event) => setRelationSource(event.target.value)}><option value="">Choose…</option>{resolvedSpans.map((item) => <option value={item.prediction_id} key={item.prediction_id}>{item.label} · turn {item.turn_number}</option>)}</select></label><label className="text-sm">Target<select aria-label="Relation target" className="block w-full rounded border p-2" value={relationTarget} onChange={(event) => setRelationTarget(event.target.value)}><option value="">Choose…</option>{resolvedSpans.map((item) => <option value={item.prediction_id} key={item.prediction_id}>{item.label} · turn {item.turn_number}</option>)}</select></label><label className="text-sm">Type<select aria-label="Relation type" className="block w-full rounded border p-2" value={relationType} onChange={(event) => setRelationType(event.target.value)}><option value="">Choose…</option>{annotationSet.annotation_policy.relation_types?.map((item) => <option key={item.relation_type}>{item.relation_type}</option>)}</select></label><Button type="button" size="sm" disabled={!relationSource || !relationTarget || !relationType} onClick={() => void saveRelation()}>Save relation</Button><ul className="sm:col-span-3">{(annotationSet.active_authored_relations ?? []).map((item) => <li key={item.relation_id} className="text-sm">{item.relation_type}: {item.source_annotation_id} → {item.target_annotation_id} · revision {item.revision_number}</li>)}</ul></section>}
      <section aria-label="Coverage declaration" className="flex flex-wrap items-end gap-2 rounded-md border p-3"><label className="text-sm font-medium">Annotation coverage<select aria-label="Annotation coverage" className="mt-1 block rounded border p-2" value={coverage} onChange={(event) => setCoverage(event.target.value as CoverageLevel)}>{(annotationSet.annotation_policy.coverage?.supported_values ?? ['not_assessed', 'prediction_review_only', 'fixed_inventory_complete']).map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></label><Button type="button" size="sm" disabled={annotationSet.locked} onClick={() => void saveCoverage()}>Save coverage</Button><p className="text-xs text-gray-600">Recall and F1 remain ineligible unless coverage is exhaustive.</p></section>
    </section>
  )
}
