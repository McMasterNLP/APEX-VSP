/**
 * Shared evaluation-session state for the five-tab Research workspace.
 *
 * @remarks
 * Lifted verbatim (structural extraction, not a behavior change) from the former
 * `ResearchEvaluationPanel`, plus the session-detail fetch the old
 * `ResearchEvaluationSessionPage` owned. The parent route element
 * ({@link ResearchEvaluationWorkspace}) calls this hook once and passes the whole
 * return value down via `<Outlet context={...} />`; each tab reads it with
 * `useOutletContext<EvaluationSessionContext>()`. This is the only shared-state
 * mechanism used here — no React context provider, no prop drilling.
 */
import { useEffect, useMemo, useState } from 'react'
import { fetchAdminSessionDetail, type AdminSessionDetailResponse } from '@/api/admin.api'
import {
  createResearchAnnotationSet,
  downloadResearchEvaluationExport,
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

/** Shared state and actions handed to every tab via `useOutletContext`. */
export interface EvaluationSessionContext {
  sessionId: number
  detail: AdminSessionDetailResponse | null
  loadingDetail: boolean
  detailError: string | null

  descriptors: ResearchEvaluatorDescriptor[]
  loadingDescriptors: boolean
  selected: string[]
  toggleEvaluator: (identifier: string) => void
  selectedDescriptors: ResearchEvaluatorDescriptor[]
  hasLiveSelection: boolean
  allowLive: boolean
  setAllowLive: (value: boolean) => void
  provider: 'openai' | 'gemini'
  setProvider: (value: 'openai' | 'gemini') => void
  availableProviders: Array<'openai' | 'gemini'>
  effectiveProvider: 'openai' | 'gemini' | undefined

  result: ResearchEvaluationResponse | null
  running: boolean
  execute: () => Promise<void>

  saving: boolean
  saveForReview: () => Promise<EvaluationRunRecord | null>

  savedRuns: EvaluationRunSummary[]
  loadingSavedRuns: boolean
  refetchSavedRuns: () => Promise<void>

  selectedRun: EvaluationRunRecord | null
  annotationSet: AnnotationSetRecord | null
  setAnnotationSet: (next: AnnotationSetRecord | null) => void
  busyRunUuid: string | null
  openSavedRun: (runUuid: string) => Promise<EvaluationRunRecord | null>
  createOrOpenSet: (run: EvaluationRunRecord) => Promise<AnnotationSetRecord | null>

  exporting: ResearchExportProfile | null
  downloadPreviewExport: (profile: ResearchExportProfile) => Promise<void>

  error: string | null
  setError: (message: string | null) => void
}

/**
 * Owns everything the evaluation workspace's five tabs share for one session.
 *
 * @param sessionId - Numeric id parsed from the `:sessionId` route param
 * @returns The full shared context; pass straight through to `<Outlet context={...} />`
 */
export function useEvaluationSession(sessionId: number): EvaluationSessionContext {
  const [detail, setDetail] = useState<AdminSessionDetailResponse | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(true)
  const [detailError, setDetailError] = useState<string | null>(null)

  const [descriptors, setDescriptors] = useState<ResearchEvaluatorDescriptor[]>([])
  const [loadingDescriptors, setLoadingDescriptors] = useState(true)
  const [selected, setSelected] = useState<string[]>([])
  const [allowLive, setAllowLive] = useState(false)
  const [provider, setProvider] = useState<'openai' | 'gemini'>('openai')

  const [result, setResult] = useState<ResearchEvaluationResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [saving, setSaving] = useState(false)

  const [savedRuns, setSavedRuns] = useState<EvaluationRunSummary[]>([])
  const [loadingSavedRuns, setLoadingSavedRuns] = useState(false)
  const [selectedRun, setSelectedRun] = useState<EvaluationRunRecord | null>(null)
  const [annotationSet, setAnnotationSet] = useState<AnnotationSetRecord | null>(null)
  const [busyRunUuid, setBusyRunUuid] = useState<string | null>(null)
  const [exporting, setExporting] = useState<ResearchExportProfile | null>(null)
  const [error, setError] = useState<string | null>(null)

  const sessionState = detail?.session.state ?? null

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoadingDetail(true)
      setDetailError(null)
      try {
        const data = await fetchAdminSessionDetail(String(sessionId))
        if (!cancelled) setDetail(data)
      } catch (e) {
        console.error('Failed to fetch session detail:', e)
        if (!cancelled) setDetailError('Failed to load session detail')
      } finally {
        if (!cancelled) setLoadingDetail(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [sessionId])

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

  const loadSavedRuns = async (onCancelled?: () => boolean) => {
    setLoadingSavedRuns(true)
    try {
      const response = await fetchSavedResearchRuns(sessionId)
      if (!onCancelled?.()) setSavedRuns(response)
    } catch (caught) {
      if (!onCancelled?.()) {
        setError(getResearchApiMessage(caught, 'Saved research runs unavailable.'))
      }
    } finally {
      if (!onCancelled?.()) setLoadingSavedRuns(false)
    }
  }

  useEffect(() => {
    // Fetched here (once, at the shared-hook level) rather than in any one tab, so
    // direct navigation to any tab — e.g. Review & Annotate with no prior tab visits —
    // still sees an accurate `savedRuns.length` and does not blank/crash.
    if (sessionState !== 'completed') return
    let cancelled = false
    void loadSavedRuns(() => cancelled)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
  const effectiveProvider = availableProviders.includes(provider) ? provider : availableProviders[0]

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

  const saveForReview = async (): Promise<EvaluationRunRecord | null> => {
    if (selectedDescriptors.length !== 1) return null
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
      return saved
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'Run and save for review failed.'))
      return null
    } finally {
      setSaving(false)
    }
  }

  const openSavedRun = async (runUuid: string): Promise<EvaluationRunRecord | null> => {
    setBusyRunUuid(runUuid)
    setError(null)
    try {
      const run = await fetchSavedResearchRun(runUuid)
      setSelectedRun(run)
      setAnnotationSet(null)
      return run
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'Saved research run could not be opened.'))
      return null
    } finally {
      setBusyRunUuid(null)
    }
  }

  const createOrOpenSet = async (run: EvaluationRunRecord): Promise<AnnotationSetRecord | null> => {
    setBusyRunUuid(run.run_uuid)
    setError(null)
    try {
      const set = await createResearchAnnotationSet(run.run_uuid, {
        guideline_identifier: run.annotation_policy.guideline_identifier,
        guideline_version: run.annotation_policy.guideline_version,
      })
      setAnnotationSet(set)
      return set
    } catch (caught) {
      setError(getResearchApiMessage(caught, 'Annotation set could not be opened.'))
      return null
    } finally {
      setBusyRunUuid(null)
    }
  }

  const downloadPreviewExport = async (profile: ResearchExportProfile) => {
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

  return {
    sessionId,
    detail,
    loadingDetail,
    detailError,

    descriptors,
    loadingDescriptors,
    selected,
    toggleEvaluator,
    selectedDescriptors,
    hasLiveSelection,
    allowLive,
    setAllowLive,
    provider,
    setProvider,
    availableProviders,
    effectiveProvider,

    result,
    running,
    execute,

    saving,
    saveForReview,

    savedRuns,
    loadingSavedRuns,
    refetchSavedRuns: loadSavedRuns,

    selectedRun,
    annotationSet,
    setAnnotationSet,
    busyRunUuid,
    openSavedRun,
    createOrOpenSet,

    exporting,
    downloadPreviewExport,

    error,
    setError,
  }
}
