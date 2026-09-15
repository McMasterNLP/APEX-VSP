/**
 * Validate tab: score a saved evaluator run's predictions against a completed annotation set.
 *
 * @remarks
 * Only `exact_span_match` (Item 3A's one registered matching policy) exists today, so there
 * is no matching-policy picker here beyond stating which policy will be used — adding a
 * second policy is future work, not implied by this UI. Trigger availability distinguishes
 * *why* validation isn't available yet (no saved run vs. no annotation set vs. annotation set
 * not `complete`) instead of showing an unexplained disabled button.
 */
import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RatioValueCell } from '@/components/admin/research/RatioValueCell'
import { ValidationResultsTable } from '@/components/admin/research/ValidationResultsTable'
import { formatDateTimeInUserTimeZone } from '@/lib/dateTime'
import type { EvaluationSessionContext } from './useEvaluationSession'

export function ValidateTab() {
  const {
    savedRuns,
    annotationSets,
    loadingAnnotationSets,
    validationRuns,
    loadingValidationRuns,
    creatingValidationRun,
    createValidationRun,
    error,
  } = useOutletContext<EvaluationSessionContext>()

  const completeAnnotationSets = annotationSets.filter((set) => set.status === 'complete')

  const [evaluationRunUuid, setEvaluationRunUuid] = useState('')
  const [annotationSetUuid, setAnnotationSetUuid] = useState('')
  const [viewedRunUuid, setViewedRunUuid] = useState<string | null>(null)

  useEffect(() => {
    if (viewedRunUuid === null && validationRuns.length > 0) {
      setViewedRunUuid(validationRuns[0].validation_run_uuid)
    }
  }, [validationRuns, viewedRunUuid])

  const onValidate = async () => {
    if (!evaluationRunUuid || !annotationSetUuid) return
    const created = await createValidationRun(evaluationRunUuid, annotationSetUuid)
    if (created) setViewedRunUuid(created.validation_run_uuid)
  }

  const viewedRun = validationRuns.find((run) => run.validation_run_uuid === viewedRunUuid) ?? null

  if (loadingAnnotationSets || loadingValidationRuns) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-gray-500">Loading validation state…</CardContent>
      </Card>
    )
  }

  if (savedRuns.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center">
          <p className="text-gray-700">Validation needs a saved evaluator run first.</p>
          <Link to="../runs" className="text-apex-600 hover:underline">
            Go to Saved Runs
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (annotationSets.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center">
          <p className="text-gray-700">
            Validation needs a human-reviewed reference — no annotation set exists for this
            session yet.
          </p>
          <Link to="../review" className="text-apex-600 hover:underline">
            Go to Review &amp; Annotate
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (completeAnnotationSets.length === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center">
          <p className="text-gray-700">
            An annotation set exists for this session, but none has been marked{' '}
            <span className="font-medium">complete</span> yet — coverage must be explicitly
            declared and the set completed before it can back a validation run.
          </p>
          <Link to="../review" className="text-apex-600 hover:underline">
            Go to Review &amp; Annotate
          </Link>
        </CardContent>
      </Card>
    )
  }

  return (
    <section aria-labelledby="validate-heading" className="space-y-6">
      <div>
        <h2 id="validate-heading" className="text-lg font-semibold text-gray-950">
          Validate
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Score one saved evaluator run's predictions against a completed reference annotation
          set. Matching policy: <span className="font-medium">exact_span_match</span> (transcript
          turn, offsets, and label must all match exactly).
        </p>
      </div>

      {error && <p role="alert" className="text-sm font-medium text-red-700">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Run a new validation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="block text-sm text-gray-700">
            Evaluator run to score
            <select
              aria-label="Evaluator run to score"
              className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5"
              value={evaluationRunUuid}
              onChange={(event) => setEvaluationRunUuid(event.target.value)}
            >
              <option value="" disabled>
                Choose a saved evaluator run…
              </option>
              {savedRuns.map((run) => (
                <option key={run.run_uuid} value={run.run_uuid}>
                  {run.evaluator_identifier} v{run.evaluator_version} ·{' '}
                  {formatDateTimeInUserTimeZone(run.created_at)}
                  {!run.transcript_matches_current ? ' · transcript mismatch' : ''}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm text-gray-700">
            Reference annotation set (complete only)
            <select
              aria-label="Reference annotation set"
              className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5"
              value={annotationSetUuid}
              onChange={(event) => setAnnotationSetUuid(event.target.value)}
            >
              <option value="" disabled>
                Choose a completed annotation set…
              </option>
              {completeAnnotationSets.map((set) => (
                <option key={set.annotation_set_uuid} value={set.annotation_set_uuid}>
                  {set.guideline_identifier} v{set.guideline_version} · {set.reviewer_reference} ·
                  coverage: {set.coverage_level.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
            {annotationSets.length > completeAnnotationSets.length && (
              <span className="mt-1 block text-xs text-gray-500">
                {annotationSets.length - completeAnnotationSets.length} other annotation set
                {annotationSets.length - completeAnnotationSets.length === 1 ? '' : 's'} for this
                session {annotationSets.length - completeAnnotationSets.length === 1 ? 'is' : 'are'}{' '}
                not yet complete and cannot be used as a reference.
              </span>
            )}
          </label>

          <Button
            type="button"
            onClick={() => void onValidate()}
            disabled={!evaluationRunUuid || !annotationSetUuid || creatingValidationRun}
          >
            {creatingValidationRun ? 'Validating…' : 'Run validation'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Validation runs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {validationRuns.length === 0 ? (
            <p className="text-sm text-gray-600">No validation runs yet for this session.</p>
          ) : (
            <ul className="space-y-1">
              {validationRuns.map((run) => (
                <li key={run.validation_run_uuid}>
                  <button
                    type="button"
                    onClick={() => setViewedRunUuid(run.validation_run_uuid)}
                    className={`flex w-full flex-wrap items-center justify-between gap-2 rounded-md p-2 text-left text-sm transition-colors ${
                      run.validation_run_uuid === viewedRunUuid
                        ? 'bg-apex-50 ring-1 ring-apex-300'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <span>
                      <span className="font-medium">
                        {run.evaluator_identifier} v{run.evaluator_version}
                      </span>
                      <span className="ml-2 text-xs text-gray-600">
                        {run.matching_policy_identifier} · coverage:{' '}
                        {run.coverage_level.replaceAll('_', ' ')} ·{' '}
                        {formatDateTimeInUserTimeZone(run.created_at)}
                      </span>
                    </span>
                    <span className="flex items-center gap-1 text-xs text-gray-600">
                      Micro F1:{' '}
                      <RatioValueCell ratio={run.results.span_classification.micro.f1} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {viewedRun && (
        <Card>
          <CardHeader>
            <CardTitle>
              Results — {viewedRun.evaluator_identifier} v{viewedRun.evaluator_version} ·{' '}
              {formatDateTimeInUserTimeZone(viewedRun.created_at)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {viewedRun.warnings.length > 0 && (
              <ul className="list-inside list-disc rounded-md bg-yellow-50 p-2 text-xs text-yellow-800">
                {viewedRun.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
            <ValidationResultsTable metrics={viewedRun.results.span_classification} />
          </CardContent>
        </Card>
      )}
    </section>
  )
}
