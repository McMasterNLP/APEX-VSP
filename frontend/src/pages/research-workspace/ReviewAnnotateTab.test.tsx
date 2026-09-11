import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useOutletContext } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ReviewAnnotateTab } from './ReviewAnnotateTab'
import type { EvaluationSessionContext } from './useEvaluationSession'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useOutletContext: vi.fn() }
})

vi.mock('@/components/admin/research/AnnotationSetWorkspace', () => ({
  AnnotationSetWorkspace: ({ run }: { run: { run_uuid: string } }) => (
    <div>Workspace for {run.run_uuid}</div>
  ),
}))

vi.mock('@/components/admin/research/ReviewProgress', () => ({
  ReviewProgress: ({ progress }: { progress: { unreviewed: number } }) => (
    <div>Progress: {progress.unreviewed} unreviewed</div>
  ),
}))

const mockedUseOutletContext = vi.mocked(useOutletContext)

const savedRun = (uuid: string, created: string) => ({
  run_uuid: uuid,
  item1_run_id: uuid,
  evaluator_identifier: 'baseline',
  evaluator_version: '1.0',
  framework_identifier: 'apex-spikes-afce',
  framework_version: '1.0',
  transcript_hash: 'a'.repeat(64),
  execution_mode: 'offline' as const,
  status: 'success' as const,
  created_at: created,
  transcript_matches_current: true,
})

function baseContext(overrides: Partial<EvaluationSessionContext> = {}): EvaluationSessionContext {
  return {
    sessionId: 42,
    detail: null,
    loadingDetail: false,
    detailError: null,
    descriptors: [],
    loadingDescriptors: false,
    selected: [],
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

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/review" element={<ReviewAnnotateTab />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ReviewAnnotateTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a locked-state message and does not blank on direct navigation with zero saved runs', () => {
    mockedUseOutletContext.mockReturnValue(baseContext({ savedRuns: [] }))
    renderAt('/review')

    expect(screen.getByText(/no saved runs yet/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to saved runs/i })).toBeInTheDocument()
  })

  it('offers an in-tab picker when saved runs exist but none is resolved yet', () => {
    mockedUseOutletContext.mockReturnValue(
      baseContext({ savedRuns: [savedRun('run-1', '2026-01-01T00:00:00Z')] })
    )
    renderAt('/review')

    expect(screen.getByText(/choose a saved run to open for review/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /open for review/i })).toBeInTheDocument()
  })

  it('does not show a run-switcher with only one saved run', () => {
    mockedUseOutletContext.mockReturnValue(
      baseContext({ savedRuns: [savedRun('run-1', '2026-01-01T00:00:00Z')] })
    )
    renderAt('/review')
    expect(screen.queryByLabelText(/switch saved run/i)).not.toBeInTheDocument()
  })

  it('shows a run-switcher when more than one saved run exists', () => {
    mockedUseOutletContext.mockReturnValue(
      baseContext({
        savedRuns: [
          savedRun('run-1', '2026-01-01T00:00:00Z'),
          savedRun('run-2', '2026-01-02T00:00:00Z'),
        ],
      })
    )
    renderAt('/review')
    expect(screen.getByLabelText(/switch saved run/i)).toBeInTheDocument()
  })

  it('renders progress and the full-width workspace once a run and annotation set are resolved', async () => {
    mockedUseOutletContext.mockReturnValue(
      baseContext({
        savedRuns: [savedRun('run-1', '2026-01-01T00:00:00Z')],
        selectedRun: { run_uuid: 'run-1' } as never,
        annotationSet: { progress: { unreviewed: 3 } } as never,
      })
    )
    renderAt('/review')

    await waitFor(() => {
      expect(screen.getByText('Progress: 3 unreviewed')).toBeInTheDocument()
    })
    expect(screen.getByText('Workspace for run-1')).toBeInTheDocument()
  })
})
