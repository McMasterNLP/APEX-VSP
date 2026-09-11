/**
 * Overview tab: transcript viewer plus quick-link cards into the other tabs.
 *
 * @remarks
 * Reuses the session detail already fetched by {@link useEvaluationSession} — no separate
 * fetch. Cards are omitted (not rendered empty) when they would have nothing meaningful to
 * show, e.g. no "Continue review" card until an annotation set exists.
 */
import { Link, useOutletContext } from 'react-router-dom'
import { formatDateTimeInUserTimeZone } from '@/lib/dateTime'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { EvaluationSessionContext } from './useEvaluationSession'

export function OverviewTab() {
  const { detail, annotationSet, savedRuns } = useOutletContext<EvaluationSessionContext>()
  const turns = detail?.session.turns ?? []
  const reviewInProgress = annotationSet && annotationSet.status !== 'complete' && !annotationSet.locked

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {reviewInProgress && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Continue review →</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-600">
              <p>
                {annotationSet.progress.unreviewed} of {annotationSet.progress.total} predictions
                remain unreviewed.
              </p>
              <Link to="../review" className="mt-2 inline-block text-apex-600 hover:underline">
                Resume review
              </Link>
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Compare evaluators →</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600">
            <p>Preview one or more research evaluators without saving anything.</p>
            <Link to="../run" className="mt-2 inline-block text-apex-600 hover:underline">
              Open Run &amp; Compare
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">View saved runs →</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-gray-600">
            <p>
              {savedRuns.length} saved run{savedRuns.length === 1 ? '' : 's'} for this session.
            </p>
            <Link to="../runs" className="mt-2 inline-block text-apex-600 hover:underline">
              Open Saved Runs
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Transcript</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 max-h-96 overflow-y-auto border rounded-lg p-3 bg-gray-50">
            {turns.length === 0 ? (
              <p className="text-gray-500 text-sm">No turns</p>
            ) : (
              turns.map((t) => (
                <div key={t.id} className="text-sm">
                  <span className="font-medium text-gray-700">
                    Turn {t.turn_number} ({t.role})
                  </span>
                  <span className="text-gray-500 ml-2 text-xs">
                    {formatDateTimeInUserTimeZone(t.timestamp)}
                  </span>
                  <p className="mt-1 text-gray-900">{t.text}</p>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
