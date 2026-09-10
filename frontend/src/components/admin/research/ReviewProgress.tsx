import type { ReviewProgress as ReviewProgressData } from '@/types/researchEvaluation'

export function ReviewProgress({ progress }: { progress: ReviewProgressData }) {
  const reviewed = progress.total - progress.unreviewed
  const percent = progress.total === 0 ? 0 : Math.round((reviewed / progress.total) * 100)
  return (
    <section aria-labelledby="annotation-progress-heading" className="space-y-2 rounded-md border border-gray-200 p-3">
      <div className="flex items-center justify-between gap-3">
        <h6 id="annotation-progress-heading" className="text-sm font-semibold text-gray-950">
          Review progress
        </h6>
        <span className="text-sm font-medium">{reviewed} / {progress.total} ({percent}%)</span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={progress.total}
        aria-valuenow={reviewed}
        aria-label="Reviewed predictions"
        className="h-2 overflow-hidden rounded-full bg-gray-200"
      >
        <div className="h-full bg-indigo-600" style={{ width: `${percent}%` }} />
      </div>
      <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        <div><dt className="font-medium">Confirmed</dt><dd>{progress.confirmed}</dd></div>
        <div><dt className="font-medium">Corrected</dt><dd>{progress.corrected}</dd></div>
        <div><dt className="font-medium">Rejected</dt><dd>{progress.rejected}</dd></div>
        <div><dt className="font-medium">Insufficient</dt><dd>{progress.insufficient_evidence}</dd></div>
        <div><dt className="font-medium">Unreviewed</dt><dd>{progress.unreviewed}</dd></div>
      </dl>
    </section>
  )
}
