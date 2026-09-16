/**
 * API client for the unified plugin registry (Phase 1-2) and its promotion
 * request/review workflow (Phase 4).
 */
import api from '@/api/client'
import type {
  PluginKind,
  PluginRegistration,
  PluginRegistrationListResponse,
  PluginStage,
  PromotionRequest,
  PromotionRequestListResponse,
  PromotionRequestStatus,
} from '@/types/pluginRegistry'

const BASE = '/v1/research'

/** Lists all registered plugins across all three kinds, optionally filtered. */
export async function fetchPluginRegistrations(filters?: {
  pluginKind?: PluginKind
  stage?: PluginStage
}): Promise<PluginRegistrationListResponse> {
  const { data } = await api.get<PluginRegistrationListResponse>(`${BASE}/plugin-registrations`, {
    params: {
      plugin_kind: filters?.pluginKind,
      stage: filters?.stage,
    },
  })
  return data
}

/**
 * Sets (or clears, with `linkedRegistrationId: null`) the informational link
 * between this registration and another same-kind registration representing
 * the same underlying model on a different surface (e.g. a trainee Evaluator
 * wrapper and its Research Evaluator adapter counterpart). Symmetric on the
 * backend -- the other registration's link is updated too. Admin-only.
 */
export async function linkPluginRegistration(
  registrationId: number,
  linkedRegistrationId: number | null
): Promise<PluginRegistration> {
  const { data } = await api.patch<PluginRegistration>(
    `${BASE}/plugin-registrations/${registrationId}/link`,
    { linked_registration_id: linkedRegistrationId }
  )
  return data
}

/** Requests that one plugin registration move to a new lifecycle stage. */
export async function createPromotionRequest(
  registrationId: number,
  requestedStage: PluginStage,
  notes?: string
): Promise<PromotionRequest> {
  const { data } = await api.post<PromotionRequest>(
    `${BASE}/plugin-registrations/${registrationId}/promotion-requests`,
    { requested_stage: requestedStage, notes: notes ?? null }
  )
  return data
}

/** Lists promotion requests for one registration, newest first. */
export async function fetchPromotionRequestsForRegistration(
  registrationId: number,
  status?: PromotionRequestStatus
): Promise<PromotionRequestListResponse> {
  const { data } = await api.get<PromotionRequestListResponse>(
    `${BASE}/plugin-registrations/${registrationId}/promotion-requests`,
    { params: { status } }
  )
  return data
}

/** Lists all promotion requests, newest first -- the review queue when filtered to pending. */
export async function fetchPromotionRequests(
  status?: PromotionRequestStatus
): Promise<PromotionRequestListResponse> {
  const { data } = await api.get<PromotionRequestListResponse>(`${BASE}/promotion-requests`, {
    params: { status },
  })
  return data
}

/** Approves a pending promotion request (admin-only on the backend). */
export async function approvePromotionRequest(
  requestId: number,
  notes?: string
): Promise<PromotionRequest> {
  const { data } = await api.post<PromotionRequest>(
    `${BASE}/promotion-requests/${requestId}/approve`,
    { notes: notes ?? null }
  )
  return data
}

/** Rejects a pending promotion request (admin-only on the backend). */
export async function rejectPromotionRequest(
  requestId: number,
  notes?: string
): Promise<PromotionRequest> {
  const { data } = await api.post<PromotionRequest>(
    `${BASE}/promotion-requests/${requestId}/reject`,
    { notes: notes ?? null }
  )
  return data
}

/** Withdraws a pending promotion request (only the original requester may withdraw it). */
export async function withdrawPromotionRequest(requestId: number): Promise<PromotionRequest> {
  const { data } = await api.post<PromotionRequest>(
    `${BASE}/promotion-requests/${requestId}/withdraw`,
    {}
  )
  return data
}
