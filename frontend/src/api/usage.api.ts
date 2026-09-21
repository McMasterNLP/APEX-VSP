/**
 * Usage guardrail API: the per-user "today's limits" view and the admin trends dashboard.
 */
import api from '@/api/client'

/** One category's today usage + limits (wire `snake_case`, mapped to camelCase here). */
export interface CategoryUsageDTO {
  category: 'chat_turn' | 'audio' | 'live_evaluation'
  label: string
  userCount: number
  userLimit: number
  userRemaining: number
  globalCount: number
  globalLimit: number
  globalRemaining: number
}

interface RawCategoryUsage {
  category: 'chat_turn' | 'audio' | 'live_evaluation'
  label: string
  user_count: number
  user_limit: number
  user_remaining: number
  global_count: number
  global_limit: number
  global_remaining: number
}

function mapCategory(row: RawCategoryUsage): CategoryUsageDTO {
  return {
    category: row.category,
    label: row.label,
    userCount: row.user_count,
    userLimit: row.user_limit,
    userRemaining: row.user_remaining,
    globalCount: row.global_count,
    globalLimit: row.global_limit,
    globalRemaining: row.global_remaining,
  }
}

/** `/v1/usage/me` response: today's usage for the signed-in user. */
export interface UsageMeDTO {
  categories: CategoryUsageDTO[]
  resetsAt: string
}

/**
 * Fetches the current user's usage against today's per-user/global caps.
 *
 * @returns Category rows plus the UTC reset instant
 */
export async function fetchMyUsage(): Promise<UsageMeDTO> {
  const { data } = await api.get<{
    categories: RawCategoryUsage[]
    resets_at: string
  }>('/v1/usage/me')
  return {
    categories: data.categories.map(mapCategory),
    resetsAt: data.resets_at,
  }
}

/** One day's per-category counts, as used by the admin usage trend chart. */
export interface UsageTrendDayDTO {
  date: string
  chat_turn: number
  audio: number
  live_evaluation: number
}

/** `/v1/admin/usage` response: today's global usage plus a recent daily trend. */
export interface UsageAdminDTO {
  categories: CategoryUsageDTO[]
  trend: UsageTrendDayDTO[]
  resetsAt: string
}

/**
 * Fetches the admin usage dashboard: today's global counts against caps, and
 * a per-day trend for the last `days` days (default matches the backend's
 * own default of 14).
 *
 * @param days - How many trailing days of trend data to request
 * @returns Category rows, daily trend rows, and the UTC reset instant
 */
export async function fetchAdminUsage(days = 14): Promise<UsageAdminDTO> {
  const { data } = await api.get<{
    categories: RawCategoryUsage[]
    trend: UsageTrendDayDTO[]
    resets_at: string
  }>('/v1/admin/usage', { params: { days } })
  return {
    categories: data.categories.map(mapCategory),
    trend: data.trend,
    resetsAt: data.resets_at,
  }
}
