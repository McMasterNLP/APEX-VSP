/**
 * Five-tab evaluation workspace for one session: Overview, Run & Compare, Saved Runs,
 * Review & Annotate, and Export.
 *
 * @remarks
 * Entry point for the Item 1/2A/2B evaluation workflow, reached from Research's
 * "Sessions" tab. This is the parent route element for a nested react-router route tree
 * (see `App.tsx`) — the first use of nested routes / `<Outlet>` in this codebase. It calls
 * {@link useEvaluationSession} once and passes the whole return value down via
 * `<Outlet context={...} />`; each tab reads it with
 * `useOutletContext<EvaluationSessionContext>()`. Renders a sticky header (breadcrumb,
 * session summary, status strip) and an underline-style tab bar built from `<NavLink>`s
 * (matching `Research.tsx`'s tab visual style), so the active tab is driven by the URL.
 */
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { Card, CardContent } from '@/components/ui/card'
import { formatDateTimeInUserTimeZone } from '@/lib/dateTime'
import { cn } from '@/lib/utils'
import { useEvaluationSession } from './research-workspace/useEvaluationSession'

/** Prefer full name, then email; fallback to numeric id (admin API adds user_* from users table). */
function formatSessionUserLabel(s: {
  user_id: number
  user_full_name?: string | null
  user_email?: string | null
}): string {
  const name = s.user_full_name?.trim()
  if (name) return name
  const email = s.user_email?.trim()
  if (email) return email
  return `User #${s.user_id}`
}

/** Maps annotation-set presence/status/locked to a short human label for the status strip. */
function annotationSetStatusLabel(
  annotationSet: { status: string; locked: boolean } | null
): string {
  if (!annotationSet) return 'None'
  if (annotationSet.locked || annotationSet.status === 'complete') return 'Locked'
  if (annotationSet.status === 'in_review') return 'In review'
  return 'Draft'
}

const WORKSPACE_TABS = [
  { path: 'overview', label: 'Overview' },
  { path: 'run', label: 'Run & Compare' },
  { path: 'runs', label: 'Saved Runs' },
  { path: 'review', label: 'Review & Annotate' },
  { path: 'export', label: 'Export' },
] as const

/**
 * Loads session context, exposes {@link useEvaluationSession} via outlet context, and
 * renders the sticky header/tab-bar shell around whichever tab route is active.
 *
 * @returns Full page layout (Navbar/Sidebar shell, sticky header, tab bar, routed outlet)
 */
export function ResearchEvaluationWorkspace() {
  const { sessionId: sessionIdParam } = useParams<{ sessionId: string }>()
  const sessionId = Number(sessionIdParam)
  const evaluationSession = useEvaluationSession(sessionId)
  const { detail, loadingDetail, detailError, savedRuns, annotationSet } = evaluationSession

  const locksReview = savedRuns.length === 0

  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 overflow-y-auto md:ml-64">
          <div className="sticky top-0 z-10 border-b border-gray-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
            <nav className="mb-3 text-sm text-gray-500">
              <Link to="/research" className="hover:underline">
                Research
              </Link>
              {' / '}
              <Link to="/research" className="hover:underline">
                Sessions
              </Link>
              {' / '}
              <span className="text-gray-900">Session #{sessionIdParam}</span>
            </nav>

            {loadingDetail && <p className="text-sm text-gray-500">Loading session…</p>}
            {!loadingDetail && detailError && (
              <p className="text-sm font-medium text-red-600">{detailError}</p>
            )}
            {!loadingDetail && !detailError && detail && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h1 className="text-xl font-bold text-gray-900">
                      Session {detail.session.id} evaluation workspace
                    </h1>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {formatSessionUserLabel(detail.session)} · Case {detail.session.case_id}
                    </p>
                  </div>
                  <span className="rounded-full border border-gray-300 bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">
                    {detail.session.state}
                  </span>
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                  <div className="rounded-md border border-gray-200 p-2">
                    <dt className="font-medium text-gray-600">Saved runs</dt>
                    <dd className="text-sm font-semibold text-gray-900">{savedRuns.length}</dd>
                  </div>
                  <div className="rounded-md border border-gray-200 p-2">
                    <dt className="font-medium text-gray-600">Annotation set</dt>
                    <dd className="text-sm font-semibold text-gray-900">
                      {annotationSetStatusLabel(annotationSet)}
                    </dd>
                  </div>
                  <div className="rounded-md border border-gray-200 p-2">
                    <dt className="font-medium text-gray-600">Coverage</dt>
                    <dd className="text-sm font-semibold text-gray-900">
                      {annotationSet?.coverage_level
                        ? annotationSet.coverage_level.replaceAll('_', ' ')
                        : '—'}
                    </dd>
                  </div>
                  <div className="rounded-md border border-gray-200 p-2">
                    <dt className="font-medium text-gray-600">Last updated</dt>
                    <dd className="text-sm font-semibold text-gray-900">
                      {annotationSet?.updated_at
                        ? formatDateTimeInUserTimeZone(annotationSet.updated_at)
                        : '—'}
                    </dd>
                  </div>
                </dl>
              </>
            )}

            <nav className="mt-4 flex gap-6" aria-label="Evaluation workspace tabs">
              {WORKSPACE_TABS.map((tab) => {
                const isReview = tab.path === 'review'
                return (
                  <NavLink
                    key={tab.path}
                    to={tab.path}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-1.5 border-b-2 px-1 pb-2 text-sm font-medium transition-colors',
                        isActive
                          ? 'border-apex-600 text-apex-700'
                          : 'border-transparent text-gray-500 hover:text-gray-800',
                        isReview && locksReview && 'text-gray-400 hover:text-gray-500'
                      )
                    }
                  >
                    {isReview && locksReview && <Lock className="h-3.5 w-3.5" aria-hidden="true" />}
                    {tab.label}
                  </NavLink>
                )
              })}
            </nav>
          </div>

          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            {!loadingDetail && detailError && (
              <Card>
                <CardContent className="py-8 text-center text-red-600">{detailError}</CardContent>
              </Card>
            )}
            {!loadingDetail && !detailError && <Outlet context={evaluationSession} />}
          </div>
        </main>
      </div>
    </div>
  )
}
