import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  completeResearchAnnotationSet,
  createHumanAnnotation,
  declareAnnotationCoverage,
  downloadResearchAnnotationExport,
  fetchResearchAnnotationSet,
  reopenResearchAnnotationSet,
  saveResearchReviewDecision,
} from '@/api/research.api'
import type {
  AnnotationOperationCapabilities,
  AnnotationSetRecord,
  EvaluationRunRecord,
  ResearchEvaluationEnvelope,
  ReviewablePrediction,
} from '@/types/researchEvaluation'
import { AnnotationSetWorkspace } from './AnnotationSetWorkspace'

vi.mock('@/api/research.api', () => ({
  completeResearchAnnotationSet: vi.fn(),
  createAuthoredRelation: vi.fn(),
  createHumanAnnotation: vi.fn(),
  declareAnnotationCoverage: vi.fn(),
  downloadResearchAnnotationExport: vi.fn(),
  fetchResearchAnnotationSet: vi.fn(),
  getResearchApiMessage: (_error: unknown, fallback: string) => fallback,
  reopenResearchAnnotationSet: vi.fn(),
  reviseHumanAnnotation: vi.fn(),
  saveResearchReviewDecision: vi.fn(),
}))

const mockedComplete = vi.mocked(completeResearchAnnotationSet)
const mockedCreateHuman = vi.mocked(createHumanAnnotation)
const mockedCoverage = vi.mocked(declareAnnotationCoverage)
const mockedDownload = vi.mocked(downloadResearchAnnotationExport)
const mockedFetchSet = vi.mocked(fetchResearchAnnotationSet)
const mockedReopen = vi.mocked(reopenResearchAnnotationSet)
const mockedSave = vi.mocked(saveResearchReviewDecision)

const sourceReference = {
  native_result_type: 'apex_feedback' as const,
  native_identifier: 'native-1',
  native_path: '$.native.result',
  adapter_version: '1.0',
}

const noOperations: AnnotationOperationCapabilities = {
  confirm: false,
  reject: false,
  change_label: false,
  change_dimension: false,
  adjust_span: false,
  change_rating: false,
  mark_insufficient_evidence: false,
  change_evidence: false,
  change_assessability: false,
  add_annotation: false,
  add_relation: false,
}

const spanOperations: AnnotationOperationCapabilities = {
  ...noOperations,
  confirm: true,
  reject: true,
  change_label: true,
  change_dimension: true,
}

const authoringSpanOperations: AnnotationOperationCapabilities = {
  ...spanOperations,
  adjust_span: true,
  add_annotation: true,
}

const ratingOperations: AnnotationOperationCapabilities = {
  ...noOperations,
  confirm: true,
  reject: true,
  change_rating: true,
  mark_insufficient_evidence: true,
  change_evidence: true,
}

const spanPrediction: ReviewablePrediction = {
  prediction_id: 'span-1',
  projection_type: 'span_annotation',
  allowed_operations: spanOperations,
  original_prediction: {
    prediction_id: 'span-1',
    framework_identifier: 'apex-spikes-afce',
    projection_type: 'span_annotation',
    turn_number: 1,
    start_offset: 0,
    end_offset: 12,
    quoted_text: 'That sounds ',
    label: 'empathic_opportunity',
    dimension: 'feeling',
    source_reference: sourceReference,
  },
}

const relationPrediction: ReviewablePrediction = {
  prediction_id: 'relation-1',
  projection_type: 'relation',
  allowed_operations: { ...noOperations, confirm: true, reject: true },
  original_prediction: {
    relation_id: 'relation-1',
    framework_identifier: 'apex-spikes-afce',
    projection_type: 'relation',
    source_annotation_id: 'span-1',
    target_annotation_id: 'span-2',
    relation_type: 'responds_to',
    source_reference: sourceReference,
  },
}

const ratingPrediction: ReviewablePrediction = {
  prediction_id: 'rating-1',
  projection_type: 'dimension_rating',
  allowed_operations: ratingOperations,
  original_prediction: {
    rating_id: 'rating-1',
    framework_identifier: 'ace-ct-inspired',
    projection_type: 'dimension_rating',
    dimension_identifier: 'respond_1',
    domain_identifier: 'respond',
    score: 4,
    scale_minimum: 1,
    scale_maximum: 5,
    score_status: 'available',
    assessability: 'text_assessable',
    evidence_turns: [1],
    rationale: 'Original rationale.',
    source_reference: {
      ...sourceReference,
      native_result_type: 'ace_ct_inspired',
    },
  },
}

function makeRun(predictions: ReviewablePrediction[]): EvaluationRunRecord {
  const spans = predictions
    .filter((item) => item.projection_type === 'span_annotation')
    .map((item) => item.original_prediction)
  const ratings = predictions
    .filter((item) => item.projection_type === 'dimension_rating')
    .map((item) => item.original_prediction)
  return {
    run_uuid: 'run-uuid',
    source_session_id: 42,
    creator_reference: 'reviewer_123',
    created_at: '2026-09-02T00:00:00Z',
    transcript_matches_current: true,
    transcript_snapshot: [
      { turn_number: 1, role: 'clinician', source_role: 'user', text: 'That sounds difficult.' },
      { turn_number: 2, role: 'patient', source_role: 'assistant', text: 'It really is.' },
    ],
    envelope: {
      status: 'success',
      run: { run_id: 'content-run-id', execution_mode: 'offline' },
      evaluator: { identifier: 'baseline', version: '1.0', display_name: 'Baseline' },
      framework: { identifier: 'apex-spikes-afce', version: '1.0' },
      transcript: { canonical_transcript_hash: 'a'.repeat(64) },
      projection: {
        spans,
        turn_labels: [],
        relations: [],
        dimension_ratings: ratings,
        global_metrics: [],
        findings: [],
        limitations: [],
      },
    } as unknown as ResearchEvaluationEnvelope,
    annotation_policy: makePolicy(),
  }
}

function makePolicy() {
  return {
    policy_identifier: 'test-policy',
    policy_version: '1.0',
    guideline_identifier: 'test-guideline',
    guideline_version: '1.0',
    guideline_validation_status: 'engineering_unvalidated' as const,
    framework_identifier: 'apex-spikes-afce',
    supported_envelope_schema_versions: ['1.0'],
    supported_adapter_versions: ['1.0'],
    operations: {
      span_annotation: spanOperations,
      turn_label: spanOperations,
      relation: { ...noOperations, confirm: true, reject: true },
      dimension_rating: ratingOperations,
      finding: { ...noOperations, confirm: true, reject: true },
    },
    label_policies: [
      {
        projection_type: 'span_annotation' as const,
        allowed_labels: ['empathic_opportunity', 'empathic_response'],
        allowed_dimensions: ['feeling', 'judgment'],
        allow_null_dimension: true,
      },
    ],
    rating_scales: [
      {
        dimension_identifier: 'respond_1',
        allowed_scores: [1, 2, 3, 4, 5],
        allowed_assessability: ['text_assessable' as const, 'partially_assessable' as const, 'not_assessable' as const],
        allow_assessability_correction: false,
      },
    ],
  }
}

function makeAuthoringSet() {
  const set = makeSet([spanPrediction])
  return {
    ...set,
    annotation_policy: {
      ...set.annotation_policy,
      operations: { ...set.annotation_policy.operations, span_annotation: authoringSpanOperations },
      span_authoring: {
        supported: true, offset_convention: 'unicode_code_point_half_open' as const,
        overlap_policy: 'allow' as const, contiguous_only: true as const, single_turn_only: true as const,
        exhaustive_annotation_meaningful: true,
        guideline_help_text: 'Select the exact evidence.', attribute_policies: [],
      },
      coverage: {
        supported_values: ['not_assessed', 'prediction_review_only', 'exhaustive'] as const,
        exhaustive_span_annotations: true, exhaustive_relations: true,
      },
    },
  }
}

function makeSet(predictions: ReviewablePrediction[]): AnnotationSetRecord {
  return {
    schema_version: '1.0',
    annotation_set_uuid: 'set-uuid',
    evaluation_run_uuid: 'run-uuid',
    transcript_hash: 'a'.repeat(64),
    transcript_matches_current: true,
    framework_identifier: 'apex-spikes-afce',
    framework_version: '1.0',
    annotation_policy: makePolicy(),
    guideline_identifier: 'test-guideline',
    guideline_version: '1.0',
    reviewer_reference: 'reviewer_123',
    status: 'draft',
    locked: false,
    revision: 3,
    eligible_predictions: predictions,
    decision_revisions: [],
    effective_decisions: [],
    transitions: [],
    progress: {
      total: predictions.length,
      confirmed: 0,
      corrected: 0,
      rejected: 0,
      insufficient_evidence: 0,
      unreviewed: predictions.length,
    },
    resolved_projection: {
      projection_version: '1.0',
      spans: [],
      turn_labels: [],
      relations: [],
      dimension_ratings: [],
      global_metrics: [],
      findings: [],
      limitations: [],
    },
    created_at: '2026-09-02T00:00:00Z',
    updated_at: '2026-09-02T00:00:00Z',
  }
}

describe('AnnotationSetWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedSave.mockImplementation(async () => makeSet([spanPrediction]))
    mockedDownload.mockResolvedValue(undefined)
    mockedCreateHuman.mockImplementation(async () => makeAuthoringSet())
    mockedCoverage.mockImplementation(async () => makeAuthoringSet())
  })

  it('saves confirm and typed label decisions without exposing span edits', async () => {
    const onChange = vi.fn()
    render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={makeSet([spanPrediction])}
        onChange={onChange}
      />
    )

    expect(screen.getByText('0 / 1 (0%)')).toBeInTheDocument()
    expect(screen.getByText(/span boundaries cannot be changed/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/start offset|end offset|corrected text/i)).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Reviewer note'), { target: { value: 'Verified.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm prediction' }))
    await waitFor(() => expect(mockedSave).toHaveBeenCalledWith('set-uuid', 'span-1', {
      expected_set_revision: 3,
      expected_decision_revision: null,
      decision: 'confirmed',
      correction: null,
      reviewer_note: 'Verified.',
    }))

    fireEvent.change(screen.getByLabelText('Corrected dimension'), { target: { value: 'judgment' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save label correction' }))
    await waitFor(() => expect(mockedSave).toHaveBeenLastCalledWith('set-uuid', 'span-1', expect.objectContaining({
      decision: 'corrected',
      correction: {
        correction_type: 'span_annotation',
        corrected_label: 'empathic_opportunity',
        corrected_dimension: 'judgment',
        corrected_start_char: null,
        corrected_end_char: null,
        corrected_text: null,
      },
    })))
  })

  it('supports typed rating, evidence, and insufficient-evidence decisions', async () => {
    render(
      <AnnotationSetWorkspace
        run={makeRun([ratingPrediction])}
        annotationSet={makeSet([ratingPrediction])}
        onChange={vi.fn()}
      />
    )

    fireEvent.change(screen.getByLabelText('Corrected score'), { target: { value: '3' } })
    fireEvent.click(screen.getByLabelText('Turn 2'))
    fireEvent.click(screen.getByRole('button', { name: 'Save rating correction' }))
    await waitFor(() => expect(mockedSave).toHaveBeenCalledWith('set-uuid', 'rating-1', expect.objectContaining({
      decision: 'corrected',
      correction: {
        correction_type: 'dimension_rating',
        corrected_score: 3,
        corrected_score_status: 'available',
        corrected_assessability: 'text_assessable',
        corrected_evidence_turns: [1, 2],
      },
    })))

    fireEvent.click(screen.getByRole('button', { name: 'Mark insufficient evidence' }))
    await waitFor(() => expect(mockedSave).toHaveBeenLastCalledWith('set-uuid', 'rating-1', expect.objectContaining({
      decision: 'insufficient_evidence',
      correction: expect.objectContaining({
        corrected_score: null,
        corrected_score_status: 'insufficient_evidence',
      }),
    })))
  })

  it('navigates the queue by keyboard and capability-gates relation controls', () => {
    render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction, relationPrediction])}
        annotationSet={makeSet([spanPrediction, relationPrediction])}
        onChange={vi.fn()}
      />
    )

    const queue = screen.getByRole('region', { name: 'Prediction review queue' })
    queue.focus()
    fireEvent.keyDown(queue, { key: 'ArrowRight' })
    expect(screen.getByText('Item 2 of 2')).toBeInTheDocument()
    expect(screen.getByText(/responds_to: span-1 → span-2/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm prediction' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject prediction' })).toBeInTheDocument()
    expect(screen.queryByText(/typed label correction|typed rating correction/i)).not.toBeInTheDocument()
  })

  it('surfaces revision conflicts and refreshes the annotation set', async () => {
    const latest = { ...makeSet([spanPrediction]), revision: 4 }
    mockedSave.mockRejectedValue({
      response: {
        data: {
          message: {
            category: 'revision_conflict',
            message: 'The annotation set changed.',
            current_set_revision: 4,
          },
        },
      },
    })
    mockedFetchSet.mockResolvedValue(latest)
    const onChange = vi.fn()
    render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={makeSet([spanPrediction])}
        onChange={onChange}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Confirm prediction' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/another review change exists/i)
    fireEvent.click(screen.getByRole('button', { name: 'Refresh newer review data' }))
    await waitFor(() => expect(mockedFetchSet).toHaveBeenCalledWith('set-uuid'))
    expect(onChange).toHaveBeenCalledWith(latest)
  })

  it('warns when the current transcript differs and reviews the immutable snapshot', () => {
    const annotationSet = { ...makeSet([spanPrediction]), transcript_matches_current: false }
    render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={annotationSet}
        onChange={vi.fn()}
      />
    )

    expect(screen.getByRole('alert')).toHaveTextContent(/immutable saved snapshot/i)
    expect(
      screen.getByText(
        (_content, element) =>
          element?.tagName === 'P' && element.textContent === 'That sounds difficult.'
      )
    ).toBeInTheDocument()
  })

  it('requires complete coverage before completing and locks the returned set', async () => {
    const incomplete = makeSet([spanPrediction])
    const locked = {
      ...incomplete,
      status: 'complete' as const,
      locked: true,
      revision: 4,
      progress: { ...incomplete.progress, confirmed: 1, unreviewed: 0 },
    }
    mockedComplete.mockResolvedValue(locked)
    const onChange = vi.fn()
    const { rerender } = render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={incomplete}
        onChange={onChange}
      />
    )

    expect(screen.getByRole('button', { name: 'Complete and lock review' })).toBeDisabled()
    expect(screen.getByText(/review all 1 remaining predictions/i)).toBeInTheDocument()

    const ready = {
      ...incomplete,
      status: 'in_review' as const,
      progress: { ...incomplete.progress, confirmed: 1, unreviewed: 0 },
    }
    rerender(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={ready}
        onChange={onChange}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Complete and lock review' }))
    await waitFor(() => expect(mockedComplete).toHaveBeenCalledWith('set-uuid', 3))
    expect(onChange).toHaveBeenCalledWith(locked)
  })

  it('disables review controls when locked and requires an audited reopen reason', async () => {
    const base = makeSet([spanPrediction])
    const locked = {
      ...base,
      status: 'complete' as const,
      locked: true,
      revision: 4,
      progress: { ...base.progress, confirmed: 1, unreviewed: 0 },
    }
    const reopened = { ...locked, status: 'in_review' as const, locked: false, revision: 5 }
    mockedReopen.mockResolvedValue(reopened)
    const onChange = vi.fn()
    render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={locked}
        onChange={onChange}
      />
    )

    expect(screen.getByRole('button', { name: 'Confirm prediction' })).toBeDisabled()
    expect(screen.getByText(/complete and locked/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reopen locked set' }))
    const submit = screen.getByRole('button', { name: 'Record reason and reopen' })
    expect(submit).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Reopen reason'), {
      target: { value: 'Documented expert second pass.' },
    })
    fireEvent.click(submit)
    await waitFor(() => expect(mockedReopen).toHaveBeenCalledWith(
      'set-uuid',
      4,
      'Documented expert second pass.'
    ))
    expect(onChange).toHaveBeenCalledWith(reopened)
  })

  it('offers all sanitized annotation export profiles without transcript text', async () => {
    render(
      <AnnotationSetWorkspace
        run={makeRun([spanPrediction])}
        annotationSet={makeSet([spanPrediction])}
        onChange={vi.fn()}
      />
    )

    for (const [label, profile] of [
      ['Full review JSON', 'full_review'],
      ['Resolved projection JSON', 'resolved_projection'],
      ['Audit history JSON', 'audit_history'],
    ] as const) {
      fireEvent.click(screen.getByRole('button', { name: label }))
      await waitFor(() => expect(mockedDownload).toHaveBeenCalledWith('set-uuid', profile))
    }
    expect(screen.getByText(/transcript text is excluded by default/i)).toBeInTheDocument()
  })

  it('authors selected text explicitly, supports Escape cancellation, and declares coverage', async () => {
    const annotationSet = makeAuthoringSet()
    const onChange = vi.fn()
    render(<AnnotationSetWorkspace run={makeRun([spanPrediction])} annotationSet={annotationSet} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Add annotation' }))
    const paragraph = document.querySelector<HTMLElement>('[data-turn-text="1"]')!
    const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT)
    let selectedNode: Text | null = null
    while (walker.nextNode()) {
      if (walker.currentNode.textContent?.includes('difficult')) selectedNode = walker.currentNode as Text
    }
    expect(selectedNode).not.toBeNull()
    const range = document.createRange()
    range.setStart(selectedNode!, 0)
    range.setEnd(selectedNode!, 9)
    const selection = window.getSelection()!
    selection.removeAllRanges(); selection.addRange(range)
    fireEvent.mouseUp(paragraph)
    expect(screen.getByRole('region', { name: 'Annotation composer' })).toHaveTextContent('difficult')

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('region', { name: 'Annotation composer' })).not.toBeInTheDocument()

    selection.removeAllRanges(); selection.addRange(range)
    fireEvent.mouseUp(paragraph)
    fireEvent.change(screen.getByLabelText('Annotation type'), { target: { value: 'empathic_response' } })
    fireEvent.click(screen.getByRole('button', { name: 'Annotate selected text' }))
    await waitFor(() => expect(mockedCreateHuman).toHaveBeenCalledWith('set-uuid', expect.objectContaining({
      expected_set_revision: 3,
      selection: expect.objectContaining({ start_offset: 12, end_offset: 21, selected_text: 'difficult' }),
      label: 'empathic_response',
    })))

    fireEvent.change(screen.getByLabelText('Annotation coverage'), { target: { value: 'prediction_review_only' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save coverage' }))
    await waitFor(() => expect(mockedCoverage).toHaveBeenCalledWith('set-uuid', 3, 'prediction_review_only'))
  })
})
