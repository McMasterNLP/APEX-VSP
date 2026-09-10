/**
 * Admin dashboard API: aggregates, session review, plugin configuration, and user overview.
 */
import api from '@/api/client'
import type { SessionDetailDTO } from '@/types/session'

/** One point on the per-turn metrics timeline (wire `snake_case`). */
export interface MetricsTimelineDTO {
  turn_number: number
  timestamp: string
  empathy_score: number
  question_type: string
  spikes_stage: string
}

/** Paginated admin session list (each row may include transcript fields). */
export interface AdminSessionListResponse {
  sessions: SessionDetailDTO[]
  total: number
  skip: number
  limit: number
}

/** Short feedback summary block for admin session cards. */
export interface AdminFeedbackSummaryDTO {
  empathy_score: number
  overall_score: number
  strengths?: string | null
  areas_for_improvement?: string | null
}

/** Session detail bundle with optional feedback and timeline. */
export interface AdminSessionDetailResponse {
  session: SessionDetailDTO
  feedback: AdminFeedbackSummaryDTO | null
  metrics_timeline: MetricsTimelineDTO[]
}

/**
 * Overview metrics and chart placeholders for the admin home dashboard.
 */
export interface AdminStats {
  totalUsers: number
  totalCases: number
  activeSessions: number
  averageScore: number
  /** Reserved for a future audit/activity feed; overview uses `fetchAdminSessions` instead. */
  recentActivity: Array<{
    userId: string
    action: string
    timestamp: string
  }>
  /** From `/v1/admin/aggregates` session_stats */
  completedSessions?: number
  totalSessions?: number
  averageDurationSeconds?: number
  /** From user_stats */
  activeUsersLast30Days?: number
  usersByRole?: Record<string, number>
  /** From performance_stats */
  averageEmpathyScore?: number
  averageCommunicationScore?: number
  averageSpikesCompletion?: number
  /** From case_stats */
  casesByCategory?: Record<string, number>
  analyticsData?: {
    /** From `performance_stats.average_score_by_month` on `/v1/admin/aggregates`. */
    averageScoreByMonth: Array<{ month: string; score: number }>
    /** Share of sessions per case title (rate = count / total_sessions). Empty if backend sends no per-case counts. */
    completionRates: Array<{ difficulty: string; rate: number }>
    /** Mapped from case_stats.cases_by_category. */
    commonChallenges: Array<{ challenge: string; frequency: number }>
  }
}

/** Raw `/v1/admin/aggregates` response used by {@link fetchAdminStats}. */
interface AggregatesResponse {
  user_stats: {
    total_users: number
    users_by_role: Record<string, number>
    active_users_last_30_days: number
  }
  session_stats: {
    total_sessions: number
    completed_sessions: number
    active_sessions: number
    average_duration_seconds: number
    sessions_by_case: Record<string, number>
  }
  performance_stats: {
    average_empathy_score: number
    average_communication_score: number
    average_spikes_completion: number
    average_overall_score: number
    average_score_by_month: Array<{ month: string; score: number }>
  }
  case_stats: {
    total_cases: number
    cases_by_category: Record<string, number>
  }
  generated_at?: string
}

/**
 * Derives completion rate rows from per-case session counts.
 *
 * @param sessionsByCase - Map of case title to session count
 * @param totalSessions - Denominator for rates
 * @returns Sorted rows with `rate = count / totalSessions`
 */
function completionRatesFromSessionsByCase(
  sessionsByCase: Record<string, number>,
  totalSessions: number
): Array<{ difficulty: string; rate: number }> {
  if (totalSessions <= 0) return []
  return Object.entries(sessionsByCase)
    .map(([caseTitle, count]) => ({
      difficulty: caseTitle,
      rate: count / totalSessions,
    }))
    .sort((a, b) => b.rate - a.rate)
}

/**
 * Maps category histogram into `{ challenge, frequency }` rows for charts.
 *
 * @param casesByCategory - Backend map of category name to count
 * @returns Array for admin “common challenges” visualization
 */
function commonChallengesFromCategories(
  casesByCategory: Record<string, number>
): Array<{ challenge: string; frequency: number }> {
  return Object.entries(casesByCategory).map(([challenge, frequency]) => ({
    challenge,
    frequency,
  }))
}

const BASE = '/v1/admin'

/** One row from `GET /v1/admin/users/overview` (snake_case wire). */
export interface AdminUserOverviewRowDTO {
  id: number
  email: string
  full_name: string | null
  role: string
  created_at: string
  session_count: number
  completed_session_count: number
  last_session_at: string | null
  average_overall_score: number | null
  average_empathy_score: number | null
}

/** Paginated user overview for admin tables. */
export interface AdminUserOverviewResponseDTO {
  users: AdminUserOverviewRowDTO[]
  total: number
  skip: number
  limit: number
}

/** Allowed sort modes for the user overview endpoint. */
export type AdminUserOverviewSort =
  | 'last_active_desc'
  | 'avg_score_desc'
  | 'email_asc'

/**
 * Fetches paginated user overview rows for admin reporting.
 *
 * @param skip - Pagination offset
 * @param limit - Page size
 * @param params - Optional `sort`, `role` filter, and search `q`
 * @returns Wire-format overview response
 */
export async function fetchAdminUserOverview(
  skip = 0,
  limit = 20,
  params?: {
    sort?: AdminUserOverviewSort
    role?: string
    q?: string
  }
): Promise<AdminUserOverviewResponseDTO> {
  const { data } = await api.get<AdminUserOverviewResponseDTO>(
    `${BASE}/users/overview`,
    {
      params: {
        skip,
        limit,
        sort: params?.sort,
        role: params?.role,
        q: params?.q,
      },
    }
  )
  return data
}

/** Roles assignable via {@link updateUserRole}. */
export type AssignableRole = 'admin' | 'trainee' | 'researcher'

/**
 * Changes a user's role (admin only).
 *
 * @param userId - Target user id
 * @param role - New role to assign
 * @returns Updated user overview row
 */
export async function updateUserRole(
  userId: number,
  role: AssignableRole
): Promise<AdminUserOverviewRowDTO> {
  const { data } = await api.patch<AdminUserOverviewRowDTO>(
    `${BASE}/users/${userId}/role`,
    { role }
  )
  return data
}

/**
 * Loads global admin aggregates and maps them into {@link AdminStats}.
 *
 * @remarks
 * Derives `completionRates` and `commonChallenges` from session/case stats; leaves monthly scores empty when absent.
 *
 * @returns Normalized stats for dashboard widgets
 */
export const fetchAdminStats = async (): Promise<AdminStats> => {
  const { data } = await api.get<AggregatesResponse>(`${BASE}/aggregates`)

  const totalSessions = data.session_stats.total_sessions
  const sessionsByCase = data.session_stats.sessions_by_case ?? {}
  const casesByCategory = data.case_stats.cases_by_category ?? {}

  return {
    totalUsers: data.user_stats.total_users,
    totalCases: data.case_stats.total_cases,
    activeSessions: data.session_stats.active_sessions,
    averageScore: data.performance_stats.average_overall_score,
    recentActivity: [],
    completedSessions: data.session_stats.completed_sessions,
    totalSessions: data.session_stats.total_sessions,
    averageDurationSeconds: data.session_stats.average_duration_seconds,
    activeUsersLast30Days: data.user_stats.active_users_last_30_days,
    usersByRole: data.user_stats.users_by_role,
    averageEmpathyScore: data.performance_stats.average_empathy_score,
    averageCommunicationScore: data.performance_stats.average_communication_score,
    averageSpikesCompletion: data.performance_stats.average_spikes_completion,
    casesByCategory,
    analyticsData: {
      averageScoreByMonth: (data.performance_stats.average_score_by_month ?? []).map(
        (row) => ({ month: row.month, score: row.score })
      ),
      completionRates: completionRatesFromSessionsByCase(sessionsByCase, totalSessions),
      commonChallenges: commonChallengesFromCategories(casesByCategory),
    },
  }
}

/**
 * Lists sessions for admin review (transcripts, metadata).
 *
 * @remarks
 * JWT is sent via the shared API client. Requires admin role server-side.
 *
 * @param skip - Pagination offset
 * @param limit - Page size
 * @returns Paginated session rows
 */
export async function fetchAdminSessions(
  skip = 0,
  limit = 20
): Promise<AdminSessionListResponse> {
  const { data } = await api.get<AdminSessionListResponse>(`${BASE}/sessions`, {
    params: { skip, limit },
  })
  return data
}

/**
 * Loads one session with feedback summary and metrics timeline.
 *
 * @param sessionId - Session id as string (URL segment)
 * @returns Detail bundle for the admin session page
 */
export async function fetchAdminSessionDetail(
  sessionId: string
): Promise<AdminSessionDetailResponse> {
  const { data } = await api.get<AdminSessionDetailResponse>(
    `${BASE}/sessions/${sessionId}`
  )
  return data
}

/** Active plugin identifiers returned by `GET /v1/admin/plugins`. */
export interface PluginsResponse {
  patient_model: string
  evaluator: string
  metrics: string[]
}

/**
 * Fetches which plugin implementations are currently active on the server.
 *
 * @returns Module paths or class names per plugin slot
 */
export async function fetchAdminPlugins(): Promise<PluginsResponse> {
  const { data } = await api.get<PluginsResponse>(`${BASE}/plugins`)
  return data
}

/** One discovered plugin with semantic version. */
export interface PluginInfo {
  name: string
  version: string
}

/** Registry response for evaluator / patient / metrics plugins. */
export interface PluginDiscoveryResponse {
  evaluators: PluginInfo[]
  patient_models: PluginInfo[]
  metrics: PluginInfo[]
}

/**
 * Lists all registered plugins (name + version) for admin dropdowns (e.g. case form).
 *
 * @returns Discovery groups from `/v1/admin/plugin-registry`
 */
export async function fetchAdminPluginRegistry(): Promise<PluginDiscoveryResponse> {
  const { data } = await api.get<PluginDiscoveryResponse>(`${BASE}/plugin-registry`)
  return data
}
