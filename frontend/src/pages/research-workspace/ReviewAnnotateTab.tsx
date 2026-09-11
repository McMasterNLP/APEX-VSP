/**
 * Review & Annotate tab: reviewing one saved run's annotation set only.
 *
 * @remarks
 * Locked until at least one saved run exists — `savedRuns` is fetched by the shared hook
 * on mount regardless of which tab is entered first, so this renders correctly even on a
 * direct navigation to `.../review` with no prior tab visits in this session. When a
 * `?run=<runUuid>` query param is present (set by the Saved Runs tab after creating/opening
 * an annotation set), it resolves that specific run; otherwise it falls back to whatever the
 * shared hook already has selected, or offers an in-tab picker.
 */
import { useEffect, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { AnnotationSetWorkspace } from '@/components/admin/research/AnnotationSetWorkspace'
import { ReviewProgress } from '@/components/admin/research/ReviewProgress'
import type { EvaluationSessionContext } from './useEvaluationSession'

export function ReviewAnnotateTab() {
  const {
    savedRuns,
    selectedRun,
    annotationSet,
    busyRunUuid,
    openSavedRun,
    createOrOpenSet,
    setAnnotationSet,
    error,
  } = useOutletContext<EvaluationSessionContext>()
  const [searchParams] = useSearchParams()
  const requestedRunUuid = searchParams.get('run')
  const [resolvingRunUuid, setResolvingRunUuid] = useState<string | null>(null)

  const openForReview = async (runUuid: string) => {
    setResolvingRunUuid(runUuid)
    const run = await openSavedRun(runUuid)
    if (run) await createOrOpenSet(run)
    setResolvingRunUuid(null)
  }

  useEffect(() => {
    if (!requestedRunUuid) return
    if (selectedRun?.run_uuid === requestedRunUuid && annotationSet) return
    void openForReview(requestedRunUuid)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedRunUuid])

  if (savedRuns.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center">
          <p className="text-gray-700">No saved runs yet — save an evaluation run first.</p>
          <Link to="../runs" className="text-apex-600 hover:underline">
            Go to Saved Runs
          </Link>
        </CardContent>
      </Card>
    )
  }

  const resolved = selectedRun && annotationSet
  const resolving = resolvingRunUuid !== null || busyRunUuid !== null

  return (
    <section aria-labelledby="review-annotate-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="review-annotate-heading" className="text-lg font-semibold text-gray-950">
          Review &amp; Annotate
        </h2>
        {savedRuns.length > 1 && (
          <label className="flex items-center gap-2 text-sm text-gray-700">
            Switch run
            <select
              aria-label="Switch saved run"
              className="rounded border border-gray-300 px-2 py-1"
              value={selectedRun?.run_uuid ?? ''}
              disabled={resolving}
              onChange={(event) => {
                if (event.target.value) void openForReview(event.target.value)
              }}
            >
              <option value="" disabled>
                Choose a saved run…
              </option>
              {savedRuns.map((run) => (
                <option key={run.run_uuid} value={run.run_uuid}>
                  {run.evaluator_identifier} v{run.evaluator_version} ·{' '}
                  {new Date(run.created_at).toLocaleString()}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {error && <p role="alert" className="text-sm font-medium text-red-700">{error}</p>}

      {!resolved && (
        <Card>
          <CardContent className="space-y-3 py-6">
            <p className="text-sm text-gray-700">Choose a saved run to open for review.</p>
            <ul className="space-y-2">
              {savedRuns.map((run) => (
                <li
                  key={run.run_uuid}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-gray-50 p-2 text-sm"
                >
                  <span>
                    <span className="font-medium">
                      {run.evaluator_identifier} v{run.evaluator_version}
                    </span>
                    <span className="ml-2 text-xs text-gray-600">
                      {run.execution_mode} · {new Date(run.created_at).toLocaleString()}
                    </span>
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={resolving}
                    onClick={() => void openForReview(run.run_uuid)}
                  >
                    {resolvingRunUuid === run.run_uuid || busyRunUuid === run.run_uuid
                      ? 'Opening…'
                      : 'Open for review'}
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {resolved && (
        <>
          <ReviewProgress progress={annotationSet.progress} />
          <AnnotationSetWorkspace run={selectedRun} annotationSet={annotationSet} onChange={setAnnotationSet} />
        </>
      )}
    </section>
  )
}
