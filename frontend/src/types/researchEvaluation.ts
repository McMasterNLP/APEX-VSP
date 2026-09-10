/** Strict wire types for the versioned research-evaluation contract. */

export type JsonPrimitive = string | number | boolean | null
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue }

export type ResearchStatus = 'success' | 'failed' | 'refused'
export type ResearchExportProfile = 'full' | 'framework_native' | 'projection' | 'tabular'

export interface SourceReference {
  native_result_type: 'apex_feedback' | 'ace_ct_inspired' | 'versioned_extension'
  native_identifier: string
  native_path: string
  adapter_version: string
}

export interface ProjectionProvenance {
  method: 'deterministic_adapter' | 'native_model' | 'native_rule'
  provider?: string | null
  model_identifier?: string | null
}

export interface SpanAnnotation {
  prediction_id: string
  framework_identifier: string
  projection_type: 'span_annotation'
  turn_number: number
  start_offset: number
  end_offset: number
  quoted_text: string
  label: string
  dimension?: string | null
  subtype?: string | null
  confidence?: number | null
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface TurnLabel {
  prediction_id: string
  framework_identifier: string
  projection_type: 'turn_label'
  turn_number: number
  label: string
  dimension?: string | null
  subtype?: string | null
  confidence?: number | null
  evidence_text?: string | null
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface ProjectedRelation {
  relation_id: string
  framework_identifier: string
  projection_type: 'relation'
  source_annotation_id: string
  target_annotation_id: string
  relation_type: string
  confidence?: number | null
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface DimensionRating {
  rating_id: string
  framework_identifier: string
  projection_type: 'dimension_rating'
  dimension_identifier: string
  domain_identifier?: string | null
  score?: number | null
  scale_minimum: number
  scale_maximum: number
  score_status: 'available' | 'insufficient_evidence' | 'not_assessable'
  assessability: 'text_assessable' | 'partially_assessable' | 'not_assessable'
  confidence?: number | null
  evidence_turns: number[]
  rationale: string
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface GlobalMetric {
  metric_id: string
  framework_identifier: string
  projection_type: 'global_metric'
  metric_name: string
  value?: number | null
  value_status: 'available' | 'unavailable'
  unit_or_scale: string
  source_label: string
  comparability_statement: string
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface ResearchFinding {
  finding_id: string
  framework_identifier: string
  projection_type: 'finding'
  finding_type:
    | 'strength'
    | 'improvement'
    | 'missed_opportunity'
    | 'warning'
    | 'general_observation'
  description: string
  evidence_turns: number[]
  confidence?: number | null
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface ResearchLimitation {
  limitation_id: string
  framework_identifier: string
  projection_type: 'limitation'
  code: string
  description: string
  affected_outputs: string[]
  severity_or_scope: 'output' | 'framework' | 'run'
  source_label: string
  source_reference: SourceReference
  provenance?: ProjectionProvenance | null
}

export interface ResearchProjection {
  projection_version: '1.0'
  spans: SpanAnnotation[]
  turn_labels: TurnLabel[]
  relations: ProjectedRelation[]
  dimension_ratings: DimensionRating[]
  global_metrics: GlobalMetric[]
  findings: ResearchFinding[]
  limitations: ResearchLimitation[]
}

export interface OutputCapabilities {
  character_spans: boolean
  turn_labels: boolean
  relations: boolean
  dimension_ratings: boolean
  global_metrics: boolean
  narrative_findings: boolean
  evidence_turns: boolean
  framework_native_view: boolean
  live_execution: boolean
}

export interface AnnotationOperationCapabilities {
  confirm: false
  reject: false
  change_label: false
  adjust_span: false
  change_rating: false
  change_evidence: false
  add_annotation: false
  add_relation: false
}

export interface ResearchCapabilities {
  outputs: OutputCapabilities
  annotation_operations: AnnotationOperationCapabilities
}

export interface ApexNativeSpan {
  span_type: 'eo' | 'elicitation' | 'response'
  turn_number: number
  start_char: number
  end_char: number
  text: string
  confidence?: number | null
  provenance?: 'rule' | 'ml' | 'llm' | null
  dimension?: string | null
  explicit_or_implicit?: 'explicit' | 'implicit' | null
  subtype?: string | null
}

export interface ApexNativeRelation {
  source_span_id: string
  target_span_id: string
  relation_type: 'responds_to' | 'elicits'
  confidence?: number | null
}

export interface ApexFeedbackNativeResult {
  native_type: 'apex_feedback'
  native_version: '1.0'
  evaluator_family: 'baseline' | 'hybrid_v1' | 'hybrid_v2'
  framework_identifier: 'apex-spikes-afce'
  framework_statement: string
  scores: {
    empathy_score: number
    communication_score: number
    spikes_completion_score: number
    overall_score: number
  }
  eo_counts_by_dimension: Record<string, { explicit: number; implicit: number }>
  elicitation_counts_by_type: Record<string, Record<string, number>>
  response_counts_by_type: Record<string, number>
  linkage_stats?: {
    total_eos: number
    addressed_count: number
    missed_count: number
    addressed_rate: number
    missed_rate: number
  } | null
  missed_opportunities_by_dimension?: Record<string, number> | null
  eo_to_elicitation_links: ApexNativeRelation[]
  eo_to_response_links: ApexNativeRelation[]
  missed_opportunities: Array<{
    span_id: string
    turn_number: number
    dimension?: string | null
    explicit_or_implicit?: 'explicit' | 'implicit' | null
    text: string
  }>
  eo_spans: ApexNativeSpan[]
  elicitation_spans: ApexNativeSpan[]
  response_spans: ApexNativeSpan[]
  spikes_coverage: { covered: string[]; percent: number }
  spikes_timestamps?: Record<string, JsonValue> | null
  spikes_strategies?: Record<string, JsonValue> | null
  question_breakdown: { open: number; closed: number; eliciting: number; ratio_open: number }
  bias_probe_info?: Record<string, JsonValue> | null
  evaluator_metadata: Record<string, JsonValue>
  latency_ms_avg: number
  strengths?: string | null
  areas_for_improvement?: string | null
  detailed_feedback?: string | null
  timeline_events: Array<{
    turn_number: number
    type: 'eo' | 'response' | 'missed' | 'spikes'
    label: string
  }>
  suggested_responses: Array<{ turn_number: number; patient_text: string; suggestion: string }>
}

export type ACECTDomain = 'respond' | 'listen' | 'speak' | 'general'
export type ACECTAssessability =
  | 'text_assessable'
  | 'partially_assessable'
  | 'not_assessable'

export interface ACECTDimensionResult {
  dimension_id: string
  domain: ACECTDomain
  score?: number | null
  insufficient_evidence: boolean
  assessability: ACECTAssessability
  confidence: number
  evidence_turn_numbers: number[]
  reasoning: string
  improvement_recommendation: string
  modality_limitation_notes: string[]
}

export interface ACECTDomainScore {
  domain: ACECTDomain
  mean_score?: number | null
  scored_dimension_count: number
  insufficient_evidence_count: number
}

export interface ACECTFrameworkResults {
  framework: 'ACE-CT-inspired'
  implementation_type: 'experimental_transcript_rubric'
  validation_status: 'experimental_unvalidated'
  publication_reproduction: false
  rubric_version: string
  approval_status: 'pending_expert_review' | 'approved_experimental'
  dimension_results: ACECTDimensionResult[]
  domain_scores: ACECTDomainScore[]
  assessability_counts: {
    text_assessable: number
    partially_assessable: number
    not_assessable: number
    scored: number
    insufficient_evidence: number
  }
  score_sources: Record<string, string>
  limitations: {
    transcript_only: true
    missing_modalities: Array<'audio' | 'video' | 'timing' | 'overlap'>
    notes: string[]
    official_model_reproduction: false
  }
}

export interface ACECTNativeResearchResult {
  native_type: 'ace_ct_inspired'
  native_version: '1.0'
  framework_results: ACECTFrameworkResults
  compatibility_projection: {
    scores: {
      empathy_score?: number | null
      communication_score?: number | null
      spikes_completion_score?: number | null
      overall_score?: number | null
    }
    score_sources: Record<string, string>
    warnings: string[]
  }
  experimental: true
  official: false
  publication_model_reproduction: false
}

export interface VersionedExtensionNativeResult {
  native_type: 'versioned_extension'
  native_version: '1.0'
  extension_identifier: string
  extension_schema_version: string
  provider_output_validated: true
  fields: Array<{ name: string; value: JsonPrimitive | JsonPrimitive[] }>
}

export type FrameworkNativeResult =
  | ApexFeedbackNativeResult
  | ACECTNativeResearchResult
  | VersionedExtensionNativeResult

export interface ResearchTranscriptIdentity {
  canonical_transcript_hash: string
  transcript_projection_version: 'apex-canonical-v1'
  turn_count: number
  role_convention: 'user=clinician;assistant=patient'
  raw_transcript_included: boolean
}

export interface ResearchTranscriptTurn {
  turn_number: number
  role: 'clinician' | 'patient'
  source_role: 'user' | 'assistant'
  text: string
}

export interface ResearchRunMetadata {
  run_id: string
  timestamp: string
  runtime_ms: number
  execution_mode: 'offline' | 'live'
  completion_status: ResearchStatus
  failure_category?: string | null
}

export interface ResearchEvaluatorMetadata {
  identifier: string
  display_name: string
  version: string
  evaluator_type: 'rule_based' | 'hybrid_llm' | 'experimental_rubric_llm'
  provider?: string | null
  model_identifier?: string | null
}

export interface ResearchFrameworkMetadata {
  identifier: string
  display_name: string
  version: string
  rubric_version?: string | null
  validation_status: string
  framework_statement: string
}

export interface ResearchAdapterMetadata {
  identifier: string
  version: string
  supported_native_type: 'apex_feedback' | 'ace_ct_inspired' | 'versioned_extension'
}

export interface ResearchEvaluationEnvelope {
  schema_version: '1.0'
  run: ResearchRunMetadata
  transcript: ResearchTranscriptIdentity
  evaluator: ResearchEvaluatorMetadata
  framework: ResearchFrameworkMetadata
  adapter: ResearchAdapterMetadata
  capabilities: ResearchCapabilities
  framework_result?: FrameworkNativeResult | null
  projection: ResearchProjection
  warnings: string[]
  status: ResearchStatus
  error?: {
    category:
      | 'evaluation_failed'
      | 'unexpected_error'
      | 'live_execution_refused'
      | 'invalid_native_result'
      | 'invalid_projection'
      | 'invalid_adapter_result'
      | 'evaluator_unavailable'
    message: string
  } | null
  provenance: {
    generated_at: string
    runtime_ms: number
    live_execution: boolean
    transcript_hash_algorithm: 'sha256'
    identifier_hash_algorithm: 'sha256-truncated-160'
  }
}

export interface ResearchEvaluationResponse {
  schema_version: '1.0'
  transcript: ResearchTranscriptIdentity
  transcript_turns: ResearchTranscriptTurn[]
  results: ResearchEvaluationEnvelope[]
}

export interface ResearchEvaluatorDescriptor {
  identifier: string
  display_name: string
  version: string
  framework: ResearchFrameworkMetadata
  adapter: ResearchAdapterMetadata
  capabilities: ResearchCapabilities
  requires_live_execution: boolean
  supported_providers: Array<'openai' | 'gemini'>
  default_selected: boolean
  availability: 'available' | 'server_live_disabled' | 'experimental_disabled'
  warnings: string[]
}

export interface ResearchEvaluatorDescriptorsResponse {
  schema_version: '1.0'
  evaluators: ResearchEvaluatorDescriptor[]
}

export interface ResearchEvaluationRunRequest {
  evaluator_identifiers: string[]
  allow_live: boolean
  provider?: 'openai' | 'gemini'
  model_identifier?: string
}
