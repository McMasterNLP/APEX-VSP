/**
 * Run & Compare tab: evaluator checklist and the "Preview" action only.
 *
 * @remarks
 * Saving a run for review lives in the Saved Runs tab instead — this tab never persists
 * anything. Preview export buttons here operate on the ephemeral `result` from this visit
 * and are captioned as not-saved.
 */
import { useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ResearchResultView } from '@/components/admin/research/ResearchResultView'
import type { ResearchExportProfile } from '@/types/researchEvaluation'
import type { EvaluationSessionContext } from './useEvaluationSession'

const PREVIEW_EXPORT_PROFILES: Array<[ResearchExportProfile, string]> = [
  ['full', 'Full JSON'],
  ['framework_native', 'Framework-native JSON'],
  ['projection', 'Projection JSON'],
  ['tabular', 'Tabular ZIP'],
]

export function RunCompareTab() {
  const {
    detail,
    descriptors,
    loadingDescriptors,
    selected,
    toggleEvaluator,
    hasLiveSelection,
    allowLive,
    setAllowLive,
    setProvider,
    availableProviders,
    effectiveProvider,
    result,
    running,
    execute,
    exporting,
    downloadPreviewExport,
    error,
  } = useOutletContext<EvaluationSessionContext>()

  const completed = detail?.session.state === 'completed'

  return (
    <section aria-labelledby="run-compare-heading" className="space-y-4">
      <div>
        <h2 id="run-compare-heading" className="text-lg font-semibold text-gray-950">
          Run &amp; Compare
        </h2>
        <p className="mt-1 text-sm font-medium text-indigo-800">
          Research evaluation — does not overwrite saved learner feedback.
        </p>
      </div>

      <p role="status" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        Results here are a preview only. Nothing on this tab is ever saved — use Saved Runs to
        run and persist an evaluator result for review.
      </p>

      {!completed && (
        <p role="status" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          Complete this session before running research evaluators.
        </p>
      )}

      {loadingDescriptors ? (
        <p role="status" className="text-sm text-gray-600">Loading research evaluators…</p>
      ) : descriptors.length === 0 ? (
        <p role="status" className="text-sm text-gray-600">No research evaluators are available.</p>
      ) : (
        <fieldset className="space-y-2" disabled={running || !completed}>
          <legend className="text-sm font-medium text-gray-800">Evaluators</legend>
          {descriptors.map((descriptor) => (
            <label
              key={descriptor.identifier}
              className="flex items-start gap-3 rounded-md border border-gray-200 p-3 focus-within:ring-2 focus-within:ring-indigo-500"
            >
              <input
                type="checkbox"
                checked={selected.includes(descriptor.identifier)}
                onChange={() => toggleEvaluator(descriptor.identifier)}
                disabled={descriptor.availability !== 'available'}
                className="mt-1 h-4 w-4"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-gray-950">
                  {descriptor.display_name} <span className="font-normal text-gray-500">v{descriptor.version}</span>
                </span>
                <span className="mt-0.5 block text-xs text-gray-600">
                  {descriptor.framework.display_name}
                  {descriptor.requires_live_execution ? ' · Requires live provider' : ' · Offline'}
                  {descriptor.availability !== 'available'
                    ? ` · ${descriptor.availability.replaceAll('_', ' ')}`
                    : ''}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      )}

      {hasLiveSelection && (
        <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3">
          <label className="flex items-center gap-2 text-sm font-medium text-amber-950">
            <input
              type="checkbox"
              checked={allowLive}
              onChange={(event) => setAllowLive(event.target.checked)}
              disabled={running || !completed}
            />
            Explicitly allow live model execution for this run
          </label>
          {allowLive && availableProviders.length > 0 && (
            <label className="block text-sm text-amber-950">
              Provider
              <select
                aria-label="Live evaluator provider"
                value={effectiveProvider}
                onChange={(event) => setProvider(event.target.value as 'openai' | 'gemini')}
                className="ml-2 rounded border border-amber-300 bg-white px-2 py-1"
              >
                {availableProviders.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
          )}
          {allowLive && availableProviders.length === 0 && (
            <p role="alert" className="text-sm font-medium text-red-800">
              The selected live evaluators do not share a supported provider.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          onClick={() => void execute()}
          disabled={
            !completed ||
            selected.length === 0 ||
            running ||
            loadingDescriptors ||
            (hasLiveSelection && allowLive && availableProviders.length === 0)
          }
        >
          {running ? 'Running preview…' : 'Preview selected evaluators — not saved'}
        </Button>
      </div>

      {selected.length === 0 && !loadingDescriptors && (
        <p className="text-sm text-gray-600">Select at least one evaluator to run.</p>
      )}
      {error && <p role="alert" className="text-sm font-medium text-red-700">{error}</p>}

      {result && (
        <div className="space-y-4" aria-live="polite">
          <div>
            <p className="text-xs text-gray-600">Preview export — not saved.</p>
            <div className="mt-1 flex flex-wrap gap-2" aria-label="Research export controls">
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
          </div>
          {result.results.map((envelope) => (
            <ResearchResultView
              key={envelope.run.run_id}
              envelope={envelope}
              transcriptTurns={result.transcript_turns}
            />
          ))}
        </div>
      )}
    </section>
  )
}
