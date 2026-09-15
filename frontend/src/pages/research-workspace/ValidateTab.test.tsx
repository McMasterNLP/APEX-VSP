import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useOutletContext } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ValidateTab } from './ValidateTab'
import type { EvaluationSessionContext } from './useEvaluationSession'
import type {
  AnnotationSetSummary,
  EvaluationRunSummary,
  ValidationRunRecord,
} from '@/types/researchEvaluation'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useOutletContext: vi.fn() }
})

const mockedUseOutletContext = vi.mocked(useOutletContext)

const savedRun = (uuid = 'run-1'): EvaluationRunSummary => ({
  run_uuid: uuid,
  item1_run_id: uuid,
  evaluator_identifier: 'baseline',
  evaluator_version: '1.0',
  framework_identifier: 'apex-spikes-afce',
  framework_version: '1.0',
  transcript_hash: 'a'.repeat(64),
  execution_mode: 'offline',
  status: 'success',
  created_at: '2026-01-01T00:00:00Z',
  transcript_matches_current: true,
})

const annotationSetSummary = (
  overrides: Partial<AnnotationSetSummary> = {}
): AnnotationSetSummary => ({
  annotation_set_uuid: 'set-1',
  evaluation_run_uuid: 'run-1',
  transcript_hash: 'a'.repeat(64),
  transcript_matches_current: true,
  guideline_identifier: 'apex-afce-expert-review',
  guideline_version: '1.0',
  reviewer_reference: 'reviewer_abc123',
  status: 'complete',
  locked: true,
  coverage_level: 'exhaustive',
  revision: 3,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  completed_at: '2026-01-02T00:00:00Z',
  ...overrides,
})

const validationRun = (overrides: Partial<ValidationRunRecord> = {}): ValidationRunRecord => ({
  validation_run_uuid: 'validation-1',
  evaluation_run_uuid: 'run-1',
  annotation_set_uuid: 'set-1',
  annotation_set_revision_at_validation: 3,
  transcript_hash: 'a'.repeat(64),
  evaluator_identifier: 'baseline',
  evaluator_version: '1.0',
  matching_policy_identifier: 'exact_span_match',
  matching_policy_version: '1.0',
  metric_implementation_version: 'span-classification-v1',
  coverage_level: 'exhaustive',
  results: {
    schema_version: '1.0',
    coverage_level: 'exhaustive',
    eligibility: {
      eligible_metric_identifiers: ['span_precision', 'span_recall', 'span_f1'],
      ineligible_metric_identifiers: [],
      metrics: [],
    },
    span_classification: {
      metric_family: 'span_classification',
      metric_implementation_version: 'span-classification-v1',
      matching_policy_identifier: 'exact_span_match',
      matching_policy_version: '1.0',
      per_label: [],
      micro: {
        true_positives: 1,
        false_positives: 0,
        false_negatives: 0,
        precision: { status: 'computed', value: '1' },
        recall: { status: 'computed', value: '1' },
        f1: { status: 'computed', value: '1' },
        labels_included: 1,
      },
      macro: {
        true_positives: 1,
        false_positives: 0,
        false_negatives: 0,
        precision: { status: 'computed', value: '1' },
        recall: { status: 'computed', value: '1' },
        f1: { status: 'computed', value: '1' },
        labels_included: 1,
      },
    },
  },
  warnings: [],
  created_by_reference: 'reviewer_abc123',
  created_at: '2026-01-03T00:00:00Z',
  ...overrides,
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
    annotationSets: [],
    loadingAnnotationSets: false,
    refetchAnnotationSets: vi.fn(),
    validationRuns: [],
    loadingValidationRuns: false,
    refetchValidationRuns: vi.fn(),
    creatingValidationRun: false,
    createValidationRun: vi.fn(),
    error: null,
    setError: vi.fn(),
    ...overrides,
  }
}

function renderTab(context: EvaluationSessionContext) {
  mockedUseOutletContext.mockReturnValue(context)
  return render(
    <MemoryRouter>
      <ValidateTab />
    </MemoryRouter>
  )
}

describe('ValidateTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('explains that a saved evaluator run is needed when none exists', () => {
    renderTab(baseContext({ savedRuns: [], annotationSets: [] }))
    expect(screen.getByText(/needs a saved evaluator run first/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to saved runs/i })).toBeInTheDocument()
  })

  it('explains that a reference annotation set is needed when a run exists but no set does', () => {
    renderTab(baseContext({ savedRuns: [savedRun()], annotationSets: [] }))
    expect(screen.getByText(/no annotation set exists for this session yet/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /go to review & annotate/i })).toBeInTheDocument()
  })

  it('explains that the annotation set exists but is not complete, distinct from "no set at all"', () => {
    renderTab(
      baseContext({
        savedRuns: [savedRun()],
        annotationSets: [annotationSetSummary({ status: 'draft', locked: false })],
      })
    )
    expect(screen.getByText(/none has been marked/i)).toBeInTheDocument()
    expect(screen.getAllByText('complete').length).toBeGreaterThan(0)
  })

  it('offers the trigger once a saved run and a complete annotation set both exist', () => {
    renderTab(
      baseContext({
        savedRuns: [savedRun()],
        annotationSets: [annotationSetSummary()],
      })
    )
    expect(screen.getByRole('button', { name: /run validation/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/evaluator run to score/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/reference annotation set/i)).toBeInTheDocument()
  })

  it('calls createValidationRun with the selected run and annotation set uuids', async () => {
    const createValidationRun = vi.fn().mockResolvedValue(validationRun())
    renderTab(
      baseContext({
        savedRuns: [savedRun('run-1')],
        annotationSets: [annotationSetSummary({ annotation_set_uuid: 'set-1' })],
        createValidationRun,
      })
    )

    fireEvent.change(screen.getByLabelText(/evaluator run to score/i), {
      target: { value: 'run-1' },
    })
    fireEvent.change(screen.getByLabelText(/reference annotation set/i), {
      target: { value: 'set-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /run validation/i }))

    await waitFor(() => expect(createValidationRun).toHaveBeenCalledWith('run-1', 'set-1'))
  })

  it('warns and disables validation when the selected run and set have different transcript hashes', () => {
    renderTab(
      baseContext({
        savedRuns: [savedRun('run-1')],
        annotationSets: [
          annotationSetSummary({ annotation_set_uuid: 'set-1', transcript_hash: 'b'.repeat(64) }),
        ],
      })
    )

    fireEvent.change(screen.getByLabelText(/evaluator run to score/i), {
      target: { value: 'run-1' },
    })
    fireEvent.change(screen.getByLabelText(/reference annotation set/i), {
      target: { value: 'set-1' },
    })

    expect(screen.getByText(/different transcripts/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run validation/i })).toBeDisabled()
  })

  it('warns but does not block validation when the run\'s framework produces no span or relation predictions', () => {
    renderTab(
      baseContext({
        savedRuns: [
          { ...savedRun('run-1'), framework_identifier: 'ace-ct-inspired' },
        ],
        annotationSets: [
          annotationSetSummary({ annotation_set_uuid: 'set-1' }),
        ],
      })
    )

    fireEvent.change(screen.getByLabelText(/evaluator run to score/i), {
      target: { value: 'run-1' },
    })

    expect(screen.getByText(/doesn.t produce span or relation predictions/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/reference annotation set/i), {
      target: { value: 'set-1' },
    })
    expect(screen.getByRole('button', { name: /run validation/i })).not.toBeDisabled()
  })

  it('only offers complete annotation sets as reference options, and notes the excluded ones', () => {
    renderTab(
      baseContext({
        savedRuns: [savedRun()],
        annotationSets: [
          annotationSetSummary({ annotation_set_uuid: 'set-complete', status: 'complete' }),
          annotationSetSummary({
            annotation_set_uuid: 'set-draft',
            status: 'draft',
            locked: false,
          }),
        ],
      })
    )
    const select = screen.getByLabelText(/reference annotation set/i) as HTMLSelectElement
    const optionValues = Array.from(select.options).map((option) => option.value)
    expect(optionValues).toContain('set-complete')
    expect(optionValues).not.toContain('set-draft')
    expect(screen.getByText(/1 other annotation set for this session is not yet complete/i)).toBeInTheDocument()
  })

  it('renders the run list newest-first with a not-available-safe headline micro F1', () => {
    renderTab(
      baseContext({
        savedRuns: [savedRun()],
        annotationSets: [annotationSetSummary()],
        validationRuns: [
          validationRun({ validation_run_uuid: 'v-2' }),
          validationRun({ validation_run_uuid: 'v-1' }),
        ],
      })
    )
    const buttons = screen.getAllByRole('button', { name: /baseline v1\.0/i })
    expect(buttons).toHaveLength(2)
  })

  it('shows the results table for the selected validation run, including any warnings', () => {
    renderTab(
      baseContext({
        savedRuns: [savedRun()],
        annotationSets: [annotationSetSummary()],
        validationRuns: [
          validationRun({
            validation_run_uuid: 'v-1',
            warnings: ['Evaluator projection includes out-of-scope content.'],
          }),
        ],
      })
    )
    expect(screen.getByText(/Evaluator projection includes out-of-scope content\./)).toBeInTheDocument()
    expect(screen.getByText('Micro average')).toBeInTheDocument()
  })
})
