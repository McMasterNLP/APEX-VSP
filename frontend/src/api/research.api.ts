/**
 * Admin-only research endpoints: anonymized sessions and export download.
 */
import api from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import type { AxiosError } from 'axios'
import type {
  ResearchEvaluationEnvelope,
  ResearchEvaluationResponse,
  ResearchEvaluationRunRequest,
  ResearchEvaluatorDescriptorsResponse,
  ResearchExportProfile,
} from '@/types/researchEvaluation'

const BASE = '/v1/research'

const API_ORIGIN = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

/**
 * Downloads session metrics as CSV (`session_metrics.csv`) with the same Bearer token as the axios client.
 *
 * @throws Error when not signed in or when the HTTP response is not OK.
 */
export async function downloadMetricsCSV(): Promise<void> {
  const token = useAuthStore.getState().token
  if (!token) {
    throw new Error('No auth token available')
  }
  const response = await fetch(`${API_ORIGIN}/v1/research/export/metrics.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error('Metrics export failed')
  const blob = await response.blob()
  triggerBlobDownload(blob, 'session_metrics.csv')
}

/**
 * Downloads all transcripts as CSV (`all_transcripts.csv`) with the same Bearer token as the axios client.
 *
 * @throws Error when not signed in or when the HTTP response is not OK.
 */
export async function downloadTranscriptsCSV(): Promise<void> {
  const token = useAuthStore.getState().token
  if (!token) {
    throw new Error('No auth token available')
  }
  const response = await fetch(`${API_ORIGIN}/v1/research/export/transcripts.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error('Transcripts export failed')
  const blob = await response.blob()
  triggerBlobDownload(blob, 'all_transcripts.csv')
}

/** Backend anonymized session row from `GET /v1/research/sessions`. */
export interface ResearchSessionDTO {
  session_id: string | number
  case_id: number
  case_name?: string | null
  duration_seconds: number
  state: string
  patient_model_plugin?: string | null
  evaluator_plugin?: string | null
  metrics_plugins?: string | null
  spikes_stage?: string | null
  spikes_coverage_percent?: number | null
  spikes_coverage?: number | null
  empathy_score?: number | null
  communication_score?: number | null
  clinical_score?: number | null
  spikes_completion_score?: number | null
  timestamp?: string | null
}

/** Paginated research session list response. */
export interface ResearchSessionsResponse {
  sessions: ResearchSessionDTO[]
  total: number
  skip: number
  limit: number
}

/** Dashboard-ready research bundle (mapped from {@link ResearchSessionsResponse}). */
export interface ResearchData {
  anonymizedSessions: Array<{
    sessionId: string
    demographics: { ageGroup: string; gender: string }
    scores: { empathy: number | null; communication: number | null; clinical: number | null }
    timestamp: string
    caseId?: number
    /** Display title from backend `case_name` (case title). */
    caseName?: string | null
    patientModelPlugin?: string | null
    evaluatorPlugin?: string | null
    metricsPlugins?: string | null
    duration_seconds?: number
    state?: string
    spikes_stage?: string | null
    spikes_coverage_percent?: number | null
    spikes_coverage?: number | null
    spikes_completion_score?: number | null
  }>
  fairnessMetrics?: {
    biasProbeConsistency: number
    demographicParity: number
    equalizedOdds: number
  }
}

/**
 * Returns true when the error is an Axios 403 Forbidden response.
 *
 * @param err - Unknown caught error
 * @returns Whether `err` represents HTTP 403
 */
function isForbidden(err: unknown): boolean {
  const ax = err as AxiosError
  const status = ax.response?.status ?? ax.status
  return Number(status) === 403
}

/**
 * Clamps a numeric score to the inclusive 0–100 range, or null if not a finite number.
 *
 * @param value - Raw score from the API
 * @returns Clamped number or null
 */
function clampScoreOrNull(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  return Math.max(0, Math.min(100, value))
}

/**
 * Fetches anonymized sessions for the Research dashboard (admin only).
 *
 * @remarks
 * JWT is attached by the shared API client. Throws a friendly error on 403.
 *
 * @param skip - Pagination offset (default 0)
 * @param limit - Page size (default 100)
 * @returns {@link ResearchSessionsResponse}
 * @throws Error with an access-denied message when the user is not admin
 */
export async function fetchResearchSessions(
  skip = 0,
  limit = 100
): Promise<ResearchSessionsResponse> {
  try {
    const { data } = await api.get<ResearchSessionsResponse>(`${BASE}/sessions`, {
      params: { skip, limit },
    })
    return data
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}

/**
 * Fetches a single anonymized research session by `anon_session_id` (admin only).
 *
 * @throws Error on 403 or when the session is not found
 */
export async function fetchResearchSessionByAnonId(
  anonSessionId: string
): Promise<Record<string, unknown>> {
  try {
    const { data } = await api.get<Record<string, unknown>>(
      `${BASE}/sessions/${encodeURIComponent(anonSessionId)}`
    )
    return data
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}

/**
 * Downloads the anonymized research export as `research_export.json` in the browser.
 *
 * @remarks
 * Creates a temporary object URL and triggers a programmatic click on a hidden anchor.
 *
 * @returns Resolves when the download has been triggered (not when the file is saved)
 * @throws Error with an access-denied message on HTTP 403
 */
export async function fetchResearchExport(): Promise<void> {
  try {
    const { data } = await api.get<Blob>(`${BASE}/export`, {
      responseType: 'blob',
      headers: { Accept: 'application/json' },
    })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'research_export.json'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}

/**
 * Builds {@link ResearchData} for the Research page from paginated anonymized sessions.
 *
 * @remarks
 * Demographics and fairness metrics are placeholders when the backend omits them.
 *
 * @returns Mapped {@link ResearchData}
 * @throws Error with an access-denied message on HTTP 403
 */
export async function fetchResearchData(): Promise<ResearchData> {
  try {
    const res = await fetchResearchSessions(0, 500)

    const anonymizedSessions = res.sessions.map((s) => {
      const empathy = clampScoreOrNull(s.empathy_score)
      const communication = clampScoreOrNull(s.communication_score)
      const clinical = clampScoreOrNull(s.clinical_score)

      return {
        sessionId: String(s.session_id),
        demographics: { ageGroup: '—', gender: '—' } as const,
        scores: { empathy, communication, clinical } as const,
        timestamp: s.timestamp ?? '',
        caseId: s.case_id,
        caseName: s.case_name ?? null,
        patientModelPlugin: s.patient_model_plugin ?? null,
        evaluatorPlugin: s.evaluator_plugin ?? null,
        metricsPlugins: s.metrics_plugins ?? null,
        duration_seconds: s.duration_seconds,
        state: s.state,
        spikes_stage: s.spikes_stage ?? null,
        spikes_coverage_percent: s.spikes_coverage_percent ?? null,
        spikes_coverage: s.spikes_coverage ?? null,
        spikes_completion_score: s.spikes_completion_score ?? null,
      }
    })
    return {
      anonymizedSessions,
      // Backend does not provide fairness metrics; omit so UI hides that section
      fairnessMetrics: undefined,
    }
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}

/** Fetches the explicit research evaluator/capability registry (admin only). */
export async function fetchResearchEvaluatorDescriptors(): Promise<ResearchEvaluatorDescriptorsResponse> {
  try {
    const { data } = await api.get<ResearchEvaluatorDescriptorsResponse>(`${BASE}/evaluators`)
    return data
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}

/** Executes one or more research evaluators without changing saved session data. */
export async function runResearchEvaluations(
  sessionId: number,
  request: ResearchEvaluationRunRequest
): Promise<ResearchEvaluationResponse> {
  try {
    const { data } = await api.post<ResearchEvaluationResponse>(
      `${BASE}/sessions/${sessionId}/evaluations`,
      request
    )
    return data
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}

/** Downloads a sanitized JSON profile or multi-table CSV ZIP for existing run envelopes. */
export async function downloadResearchEvaluationExport(
  sessionId: number,
  profile: ResearchExportProfile,
  envelopes: ResearchEvaluationEnvelope[]
): Promise<void> {
  try {
    const { data } = await api.post<Blob>(
      `${BASE}/sessions/${sessionId}/evaluation-exports`,
      { profile, envelopes, include_transcript_content: false },
      { responseType: 'blob' }
    )
    const extension = profile === 'tabular' ? 'zip' : 'json'
    triggerBlobDownload(data, `apex_research_${profile}.${extension}`)
  } catch (err) {
    if (isForbidden(err)) {
      throw new Error('Access denied. Admin privileges required.')
    }
    throw err
  }
}
