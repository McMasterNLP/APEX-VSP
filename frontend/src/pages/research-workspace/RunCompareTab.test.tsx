import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunCompareTab } from './RunCompareTab'
import { runResearchEvaluations } from '@/api/research.api'
import type { EvaluationSessionContext } from './useEvaluationSession'
import { useOutletContext } from 'react-router-dom'

vi.mock('@/api/research.api', () => ({
  runResearchEvaluations: vi.fn(),
  getResearchApiMessage: (_error: unknown, fallback: string) => fallback,
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useOutletContext: vi.fn() }
})

vi.mock('@/components/admin/research/ResearchResultView', () => ({
  ResearchResultView: ({ envelope }: { envelope: { evaluator: { display_name: string } } }) => (
    <div>{envelope.evaluator.display_name}</div>
  ),
}))

const mockedRun = vi.mocked(runResearchEvaluations)
const mockedUseOutletContext = vi.mocked(useOutletContext)

function baseContext(overrides: Partial<EvaluationSessionContext> = {}): EvaluationSessionContext {
  return {
    sessionId: 42,
    detail: {
      session: { id: 42, state: 'completed' },
    } as never,
    loadingDetail: false,
    detailError: null,
    descriptors: [
      {
        identifier: 'baseline',
        display_name: 'APEX baseline',
        version: '1.0',
        framework: { display_name: 'APEX SPIKES / AFCE-aligned' } as never,
        requires_live_execution: false,
        supported_providers: [],
        default_selected: true,
        availability: 'available',
        warnings: [],
      } as never,
    ],
    loadingDescriptors: false,
    selected: ['baseline'],
    toggleEvaluator: vi.fn(),
    selectedDescriptors: [],
    hasLiveSelection: false,
    allowLive: false,
    setAllowLive: vi.fn(),
    provider: 'openai',
    setProvider: vi.fn(),
    availableProviders: [],
    effectiveProvider: undefined,
    result: null,
    running: false,
    execute: vi.fn(),
    saving: false,
    saveForReview: vi.fn(),
    savedRuns: [],
    loadingSavedRuns: false,
    refetchSavedRuns: vi.fn(),
    selectedRun: null,
    annotationSet: null,
    setAnnotationSet: vi.fn(),
    busyRunUuid: null,
    openSavedRun: vi.fn(),
    createOrOpenSet: vi.fn(),
    exporting: null,
    downloadPreviewExport: vi.fn(),
    error: null,
    setError: vi.fn(),
    ...overrides,
  }
}

describe('RunCompareTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('runs the preview via execute() and never calls a save action', async () => {
    const execute = vi.fn()
    mockedUseOutletContext.mockReturnValue(baseContext({ execute }))
    render(<RunCompareTab />)

    fireEvent.click(screen.getByRole('button', { name: /preview selected evaluators/i }))
    await waitFor(() => expect(execute).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('button', { name: /run and save for review/i })).not.toBeInTheDocument()
    expect(mockedRun).not.toHaveBeenCalled() // execute() is the hook's function, not called directly here
  })

  it('shows the not-saved banner and renders preview results when a result is present', () => {
    mockedUseOutletContext.mockReturnValue(
      baseContext({
        result: {
          schema_version: '1.0',
          transcript: {} as never,
          transcript_turns: [],
          results: [{ run: { run_id: 'one' }, evaluator: { display_name: 'APEX baseline' } } as never],
        },
      })
    )
    render(<RunCompareTab />)

    expect(screen.getByText(/preview only/i)).toBeInTheDocument()
    expect(screen.getByText(/preview export — not saved/i)).toBeInTheDocument()
    expect(screen.getAllByText('APEX baseline').length).toBeGreaterThan(0)
  })
})
