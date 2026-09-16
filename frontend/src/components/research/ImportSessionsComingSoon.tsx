/**
 * "Import Sessions" tab: a preview of an upcoming capability, not a built feature.
 *
 * @remarks
 * Deliberately not wired to any backend endpoint yet -- this is a teaser card describing
 * what's planned (manual session authoring, JSON transcript import, and annotated import
 * for reference ground truth), so researchers know it's coming without implying it works.
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Sparkles, PenLine, Upload, ClipboardCheck } from 'lucide-react'

const PLANNED_CAPABILITIES = [
  {
    icon: PenLine,
    title: 'Author a session by hand',
    description:
      'Type out clinician/patient turns directly, save it as a completed session, and run any evaluator against it -- no live conversation required.',
  },
  {
    icon: Upload,
    title: 'Import a transcript (JSON)',
    description:
      'Upload a transcript you already have as a simple JSON list of turns, and it becomes a completed session ready for evaluation the same way.',
  },
  {
    icon: ClipboardCheck,
    title: 'Bring your own ground truth',
    description:
      'Import externally-annotated reference data alongside a transcript, so it can back a validation run the same way a human-reviewed annotation set does today.',
  },
]

export function ImportSessionsComingSoon() {
  return (
    <section aria-labelledby="import-sessions-heading" className="space-y-6">
      <div>
        <h2 id="import-sessions-heading" className="text-lg font-semibold text-gray-950">
          Import Sessions
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Not built yet -- here&apos;s what&apos;s planned.
        </p>
      </div>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-5 w-5 text-apex-600" />
            Coming soon
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600">
            Right now, running an evaluator requires a real trainee session. This tab will let
            researchers create or bring in transcripts that never came from a live session --
            typed by hand, imported as a file, or imported with existing ground-truth
            annotations -- and run the same evaluation, review, and validation tools on them.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            {PLANNED_CAPABILITIES.map((capability) => {
              const Icon = capability.icon
              return (
                <div
                  key={capability.title}
                  className="rounded-md border border-gray-200 bg-gray-50 p-3"
                >
                  <Icon className="h-4 w-4 text-apex-600" />
                  <p className="mt-2 text-sm font-medium text-gray-900">{capability.title}</p>
                  <p className="mt-1 text-xs text-gray-600">{capability.description}</p>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </section>
  )
}
