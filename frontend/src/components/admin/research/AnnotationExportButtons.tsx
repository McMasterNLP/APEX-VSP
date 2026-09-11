import { useState } from 'react'
import { downloadResearchAnnotationExport, getResearchApiMessage } from '@/api/research.api'
import type { AnnotationExportProfile } from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'

/** One-line, plain-language description shown next to each saved-run export button. */
const EXPORT_PROFILES: Array<{
  profile: AnnotationExportProfile
  label: string
  description: string
}> = [
  {
    profile: 'full_review',
    label: 'Full review JSON',
    description: 'Every prediction, decision, and revision history — the complete audit-friendly record.',
  },
  {
    profile: 'resolved_projection',
    label: 'Resolved projection JSON',
    description: "Reviewer-corrected reference; this is Item 3A's eventual validation input.",
  },
  {
    profile: 'audit_history',
    label: 'Audit history JSON',
    description: 'The append-only decision/transition log for this annotation set.',
  },
]

/**
 * Shared saved-run export button row: `full_review` / `resolved_projection` / `audit_history`.
 *
 * @remarks
 * Reused by {@link AnnotationSetActions} (inside `AnnotationSetWorkspace`, in the Review &
 * Annotate tab) and by the workspace's Export tab, so the three export actions have exactly
 * one implementation. Only the export action is shared here — lifecycle actions
 * (complete/reopen/refresh) stay in `AnnotationSetActions` and are not duplicated.
 *
 * @param annotationSetUuid - Target annotation set for `downloadResearchAnnotationExport`
 * @param showDescriptions - Whether to render the one-line description under each button
 */
export function AnnotationExportButtons({
  annotationSetUuid,
  showDescriptions = false,
}: {
  annotationSetUuid: string
  showDescriptions?: boolean
}) {
  const [busyProfile, setBusyProfile] = useState<AnnotationExportProfile | null>(null)
  const [error, setError] = useState<string | null>(null)

  const download = async (profile: AnnotationExportProfile) => {
    setBusyProfile(profile)
    setError(null)
    try {
      await downloadResearchAnnotationExport(annotationSetUuid, profile)
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'The annotation export could not be downloaded.'))
    } finally {
      setBusyProfile(null)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2" aria-label="Annotation export controls">
        {EXPORT_PROFILES.map(({ profile, label, description }) => (
          <div key={profile} className="flex flex-col gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busyProfile !== null}
              onClick={() => void download(profile)}
            >
              {busyProfile === profile ? 'Preparing…' : label}
            </Button>
            {showDescriptions && <p className="max-w-xs text-xs text-gray-600">{description}</p>}
          </div>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm font-medium text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
