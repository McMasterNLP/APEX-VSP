/**
 * Export tab: preview exports (ephemeral) and saved-run/review exports (durable), grouped.
 *
 * @remarks
 * Preview exports reuse the shared hook's `downloadPreviewExport` (same
 * `downloadResearchEvaluationExport` call the old panel made) and only render when this
 * visit's `result` is still in memory — they are not persisted anywhere, so they are
 * captioned as regeneratable from Run & Compare. Saved-run exports reuse
 * {@link AnnotationExportButtons}, the same small component `AnnotationSetActions` uses
 * inside the Review & Annotate tab's workspace, so there is exactly one implementation of
 * the three export buttons.
 */
import { Link, useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AnnotationExportButtons } from '@/components/admin/research/AnnotationExportButtons'
import type { ResearchExportProfile } from '@/types/researchEvaluation'
import type { EvaluationSessionContext } from './useEvaluationSession'

const PREVIEW_EXPORT_PROFILES: Array<[ResearchExportProfile, string]> = [
  ['full', 'Full JSON'],
  ['framework_native', 'Framework-native JSON'],
  ['projection', 'Projection JSON'],
  ['tabular', 'Tabular ZIP'],
]

export function ExportTab() {
  const { result, exporting, downloadPreviewExport, annotationSet } =
    useOutletContext<EvaluationSessionContext>()

  const hasPreview = result !== null
  const hasAnnotationSet = annotationSet !== null

  if (!hasPreview && !hasAnnotationSet) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center text-gray-600">
          <p>Nothing to export yet.</p>
          <p className="text-sm">
            Run a preview on{' '}
            <Link to="../run" className="text-apex-600 hover:underline">
              Run &amp; Compare
            </Link>{' '}
            or open a run on{' '}
            <Link to="../runs" className="text-apex-600 hover:underline">
              Saved Runs
            </Link>{' '}
            to unlock exports here.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {hasPreview && (
        <Card>
          <CardHeader>
            <CardTitle>Preview exports — not saved</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-gray-600">
              Regenerate from Run &amp; Compare if you need this again — these are not persisted.
            </p>
            <div className="flex flex-wrap gap-2" aria-label="Research export controls">
              {PREVIEW_EXPORT_PROFILES.map(([profile, label]) => (
                <Button
                  key={profile}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void downloadPreviewExport(profile)}
                  disabled={exporting !== null}
                >
                  {exporting === profile ? 'Preparing…' : label}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {hasAnnotationSet && annotationSet && (
        <Card>
          <CardHeader>
            <CardTitle>Saved run &amp; review exports</CardTitle>
          </CardHeader>
          <CardContent>
            <AnnotationExportButtons
              annotationSetUuid={annotationSet.annotation_set_uuid}
              showDescriptions
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
