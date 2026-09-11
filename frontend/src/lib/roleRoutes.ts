import type { Role } from '@/store/authStore'

/**
 * Default landing route after login (and the fallback used by
 * {@link ProtectedRoute} when a role is blocked from the route it tried to
 * reach).
 *
 * @remarks
 * Admin, trainee, and researcher all land on the shared dashboard --
 * researcher has the same general app access as trainee/admin, plus the
 * researcher-only `/research` area, minus true admin-only routes. Kept as a
 * named helper (rather than inlining `/dashboard`) so a future role with a
 * different default landing page only needs a change here.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- role kept in the signature so a future role-specific default needs no call-site changes
export const getHomeRouteForRole = (role?: Role): string => {
  return '/dashboard'
}
