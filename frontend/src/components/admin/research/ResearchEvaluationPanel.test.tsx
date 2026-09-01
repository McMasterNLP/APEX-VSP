import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResearchEvaluationPanel } from './ResearchEvaluationPanel'
import {
  downloadResearchEvaluationExport,
  fetchResearchEvaluatorDescriptors,
  runResearchEvaluations,
} from '@/api/research.api'
import type {
  ResearchEvaluationResponse,
  ResearchEvaluatorDescriptor,
} from '@/types/researchEvaluation'

vi.mock('@/api/research.api', () => ({
  fetchResearchEvaluatorDescriptors: vi.fn(),
  runResearchEvaluations: vi.fn(),
  downloadResearchEvaluationExport: vi.fn(),
}))

const mockedDescriptors = vi.mocked(fetchResearchEvaluatorDescriptors)
const mockedRun = vi.mocked(runResearchEvaluations)
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
    confirm: false as const,
    reject: false as const,
    change_label: false as const,
    adjust_span: false as const,
    change_rating: false as const,
    change_evidence: false as const,
    add_annotation: false as const,
    add_relation: false as const,
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
    fireEvent.click(screen.getByRole('button', { name: /run selected evaluators/i }))

    await waitFor(() =>
      expect(mockedRun).toHaveBeenCalledWith(42, {
        evaluator_identifiers: ['baseline'],
        allow_live: false,
      })
    )
    expect(screen.queryByRole('button', { name: /confirm|reject|correct/i })).not.toBeInTheDocument()
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
    expect(screen.getByRole('button', { name: /run selected evaluators/i })).toBeDisabled()
    expect(mockedRun).not.toHaveBeenCalled()
    expect(mockedExport).not.toHaveBeenCalled()
  })
})
