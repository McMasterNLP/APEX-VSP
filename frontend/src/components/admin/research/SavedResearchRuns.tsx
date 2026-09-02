import type {
  AnnotationSetRecord,
  EvaluationRunRecord,
  EvaluationRunSummary,
} from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'

interface SavedResearchRunsProps {
  runs: EvaluationRunSummary[]
  loading: boolean
  selectedRun: EvaluationRunRecord | null
  annotationSet: AnnotationSetRecord | null
  busyRunUuid: string | null
  onOpen: (runUuid: string) => void
  onCreateOrOpenSet: (run: EvaluationRunRecord) => void
}

export function SavedResearchRuns({
  runs,
  loading,
  selectedRun,
  annotationSet,
  busyRunUuid,
  onOpen,
  onCreateOrOpenSet,
}: SavedResearchRunsProps) {
  return (
    <section aria-labelledby="saved-research-runs-heading" className="space-y-3 rounded-lg border border-gray-200 p-3">
      <div>
        <h5 id="saved-research-runs-heading" className="text-sm font-semibold text-gray-950">
          Saved research runs
        </h5>
        <p className="text-xs text-gray-600">
          Saved runs contain an immutable evaluator envelope and annotation transcript snapshot.
        </p>
      </div>
      {loading ? (
        <p role="status" className="text-sm text-gray-600">Loading saved runs…</p>
      ) : runs.length === 0 ? (
        <p className="text-sm text-gray-600">No evaluator result has been saved for review.</p>
      ) : (
        <ul className="space-y-2">
          {runs.map((run) => (
            <li key={run.run_uuid} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-gray-50 p-2 text-sm">
              <span>
                <span className="font-medium">{run.evaluator_identifier} v{run.evaluator_version}</span>
                <span className="ml-2 text-xs text-gray-600">{run.execution_mode} · {new Date(run.created_at).toLocaleString()}</span>
                {!run.transcript_matches_current && (
                  <span className="ml-2 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-950">
                    Transcript mismatch
                  </span>
                )}
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onOpen(run.run_uuid)}
                disabled={busyRunUuid !== null}
                aria-label={`Open saved ${run.evaluator_identifier} research run`}
              >
                {busyRunUuid === run.run_uuid ? 'Opening…' : 'Open'}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {selectedRun && (
        <div className="space-y-2 rounded-md border border-indigo-200 bg-indigo-50 p-3 text-sm">
          <p className="font-medium text-indigo-950">
            Selected saved run: {selectedRun.envelope.evaluator.display_name}
          </p>
          <p className="text-xs text-indigo-900">
            Guideline: {selectedRun.annotation_policy.guideline_identifier} v{selectedRun.annotation_policy.guideline_version}
          </p>
          {!selectedRun.transcript_matches_current && (
            <p role="alert" className="font-medium text-amber-950">
              The current session transcript differs. Review uses the immutable saved snapshot.
            </p>
          )}
          <Button
            type="button"
            size="sm"
            onClick={() => onCreateOrOpenSet(selectedRun)}
            disabled={busyRunUuid !== null}
          >
            {busyRunUuid === selectedRun.run_uuid ? 'Opening annotation set…' : 'Create or open annotation set'}
          </Button>
          {annotationSet?.evaluation_run_uuid === selectedRun.run_uuid && (
            <p role="status" className="font-medium text-indigo-950">
              Annotation set: {annotationSet.status.replace('_', ' ')} · revision {annotationSet.revision} · {annotationSet.progress.unreviewed} unreviewed
            </p>
          )}
        </div>
      )}
    </section>
  )
}
