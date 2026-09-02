import { useState } from 'react'
import type { AxiosError } from 'axios'
import {
  completeResearchAnnotationSet,
  downloadResearchAnnotationExport,
  fetchResearchAnnotationSet,
  getResearchApiMessage,
  reopenResearchAnnotationSet,
} from '@/api/research.api'
import type {
  AnnotationExportProfile,
  AnnotationSetRecord,
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

const exportProfiles: Array<[AnnotationExportProfile, string]> = [
  ['full_review', 'Full review JSON'],
  ['resolved_projection', 'Resolved projection JSON'],
  ['audit_history', 'Audit history JSON'],
]

function revisionConflict(error: unknown): ResearchRevisionConflict | null {
  const payload = (error as AxiosError<{ message?: ResearchRevisionConflict }>).response?.data
    ?.message
  return payload?.category === 'revision_conflict' ? payload : null
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

  const complete = () => runMutation(
    'complete',
    () => completeResearchAnnotationSet(annotationSet.annotation_set_uuid, annotationSet.revision),
    'The annotation set could not be completed.'
  )

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

  const download = async (profile: AnnotationExportProfile) => {
    setBusyAction(profile)
    setError(null)
    try {
      await downloadResearchAnnotationExport(annotationSet.annotation_set_uuid, profile)
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'The annotation export could not be downloaded.'))
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
          <Button type="button" size="sm" onClick={() => void complete()} disabled={!completionReady || busyAction !== null}>
            {busyAction === 'complete' ? 'Completing…' : 'Complete and lock review'}
          </Button>
        )}
      </div>

      {!annotationSet.locked && !completionReady && (
        <p role="status" className="text-xs text-gray-700">
          Review all {annotationSet.progress.unreviewed} remaining predictions before completion.
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
        <div className="mt-2 flex flex-wrap gap-2" aria-label="Annotation export controls">
          {exportProfiles.map(([profile, label]) => (
            <Button
              key={profile}
              type="button"
              variant="outline"
              size="sm"
              disabled={busyAction !== null}
              onClick={() => void download(profile)}
            >
              {busyAction === profile ? 'Preparing…' : label}
            </Button>
          ))}
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
