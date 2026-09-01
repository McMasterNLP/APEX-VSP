/**
 * Admin console: overview stats, user directory, session logs, analytics, cases CRUD, plugins.
 */
import { useEffect, useState } from 'react'
import {
  fetchAdminStats,
  fetchAdminSessions,
  fetchAdminSessionDetail,
  fetchAdminPluginRegistry,
  fetchAdminUserOverview,
  type AdminStats,
  type AdminSessionListResponse,
  type AdminSessionDetailResponse,
  type AdminUserOverviewResponseDTO,
  type AdminUserOverviewSort,
} from '@/api/admin.api'
import type { PluginsResponse } from '@/types/plugins'
import { MetricCard } from '@/components/MetricCard'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { Button } from '@/components/ui/button'
import { Users, FileText, Activity, TrendingUp, Download, Plus, BarChart3, MessageSquare, Puzzle, ExternalLink, Clock, UserCheck } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateInUserTimeZone, formatDateTimeInUserTimeZone } from '@/lib/dateTime'
import { formatPluginName, formatMetricsPluginsDisplay } from '@/lib/formatPluginName'
import { cn } from '@/lib/utils'
import { ResearchEvaluationPanel } from '@/components/admin/research/ResearchEvaluationPanel'

// ---- Session detail panel ----

/**
 * Inline transcript, feedback summary, and metrics timeline for a selected admin session.
 *
 * @param props - Detail payload and close handler
 * @param props.detail - Session + feedback + timeline from admin API
 * @param props.onClose - Clears selection in parent state
 * @returns Card panel JSX
 */
function SessionDetailPanel({
  detail,
  onClose,
}: {
  detail: AdminSessionDetailResponse
  onClose: () => void
}) {
  const { session, feedback, metrics_timeline } = detail
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Session {session.id} – Transcript & Feedback</CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            {formatSessionUserLabel(session)}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Transcript */}
        <section>
          <h4 className="font-medium mb-3">Transcript</h4>
          <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3 bg-gray-50">
            {session.turns.length === 0 ? (
              <p className="text-gray-500 text-sm">No turns</p>
            ) : (
              session.turns.map((t) => (
                <div key={t.id} className="text-sm">
                  <span className="font-medium text-gray-700">
                    Turn {t.turn_number} ({t.role})
                  </span>
                  <span className="text-gray-500 ml-2 text-xs">
                    {formatDateTimeInUserTimeZone(t.timestamp)}
                  </span>
                  <p className="mt-1 text-gray-900">{t.text}</p>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Feedback summary */}
        <section>
          <h4 className="font-medium mb-3">Feedback Summary</h4>
          {feedback ? (
            <div className="space-y-2 border rounded-lg p-3 bg-gray-50">
              <div>
                <span className="text-sm font-medium">Empathy score: </span>
                <span>{feedback.empathy_score.toFixed(1)}</span>
              </div>
              <div>
                <span className="text-sm font-medium">Overall score: </span>
                <span>{feedback.overall_score.toFixed(1)}</span>
              </div>
              {feedback.strengths && (
                <div>
                  <span className="text-sm font-medium">Strengths: </span>
                  <p className="text-sm text-gray-700 mt-1">{feedback.strengths}</p>
                </div>
              )}
              {feedback.areas_for_improvement && (
                <div>
                  <span className="text-sm font-medium">Areas for improvement: </span>
                  <p className="text-sm text-gray-700 mt-1">{feedback.areas_for_improvement}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No feedback generated yet.</p>
          )}
        </section>

        {/* Evaluation Details */}
        <section>
          <h4 className="font-medium mb-3">Evaluation Details</h4>
          <div className="space-y-2 border rounded-lg p-3 bg-gray-50">
            <div>
              <span className="text-sm font-medium">Evaluator: </span>
              <span className="text-sm text-gray-700" title={session.evaluator_plugin || undefined}>
                {session.evaluator_plugin ? formatPluginName(session.evaluator_plugin) : 'Server default'}
              </span>
            </div>
            <div>
              <span className="text-sm font-medium">Patient model: </span>
              <span className="text-sm text-gray-700" title={session.patient_model_plugin || undefined}>
                {session.patient_model_plugin ? formatPluginName(session.patient_model_plugin) : 'Server default'}
              </span>
            </div>
            <div>
              <span className="text-sm font-medium">Metrics plugins: </span>
              <span className="text-sm text-gray-700">
                {formatMetricsPluginsDisplay(
                  session.metrics_plugins as string | string[] | null | undefined
                ) || '—'}
              </span>
            </div>
          </div>
        </section>

        {/* Metrics timeline */}
        <section>
          <h4 className="font-medium mb-3">Metrics Timeline</h4>
          {metrics_timeline.length === 0 ? (
            <p className="text-gray-500 text-sm">No metrics timeline</p>
          ) : (
            <ul className="space-y-2 border rounded-lg p-3 bg-gray-50 max-h-48 overflow-y-auto">
              {metrics_timeline.map((m, i) => (
                <li key={i} className="text-sm flex justify-between gap-4">
                  <span>Turn {m.turn_number}</span>
                  <span>{formatDateTimeInUserTimeZone(m.timestamp)}</span>
                  <span>Empathy: {m.empathy_score.toFixed(1)}</span>
                  <span>{m.question_type}</span>
                  <span>{m.spikes_stage}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <ResearchEvaluationPanel sessionId={session.id} sessionState={session.state} />
      </CardContent>
    </Card>
  )
}

// ---- NEW: cases CRUD imports ----
import { CasesTable } from '@/components/admin/CasesTable'
import { CaseForm } from '@/components/admin/CaseForm'
import { listCases, createCase, updateCase, deleteCase } from '@/api/cases.api'
import type { Case } from '@/types/case'
import type { SessionDetailDTO } from '@/types/session'

const PLUGIN_DESCRIPTIONS: Record<string, Record<string, string>> = {
  evaluator: {
    apex_hybrid_evaluator: 'Evaluates conversations using the SPIKES communication framework and empathy detection with a hybrid rule + LLM pipeline.',
    apex_baseline_evaluator: 'Baseline evaluator using rule-based scoring for empathy and SPIKES coverage.',
    apex_hybrid_v2_evaluator: 'Second-generation hybrid evaluator with improved LLM merge and scoring heuristics.',
  },
  patient_model: {
    default_llm_patient: 'LLM-powered patient model that generates realistic responses based on case context and conversation history.',
  },
  metrics: {
    apex_metrics: 'Provides empathic opportunity counts, response type breakdowns, and SPIKES coverage analytics for research dashboards.',
  },
}

function pluginDescription(kind: string, name: string): string {
  const normalized = name.toLowerCase().replace(/[\s-]+/g, '_')
  const kindMap = PLUGIN_DESCRIPTIONS[kind]
  if (kindMap) {
    for (const [key, desc] of Object.entries(kindMap)) {
      if (normalized.includes(key) || key.includes(normalized)) return desc
    }
  }
  return 'Custom plugin registered via the plugin configuration.'
}

const OVERVIEW_RECENT_SESSIONS_LIMIT = 8
const USERS_PAGE_SIZE = 20

/**
 * Formats nullable aggregate scores as `x.x / 100` or an em dash.
 *
 * @param value - Score from admin aggregates
 * @returns Display string
 */
function formatAdminScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(1)} / 100`
}

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

/**
 * Tabbed admin dashboard: loads stats, sessions, cases, plugins, and user overview on demand.
 *
 * @returns Full admin layout
 */
export const Admin = () => {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [overviewRecentSessions, setOverviewRecentSessions] = useState<SessionDetailDTO[]>([])
  const [overviewSessionsLoading, setOverviewSessionsLoading] = useState(true)
  const [overviewSessionsError, setOverviewSessionsError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'sessions' | 'analytics' | 'cases' | 'plugins'>('overview')

  // ---- NEW: cases state ----
  const [caseItems, setCaseItems] = useState<Case[]>([])
  const [caseLoading, setCaseLoading] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [editing, setEditing] = useState<Case | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // ---- Session logs state ----
  const [sessionsData, setSessionsData] = useState<AdminSessionListResponse | null>(null)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<AdminSessionDetailResponse | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  // Plugins page: installed plugins (name + version)
  const [installedPlugins, setInstalledPlugins] = useState<PluginsResponse | null>(null)
  const [pluginsLoading, setPluginsLoading] = useState(false)
  const [pluginsError, setPluginsError] = useState<string | null>(null)

  const [userOverviewData, setUserOverviewData] = useState<AdminUserOverviewResponseDTO | null>(null)
  const [userOverviewLoading, setUserOverviewLoading] = useState(false)
  const [userOverviewError, setUserOverviewError] = useState<string | null>(null)
  const [usersSkip, setUsersSkip] = useState(0)
  const [usersSort, setUsersSort] = useState<AdminUserOverviewSort>('last_active_desc')

  useEffect(() => {
    /**
     * Loads aggregate stats and recent sessions for the Overview tab on mount.
     */
    const loadOverview = async () => {
      setOverviewSessionsLoading(true)
      setOverviewSessionsError(null)
      const [statsResult, sessionsResult] = await Promise.allSettled([
        fetchAdminStats(),
        fetchAdminSessions(0, OVERVIEW_RECENT_SESSIONS_LIMIT),
      ])

      if (statsResult.status === 'fulfilled') {
        setStats(statsResult.value)
      } else {
        console.error('Failed to fetch admin stats:', statsResult.reason)
      }

      if (sessionsResult.status === 'fulfilled') {
        setOverviewRecentSessions(sessionsResult.value.sessions)
        setOverviewSessionsError(null)
      } else {
        console.error('Failed to fetch overview sessions:', sessionsResult.reason)
        setOverviewRecentSessions([])
        setOverviewSessionsError('Could not load recent sessions.')
      }

      setLoading(false)
      setOverviewSessionsLoading(false)
    }
    void loadOverview()
  }, [])

  // ---- NEW: fetch cases when switching to the Cases tab ----
  /**
   * Refetches the case list from the API and updates `caseItems`.
   */
  const refreshCases = async () => {
    setCaseLoading(true)
    try {
      const { items } = await listCases()
      setCaseItems(items)
    } catch (e) {
      console.error('Failed to fetch cases:', e)
    } finally {
      setCaseLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'cases') {
      void refreshCases()
    }
  }, [activeTab])

  /**
   * Refetches admin session logs (first page) for the Session Logs tab.
   */
  const refreshSessions = async () => {
    setSessionsLoading(true)
    setSessionsError(null)
    try {
      const data = await fetchAdminSessions(0, 50)
      setSessionsData(data)
    } catch (e) {
      console.error('Failed to fetch sessions:', e)
      setSessionsError('Failed to load session logs')
    } finally {
      setSessionsLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'sessions') {
      void refreshSessions()
    }
  }, [activeTab])

  /**
   * Loads the plugin registry (evaluators, patient models, metrics) for the Plugins tab.
   */
  const loadPlugins = async () => {
    setPluginsLoading(true)
    setPluginsError(null)
    try {
      const data = await fetchAdminPluginRegistry()
      setInstalledPlugins(data)
    } catch (e) {
      console.error('Failed to fetch plugins:', e)
      setPluginsError('Failed to load plugins')
    } finally {
      setPluginsLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'plugins') {
      void loadPlugins()
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab !== 'users') return
    let cancelled = false

    /**
     * Loads paginated user overview rows; skips state updates when `cancelled` (tab change/unmount).
     */
    const loadUserOverview = async () => {
      setUserOverviewLoading(true)
      setUserOverviewError(null)
      try {
        const data = await fetchAdminUserOverview(usersSkip, USERS_PAGE_SIZE, {
          sort: usersSort,
        })
        if (!cancelled) setUserOverviewData(data)
      } catch (e) {
        console.error('Failed to fetch user overview:', e)
        if (!cancelled) {
          setUserOverviewError('Failed to load user overview')
          setUserOverviewData(null)
        }
      } finally {
        if (!cancelled) setUserOverviewLoading(false)
      }
    }

    void loadUserOverview()
    return () => {
      cancelled = true
    }
  }, [activeTab, usersSkip, usersSort])

  /**
   * Fetches full session detail (transcript, feedback, timeline) for the side panel.
   *
   * @param sessionId - Session primary key
   */
  const handleSessionRowClick = async (sessionId: number) => {
    setSelectedDetail(null)
    setDetailError(null)
    setDetailLoading(true)
    try {
      const detail = await fetchAdminSessionDetail(String(sessionId))
      setSelectedDetail(detail)
    } catch (e) {
      console.error('Failed to fetch session detail:', e)
      setDetailError('Failed to load session detail')
    } finally {
      setDetailLoading(false)
    }
  }

  /**
   * Clears the session detail panel and any load error.
   */
  const clearSelectedSession = () => {
    setSelectedDetail(null)
    setDetailError(null)
  }

  /**
   * Downloads current admin stats and metadata as a dated JSON file in the browser.
   */
  const handleExportData = () => {
    const dataToExport = {
      stats,
      exportedAt: new Date().toISOString(),
      type: 'admin_analytics',
    }
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `apex_analytics_${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  /** Tab definitions: id, label, and icon for the admin sub-navigation. */
  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'users', label: 'User Management', icon: Users },
    { id: 'sessions', label: 'Session Logs', icon: MessageSquare },
    { id: 'analytics', label: 'Analytics', icon: TrendingUp },
    { id: 'cases', label: 'Case Management', icon: FileText },
    { id: 'plugins', label: 'Plugins', icon: Puzzle },
  ] as const

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-500">Loading admin dashboard...</div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-500">Failed to load stats</div>
      </div>
    )
  }

  // ---- NEW: cases handlers ----
  /**
   * Opens the case form in create mode with no initial values.
   */
  const onCreateClick = () => {
    setEditing(null)
    setFormMode('create')
    setFormOpen(true)
  }

  /**
   * Opens the case form prefilled for editing the given case.
   *
   * @param c - Case to edit
   */
  const onEdit = (c: Case) => {
    setEditing(c)
    setFormMode('edit')
    setFormOpen(true)
  }

  /**
   * Prompts for confirmation, deletes the case, and refreshes the list.
   *
   * @param id - Case id to delete
   */
  const onDelete = async (id: number) => {
    if (!confirm('Delete this case?')) return
    await deleteCase(id)
    await refreshCases()
  }

  /**
   * Creates or updates a case from the modal form, then closes and refreshes.
   *
   * @param vals - Partial case fields from the admin case form modal
   */
  const onSubmitForm = async (vals: Partial<Case>) => {
    setSubmitting(true)
    try {
      if (formMode === 'create') {
        await createCase(vals)
      } else if (editing) {
        await updateCase(editing.id, vals)
      }
      setFormOpen(false)
      await refreshCases()
    } finally {
      setSubmitting(false)
    }
  }

  /**
   * Renders the active tab’s body (overview, users, sessions, analytics, cases, plugins).
   *
   * @returns Tab panel JSX or null when stats are missing
   */
  const renderTabContent = () => {
    if (!stats) return null

    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-8">
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard title="Total Users" value={stats.totalUsers} icon={Users} description="Registered trainees" />
              <MetricCard title="Total Cases" value={stats.totalCases} icon={FileText} description="Available training cases" />
              <MetricCard title="Active Sessions" value={stats.activeSessions} icon={Activity} description="Currently in progress" />
              <MetricCard title="Average Score" value={`${(Number.parseFloat(stats.averageScore.toString())).toFixed(2)}%`} icon={TrendingUp} description="Across all sessions" />
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                title="Completed Sessions"
                value={stats.completedSessions ?? '—'}
                icon={BarChart3}
                description="Sessions marked completed"
              />
              <MetricCard
                title="Total Sessions"
                value={stats.totalSessions ?? '—'}
                icon={MessageSquare}
                description="All sessions in the system"
              />
              <MetricCard
                title="Active users (30d)"
                value={stats.activeUsersLast30Days ?? '—'}
                icon={UserCheck}
                description="Users with session activity"
              />
              <MetricCard
                title="Avg. session duration"
                value={
                  typeof stats.averageDurationSeconds === 'number'
                    ? `${Math.round(stats.averageDurationSeconds / 60)} min`
                    : '—'
                }
                icon={Clock}
                description="Mean length of sessions"
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Recent sessions</CardTitle>
                <p className="mt-1 text-sm text-gray-500">
                  Latest sessions by start time. See
                  <button
                    type="button"
                    className="mx-1 inline p-0 font-medium text-primary underline-offset-4 hover:underline"
                    onClick={() => setActiveTab('sessions')}
                  >
                    Session Logs
                  </button>
                  for the full list and transcripts.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {overviewSessionsLoading ? (
                    <p className="text-sm text-gray-500">Loading recent sessions…</p>
                  ) : overviewSessionsError ? (
                    <p className="text-sm text-destructive">{overviewSessionsError}</p>
                  ) : overviewRecentSessions.length === 0 ? (
                    <p className="text-sm text-gray-500">No sessions yet.</p>
                  ) : (
                    overviewRecentSessions.map((session) => (
                      <div
                        key={session.id}
                        className="flex items-center justify-between border-b pb-3 last:border-0 last:pb-0 gap-4"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {session.case_title?.trim() || `Session ${session.id}`}
                          </p>
                          <p className="text-xs text-gray-500">
                            {formatSessionUserLabel(session)} · {session.status} · {session.state}
                          </p>
                        </div>
                        <p className="text-xs text-gray-500 shrink-0">
                          {formatDateTimeInUserTimeZone(session.started_at)}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )

      case 'users':
        return (
          <div className="space-y-6">
            <Card>
              <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle>User Overview</CardTitle>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="text-sm text-gray-600 flex items-center gap-2">
                    Sort
                    <select
                      className="rounded-md border border-input bg-background px-2 py-1 text-sm"
                      value={usersSort}
                      onChange={(e) => {
                        setUsersSort(e.target.value as AdminUserOverviewSort)
                        setUsersSkip(0)
                      }}
                    >
                      <option value="last_active_desc">Last active (newest)</option>
                      <option value="avg_score_desc">Avg overall score (high)</option>
                      <option value="email_asc">Email (A–Z)</option>
                    </select>
                  </label>
                </div>
              </CardHeader>
              <CardContent>
                {userOverviewLoading ? (
                  <p className="text-gray-500 py-8 text-center">Loading users…</p>
                ) : userOverviewError ? (
                  <p className="text-destructive py-8 text-center">{userOverviewError}</p>
                ) : !userOverviewData || userOverviewData.users.length === 0 ? (
                  <p className="text-gray-500 py-8 text-center">No users found</p>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full border-separate border-spacing-0 text-sm">
                        <thead>
                          <tr className="border-b">
                            <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                              Name
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                              Email
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                              Role
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium tabular-nums whitespace-nowrap">
                              Sessions
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium tabular-nums whitespace-nowrap">
                              Completed
                            </th>
                            <th className="px-4 py-2.5 pl-6 text-left font-medium whitespace-nowrap">
                              Avg overall
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                              Avg empathy
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                              Last active
                            </th>
                            <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">
                              Registered
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {userOverviewData.users.map((user) => (
                            <tr key={user.id} className="border-b">
                              <td className="px-4 py-2.5 align-top">{user.full_name?.trim() || '—'}</td>
                              <td className="px-4 py-2.5 align-top">{user.email}</td>
                              <td className="px-4 py-2.5 align-top">
                                <span
                                  className={cn(
                                    'inline-flex px-2 py-1 rounded-full text-xs font-medium',
                                    user.role === 'admin'
                                      ? 'bg-purple-100 text-purple-800'
                                      : 'bg-apex-100 text-apex-800'
                                  )}
                                >
                                  {user.role}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-left tabular-nums whitespace-nowrap">
                                {user.session_count}
                              </td>
                              <td className="px-4 py-2.5 text-left tabular-nums whitespace-nowrap">
                                {user.completed_session_count}
                              </td>
                              <td className="px-4 py-2.5 pl-6 text-left tabular-nums whitespace-nowrap">
                                {formatAdminScore(user.average_overall_score)}
                              </td>
                              <td className="px-4 py-2.5 text-left tabular-nums whitespace-nowrap">
                                {formatAdminScore(user.average_empathy_score)}
                              </td>
                              <td className="px-4 py-2.5 text-left whitespace-nowrap">
                                {user.last_session_at
                                  ? formatDateTimeInUserTimeZone(user.last_session_at)
                                  : '—'}
                              </td>
                              <td className="px-4 py-2.5 text-left whitespace-nowrap text-gray-600">
                                {formatDateInUserTimeZone(user.created_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-gray-600">
                      <span>
                        Showing{' '}
                        {userOverviewData.total === 0
                          ? 0
                          : usersSkip + 1}
                        –
                        {usersSkip + userOverviewData.users.length} of {userOverviewData.total}
                      </span>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={usersSkip <= 0 || userOverviewLoading}
                          onClick={() => setUsersSkip((s) => Math.max(0, s - USERS_PAGE_SIZE))}
                        >
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={
                            userOverviewLoading ||
                            usersSkip + userOverviewData.users.length >= userOverviewData.total
                          }
                          onClick={() => setUsersSkip((s) => s + USERS_PAGE_SIZE)}
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        )

      case 'sessions':
        return (
          <div className="flex h-full min-h-0 flex-col space-y-6">
            <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <CardHeader>
                <CardTitle>Session Logs</CardTitle>
                <p className="text-sm text-gray-500 mt-1">
                  Click a row to view transcript and feedback
                </p>
              </CardHeader>
              <CardContent className="min-h-0 flex-1">
                {sessionsLoading ? (
                  <p className="text-gray-500 py-8 text-center">Loading sessions…</p>
                ) : sessionsError ? (
                  <p className="text-red-600 py-8 text-center">{sessionsError}</p>
                ) : !sessionsData || sessionsData.sessions.length === 0 ? (
                  <p className="text-gray-500 py-8 text-center">No sessions found</p>
                ) : (
                  <div className="h-full overflow-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 font-medium">Session ID</th>
                          <th className="text-left py-2 font-medium">User</th>
                          <th className="text-left py-2 font-medium">Case ID</th>
                          <th className="text-left py-2 font-medium">Started</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sessionsData.sessions.map((s) => (
                          <tr
                            key={s.id}
                            onClick={() => handleSessionRowClick(s.id)}
                            className={cn(
                              'border-b cursor-pointer transition-colors',
                              selectedDetail?.session.id === s.id
                                ? 'bg-apex-50'
                                : 'hover:bg-gray-50'
                            )}
                          >
                            <td className="py-2">{s.id}</td>
                            <td className="py-2">{formatSessionUserLabel(s)}</td>
                            <td className="py-2">{s.case_id}</td>
                            <td className="py-2">{formatDateTimeInUserTimeZone(s.started_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Session detail panel */}
            {selectedDetail && (
              <SessionDetailPanel
                detail={selectedDetail}
                onClose={clearSelectedSession}
              />
            )}
            {detailLoading && (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  Loading session detail…
                </CardContent>
              </Card>
            )}
            {detailError && !detailLoading && (
              <Card>
                <CardContent className="py-8 text-center text-red-600">
                  {detailError}
                </CardContent>
              </Card>
            )}
          </div>
        )

      case 'analytics':
        return (
          <div className="space-y-6">
            {stats.analyticsData && (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Performance Trends</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div>
                        <h4 className="font-medium mb-2">Average Score by Month</h4>
                        {stats.analyticsData.averageScoreByMonth.length === 0 ? (
                          <p className="text-sm text-gray-500">
                            No monthly score data yet. Completed sessions with scores will appear here.
                          </p>
                        ) : (
                          <div className="space-y-2">
                            {stats.analyticsData.averageScoreByMonth.map((data, index) => (
                              <div key={index} className="flex items-center justify-between">
                                <span className="text-sm">{data.month}</span>
                                <div className="flex items-center gap-2">
                                  <div className="w-20 h-2 bg-gray-200 rounded-full">
                                    <div className="h-full rounded-full bg-apex-500" style={{ width: `${data.score}%` }} />
                                  </div>
                                  <span className="text-sm font-medium">{data.score}%</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader>
                      <CardTitle>Session share by case</CardTitle>
                      <p className="text-sm text-gray-500 mt-1">
                        Share of all sessions per case (from admin aggregates).
                      </p>
                    </CardHeader>
                    <CardContent>
                      {stats.analyticsData.completionRates.length === 0 ? (
                        <p className="text-sm text-gray-500">
                          No per-case session counts yet (backend may return an empty breakdown).
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {stats.analyticsData.completionRates.map((data, index) => (
                            <div key={index} className="flex items-center justify-between">
                              <span className="text-sm capitalize">{data.difficulty}</span>
                              <div className="flex items-center gap-2">
                                <div className="w-16 h-2 bg-gray-200 rounded-full">
                                  <div className="h-full rounded-full bg-apex-500" style={{ width: `${data.rate * 100}%` }} />
                                </div>
                                <span className="text-sm font-medium">{Math.round(data.rate * 100)}%</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Cases by category</CardTitle>
                      <p className="text-sm text-gray-500 mt-1">From cohort case statistics.</p>
                    </CardHeader>
                    <CardContent>
                      {stats.analyticsData.commonChallenges.length === 0 ? (
                        <p className="text-sm text-gray-500">No category breakdown available.</p>
                      ) : (
                        <div className="space-y-2">
                          {stats.analyticsData.commonChallenges.map((challenge, index) => (
                            <div key={index} className="flex items-center justify-between text-sm">
                              <span>{challenge.challenge}</span>
                              <span className="font-medium">{challenge.frequency} cases</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </>
            )}
          </div>
        )

      case 'cases':
        return (
          <div className="space-y-6">
            

            {caseLoading ? (
              <div className="text-gray-500">Loading cases…</div>
            ) : (
              <Card>
                
                <CardHeader>
                <div className="flex items-center justify-between">
                <CardTitle>Cases</CardTitle>
              <Button onClick={onCreateClick} className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                Create New Case
              </Button>
            </div>
                 
                </CardHeader>
                <CardContent>
                  <CasesTable items={caseItems} onEdit={onEdit} onDelete={onDelete} />
                </CardContent>
              </Card>
            )}

            <CaseForm
              open={formOpen}
              onClose={() => setFormOpen(false)}
              mode={formMode}
              initial={editing ?? undefined}
              onSubmit={onSubmitForm}
              submitting={submitting}
            />
          </div>
        )

      case 'plugins':
        return (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xl font-semibold">Installed Plugins</h2>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" asChild>
                  <a href="/docs/developer-onboarding" className="flex items-center gap-2">
                    <ExternalLink className="h-4 w-4" />
                    Onboarding
                  </a>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <a href="/docs/plugin-developer-guide" className="flex items-center gap-2">
                    <ExternalLink className="h-4 w-4" />
                    Plugin guide
                  </a>
                </Button>
              </div>
            </div>

            {pluginsLoading ? (
              <p className="text-gray-500 py-8">Loading plugins…</p>
            ) : pluginsError ? (
              <p className="text-red-600 py-8">{pluginsError}</p>
            ) : (
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold">Patient Models</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Generate simulated patient responses during training sessions.
                  </p>
                  {installedPlugins?.patient_models?.length ? (
                    <div className="mt-2 space-y-2">
                      {installedPlugins.patient_models.map((p) => (
                        <div key={p.name} className="border rounded-lg p-4 bg-white shadow-sm">
                          <div className="font-medium text-gray-900" title={p.name}>
                            {formatPluginName(p.name)}
                          </div>
                          <div className="text-sm text-gray-500">Version {p.version}</div>
                          <p className="text-sm text-gray-600 mt-1">
                            {pluginDescription('patient_model', p.name)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm mt-2">No patient model plugins registered.</p>
                  )}
                </div>

                <div>
                  <h3 className="font-semibold">Evaluators</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Score clinician communication and produce feedback after each session.
                  </p>
                  {installedPlugins?.evaluators?.length ? (
                    <div className="mt-2 space-y-2">
                      {installedPlugins.evaluators.map((p) => (
                        <div key={p.name} className="border rounded-lg p-4 bg-white shadow-sm">
                          <div className="font-medium text-gray-900" title={p.name}>
                            {formatPluginName(p.name)}
                          </div>
                          <div className="text-sm text-gray-500">Version {p.version}</div>
                          <p className="text-sm text-gray-600 mt-1">
                            {pluginDescription('evaluator', p.name)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm mt-2">No evaluator plugins registered.</p>
                  )}
                </div>

                <div>
                  <h3 className="font-semibold">Metrics Plugins</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    Compute additional analytics metrics for research dashboards and data exports.
                  </p>
                  {installedPlugins?.metrics?.length ? (
                    <div className="mt-2 space-y-2">
                      {installedPlugins.metrics.map((p) => (
                        <div key={p.name} className="border rounded-lg p-4 bg-white shadow-sm">
                          <div className="font-medium text-gray-900" title={p.name}>
                            {formatPluginName(p.name)}
                          </div>
                          <div className="text-sm text-gray-500">Version {p.version}</div>
                          <p className="text-sm text-gray-600 mt-1">
                            {pluginDescription('metrics', p.name)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm mt-2">No metrics plugins registered.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main
          className={cn(
            'flex-1 md:ml-64',
            activeTab === 'sessions' ? 'overflow-hidden' : 'overflow-y-auto'
          )}
        >
          <div
            className={cn(
              'mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8',
              activeTab === 'sessions' && 'flex h-full min-h-0 flex-col'
            )}
          >
            <nav className="mb-4 text-sm text-gray-500">
              Dashboard / <span className="text-gray-900">Admin</span>
            </nav>

            <div className="mb-8">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
                  <p className="mt-2 text-gray-600">Manage users, monitor sessions, and analyze platform performance</p>
                </div>
                <Button onClick={handleExportData} variant="outline" className="flex items-center gap-2">
                  <Download className="h-4 w-4" />
                  Export JSON
                </Button>
              </div>
            </div>

            {/* Tabs */}
            <div className="mb-8">
              <nav className="flex gap-8">
                {tabs.map((tab) => {
                  const Icon = tab.icon
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={cn(
                        'flex items-center gap-2 py-2 px-4 rounded-md font-medium text-sm transition-colors',
                        activeTab === tab.id
                          ? 'bg-apex-600 text-white shadow-sm'
                          : 'border border-gray-200 bg-gray-100 text-gray-700 hover:bg-apex-100 hover:text-apex-700'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {tab.label}
                    </button>
                  )
                })}
              </nav>
              <div className="mt-4 border-b border-gray-200" />
            </div>

            <div className={cn(activeTab === 'sessions' && 'min-h-0 flex-1')}>
              {renderTabContent()}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
