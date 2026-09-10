import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResearchEvaluationPanel } from './ResearchEvaluationPanel'
import {
  downloadResearchEvaluationExport,
  fetchSavedResearchRuns,
  fetchResearchEvaluatorDescriptors,
  runResearchEvaluations,
  saveResearchEvaluationRun,
} from '@/api/research.api'
import type {
  ResearchEvaluationResponse,
  ResearchEvaluatorDescriptor,
} from '@/types/researchEvaluation'

vi.mock('@/api/research.api', () => ({
  createResearchAnnotationSet: vi.fn(),
  fetchSavedResearchRun: vi.fn(),
  fetchSavedResearchRuns: vi.fn(),
  fetchResearchEvaluatorDescriptors: vi.fn(),
  getResearchApiMessage: (_error: unknown, fallback: string) => fallback,
  runResearchEvaluations: vi.fn(),
  saveResearchEvaluationRun: vi.fn(),
  downloadResearchEvaluationExport: vi.fn(),
}))

vi.mock('./ResearchResultView', () => ({
  ResearchResultView: ({ envelope }: { envelope: { status: string; evaluator: { display_name: string } } }) => (
    <div>{envelope.evaluator.display_name}: {envelope.status}</div>
  ),
}))

const mockedDescriptors = vi.mocked(fetchResearchEvaluatorDescriptors)
const mockedSavedRuns = vi.mocked(fetchSavedResearchRuns)
const mockedRun = vi.mocked(runResearchEvaluations)
const mockedSave = vi.mocked(saveResearchEvaluationRun)
const mockedExport = vi.mocked(downloadResearchEvaluationExport)

const capabilities = {
  outputs: {
    character_spans: true,
    turn_labels: true,
    relations: true,
    dimension_ratings: false,
    global_metrics: true,
    narrative_findings: true,
    evidence_turns: true,
    framework_native_view: true,
    live_execution: false,
  },
  annotation_operations: {
    confirm: true,
    reject: true,
    change_label: true,
    change_dimension: true,
    adjust_span: false as const,
    change_rating: false,
    mark_insufficient_evidence: false,
    change_evidence: false,
    change_assessability: false,
    add_annotation: false as const,
    add_relation: false as const,
  },
  annotation_by_projection: {
    span_annotation: {
      confirm: true, reject: true, change_label: true, change_dimension: true,
      adjust_span: false as const, change_rating: false,
      mark_insufficient_evidence: false, change_evidence: false,
      change_assessability: false, add_annotation: false as const, add_relation: false as const,
    },
    turn_label: {
      confirm: true, reject: true, change_label: true, change_dimension: true,
      adjust_span: false as const, change_rating: false,
      mark_insufficient_evidence: false, change_evidence: false,
      change_assessability: false, add_annotation: false as const, add_relation: false as const,
    },
    relation: {
      confirm: true, reject: true, change_label: false, change_dimension: false,
      adjust_span: false as const, change_rating: false,
      mark_insufficient_evidence: false, change_evidence: false,
      change_assessability: false, add_annotation: false as const, add_relation: false as const,
    },
    dimension_rating: {
      confirm: false, reject: false, change_label: false, change_dimension: false,
      adjust_span: false as const, change_rating: false,
      mark_insufficient_evidence: false, change_evidence: false,
      change_assessability: false, add_annotation: false as const, add_relation: false as const,
    },
    finding: {
      confirm: true, reject: true, change_label: false, change_dimension: false,
      adjust_span: false as const, change_rating: false,
      mark_insufficient_evidence: false, change_evidence: false,
      change_assessability: false, add_annotation: false as const, add_relation: false as const,
    },
  },
}

function descriptor(overrides: Partial<ResearchEvaluatorDescriptor> = {}): ResearchEvaluatorDescriptor {
  return {
    identifier: 'baseline',
    display_name: 'APEX baseline',
    version: '1.0',
    framework: {
      identifier: 'apex-spikes-afce',
      display_name: 'APEX SPIKES / AFCE-aligned',
      version: '1.0',
      validation_status: 'engineering_baseline_unvalidated',
      framework_statement: 'AFCE-aligned, rule-based operationalization of selected constructs.',
    },
    adapter: {
      identifier: 'apex.feedback.adapter',
      version: '1.0',
      supported_native_type: 'apex_feedback',
    },
    capabilities,
    requires_live_execution: false,
    supported_providers: [],
    default_selected: true,
    availability: 'available',
    warnings: [],
    ...overrides,
  }
}

describe('ResearchEvaluationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedDescriptors.mockResolvedValue({ schema_version: '1.0', evaluators: [descriptor()] })
    mockedSavedRuns.mockResolvedValue([])
  })

  it('loads descriptors, defaults to baseline, and executes explicitly', async () => {
    mockedRun.mockResolvedValue({
      schema_version: '1.0',
      transcript: {},
      transcript_turns: [],
      results: [],
    } as ResearchEvaluationResponse)
    render(<ResearchEvaluationPanel sessionId={42} sessionState="completed" />)

    expect(screen.getByText(/does not overwrite saved learner feedback/i)).toBeInTheDocument()
    const baseline = await screen.findByRole('checkbox', { name: /APEX baseline/i })
    expect(baseline).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: /preview selected evaluators/i }))

    await waitFor(() =>
      expect(mockedRun).toHaveBeenCalledWith(42, {
        evaluator_identifiers: ['baseline'],
        allow_live: false,
      })
    )
    expect(screen.queryByRole('button', { name: /confirm|reject|correct/i })).not.toBeInTheDocument()
  })

  it('keeps preview distinct from explicit server run and save', async () => {
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
    } as unknown as import('@/types/researchEvaluation').EvaluationRunRecord)
    render(<ResearchEvaluationPanel sessionId={42} sessionState="completed" />)
    await screen.findByText(/APEX baseline/i)

    fireEvent.click(screen.getByRole('button', { name: /run and save for review/i }))
    await waitFor(() =>
      expect(mockedSave).toHaveBeenCalledWith(42, {
        evaluator_identifier: 'baseline',
        allow_live: false,
      })
    )
    expect(mockedRun).not.toHaveBeenCalled()
    expect(await screen.findByText(/selected saved run: APEX baseline/i)).toBeInTheDocument()
    expect(screen.getByText(/saving reruns the evaluator on the server/i)).toBeInTheDocument()
  })

  it('shows live requirements without enabling live execution automatically', async () => {
    mockedDescriptors.mockResolvedValue({
      schema_version: '1.0',
      evaluators: [
        descriptor({
          identifier: 'hybrid_v1',
          display_name: 'APEX hybrid v1',
          default_selected: false,
          requires_live_execution: true,
          supported_providers: ['openai'],
          capabilities: {
            ...capabilities,
            outputs: { ...capabilities.outputs, live_execution: true },
          },
        }),
      ],
    })
    render(<ResearchEvaluationPanel sessionId={42} sessionState="completed" />)
    await screen.findByText(/requires live provider/i)
    expect(screen.queryByLabelText(/explicitly allow live/i)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: /APEX hybrid v1/i }))
    expect(screen.getByLabelText(/explicitly allow live/i)).not.toBeChecked()
  })

  it('blocks execution for an incomplete session', async () => {
    render(<ResearchEvaluationPanel sessionId={42} sessionState="active" />)
    await screen.findByText(/APEX baseline/i)
    expect(screen.getByText(/complete this session/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /preview selected evaluators/i })).toBeDisabled()
    expect(mockedRun).not.toHaveBeenCalled()
    expect(mockedExport).not.toHaveBeenCalled()
  })

  it('surfaces descriptor loading errors', async () => {
    mockedDescriptors.mockRejectedValue(new Error('Descriptor service unavailable.'))
    render(<ResearchEvaluationPanel sessionId={42} sessionState="completed" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Descriptor service unavailable.')
    expect(screen.getByRole('button', { name: /preview selected evaluators/i })).toBeDisabled()
  })

  it('renders partial success and exports the exact returned envelopes', async () => {
    const results = [
      { run: { run_id: 'one' }, evaluator: { display_name: 'APEX baseline' }, status: 'success' },
      { run: { run_id: 'two' }, evaluator: { display_name: 'Experimental evaluator' }, status: 'failed' },
    ]
    mockedRun.mockResolvedValue({
      schema_version: '1.0',
      transcript: {},
      transcript_turns: [],
      results,
    } as unknown as ResearchEvaluationResponse)
    mockedExport.mockResolvedValue(undefined)
    render(<ResearchEvaluationPanel sessionId={42} sessionState="completed" />)

    await screen.findByText(/APEX baseline/i)
    fireEvent.click(screen.getByRole('button', { name: /preview selected evaluators/i }))
    expect(await screen.findByText('APEX baseline: success')).toBeInTheDocument()
    expect(screen.getByText('Experimental evaluator: failed')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Full JSON' }))
    await waitFor(() => expect(mockedExport).toHaveBeenCalledWith(42, 'full', results))
  })

  it('disables unavailable evaluators while preserving their visible status', async () => {
    mockedDescriptors.mockResolvedValue({
      schema_version: '1.0',
      evaluators: [descriptor({ availability: 'server_live_disabled' })],
    })
    render(<ResearchEvaluationPanel sessionId={42} sessionState="completed" />)

    const evaluator = await screen.findByRole('checkbox', { name: /APEX baseline/i })
    expect(evaluator).toBeDisabled()
    expect(screen.getByText(/server live disabled/i)).toBeInTheDocument()
  })
})
