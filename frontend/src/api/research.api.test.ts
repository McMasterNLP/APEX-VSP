/**
 * Verification tests for research.api.ts
 *
 * Covers:
 *   - fetchResearchSessions: HTTP call, params, response pass-through, 403 -> friendly error
 *   - fetchResearchSessionByAnonId: URL construction, error handling
 *   - fetchResearchExport: blob download, DOM interactions, 403 error
 *   - fetchResearchData: maps to ResearchData, score clamping, fairnessMetrics absent
 *   - downloadMetricsCSV: uses native fetch, token from the auth store, triggers download
 *   - downloadTranscriptsCSV: same pattern, different URL/filename
 */

import assert from 'node:assert/strict'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchResearchSessions,
  fetchResearchSessionByAnonId,
  fetchResearchExport,
  fetchResearchData,
  downloadMetricsCSV,
  downloadTranscriptsCSV,
} from '@/api/research.api'
import type { ResearchSessionDTO, ResearchSessionsResponse } from '@/api/research.api'
import { useAuthStore } from '@/store/authStore'
import { apiGet } from '@/test/authTestMocks'

// Global setup wires `api.get` → `apiGet`. Prefer `mockImplementationOnce(() => Promise.reject(...))`
// for error paths: `mockRejectedValue` is unreliable with Vitest's restoreMocks lifecycle in this project.
const mockedGet = vi.mocked(apiGet)

/** Plain object: Vitest/mock pipelines can strip AxiosError `response` from rejections. */
function makeAxios403(): import('axios').AxiosError {
  return {
    isAxiosError: true,
    name: 'AxiosError',
    message: 'Forbidden',
    response: { status: 403, data: {}, statusText: 'Forbidden', headers: {}, config: {} },
  } as import('axios').AxiosError
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSessionDTO(overrides: Partial<ResearchSessionDTO> = {}): ResearchSessionDTO {
  return {
    session_id: 'anon_abc123456789',
    case_id: 5,
    case_name: 'Oncology Case',
    duration_seconds: 240,
    state: 'completed',
    patient_model_plugin: null,
    evaluator_plugin: null,
    metrics_plugins: null,
    spikes_stage: null,
    empathy_score: 70.0,
    communication_score: 65.0,
    clinical_score: 55.0,
    spikes_completion_score: 50.0,
    timestamp: '2024-03-15T10:00:00Z',
    ...overrides,
  }
}

function makeSessionsResponse(
  sessions: ResearchSessionDTO[] = [],
  overrides: Partial<ResearchSessionsResponse> = {}
): ResearchSessionsResponse {
  return {
    sessions,
    total: sessions.length,
    skip: 0,
    limit: 100,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// fetchResearchSessions
// ---------------------------------------------------------------------------

describe('fetchResearchSessions', () => {
  beforeEach(() => mockedGet.mockReset())

  it('calls GET /v1/research/sessions with default skip=0 and limit=100', async () => {
    mockedGet.mockResolvedValue({ data: makeSessionsResponse() })
    await fetchResearchSessions()
    expect(mockedGet).toHaveBeenCalledWith('/v1/research/sessions', {
      params: { skip: 0, limit: 100 },
    })
  })

  it('passes custom skip and limit params', async () => {
    mockedGet.mockResolvedValue({ data: makeSessionsResponse() })
    await fetchResearchSessions(50, 200)
    expect(mockedGet).toHaveBeenCalledWith('/v1/research/sessions', {
      params: { skip: 50, limit: 200 },
    })
  })

  it('returns the response data as-is', async () => {
    const response = makeSessionsResponse([makeSessionDTO()], { total: 1 })
    mockedGet.mockResolvedValue({ data: response })
    const result = await fetchResearchSessions()
    expect(result.total).toBe(1)
    expect(result.sessions).toHaveLength(1)
    expect(result.sessions[0].session_id).toBe('anon_abc123456789')
  })

  it('throws an access-denied error on 403', async () => {
    mockedGet.mockImplementationOnce(() => Promise.reject(makeAxios403()))
    const err = await fetchResearchSessions().then(
      () => null,
      (e: unknown) => e as Error
    )
    assert.ok(err)
    assert.strictEqual(err.message, 'Access denied. Admin privileges required.')
  })

  it('propagates non-403 errors unchanged', async () => {
    const serverErr = new Error('Server error')
    mockedGet.mockImplementationOnce(() => Promise.reject(serverErr))
    const err = await fetchResearchSessions().then(
      () => null,
      (e: unknown) => e as Error
    )
    assert.strictEqual(err, serverErr)
  })
})

// ---------------------------------------------------------------------------
// fetchResearchSessionByAnonId
// ---------------------------------------------------------------------------

describe('fetchResearchSessionByAnonId', () => {
  beforeEach(() => mockedGet.mockReset())

  it('calls GET /v1/research/sessions/{encoded_id}', async () => {
    mockedGet.mockResolvedValue({ data: { session_id: 'anon_abc', case_id: 1 } })
    await fetchResearchSessionByAnonId('anon_abc123456789')
    expect(mockedGet).toHaveBeenCalledWith(
      '/v1/research/sessions/anon_abc123456789'
    )
  })

  it('returns the session detail object', async () => {
    const detail = { session_id: 'anon_xyz', case_id: 7, turns: [] }
    mockedGet.mockResolvedValue({ data: detail })
    const result = await fetchResearchSessionByAnonId('anon_xyz')
    expect(result).toEqual(detail)
  })

  it('throws access-denied on 403', async () => {
    mockedGet.mockImplementationOnce(() => Promise.reject(makeAxios403()))
    const err = await fetchResearchSessionByAnonId('anon_abc').then(
      () => null,
      (e: unknown) => e as Error
    )
    assert.ok(err)
    assert.strictEqual(err.message, 'Access denied. Admin privileges required.')
  })

  it('propagates non-403 errors', async () => {
    const notFound = new Error('Not found')
    mockedGet.mockImplementationOnce(() => Promise.reject(notFound))
    const err = await fetchResearchSessionByAnonId('anon_abc').then(
      () => null,
      (e: unknown) => e as Error
    )
    assert.strictEqual(err, notFound)
  })
})

// ---------------------------------------------------------------------------
// fetchResearchExport
// ---------------------------------------------------------------------------

describe('fetchResearchExport', () => {
  beforeEach(() => {
    mockedGet.mockReset()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:mock-url'),
      revokeObjectURL: vi.fn(),
    })
  })

  it('calls GET /v1/research/export with blob responseType', async () => {
    const blob = new Blob(['[]'], { type: 'application/json' })
    mockedGet.mockResolvedValue({ data: blob })
    await fetchResearchExport()
    expect(mockedGet).toHaveBeenCalledWith('/v1/research/export', {
      responseType: 'blob',
      headers: { Accept: 'application/json' },
    })
  })

  it('triggers a download anchor click', async () => {
    const blob = new Blob(['[]'])
    mockedGet.mockResolvedValue({ data: blob })

    const mockAnchor = {
      href: '',
      download: '',
      click: vi.fn(),
    }
    const createElement = vi.spyOn(document, 'createElement').mockReturnValue(
      mockAnchor as unknown as HTMLAnchorElement
    )
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => el)
    const removeChild = vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el)

    await fetchResearchExport()

    expect(mockAnchor.download).toBe('research_export.json')
    expect(mockAnchor.click).toHaveBeenCalledOnce()

    createElement.mockRestore()
    appendChild.mockRestore()
    removeChild.mockRestore()
  })

  it('throws access-denied on 403', async () => {
    mockedGet.mockImplementationOnce(() => Promise.reject(makeAxios403()))
    const err = await fetchResearchExport().then(
      () => null,
      (e: unknown) => e as Error
    )
    assert.ok(err)
    assert.strictEqual(err.message, 'Access denied. Admin privileges required.')
  })
})

// ---------------------------------------------------------------------------
// fetchResearchData
// ---------------------------------------------------------------------------

describe('fetchResearchData', () => {
  beforeEach(() => mockedGet.mockReset())

  it('calls fetchResearchSessions(0, 500) internally', async () => {
    mockedGet.mockResolvedValue({ data: makeSessionsResponse() })
    await fetchResearchData()
    expect(mockedGet).toHaveBeenCalledWith('/v1/research/sessions', {
      params: { skip: 0, limit: 500 },
    })
  })

  it('maps sessions to anonymizedSessions with camelCase fields', async () => {
    const dto = makeSessionDTO({
      session_id: 'anon_session_001',
      case_id: 3,
      case_name: 'Cardiology',
      timestamp: '2024-05-01T12:00:00Z',
    })
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([dto]) })

    const result = await fetchResearchData()
    const session = result.anonymizedSessions[0]

    expect(session.sessionId).toBe('anon_session_001')
    expect(session.caseId).toBe(3)
    expect(session.caseName).toBe('Cardiology')
    expect(session.timestamp).toBe('2024-05-01T12:00:00Z')
  })

  it('clamps empathy score to [0, 100]', async () => {
    const dto = makeSessionDTO({ empathy_score: 150.0 })
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([dto]) })
    const result = await fetchResearchData()
    expect(result.anonymizedSessions[0].scores.empathy).toBe(100)
  })

  it('clamps negative scores to 0', async () => {
    const dto = makeSessionDTO({ empathy_score: -10.0, communication_score: -5.0 })
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([dto]) })
    const result = await fetchResearchData()
    const { scores } = result.anonymizedSessions[0]
    expect(scores.empathy).toBe(0)
    expect(scores.communication).toBe(0)
  })

  it('returns null for non-finite scores', async () => {
    const dto = makeSessionDTO({ empathy_score: null })
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([dto]) })
    const result = await fetchResearchData()
    expect(result.anonymizedSessions[0].scores.empathy).toBeNull()
  })

  it('maps demographics placeholder values', async () => {
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([makeSessionDTO()]) })
    const result = await fetchResearchData()
    const { demographics } = result.anonymizedSessions[0]
    expect(demographics.ageGroup).toBe('—')
    expect(demographics.gender).toBe('—')
  })

  it('omits fairnessMetrics (undefined) when backend does not provide them', async () => {
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([makeSessionDTO()]) })
    const result = await fetchResearchData()
    expect(result.fairnessMetrics).toBeUndefined()
  })

  it('passes through spikes fields', async () => {
    const dto = makeSessionDTO({
      spikes_stage: 'knowledge',
      spikes_coverage_percent: 83.3,
      spikes_completion_score: 66.7,
    })
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([dto]) })
    const result = await fetchResearchData()
    const session = result.anonymizedSessions[0]
    expect(session.spikes_stage).toBe('knowledge')
    expect(session.spikes_coverage_percent).toBe(83.3)
    expect(session.spikes_completion_score).toBe(66.7)
  })

  it('handles empty session list', async () => {
    mockedGet.mockResolvedValue({ data: makeSessionsResponse([]) })
    const result = await fetchResearchData()
    expect(result.anonymizedSessions).toEqual([])
  })

  it('throws access-denied on 403', async () => {
    mockedGet.mockImplementationOnce(() => Promise.reject(makeAxios403()))
    const err = await fetchResearchData().then(
      () => null,
      (e: unknown) => e as Error
    )
    assert.ok(err)
    assert.strictEqual(err.message, 'Access denied. Admin privileges required.')
  })

  it('maps multiple sessions in order', async () => {
    const dtos = ['anon_aaa', 'anon_bbb', 'anon_ccc'].map((id) =>
      makeSessionDTO({ session_id: id })
    )
    mockedGet.mockResolvedValue({ data: makeSessionsResponse(dtos) })
    const result = await fetchResearchData()
    expect(result.anonymizedSessions.map((s) => s.sessionId)).toEqual([
      'anon_aaa',
      'anon_bbb',
      'anon_ccc',
    ])
  })
})

// ---------------------------------------------------------------------------
// downloadMetricsCSV
// ---------------------------------------------------------------------------

describe('downloadMetricsCSV', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    useAuthStore.setState({ token: null })
  })

  it('rejects when no authenticated token is available', async () => {
    await expect(downloadMetricsCSV()).rejects.toThrow('No auth token available')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('fetches metrics CSV with the auth-store Bearer token', async () => {
    useAuthStore.setState({ token: 'my-jwt' })
    const blob = new Blob(['csv'], { type: 'text/csv' })
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    })
    vi.stubGlobal('fetch', mockFetch)
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:metrics'),
      revokeObjectURL: vi.fn(),
    })

    const mockAnchor = { href: '', download: '', click: vi.fn() }
    vi.spyOn(document, 'createElement').mockReturnValue(
      mockAnchor as unknown as HTMLAnchorElement
    )

    await downloadMetricsCSV()

    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/v1/research/export/metrics.csv')
    expect((options.headers as Record<string, string>)['Authorization']).toBe('Bearer my-jwt')
    expect(mockAnchor.download).toBe('session_metrics.csv')
    expect(mockAnchor.click).toHaveBeenCalledOnce()
  })

  it('throws when the fetch response is not ok', async () => {
    useAuthStore.setState({ token: 'tok' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, blob: vi.fn() }))
    await expect(downloadMetricsCSV()).rejects.toThrow('Metrics export failed')
  })
})

// ---------------------------------------------------------------------------
// downloadTranscriptsCSV
// ---------------------------------------------------------------------------

describe('downloadTranscriptsCSV', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    useAuthStore.setState({ token: null })
  })

  it('rejects when no authenticated token is available', async () => {
    await expect(downloadTranscriptsCSV()).rejects.toThrow('No auth token available')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('fetches transcripts CSV and triggers download', async () => {
    useAuthStore.setState({ token: 'jwt-tok' })
    const blob = new Blob(['t'], { type: 'text/csv' })
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    })
    vi.stubGlobal('fetch', mockFetch)
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:transcripts'),
      revokeObjectURL: vi.fn(),
    })

    const mockAnchor = { href: '', download: '', click: vi.fn() }
    vi.spyOn(document, 'createElement').mockReturnValue(
      mockAnchor as unknown as HTMLAnchorElement
    )

    await downloadTranscriptsCSV()

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/v1/research/export/transcripts.csv')
    expect(mockAnchor.download).toBe('all_transcripts.csv')
    expect(mockAnchor.click).toHaveBeenCalledOnce()
  })

  it('throws when the fetch response is not ok', async () => {
    useAuthStore.setState({ token: 'tok' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, blob: vi.fn() }))
    await expect(downloadTranscriptsCSV()).rejects.toThrow('Transcripts export failed')
  })
})
