import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type {
  ApexFeedbackNativeResult,
  ResearchEvaluationEnvelope,
  ResearchTranscriptTurn,
} from '@/types/researchEvaluation'
import { ResearchResultView } from './ResearchResultView'

const turns: ResearchTranscriptTurn[] = [
  { turn_number: 1, role: 'clinician', source_role: 'user', text: 'How are you feeling?' },
  { turn_number: 2, role: 'patient', source_role: 'assistant', text: 'I feel very worried.' },
  { turn_number: 3, role: 'clinician', source_role: 'user', text: 'I understand your worry.' },
]

const sourceReference = {
  native_result_type: 'apex_feedback' as const,
  native_identifier: 'baseline',
  native_path: '$.eo_spans[0]',
  adapter_version: '1.0',
}

const nativeResult: ApexFeedbackNativeResult = {
  native_type: 'apex_feedback',
  native_version: '1.0',
  evaluator_family: 'baseline',
  framework_identifier: 'apex-spikes-afce',
  framework_statement: 'AFCE-aligned rule-based operationalization.',
  scores: {
    empathy_score: 80,
    communication_score: 75,
    spikes_completion_score: 50,
    overall_score: 70,
  },
  eo_counts_by_dimension: { Feeling: { explicit: 1, implicit: 0 } },
  elicitation_counts_by_type: { direct: { Feeling: 1 } },
  response_counts_by_type: { understanding: 1 },
  linkage_stats: {
    total_eos: 1,
    addressed_count: 1,
    missed_count: 0,
    addressed_rate: 1,
    missed_rate: 0,
  },
  missed_opportunities_by_dimension: { Feeling: 0 },
  eo_to_elicitation_links: [],
  eo_to_response_links: [],
  missed_opportunities: [],
  eo_spans: [
    {
      span_type: 'eo',
      turn_number: 2,
      start_char: 7,
      end_char: 19,
      text: 'very worried',
      confidence: 0.9,
      provenance: 'rule',
      dimension: 'Feeling',
      explicit_or_implicit: 'explicit',
    },
  ],
  elicitation_spans: [],
  response_spans: [],
  spikes_coverage: { covered: ['perception', 'emotion'], percent: 2 / 6 },
  spikes_timestamps: null,
  spikes_strategies: null,
  question_breakdown: { open: 1, closed: 0, eliciting: 1, ratio_open: 1 },
  bias_probe_info: null,
  evaluator_metadata: { phase: 'baseline_rule_v1' },
  latency_ms_avg: 4.5,
  strengths: 'Acknowledged emotion.',
  areas_for_improvement: 'Invite more detail.',
  detailed_feedback: 'Synthetic test feedback.',
  timeline_events: [{ turn_number: 2, type: 'eo', label: 'Empathy opportunity' }],
  suggested_responses: [],
}

function envelope(
  overrides: Partial<ResearchEvaluationEnvelope> = {}
): ResearchEvaluationEnvelope {
  return {
    schema_version: '1.0',
    run: {
      run_id: 'run-123',
      timestamp: '2026-09-01T12:00:00Z',
      runtime_ms: 4.5,
      execution_mode: 'offline',
      completion_status: 'success',
    },
    transcript: {
      canonical_transcript_hash: 'a'.repeat(64),
      transcript_projection_version: 'apex-canonical-v1',
      turn_count: 3,
      role_convention: 'user=clinician;assistant=patient',
      raw_transcript_included: false,
    },
    evaluator: {
      identifier: 'baseline',
      display_name: 'APEX baseline',
      version: '1.0',
      evaluator_type: 'rule_based',
    },
    framework: {
      identifier: 'apex-spikes-afce',
      display_name: 'APEX SPIKES / AFCE-aligned',
      version: '1.0',
      validation_status: 'engineering_baseline_unvalidated',
      framework_statement: 'AFCE-aligned, not an official framework implementation.',
    },
    adapter: {
      identifier: 'apex.feedback.adapter',
      version: '1.0',
      supported_native_type: 'apex_feedback',
    },
    capabilities: {
      outputs: {
        character_spans: true,
        turn_labels: true,
        relations: true,
        dimension_ratings: true,
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
        adjust_span: false,
        change_rating: false,
        mark_insufficient_evidence: false,
        change_evidence: false,
        change_assessability: false,
        add_annotation: false,
        add_relation: false,
      },
      annotation_by_projection: {
        span_annotation: {
          confirm: true, reject: true, change_label: true, change_dimension: true,
          adjust_span: false, change_rating: false, mark_insufficient_evidence: false,
          change_evidence: false, change_assessability: false,
          add_annotation: false, add_relation: false,
        },
        turn_label: {
          confirm: true, reject: true, change_label: true, change_dimension: true,
          adjust_span: false, change_rating: false, mark_insufficient_evidence: false,
          change_evidence: false, change_assessability: false,
          add_annotation: false, add_relation: false,
        },
        relation: {
          confirm: true, reject: true, change_label: false, change_dimension: false,
          adjust_span: false, change_rating: false, mark_insufficient_evidence: false,
          change_evidence: false, change_assessability: false,
          add_annotation: false, add_relation: false,
        },
        dimension_rating: {
          confirm: false, reject: false, change_label: false, change_dimension: false,
          adjust_span: false, change_rating: false, mark_insufficient_evidence: false,
          change_evidence: false, change_assessability: false,
          add_annotation: false, add_relation: false,
        },
        finding: {
          confirm: true, reject: true, change_label: false, change_dimension: false,
          adjust_span: false, change_rating: false, mark_insufficient_evidence: false,
          change_evidence: false, change_assessability: false,
          add_annotation: false, add_relation: false,
        },
      },
    },
    framework_result: nativeResult,
    projection: {
      projection_version: '1.0',
      spans: [
        {
          prediction_id: 'span-feeling',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'span_annotation',
          turn_number: 2,
          start_offset: 7,
          end_offset: 19,
          quoted_text: 'very worried',
          label: 'Feeling',
          subtype: 'explicit',
          confidence: 0.9,
          source_reference: sourceReference,
        },
        {
          prediction_id: 'span-emotion',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'span_annotation',
          turn_number: 2,
          start_offset: 12,
          end_offset: 19,
          quoted_text: 'worried',
          label: 'Emotion',
          confidence: 0.8,
          source_reference: { ...sourceReference, native_path: '$.turn_labels[0]' },
        },
      ],
      turn_labels: [
        {
          prediction_id: 'turn-emotion',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'turn_label',
          turn_number: 3,
          label: 'SPIKES stage',
          subtype: 'emotion',
          confidence: null,
          evidence_text: 'I understand your worry.',
          source_reference: { ...sourceReference, native_path: '$.timeline_events[0]' },
        },
      ],
      relations: [
        {
          relation_id: 'relation-1',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'relation',
          source_annotation_id: 'span-feeling',
          target_annotation_id: 'span-emotion',
          relation_type: 'responds_to',
          confidence: 0.8,
          source_reference: sourceReference,
        },
      ],
      dimension_ratings: [
        {
          rating_id: 'rating-1',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'dimension_rating',
          dimension_identifier: 'empathic response',
          domain_identifier: 'respond',
          score: 4,
          scale_minimum: 1,
          scale_maximum: 5,
          score_status: 'available',
          assessability: 'text_assessable',
          confidence: 0.8,
          evidence_turns: [2],
          rationale: 'The clinician recognized the emotion.',
          source_reference: sourceReference,
        },
      ],
      global_metrics: [
        {
          metric_id: 'metric-1',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'global_metric',
          metric_name: 'overall_score',
          value: 70,
          value_status: 'available',
          unit_or_scale: '0-100',
          source_label: 'APEX baseline native score',
          comparability_statement: 'Only comparable within this evaluator version.',
          source_reference: sourceReference,
        },
      ],
      findings: [
        {
          finding_id: 'finding-1',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'finding',
          finding_type: 'strength',
          description: 'Acknowledged emotion.',
          evidence_turns: [3],
          confidence: null,
          source_reference: sourceReference,
        },
      ],
      limitations: [
        {
          limitation_id: 'limitation-1',
          framework_identifier: 'apex-spikes-afce',
          projection_type: 'limitation',
          code: 'rule_based_baseline',
          description: 'This baseline is an engineering operationalization.',
          affected_outputs: ['spans', 'metrics'],
          severity_or_scope: 'framework',
          source_label: 'APEX adapter declaration',
          source_reference: sourceReference,
        },
      ],
    },
    warnings: ['Synthetic fixture warning.'],
    status: 'success',
    provenance: {
      generated_at: '2026-09-01T12:00:00Z',
      runtime_ms: 4.5,
      live_execution: false,
      transcript_hash_algorithm: 'sha256',
      identifier_hash_algorithm: 'sha256-truncated-160',
    },
    ...overrides,
  }
}

describe('ResearchResultView', () => {
  it('renders capability-driven projections, overlap details, native data, and provenance', async () => {
    const clipboardWrite = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: clipboardWrite },
    })
    render(<ResearchResultView envelope={envelope()} transcriptTurns={turns} />)

    expect(screen.getByRole('heading', { name: 'Annotated transcript' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Relations' })).toBeInTheDocument()
    expect(screen.getByText('2', { selector: 'sup' })).toHaveAccessibleName('2 overlapping annotations')
    fireEvent.click(screen.getByRole('button', { name: /Feeling \(explicit\), Emotion: worried/i }))
    expect(screen.getByText(/Selected annotation: Feeling/i)).toBeInTheDocument()
    expect(screen.getByText('responds to')).toBeInTheDocument()
    expect(screen.getByText('4 / 5')).toBeInTheDocument()
    expect(screen.getByText(/Only comparable within this evaluator version/i)).toBeInTheDocument()
    expect(screen.getByText('Acknowledged emotion.')).toBeInTheDocument()
    expect(screen.getByText(/engineering operationalization/i)).toBeInTheDocument()
    expect(screen.getByText(/SPIKES coverage/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Evidence turn 2' }))
    expect(document.activeElement).toHaveAttribute('data-turn-number', '2')
    fireEvent.click(screen.getByRole('button', { name: /copy full transcript hash/i }))
    expect(clipboardWrite).toHaveBeenCalledWith('a'.repeat(64))
    await waitFor(() => expect(screen.getByRole('button', { name: /copy full transcript hash/i })).toHaveTextContent('Copied'))
    expect(screen.queryByRole('button', { name: /confirm|reject|change label/i })).not.toBeInTheDocument()
  })

  it('ignores malformed spans and safely handles empty annotations', () => {
    const invalid = envelope()
    invalid.projection.spans = [
      {
        ...invalid.projection.spans[0],
        prediction_id: 'bad-span',
        start_offset: 100,
        end_offset: 105,
        quoted_text: '<script>alert(1)</script>',
      },
    ]
    invalid.projection.turn_labels = []
    render(<ResearchResultView envelope={invalid} transcriptTurns={turns} />)

    expect(screen.getByText(/1 invalid span was ignored defensively/i)).toBeInTheDocument()
    expect(screen.queryByText('<script>alert(1)</script>')).not.toBeInTheDocument()
  })

  it('uses declared capabilities instead of evaluator-name checks', () => {
    const result = envelope()
    result.evaluator.identifier = 'completely-new-evaluator'
    result.capabilities.outputs = {
      ...result.capabilities.outputs,
      character_spans: false,
      turn_labels: false,
      relations: false,
      dimension_ratings: false,
      global_metrics: false,
      narrative_findings: false,
      framework_native_view: false,
    }
    render(<ResearchResultView envelope={result} transcriptTurns={turns} />)

    expect(screen.getByRole('heading', { name: 'Provenance' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Limitations' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Annotated transcript' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Global metrics' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Framework-native result' })).not.toBeInTheDocument()
  })

  it('shows failed runs alongside provenance without projection controls', () => {
    const failed = envelope({
      status: 'failed',
      run: {
        ...envelope().run,
        completion_status: 'failed',
        failure_category: 'evaluation_failed',
      },
      framework_result: null,
      error: { category: 'evaluation_failed', message: 'Synthetic evaluator failure.' },
    })
    render(<ResearchResultView envelope={failed} transcriptTurns={turns} />)

    expect(screen.getByText('Status: failed')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Synthetic evaluator failure.')
    expect(screen.getByRole('heading', { name: 'Provenance' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Annotated transcript' })).not.toBeInTheDocument()
  })
})
