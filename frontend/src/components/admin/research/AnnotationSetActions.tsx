import { useState } from 'react'
import type { AxiosError } from 'axios'
import {
  completeResearchAnnotationSet,
  declareAnnotationCoverage,
  fetchResearchAnnotationSet,
  getResearchApiMessage,
  reopenResearchAnnotationSet,
} from '@/api/research.api'
import type {
  AnnotationSetRecord,
  CoverageLevel,
  ResearchRevisionConflict,
} from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { AnnotationExportButtons } from './AnnotationExportButtons'

function revisionConflict(error: unknown): ResearchRevisionConflict | null {
  const payload = (error as AxiosError<{ message?: ResearchRevisionConflict }>).response?.data
    ?.message
  return payload?.category === 'revision_conflict' ? payload : null
}

/** Coverage values a reviewer can actually finish on (`not_assessed` blocks completion server-side). */
const ASSESSABLE_COVERAGE_VALUES: CoverageLevel[] = [
  'prediction_review_only',
  'exhaustive',
  'fixed_inventory_complete',
]

/** One-line explanation of what each assessed coverage level unlocks for validation. */
const COVERAGE_HELP_TEXT: Record<CoverageLevel, string> = {
  not_assessed: 'No completeness claim — recall and F1 will not be eligible.',
  prediction_review_only:
    'Only the evaluator\'s own predictions were reviewed. Precision may be eligible; recall and F1 will not.',
  exhaustive:
    'The full transcript was searched for anything the evaluator missed. Precision, recall, and F1 are all eligible.',
  fixed_inventory_complete:
    'A fixed, known inventory of items was reviewed in full. Inventory-specific accuracy is eligible.',
}

export function AnnotationSetActions({
  annotationSet,
  onChange,
}: {
  annotationSet: AnnotationSetRecord
  onChange: (next: AnnotationSetRecord) => void
}) {
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<ResearchRevisionConflict | null>(null)
  const [reopenDialog, setReopenDialog] = useState(false)
  const [reopenReason, setReopenReason] = useState('')
  const [finishDialog, setFinishDialog] = useState(false)
  const supportedCoverageValues =
    annotationSet.annotation_policy.coverage?.supported_values ??
    (['not_assessed', 'prediction_review_only', 'fixed_inventory_complete'] as const)
  const assessableCoverageValues = supportedCoverageValues.filter((value) =>
    ASSESSABLE_COVERAGE_VALUES.includes(value)
  )
  const [selectedCoverage, setSelectedCoverage] = useState<CoverageLevel>(
    (annotationSet.coverage_level && assessableCoverageValues.includes(annotationSet.coverage_level)
      ? annotationSet.coverage_level
      : assessableCoverageValues[0]) ?? 'prediction_review_only'
  )
  const trimmedReason = reopenReason.trim()
  const completionReady = annotationSet.progress.unreviewed === 0

  const runMutation = async (
    action: string,
    operation: () => Promise<AnnotationSetRecord>,
    fallback: string
  ) => {
    setBusyAction(action)
    setError(null)
    setConflict(null)
    try {
      onChange(await operation())
      return true
    } catch (caught) {
      const conflictPayload = revisionConflict(caught)
      if (conflictPayload) {
        setConflict(conflictPayload)
        setError('Another review change exists. Refresh before changing lifecycle state.')
      } else {
        setError(getResearchApiMessage(caught, fallback))
      }
      return false
    } finally {
      setBusyAction(null)
    }
  }

  /**
   * Declares the chosen coverage level and completes/locks the set as a single reviewer
   * action, rather than two separate "save coverage" then "complete" steps: coverage is
   * re-affirmed immediately before the set is frozen, using whichever revision the coverage
   * declaration itself returns (not the possibly-stale prop) to complete against.
   */
  const finishAndLock = async () => {
    const changed = await runMutation(
      'finish',
      async () => {
        const withCoverage = await declareAnnotationCoverage(
          annotationSet.annotation_set_uuid,
          annotationSet.revision,
          selectedCoverage
        )
        return completeResearchAnnotationSet(annotationSet.annotation_set_uuid, withCoverage.revision)
      },
      'The annotation set could not be finished and locked.'
    )
    if (changed) setFinishDialog(false)
  }

  const reopen = async () => {
    if (!trimmedReason || trimmedReason.length > 500) return
    const changed = await runMutation(
      'reopen',
      () => reopenResearchAnnotationSet(
        annotationSet.annotation_set_uuid,
        annotationSet.revision,
        trimmedReason
      ),
      'The annotation set could not be reopened.'
    )
    if (changed) {
      setReopenReason('')
      setReopenDialog(false)
    }
  }

  const refresh = async () => {
    setBusyAction('refresh')
    setError(null)
    try {
      onChange(await fetchResearchAnnotationSet(annotationSet.annotation_set_uuid))
      setConflict(null)
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'The annotation set could not be refreshed.'))
    } finally {
      setBusyAction(null)
    }
  }

  return (
    <section aria-labelledby="annotation-set-actions-heading" className="space-y-3 rounded-md border border-gray-200 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h6 id="annotation-set-actions-heading" className="text-sm font-semibold text-gray-950">
            Review lifecycle
          </h6>
          <p className="text-sm text-gray-700">
            Status: <strong className="capitalize">{annotationSet.status.replaceAll('_', ' ')}</strong>
            {' · '}{annotationSet.locked ? 'Locked' : 'Editable'}
          </p>
        </div>
        {annotationSet.locked ? (
          <Button type="button" variant="outline" size="sm" onClick={() => setReopenDialog(true)} disabled={busyAction !== null}>
            Reopen locked set
          </Button>
        ) : (
          <Button type="button" size="sm" onClick={() => setFinishDialog(true)} disabled={!completionReady || busyAction !== null}>
            Complete and lock review
          </Button>
        )}
      </div>

      {!annotationSet.locked && !completionReady && (
        <p role="status" className="text-xs text-gray-700">
          Review all {annotationSet.progress.unreviewed} remaining predictions before completion.
        </p>
      )}
      {!annotationSet.locked && completionReady && (
        <p role="status" className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm font-medium text-emerald-950">
          All {annotationSet.progress.total} predictions reviewed. Ready to finish and lock.
        </p>
      )}
      {annotationSet.locked && (
        <p role="status" className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm font-medium text-emerald-950">
          Complete and locked. Decisions cannot change unless an administrator records a reopen reason.
        </p>
      )}

      <div>
        <p className="text-sm font-medium text-gray-800">Sanitized exports</p>
        <p className="text-xs text-gray-600">Transcript text is excluded by default.</p>
        <div className="mt-2">
          <AnnotationExportButtons annotationSetUuid={annotationSet.annotation_set_uuid} />
        </div>
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span>{error}</span>
          {conflict && (
            <Button type="button" size="sm" variant="outline" disabled={busyAction !== null} onClick={() => void refresh()}>
              {busyAction === 'refresh' ? 'Refreshing…' : 'Refresh newer review data'}
            </Button>
          )}
        </div>
      )}

      <Dialog open={finishDialog} onOpenChange={setFinishDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Finish and lock review?</DialogTitle>
            <DialogDescription>
              Declare how thoroughly this set was reviewed, then complete and lock it. Locking is
              one-way; an administrator can reopen it later with a recorded reason, but the
              coverage you declare here determines which validation metrics can ever be computed
              against this set.
            </DialogDescription>
          </DialogHeader>
          <label className="block text-sm font-medium text-gray-800">
            Annotation coverage
            <select
              aria-label="Annotation coverage"
              className="mt-1 block w-full rounded border p-2"
              value={selectedCoverage}
              onChange={(event) => setSelectedCoverage(event.target.value as CoverageLevel)}
            >
              {assessableCoverageValues.map((value) => (
                <option key={value} value={value}>
                  {value.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <p className="text-xs text-gray-600">{COVERAGE_HELP_TEXT[selectedCoverage]}</p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setFinishDialog(false)} disabled={busyAction !== null}>
              Cancel
            </Button>
            <Button type="button" onClick={() => void finishAndLock()} disabled={busyAction !== null}>
              {busyAction === 'finish' ? 'Finishing…' : 'Finish and lock'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={reopenDialog} onOpenChange={setReopenDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reopen annotation set?</DialogTitle>
            <DialogDescription>
              Reopening unlocks decisions and adds an immutable audit transition. Record why another review pass is required.
            </DialogDescription>
          </DialogHeader>
          <label className="block text-sm font-medium text-gray-800">
            Reopen reason
            <Textarea
              value={reopenReason}
              onChange={(event) => setReopenReason(event.target.value)}
              maxLength={500}
              aria-label="Reopen reason"
              className="mt-1"
            />
          </label>
          <p className="text-right text-xs text-gray-600">{reopenReason.length} / 500</p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setReopenDialog(false)} disabled={busyAction !== null}>
              Cancel
            </Button>
            <Button type="button" onClick={() => void reopen()} disabled={!trimmedReason || trimmedReason.length > 500 || busyAction !== null}>
              {busyAction === 'reopen' ? 'Reopening…' : 'Record reason and reopen'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  )
}
