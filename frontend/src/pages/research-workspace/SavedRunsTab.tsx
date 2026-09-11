/**
 * Saved Runs tab: "Run and save for review" plus the saved-runs list.
 *
 * @remarks
 * Fully separate from the Run & Compare tab's Preview action — this button always
 * persists a fresh server-side evaluator run. The evaluator selection itself is shared
 * hook state (`selected`), chosen on the Run & Compare tab's checklist; this tab only
 * requires that selection to resolve to exactly one evaluator before saving.
 * Once a run is opened and its annotation set is created/opened, navigates to
 * `../review?run=<runUuid>` so Review & Annotate knows which run to show.
 */
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { SavedResearchRuns } from '@/components/admin/research/SavedResearchRuns'
import type { EvaluationRunRecord } from '@/types/researchEvaluation'
import type { EvaluationSessionContext } from './useEvaluationSession'

export function SavedRunsTab() {
  const navigate = useNavigate()
  const {
    detail,
    selectedDescriptors,
    hasLiveSelection,
    allowLive,
    availableProviders,
    saving,
    saveForReview,
    savedRuns,
    loadingSavedRuns,
    selectedRun,
    annotationSet,
    busyRunUuid,
    openSavedRun,
    createOrOpenSet,
    error,
  } = useOutletContext<EvaluationSessionContext>()

  const completed = detail?.session.state === 'completed'

  const onOpen = (runUuid: string) => {
    void openSavedRun(runUuid)
  }

  const onCreateOrOpenSet = async (run: EvaluationRunRecord) => {
    const set = await createOrOpenSet(run)
    if (set) navigate(`../review?run=${encodeURIComponent(run.run_uuid)}`)
  }

  return (
    <section aria-labelledby="saved-runs-heading" className="space-y-4">
      <div>
        <h2 id="saved-runs-heading" className="text-lg font-semibold text-gray-950">
          Saved Runs
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Saving reruns the evaluator on the server. Live or stochastic results may differ
          from a preview.
        </p>
      </div>

      <div className="rounded-md border border-gray-200 p-3">
        <p className="text-sm text-gray-700">
          Selected evaluator{selectedDescriptors.length === 1 ? '' : 's'}:{' '}
          {selectedDescriptors.length === 0
            ? 'none'
            : selectedDescriptors.map((d) => d.display_name).join(', ')}
        </p>
        {selectedDescriptors.length !== 1 && (
          <p className="mt-1 text-xs text-gray-600">
            Select exactly one evaluator on{' '}
            <Link to="../run" className="text-apex-600 hover:underline">
              Run &amp; Compare
            </Link>{' '}
            to save a review run.
          </p>
        )}
        <Button
          type="button"
          className="mt-2"
          onClick={() => void saveForReview()}
          disabled={
            !completed ||
            selectedDescriptors.length !== 1 ||
            saving ||
            (hasLiveSelection && !allowLive) ||
            (hasLiveSelection && availableProviders.length === 0)
          }
        >
          {saving ? 'Running and saving…' : 'Run and save for review'}
        </Button>
      </div>

      {error && <p role="alert" className="text-sm font-medium text-red-700">{error}</p>}

      <SavedResearchRuns
        runs={savedRuns}
        loading={loadingSavedRuns}
        selectedRun={selectedRun}
        annotationSet={annotationSet}
        busyRunUuid={busyRunUuid}
        onOpen={onOpen}
        onCreateOrOpenSet={(run) => void onCreateOrOpenSet(run)}
      />
    </section>
  )
}
