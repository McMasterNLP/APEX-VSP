import { useEffect, useMemo, useState } from 'react'
import {
  downloadResearchEvaluationExport,
  fetchResearchEvaluatorDescriptors,
  runResearchEvaluations,
} from '@/api/research.api'
import type {
  ResearchEvaluationResponse,
  ResearchEvaluatorDescriptor,
  ResearchExportProfile,
} from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'

interface ResearchEvaluationPanelProps {
  sessionId: number
  sessionState: string
}

const statusStyles: Record<string, string> = {
  success: 'bg-emerald-100 text-emerald-900',
  failed: 'bg-red-100 text-red-900',
  refused: 'bg-amber-100 text-amber-950',
}

export function ResearchEvaluationPanel({
  sessionId,
  sessionState,
}: ResearchEvaluationPanelProps) {
  const [descriptors, setDescriptors] = useState<ResearchEvaluatorDescriptor[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [allowLive, setAllowLive] = useState(false)
  const [provider, setProvider] = useState<'openai' | 'gemini'>('openai')
  const [result, setResult] = useState<ResearchEvaluationResponse | null>(null)
  const [loadingDescriptors, setLoadingDescriptors] = useState(true)
  const [running, setRunning] = useState(false)
  const [exporting, setExporting] = useState<ResearchExportProfile | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoadingDescriptors(true)
      setError(null)
      try {
        const response = await fetchResearchEvaluatorDescriptors()
        if (cancelled) return
        setDescriptors(response.evaluators)
        setSelected(
          response.evaluators
            .filter((descriptor) => descriptor.default_selected)
            .map((descriptor) => descriptor.identifier)
        )
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : 'Evaluator descriptors unavailable.')
        }
      } finally {
        if (!cancelled) setLoadingDescriptors(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedDescriptors = useMemo(
    () => descriptors.filter((descriptor) => selected.includes(descriptor.identifier)),
    [descriptors, selected]
  )
  const hasLiveSelection = selectedDescriptors.some(
    (descriptor) => descriptor.requires_live_execution
  )
  const availableProviders = useMemo(() => {
    const providerSets = selectedDescriptors
      .filter((descriptor) => descriptor.requires_live_execution)
      .map((descriptor) => new Set(descriptor.supported_providers))
    if (providerSets.length === 0) return []
    return [...providerSets[0]].filter((candidate) =>
      providerSets.every((supported) => supported.has(candidate))
    )
  }, [selectedDescriptors])

  const toggleEvaluator = (identifier: string) => {
    setSelected((current) =>
      current.includes(identifier)
        ? current.filter((item) => item !== identifier)
        : [...current, identifier]
    )
  }

  const execute = async () => {
    setRunning(true)
    setError(null)
    try {
      const response = await runResearchEvaluations(sessionId, {
        evaluator_identifiers: selected,
        allow_live: allowLive,
        ...(hasLiveSelection && allowLive ? { provider } : {}),
      })
      setResult(response)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Research evaluation failed.')
    } finally {
      setRunning(false)
    }
  }

  const download = async (profile: ResearchExportProfile) => {
    if (!result) return
    setExporting(profile)
    setError(null)
    try {
      await downloadResearchEvaluationExport(sessionId, profile, result.results)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Research export failed.')
    } finally {
      setExporting(null)
    }
  }

  const completed = sessionState === 'completed'
  return (
    <section aria-labelledby="research-evaluation-heading" className="space-y-4 border-t pt-6">
      <div>
        <h4 id="research-evaluation-heading" className="font-semibold text-gray-950">
          Research Evaluation
        </h4>
        <p className="mt-1 text-sm font-medium text-indigo-800">
          Research evaluation — does not overwrite saved learner feedback.
        </p>
      </div>

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
                value={provider}
                onChange={(event) => setProvider(event.target.value as 'openai' | 'gemini')}
                className="ml-2 rounded border border-amber-300 bg-white px-2 py-1"
              >
                {availableProviders.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}

      <Button
        type="button"
        onClick={() => void execute()}
        disabled={!completed || selected.length === 0 || running || loadingDescriptors}
      >
        {running ? 'Running research evaluation…' : 'Run selected evaluators'}
      </Button>

      {selected.length === 0 && !loadingDescriptors && (
        <p className="text-sm text-gray-600">Select at least one evaluator to run.</p>
      )}
      {error && <p role="alert" className="text-sm font-medium text-red-700">{error}</p>}

      {result && (
        <div className="space-y-4" aria-live="polite">
          <div className="flex flex-wrap gap-2" aria-label="Research export controls">
            {(
              [
                ['full', 'Full JSON'],
                ['framework_native', 'Framework-native JSON'],
                ['projection', 'Projection JSON'],
                ['tabular', 'Tabular ZIP'],
              ] as Array<[ResearchExportProfile, string]>
            ).map(([profile, label]) => (
              <Button
                key={profile}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void download(profile)}
                disabled={exporting !== null}
              >
                {exporting === profile ? 'Preparing…' : label}
              </Button>
            ))}
          </div>
          {result.results.map((envelope) => (
            <article key={envelope.run.run_id} className="rounded-lg border border-gray-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h5 className="font-medium text-gray-950">{envelope.evaluator.display_name}</h5>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusStyles[envelope.status]}`}>
                  {envelope.status}
                </span>
              </div>
              {envelope.error && (
                <p role="alert" className="mt-2 text-sm text-red-700">
                  {envelope.error.message}
                </p>
              )}
              {envelope.status === 'success' && (
                <p className="mt-2 text-sm text-gray-600">
                  Validated {envelope.framework.display_name} result · {envelope.run.runtime_ms.toFixed(1)} ms
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
