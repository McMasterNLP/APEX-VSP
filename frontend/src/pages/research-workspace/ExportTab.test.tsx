import { render, screen } from '@testing-library/react'
import { MemoryRouter, useOutletContext } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ExportTab } from './ExportTab'
import type { EvaluationSessionContext } from './useEvaluationSession'
import type { ValidationRunRecord } from '@/types/researchEvaluation'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useOutletContext: vi.fn() }
})

vi.mock('@/components/admin/research/AnnotationExportButtons', () => ({
  AnnotationExportButtons: () => <div>annotation export buttons</div>,
}))

vi.mock('@/components/admin/research/ValidationExportButtons', () => ({
  ValidationExportButtons: ({ validationRunUuid }: { validationRunUuid: string }) => (
    <div>validation export buttons for {validationRunUuid}</div>
  ),
}))

const mockedUseOutletContext = vi.mocked(useOutletContext)

const validationRun = (overrides: Partial<ValidationRunRecord> = {}): ValidationRunRecord => ({
  validation_run_uuid: 'validation-1',
  evaluation_run_uuid: 'run-1',
  annotation_set_uuid: 'set-1',
  annotation_set_revision_at_validation: 1,
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
    eligibility: { eligible_metric_identifiers: [], ineligible_metric_identifiers: [], metrics: [] },
    span_classification: {
      metric_family: 'span_classification',
      metric_implementation_version: 'span-classification-v1',
      matching_policy_identifier: 'exact_span_match',
      matching_policy_version: '1.0',
      per_label: [],
      micro: {
        true_positives: 0,
        false_positives: 0,
        false_negatives: 0,
        precision: { status: 'computed', value: '1' },
        recall: { status: 'computed', value: '1' },
        f1: { status: 'computed', value: '1' },
        labels_included: 0,
      },
      macro: {
        true_positives: 0,
        false_positives: 0,
        false_negatives: 0,
        precision: { status: 'computed', value: '1' },
        recall: { status: 'computed', value: '1' },
        f1: { status: 'computed', value: '1' },
        labels_included: 0,
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
      <ExportTab />
    </MemoryRouter>
  )
}

describe('ExportTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the empty state when there is nothing to export at all', () => {
    renderTab(baseContext())
    expect(screen.getByText(/nothing to export yet/i)).toBeInTheDocument()
  })

  it('renders a third "Validation exports" group only once a validation run exists', () => {
    renderTab(baseContext({ validationRuns: [validationRun()] }))
    expect(screen.getByText('Validation exports')).toBeInTheDocument()
    expect(screen.getByText('validation export buttons for validation-1')).toBeInTheDocument()
    // Neither of the other two groups renders when their own preconditions aren't met.
    expect(screen.queryByText('Preview exports — not saved')).not.toBeInTheDocument()
    expect(screen.queryByText('Saved run & review exports')).not.toBeInTheDocument()
  })

  it('lists one export row per validation run', () => {
    renderTab(
      baseContext({
        validationRuns: [
          validationRun({ validation_run_uuid: 'v-1' }),
          validationRun({ validation_run_uuid: 'v-2' }),
        ],
      })
    )
    expect(screen.getByText('validation export buttons for v-1')).toBeInTheDocument()
    expect(screen.getByText('validation export buttons for v-2')).toBeInTheDocument()
  })
})
