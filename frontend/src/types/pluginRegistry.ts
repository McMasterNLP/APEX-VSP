/**
 * Types for the unified plugin registry (Phase 1-2) and its promotion request/review
 * workflow (Phase 4). Mirrors backend/src/domain/models/plugin_registration.py and
 * plugin_promotion_request.py.
 */
import type { JsonValue } from './researchEvaluation'

export type PluginKind = 'evaluator' | 'patient_model' | 'metrics'
export type RegistrationKind = 'variant' | 'native'
export type PluginStage =
  | 'draft'
  | 'experimental'
  | 'under_review'
  | 'promoted'
  | 'deprecated'
  | 'retired'

export interface PluginRegistration {
  id: number
  plugin_kind: PluginKind
  registration_kind: RegistrationKind
  stage: PluginStage
  identifier: string
  display_name: string
  version: string
  module_path: string | null
  config: JsonValue | null
  metadata: JsonValue | null
  /**
   * Optional pointer to another registration of the same plugin_kind that
   * represents the same underlying model on a different surface (e.g. a
   * trainee-facing Evaluator wrapper linked to its Research Evaluator
   * adapter counterpart). Purely informational -- set/cleared symmetrically
   * via the /link endpoint; never affects stage or execution.
   */
  linked_registration_id: number | null
  created_at: string
  updated_at: string
  promoted_at: string | null
  deprecated_at: string | null
}

export interface PluginRegistrationListResponse {
  registrations: PluginRegistration[]
}

export type PromotionRequestStatus = 'pending' | 'approved' | 'rejected' | 'withdrawn'

export interface PromotionRequest {
  id: number
  registration_id: number
  requested_stage: PluginStage
  status: PromotionRequestStatus
  requested_by_user_id: number | null
  request_notes: string | null
  reviewed_by_user_id: number | null
  review_notes: string | null
  created_at: string
  updated_at: string
  reviewed_at: string | null
}

export interface PromotionRequestListResponse {
  requests: PromotionRequest[]
}

/** Stage progression used to suggest the "next" stage in the request-promotion UI. */
export const STAGE_ORDER: PluginStage[] = [
  'draft',
  'experimental',
  'under_review',
  'promoted',
  'deprecated',
  'retired',
]

export function nextStage(current: PluginStage): PluginStage | null {
  const idx = STAGE_ORDER.indexOf(current)
  if (idx === -1 || idx === STAGE_ORDER.length - 1) return null
  return STAGE_ORDER[idx + 1]
}

/**
 * Soft-enforcement helper: true when a registration's stage means it hasn't
 * been reviewed/approved yet. This never blocks selection anywhere in the
 * app today -- the registry stage is descriptive, not enforced -- but the
 * UI uses this to show a "not yet promoted" warning wherever a not-yet-
 * promoted plugin is surfaced, so the distinction is visible rather than
 * silent.
 */
export function isNotYetPromoted(stage: PluginStage): boolean {
  return stage !== 'promoted' && stage !== 'deprecated'
}
