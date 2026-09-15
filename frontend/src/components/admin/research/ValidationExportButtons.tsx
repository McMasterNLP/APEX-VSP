import { useState } from 'react'
import { downloadResearchValidationExport, getResearchApiMessage } from '@/api/research.api'
import type { ValidationExportProfile } from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'

/** One-line, plain-language description shown next to each validation-run export button. */
const EXPORT_PROFILES: Array<{ profile: ValidationExportProfile; label: string; description: string }> = [
  {
    profile: 'full',
    label: 'Full JSON',
    description: 'Run identity, coverage, eligibility, and every computed metric.',
  },
  {
    profile: 'results_only',
    label: 'Results only JSON',
    description: 'Just the computed span-classification results, without run identity metadata.',
  },
]

/**
 * Validation-run export button row: `full` / `results_only`.
 *
 * @remarks
 * Mirrors {@link AnnotationExportButtons} (same download pattern, same one-implementation
 * principle) but targets `POST /validation-runs/{uuid}/exports`. Transcript content is never
 * requested from this UI, matching the annotation exports' existing default.
 */
export function ValidationExportButtons({
  validationRunUuid,
  showDescriptions = false,
}: {
  validationRunUuid: string
  showDescriptions?: boolean
}) {
  const [busyProfile, setBusyProfile] = useState<ValidationExportProfile | null>(null)
  const [error, setError] = useState<string | null>(null)

  const download = async (profile: ValidationExportProfile) => {
    setBusyProfile(profile)
    setError(null)
    try {
      await downloadResearchValidationExport(validationRunUuid, profile)
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'The validation export could not be downloaded.'))
    } finally {
      setBusyProfile(null)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2" aria-label="Validation export controls">
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
