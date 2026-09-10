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
  method: 'deterministic_adapter' | 'native_model' | 'native_rule' | 'human_correction' | 'human_annotation'
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
  confirm: boolean
  reject: boolean
  change_label: boolean
  change_dimension: boolean
  adjust_span: boolean
  change_rating: boolean
  mark_insufficient_evidence: boolean
  change_evidence: boolean
  change_assessability: boolean
  add_annotation: boolean
  add_relation: boolean
}

export interface ProjectionAnnotationCapabilities {
  span_annotation: AnnotationOperationCapabilities
  turn_label: AnnotationOperationCapabilities
  relation: AnnotationOperationCapabilities
  dimension_rating: AnnotationOperationCapabilities
  finding: AnnotationOperationCapabilities
}

export interface ResearchCapabilities {
  outputs: OutputCapabilities
  annotation_operations: AnnotationOperationCapabilities
  annotation_by_projection: ProjectionAnnotationCapabilities
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

export type ReviewProjectionType =
  | 'span_annotation'
  | 'turn_label'
  | 'relation'
  | 'dimension_rating'
  | 'finding'

export type ReviewableProjection =
  | SpanAnnotation
  | TurnLabel
  | ProjectedRelation
  | DimensionRating
  | ResearchFinding

export type AnnotationSetStatus = 'draft' | 'in_review' | 'complete'
export type ReviewDecision =
  | 'confirmed'
  | 'rejected'
  | 'corrected'
  | 'insufficient_evidence'

export interface LabelPolicy {
  projection_type: 'span_annotation' | 'turn_label'
  allowed_labels: string[]
  allowed_dimensions: string[]
  allow_null_dimension: boolean
}

export interface RatingScalePolicy {
  dimension_identifier: string
  allowed_scores: number[]
  allowed_assessability: Array<
    'text_assessable' | 'partially_assessable' | 'not_assessable'
  >
  allow_assessability_correction: boolean
}

export interface AnnotationPolicyDescriptor {
  policy_identifier: string
  policy_version: string
  guideline_identifier: string
  guideline_version: string
  guideline_validation_status:
    | 'engineering_unvalidated'
    | 'experimental_unvalidated'
    | 'approved'
  framework_identifier: string
  supported_envelope_schema_versions: string[]
  supported_adapter_versions: string[]
  operations: ProjectionAnnotationCapabilities
  label_policies: LabelPolicy[]
  rating_scales: RatingScalePolicy[]
  span_authoring?: SpanAuthoringPolicy
  relation_types?: RelationTypePolicy[]
  coverage?: CoveragePolicy
}

export interface SpanAttributeValue { identifier: string; value: string }
export interface SpanAttributePolicy {
  identifier: string
  display_name: string
  allowed_values: string[]
  allowed_for_labels: string[]
  required_for_labels: string[]
}
export interface SpanAuthoringPolicy {
  supported: boolean
  offset_convention: 'unicode_code_point_half_open'
  overlap_policy: 'allow' | 'forbid'
  contiguous_only: true
  single_turn_only: true
  exhaustive_annotation_meaningful: boolean
  guideline_help_text: string
  attribute_policies: SpanAttributePolicy[]
}
export interface RelationTypePolicy {
  relation_type: string
  allowed_source_labels: string[]
  allowed_target_labels: string[]
  allow_self_relation: boolean
}
export type CoverageLevel = 'not_assessed' | 'prediction_review_only' | 'exhaustive' | 'fixed_inventory_complete'
export interface CoveragePolicy {
  supported_values: CoverageLevel[]
  exhaustive_span_annotations: boolean
  exhaustive_relations: boolean
}

export interface ReviewablePrediction {
  prediction_id: string
  projection_type: ReviewProjectionType
  original_prediction: ReviewableProjection
  allowed_operations: AnnotationOperationCapabilities
}

export interface SpanCorrection {
  correction_type: 'span_annotation'
  corrected_label: string
  corrected_dimension: string | null
  corrected_start_char?: number | null
  corrected_end_char?: number | null
  corrected_text?: string | null
  transcript_hash?: string | null
  corrected_turn_number?: number | null
  corrected_speaker?: 'clinician' | 'patient' | null
  corrected_attributes?: SpanAttributeValue[]
}

export interface TurnLabelCorrection {
  correction_type: 'turn_label'
  corrected_label: string
  corrected_dimension: string | null
}

export interface DimensionRatingCorrection {
  correction_type: 'dimension_rating'
  corrected_score: number | null
  corrected_score_status: 'available' | 'insufficient_evidence' | 'not_assessable'
  corrected_assessability:
    | 'text_assessable'
    | 'partially_assessable'
    | 'not_assessable'
  corrected_evidence_turns: number[]
}

export type TypedCorrection =
  | SpanCorrection
  | TurnLabelCorrection
  | DimensionRatingCorrection

export interface ResearchEvaluationRunSaveRequest {
  evaluator_identifier: string
  allow_live: boolean
  provider?: 'openai' | 'gemini'
  model_identifier?: string
}

export interface EvaluationRunRecord {
  run_uuid: string
  source_session_id: number
  envelope: ResearchEvaluationEnvelope
  transcript_snapshot: ResearchTranscriptTurn[]
  creator_reference: string
  created_at: string
  transcript_matches_current: boolean
  current_transcript_hash?: string | null
  annotation_policy: AnnotationPolicyDescriptor
}

export interface EvaluationRunSummary {
  run_uuid: string
  item1_run_id: string
  evaluator_identifier: string
  evaluator_version: string
  framework_identifier: string
  framework_version: string
  transcript_hash: string
  execution_mode: 'offline' | 'live'
  status: ResearchStatus
  created_at: string
  transcript_matches_current: boolean
}

export interface AnnotationSetCreateRequest {
  guideline_identifier: string
  guideline_version: string
  set_note?: string
}

export interface ReviewDecisionWriteRequest {
  expected_set_revision: number
  expected_decision_revision?: number | null
  decision: ReviewDecision
  correction?: TypedCorrection | null
  reviewer_note?: string | null
}

export interface DecisionRevisionRecord {
  decision_uuid: string
  prediction_id: string
  projection_type: ReviewProjectionType
  revision_number: number
  decision: ReviewDecision
  correction?: TypedCorrection | null
  reviewer_note?: string | null
  reviewer_reference: string
  supersedes_uuid?: string | null
  created_at: string
}

export interface AnnotationTransitionRecord {
  transition_uuid: string
  from_status: AnnotationSetStatus
  to_status: AnnotationSetStatus
  set_revision: number
  reason?: string | null
  actor_reference: string
  created_at: string
}

export interface ReviewProgress {
  total: number
  confirmed: number
  corrected: number
  rejected: number
  insufficient_evidence: number
  unreviewed: number
}

export interface AnnotationSetRecord {
  schema_version: '1.0' | '1.1'
  annotation_set_uuid: string
  evaluation_run_uuid: string
  transcript_hash: string
  transcript_matches_current: boolean
  framework_identifier: string
  framework_version: string
  annotation_policy: AnnotationPolicyDescriptor
  guideline_identifier: string
  guideline_version: string
  reviewer_reference: string
  status: AnnotationSetStatus
  locked: boolean
  revision: number
  eligible_predictions: ReviewablePrediction[]
  decision_revisions: DecisionRevisionRecord[]
  effective_decisions: DecisionRevisionRecord[]
  transitions: AnnotationTransitionRecord[]
  progress: ReviewProgress
  resolved_projection: ResearchProjection
  human_annotation_revisions?: HumanAnnotationRevisionRecord[]
  active_human_annotations?: HumanAnnotationRevisionRecord[]
  authored_relation_revisions?: AuthoredRelationRevisionRecord[]
  active_authored_relations?: AuthoredRelationRevisionRecord[]
  coverage_revisions?: CoverageDeclarationRecord[]
  coverage?: CoverageDeclarationRecord | null
  coverage_level?: CoverageLevel
  reference_projection?: { projection: ResearchProjection; coverage: CoverageLevel } | null
  validation_eligibility?: ValidationEligibilityRecord | null
  set_note?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
  locked_at?: string | null
  reopened_at?: string | null
}

export interface CanonicalSpanSelection {
  transcript_hash: string
  start_turn_number: number
  end_turn_number: number
  speaker: 'clinician' | 'patient'
  start_offset: number
  end_offset: number
  selected_text: string
}
export interface HumanAnnotationCreateRequest {
  expected_set_revision: number
  selection: CanonicalSpanSelection
  label: string
  dimension?: string | null
  attributes: SpanAttributeValue[]
  reviewer_note?: string | null
}
export interface HumanAnnotationRevisionRecord {
  revision_uuid: string
  annotation_id: string
  revision_number: number
  set_revision: number
  operation: 'create' | 'relabel' | 'edit_attributes' | 'adjust_span' | 'retire' | 'restore'
  status: 'active' | 'retired'
  origin: 'human_added'
  transcript_hash: string
  turn_number: number
  speaker: 'clinician' | 'patient'
  start_offset: number
  end_offset: number
  selected_text: string
  label: string
  dimension?: string | null
  attributes: SpanAttributeValue[]
  reviewer_reference: string
  guideline_identifier: string
  guideline_version: string
  created_at: string
}
export interface AuthoredRelationRevisionRecord {
  revision_uuid: string
  relation_id: string
  revision_number: number
  set_revision: number
  operation: 'create' | 'correct' | 'retire' | 'restore'
  status: 'active' | 'retired'
  source_annotation_id: string
  target_annotation_id: string
  relation_type: string
  created_at: string
}
export interface CoverageDeclarationRecord {
  revision_uuid: string
  coverage_revision: number
  set_revision: number
  coverage: CoverageLevel
  reviewer_reference: string
  guideline_identifier: string
  guideline_version: string
  created_at: string
}
export interface MetricEligibilityRecord {
  metric_identifier: string
  eligible: boolean
  reason_code: string
  explanation: string
  required_coverage: CoverageLevel
  current_coverage: CoverageLevel
}
export interface ValidationEligibilityRecord {
  eligible_metric_identifiers: string[]
  ineligible_metric_identifiers: string[]
  metrics: MetricEligibilityRecord[]
}

export interface ResearchRevisionConflict {
  category: 'revision_conflict'
  message: string
  current_set_revision?: number
  current_decision_revision?: number
}

export type AnnotationExportProfile =
  | 'full_review'
  | 'resolved_projection'
  | 'audit_history'
