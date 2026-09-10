import { useEffect, useMemo, useState } from 'react'
import {
  downloadResearchEvaluationExport,
  createResearchAnnotationSet,
  fetchSavedResearchRun,
  fetchSavedResearchRuns,
  fetchResearchEvaluatorDescriptors,
  getResearchApiMessage,
  runResearchEvaluations,
  saveResearchEvaluationRun,
} from '@/api/research.api'
import type {
  AnnotationSetRecord,
  EvaluationRunRecord,
  EvaluationRunSummary,
  ResearchEvaluationResponse,
  ResearchEvaluatorDescriptor,
  ResearchExportProfile,
} from '@/types/researchEvaluation'
import { Button } from '@/components/ui/button'
import { ResearchResultView } from './ResearchResultView'
import { SavedResearchRuns } from './SavedResearchRuns'
import { AnnotationSetWorkspace } from './AnnotationSetWorkspace'

interface ResearchEvaluationPanelProps {
  sessionId: number
  sessionState: string
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
  const [saving, setSaving] = useState(false)
  const [savedRuns, setSavedRuns] = useState<EvaluationRunSummary[]>([])
  const [loadingSavedRuns, setLoadingSavedRuns] = useState(false)
  const [selectedRun, setSelectedRun] = useState<EvaluationRunRecord | null>(null)
  const [annotationSet, setAnnotationSet] = useState<AnnotationSetRecord | null>(null)
  const [busyRunUuid, setBusyRunUuid] = useState<string | null>(null)
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
            .filter(
              (descriptor) =>
                descriptor.default_selected && descriptor.availability === 'available'
            )
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

  useEffect(() => {
    if (sessionState !== 'completed') return
    let cancelled = false
    const load = async () => {
      setLoadingSavedRuns(true)
      try {
        const response = await fetchSavedResearchRuns(sessionId)
        if (!cancelled) setSavedRuns(response)
      } catch (caught) {
        if (!cancelled) {
          setError(getResearchApiMessage(caught, 'Saved research runs unavailable.'))
        }
      } finally {
        if (!cancelled) setLoadingSavedRuns(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [sessionId, sessionState])

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
  const effectiveProvider = availableProviders.includes(provider)
    ? provider
    : availableProviders[0]

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
        ...(hasLiveSelection && allowLive && effectiveProvider
          ? { provider: effectiveProvider }
          : {}),
      })
      setResult(response)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Research evaluation failed.')
    } finally {
      setRunning(false)
    }
  }

  const saveForReview = async () => {
    if (selectedDescriptors.length !== 1) return
    const descriptor = selectedDescriptors[0]
    setSaving(true)
    setError(null)
    try {
      const saved = await saveResearchEvaluationRun(sessionId, {
        evaluator_identifier: descriptor.identifier,
        allow_live: allowLive,
        ...(descriptor.requires_live_execution && allowLive && effectiveProvider
          ? { provider: effectiveProvider }
          : {}),
      })
      setSelectedRun(saved)
      setAnnotationSet(null)
      setSavedRuns((current) => [
        {
          run_uuid: saved.run_uuid,
          item1_run_id: saved.envelope.run.run_id,
          evaluator_identifier: saved.envelope.evaluator.identifier,
          evaluator_version: saved.envelope.evaluator.version,
          framework_identifier: saved.envelope.framework.identifier,
          framework_version: saved.envelope.framework.version,
          transcript_hash: saved.envelope.transcript.canonical_transcript_hash,
          execution_mode: saved.envelope.run.execution_mode,
          status: saved.envelope.status,
          created_at: saved.created_at,
          transcript_matches_current: saved.transcript_matches_current,
        },
        ...current.filter((item) => item.run_uuid !== saved.run_uuid),
      ])
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'Run and save for review failed.'))
    } finally {
      setSaving(false)
    }
  }

  const openSavedRun = async (runUuid: string) => {
    setBusyRunUuid(runUuid)
    setError(null)
    try {
      setSelectedRun(await fetchSavedResearchRun(runUuid))
      setAnnotationSet(null)
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'Saved research run could not be opened.'))
    } finally {
      setBusyRunUuid(null)
    }
  }

  const createOrOpenSet = async (run: EvaluationRunRecord) => {
    setBusyRunUuid(run.run_uuid)
    setError(null)
    try {
      setAnnotationSet(
        await createResearchAnnotationSet(run.run_uuid, {
          guideline_identifier: run.annotation_policy.guideline_identifier,
          guideline_version: run.annotation_policy.guideline_version,
        })
      )
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'Annotation set could not be opened.'))
    } finally {
      setBusyRunUuid(null)
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
            saving ||
            loadingDescriptors ||
            (hasLiveSelection && allowLive && availableProviders.length === 0)
          }
        >
          {running ? 'Running preview…' : 'Preview selected evaluators — not saved'}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void saveForReview()}
          disabled={
            !completed ||
            selected.length !== 1 ||
            running ||
            saving ||
            loadingDescriptors ||
            (hasLiveSelection && !allowLive) ||
            (hasLiveSelection && availableProviders.length === 0)
          }
        >
          {saving ? 'Running and saving…' : 'Run and save for review'}
        </Button>
      </div>
      <p className="text-xs text-gray-600">
        Saving reruns the evaluator on the server. Live or stochastic results may differ from a preview.
      </p>
      {selected.length > 1 && (
        <p className="text-xs text-gray-600">Select exactly one evaluator to save a review run.</p>
      )}

      {selected.length === 0 && !loadingDescriptors && (
        <p className="text-sm text-gray-600">Select at least one evaluator to run.</p>
      )}
      {error && <p role="alert" className="text-sm font-medium text-red-700">{error}</p>}

      {completed && (
        <SavedResearchRuns
          runs={savedRuns}
          loading={loadingSavedRuns}
          selectedRun={selectedRun}
          annotationSet={annotationSet}
          busyRunUuid={busyRunUuid}
          onOpen={(runUuid) => void openSavedRun(runUuid)}
          onCreateOrOpenSet={(run) => void createOrOpenSet(run)}
        />
      )}

      {selectedRun && annotationSet && (
        <AnnotationSetWorkspace
          run={selectedRun}
          annotationSet={annotationSet}
          onChange={setAnnotationSet}
        />
      )}

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
