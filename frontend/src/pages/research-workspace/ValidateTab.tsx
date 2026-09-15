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

const SPAN_OR_RELATION_CAPABLE_FRAMEWORKS = new Set(['apex-spikes-afce'])

export function ValidateTab() {
  const {
    savedRuns,
    annotationSets,
    loadingAnnotationSets,
    validationRuns,
    loadingValidationRuns,
    creatingValidationRun,
    createValidationRun,
    includeArchivedValidationRuns,
    setIncludeArchivedValidationRuns,
    archivingValidationRunUuid,
    setValidationRunArchived,
    error,
  } = useOutletContext<EvaluationSessionContext>()

  const completeAnnotationSets = annotationSets.filter((set) => set.status === 'complete')

  const [evaluationRunUuid, setEvaluationRunUuid] = useState('')
  const [annotationSetUuid, setAnnotationSetUuid] = useState('')
  const [viewedRunUuid, setViewedRunUuid] = useState<string | null>(null)

  const selectedEvaluationRun = savedRuns.find((run) => run.run_uuid === evaluationRunUuid) ?? null
  const selectedAnnotationSet =
    completeAnnotationSets.find((set) => set.annotation_set_uuid === annotationSetUuid) ?? null
  // The backend only lets a validation run be created when the evaluator run and the
  // reference annotation set share the same transcript hash (Item 3A's own gate) --
  // checking that here, before the request, turns a generic server rejection into an
  // explanation of exactly which two selections disagree and why.
  const transcriptMismatch =
    selectedEvaluationRun !== null &&
    selectedAnnotationSet !== null &&
    selectedEvaluationRun.transcript_hash !== selectedAnnotationSet.transcript_hash

  // Item 3A implements exactly one metric family -- span/label classification -- and
  // nothing else (no relation, rating, or global-score metrics exist yet; see
  // `research_validation/metrics.py`). Frameworks that produce no span or relation
  // predictions at all (today: `ace-ct-inspired`, dimension ratings only) will still let
  // you create a validation run, but it comes back an empty per-label table with every
  // recall/F1 cell reading "ineligible" -- a confusing result that has nothing to do with
  // coverage. This is a soft heuristic (an allowlist of frameworks known to produce spans
  // or relations, not a hard gate), so it warns rather than blocks: a future framework not
  // yet added here defaults to "warn," never to a silent false negative.
  const selectedFrameworkLacksSpanSupport =
    selectedEvaluationRun !== null &&
    !SPAN_OR_RELATION_CAPABLE_FRAMEWORKS.has(selectedEvaluationRun.framework_identifier)

  useEffect(() => {
    if (viewedRunUuid === null && validationRuns.length > 0) {
      setViewedRunUuid(validationRuns[0].validation_run_uuid)
    }
  }, [validationRuns, viewedRunUuid])

  const onValidate = async () => {
    if (!evaluationRunUuid || !annotationSetUuid || transcriptMismatch) return
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

          {transcriptMismatch && (
            <p role="status" className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
              This evaluator run and annotation set were scored against different
              transcripts (their transcript hashes don&apos;t match), so a validation run
              between them would be rejected. Choose a run and reference set captured from
              the same transcript.
            </p>
          )}

          {!transcriptMismatch && selectedFrameworkLacksSpanSupport && (
            <p role="status" className="rounded border border-sky-300 bg-sky-50 p-2 text-sm text-sky-900">
              This evaluator&apos;s framework doesn&apos;t produce span or relation
              predictions. The only validation metrics implemented so far score span/label
              classification, so this run will still create a validation record but every
              per-label row and recall/F1 cell will come back empty or ineligible -- that
              reflects a metric family gap, not something wrong with your review.
            </p>
          )}

          <Button
            type="button"
            onClick={() => void onValidate()}
            disabled={!evaluationRunUuid || !annotationSetUuid || transcriptMismatch || creatingValidationRun}
          >
            {creatingValidationRun ? 'Validating…' : 'Run validation'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>Validation runs</CardTitle>
          <label className="flex items-center gap-2 text-sm font-normal text-gray-700">
            <input
              type="checkbox"
              checked={includeArchivedValidationRuns}
              onChange={(event) => setIncludeArchivedValidationRuns(event.target.checked)}
            />
            Show archived runs
          </label>
        </CardHeader>
        <CardContent className="space-y-3">
          {validationRuns.length === 0 ? (
            <p className="text-sm text-gray-600">
              {includeArchivedValidationRuns
                ? 'No validation runs (including archived) yet for this session.'
                : 'No validation runs yet for this session.'}
            </p>
          ) : (
            <ul className="space-y-1">
              {validationRuns.map((run) => (
                <li
                  key={run.validation_run_uuid}
                  className={`flex flex-wrap items-center gap-2 rounded-md p-2 text-sm transition-colors ${
                    run.validation_run_uuid === viewedRunUuid
                      ? 'bg-apex-50 ring-1 ring-apex-300'
                      : 'bg-gray-50 hover:bg-gray-100'
                  } ${run.archived ? 'opacity-70' : ''}`}
                >
                  <button
                    type="button"
                    onClick={() => setViewedRunUuid(run.validation_run_uuid)}
                    className="flex flex-1 flex-wrap items-center justify-between gap-2 text-left"
                  >
                    <span>
                      <span className="font-medium">
                        {run.evaluator_identifier} v{run.evaluator_version}
                      </span>
                      {run.archived && (
                        <span className="ml-2 rounded border border-gray-300 bg-white px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-gray-500">
                          Archived
                        </span>
                      )}
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
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={archivingValidationRunUuid === run.validation_run_uuid}
                    onClick={() => void setValidationRunArchived(run.validation_run_uuid, !run.archived)}
                  >
                    {archivingValidationRunUuid === run.validation_run_uuid
                      ? 'Saving…'
                      : run.archived
                        ? 'Unarchive'
                        : 'Archive'}
                  </Button>
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
