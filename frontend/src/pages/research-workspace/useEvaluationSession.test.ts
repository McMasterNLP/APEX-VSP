import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useEvaluationSession } from './useEvaluationSession'
import { fetchAdminSessionDetail } from '@/api/admin.api'
import {
  fetchResearchEvaluatorDescriptors,
  fetchSavedResearchRuns,
  runResearchEvaluations,
  saveResearchEvaluationRun,
} from '@/api/research.api'

vi.mock('@/api/admin.api', async () => {
  const actual = await vi.importActual<typeof import('@/api/admin.api')>('@/api/admin.api')
  return { ...actual, fetchAdminSessionDetail: vi.fn() }
})

vi.mock('@/api/research.api', () => ({
  createResearchAnnotationSet: vi.fn(),
  downloadResearchEvaluationExport: vi.fn(),
  fetchSavedResearchRun: vi.fn(),
  fetchSavedResearchRuns: vi.fn(),
  fetchResearchEvaluatorDescriptors: vi.fn(),
  getResearchApiMessage: (_error: unknown, fallback: string) => fallback,
  runResearchEvaluations: vi.fn(),
  saveResearchEvaluationRun: vi.fn(),
}))

const mockedFetchDetail = vi.mocked(fetchAdminSessionDetail)
const mockedDescriptors = vi.mocked(fetchResearchEvaluatorDescriptors)
const mockedSavedRuns = vi.mocked(fetchSavedResearchRuns)
const mockedRun = vi.mocked(runResearchEvaluations)
const mockedSave = vi.mocked(saveResearchEvaluationRun)

function descriptor(overrides: Record<string, unknown> = {}) {
  return {
    identifier: 'baseline',
    display_name: 'APEX baseline',
    version: '1.0',
    framework: { identifier: 'apex-spikes-afce', display_name: 'APEX SPIKES / AFCE-aligned' },
    adapter: { identifier: 'apex.feedback.adapter', version: '1.0' },
    capabilities: {},
    requires_live_execution: false,
    supported_providers: [],
    default_selected: true,
    availability: 'available',
    warnings: [],
    ...overrides,
  }
}

describe('useEvaluationSession', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedFetchDetail.mockResolvedValue({
      session: { id: 42, state: 'completed', turns: [] },
      feedback: null,
      metrics_timeline: [],
    } as never)
    mockedDescriptors.mockResolvedValue({ schema_version: '1.0', evaluators: [descriptor()] } as never)
    mockedSavedRuns.mockResolvedValue([])
  })

  it('fetches saved runs on mount regardless of which tab will render (completed session)', async () => {
    renderHook(() => useEvaluationSession(42))
    await waitFor(() => expect(mockedSavedRuns).toHaveBeenCalledWith(42))
  })

  it('does not fetch saved runs for an incomplete session', async () => {
    mockedFetchDetail.mockResolvedValue({
      session: { id: 42, state: 'active', turns: [] },
      feedback: null,
      metrics_timeline: [],
    } as never)
    renderHook(() => useEvaluationSession(42))
    await waitFor(() => expect(mockedFetchDetail).toHaveBeenCalled())
    expect(mockedSavedRuns).not.toHaveBeenCalled()
  })

  it('execute() runs a non-persisting preview with the selected evaluators', async () => {
    mockedRun.mockResolvedValue({
      schema_version: '1.0',
      transcript: {},
      transcript_turns: [],
      results: [],
    } as never)
    const { result } = renderHook(() => useEvaluationSession(42))
    await waitFor(() => expect(result.current.descriptors.length).toBe(1))
    expect(result.current.selected).toEqual(['baseline'])

    await act(async () => {
      await result.current.execute()
    })

    expect(mockedRun).toHaveBeenCalledWith(42, {
      evaluator_identifiers: ['baseline'],
      allow_live: false,
    })
    expect(mockedSave).not.toHaveBeenCalled()
  })

  it('saveForReview() persists exactly one selected evaluator, distinct from preview', async () => {
    mockedSave.mockResolvedValue({
      run_uuid: 'saved-run-uuid',
      created_at: '2026-09-02T00:00:00Z',
      transcript_matches_current: true,
      envelope: {
        status: 'success',
        run: { run_id: 'run_content', execution_mode: 'offline' },
        evaluator: { identifier: 'baseline', version: '1.0', display_name: 'APEX baseline' },
        framework: { identifier: 'apex-spikes-afce', version: '1.0' },
        transcript: { canonical_transcript_hash: 'a'.repeat(64) },
      },
      annotation_policy: {
        guideline_identifier: 'apex-afce-expert-review',
        guideline_version: '1.0',
      },
    } as never)
    const { result } = renderHook(() => useEvaluationSession(42))
    await waitFor(() => expect(result.current.descriptors.length).toBe(1))

    await act(async () => {
      await result.current.saveForReview()
    })

    expect(mockedSave).toHaveBeenCalledWith(42, {
      evaluator_identifier: 'baseline',
      allow_live: false,
    })
    expect(mockedRun).not.toHaveBeenCalled()
    expect(result.current.selectedRun?.run_uuid).toBe('saved-run-uuid')
    expect(result.current.savedRuns[0].run_uuid).toBe('saved-run-uuid')
  })

  it('saveForReview() is a no-op when more than one evaluator is selected', async () => {
    mockedDescriptors.mockResolvedValue({
      schema_version: '1.0',
      evaluators: [descriptor(), descriptor({ identifier: 'second', display_name: 'Second' })],
    } as never)
    const { result } = renderHook(() => useEvaluationSession(42))
    await waitFor(() => expect(result.current.descriptors.length).toBe(2))
    expect(result.current.selected.length).toBe(2)

    await act(async () => {
      const saved = await result.current.saveForReview()
      expect(saved).toBeNull()
    })
    expect(mockedSave).not.toHaveBeenCalled()
  })
})
