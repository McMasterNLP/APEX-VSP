/**
 * Shared, real (non-anonymized) session list table backed by `fetchAdminSessions`.
 *
 * @remarks
 * Extracted from Admin.tsx's Sessions tab so both the Admin "Session Logs" tab and the
 * Research "Evaluate Sessions" tab render the same rows from the same data source, each
 * supplying its own row-click behavior (open an inline detail panel vs navigate to the
 * evaluation workspace).
 */
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  fetchAdminSessions,
  fetchSessionFilterOptions,
  type AdminSessionListFilters,
  type AdminSessionListResponse,
  type EvaluationStatusFilter,
  type SessionFilterOptionsResponse,
} from '@/api/admin.api'
import { fetchSessionEvaluationStatuses, type SessionEvaluationStatusDTO } from '@/api/research.api'
import { formatDateTimeInUserTimeZone } from '@/lib/dateTime'
import { cn } from '@/lib/utils'
import type { SessionDetailDTO } from '@/types/session'

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

/** The four evaluation-status chip states, ranked so "needs attention" sorts first. */
type EvaluationChipLabel = 'Needs review' | 'In review' | 'No runs yet' | 'Locked'

interface EvaluationChip {
  label: EvaluationChipLabel
  /** Sort rank: 0 = surfaces first. */
  rank: 0 | 1 | 2 | 3
}

/**
 * Derives the Sessions-list status chip from a session's bulk evaluation-status row.
 *
 * @remarks
 * Precedence matches the product definition exactly:
 * - No runs yet: zero saved evaluation runs.
 * - Locked: an annotation set exists with `status === 'complete'` or `locked === true`.
 * - In review: an annotation set exists with `status` of `draft`/`in_review` and not locked.
 * - Needs review: at least one saved run exists but no annotation set has been created yet.
 *
 * @param status - This session's row from {@link fetchSessionEvaluationStatuses}, if loaded
 * @returns Chip label and its sort rank
 */
function evaluationChipFor(status: SessionEvaluationStatusDTO | undefined): EvaluationChip {
  if (!status || !status.has_saved_runs) return { label: 'No runs yet', rank: 2 }
  if (status.latest_annotation_set_status === 'complete' || status.latest_annotation_set_locked) {
    return { label: 'Locked', rank: 3 }
  }
  if (
    status.latest_annotation_set_status === 'draft' ||
    status.latest_annotation_set_status === 'in_review'
  ) {
    return { label: 'In review', rank: 1 }
  }
  return { label: 'Needs review', rank: 0 }
}

const CHIP_CLASSNAMES: Record<EvaluationChipLabel, string> = {
  'Needs review': 'bg-amber-100 text-amber-900 border-amber-300',
  'In review': 'bg-indigo-100 text-indigo-900 border-indigo-300',
  'No runs yet': 'bg-gray-100 text-gray-700 border-gray-300',
  Locked: 'bg-emerald-100 text-emerald-900 border-emerald-300',
}

/** `evaluation_status` dropdown options, in the same order the chip precedence surfaces them. */
const EVALUATION_STATUS_OPTIONS: Array<{ value: EvaluationStatusFilter; label: string }> = [
  { value: 'needs_review', label: 'Needs review' },
  { value: 'in_review', label: 'In review' },
  { value: 'locked', label: 'Locked' },
  { value: 'no_runs', label: 'No runs yet' },
]

/** Known session states (see `Session.state` on the backend entity). */
const SESSION_STATE_OPTIONS = ['active', 'paused', 'completed', 'abandoned']

/** One active filter, for the removable-chip row. */
interface ActiveFilterChip {
  key: string
  label: string
  onRemove: () => void
}

export interface AdminSessionsTableProps {
  /** Called when a row is clicked; receives the full session row. */
  onRowClick: (session: SessionDetailDTO) => void
  /** Row id considered "selected" for highlighting (optional). */
  selectedSessionId?: number | null
  /** Page size for the underlying `fetchAdminSessions` call. Defaults to 50. */
  limit?: number
  /**
   * Shows a per-row evaluation/annotation status chip, defaults the sort order to
   * surface sessions needing attention first, and enables the evaluation-status and
   * evaluator filters.
   *
   * @remarks
   * Only meaningful for the Research "Evaluate Sessions" tab's review workflow;
   * Admin's own Sessions tab is general session management and isn't about review
   * status, so it leaves this off (default `false`) rather than forking the component.
   */
  showEvaluationStatus?: boolean
}

/**
 * Loads and renders the real-session table (id, user, case, started) used by both
 * Admin's Session Logs tab and Research's Evaluate Sessions tab.
 *
 * @remarks
 * Filters are reflected in the URL's search params (`caseId`, `patientPlugin`,
 * `evaluatorPlugin`, `state`, `evalStatus`, `evaluatorId`, plus the pre-existing
 * `userId`/`startDate`/`endDate`) so a filtered view is shareable/bookmarkable between
 * researchers, the same pattern `Research.tsx` already uses for its own `?tab=` param.
 * `userId` deliberately stays a raw numeric input rather than a named dropdown: this
 * table is real (non-anonymized) session data, and the Research "Evaluate Sessions" tab
 * exposes it to researchers with the trainee's identity already redacted server-side
 * (see `_with_session_user_info` on the backend) -- a searchable "pick a trainee by
 * name" dropdown here would leak back exactly what that redaction exists to prevent.
 *
 * @param props - Row-click handler, optional selected id, page size, and evaluation-status display
 * @returns Table card content (loading/error/empty states included)
 */
export function AdminSessionsTable({
  onRowClick,
  selectedSessionId,
  limit = 50,
  showEvaluationStatus = false,
}: AdminSessionsTableProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [sessionsData, setSessionsData] = useState<AdminSessionListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusesById, setStatusesById] = useState<Map<number, SessionEvaluationStatusDTO>>(
    new Map()
  )
  const [filterOptions, setFilterOptions] = useState<SessionFilterOptionsResponse | null>(null)

  const [skip, setSkip] = useState(0)

  const userIdInput = searchParams.get('userId') ?? ''
  const caseIdInput = searchParams.get('caseId') ?? ''
  const startDate = searchParams.get('startDate') ?? ''
  const endDate = searchParams.get('endDate') ?? ''
  const stateInput = searchParams.get('state') ?? ''
  const patientPluginInput = searchParams.get('patientPlugin') ?? ''
  const evaluatorPluginInput = searchParams.get('evaluatorPlugin') ?? ''
  const evaluationStatusInput = searchParams.get('evalStatus') ?? ''
  const evaluatorIdInput = searchParams.get('evaluatorId') ?? ''

  /** Sets or removes one filter param, leaving every other search param untouched. */
  const setFilterParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  const filters: AdminSessionListFilters = useMemo(() => {
    const parsedUserId = Number.parseInt(userIdInput, 10)
    const parsedCaseId = Number.parseInt(caseIdInput, 10)
    const parsedEvaluatorId = Number.parseInt(evaluatorIdInput, 10)
    return {
      userId: Number.isFinite(parsedUserId) && userIdInput.trim() !== '' ? parsedUserId : undefined,
      caseId: Number.isFinite(parsedCaseId) && caseIdInput.trim() !== '' ? parsedCaseId : undefined,
      startDate: startDate || undefined,
      endDate: endDate || undefined,
      state: stateInput || undefined,
      patientPlugin: patientPluginInput || undefined,
      evaluatorPlugin: evaluatorPluginInput || undefined,
      evaluatorUserId:
        showEvaluationStatus && Number.isFinite(parsedEvaluatorId) && evaluatorIdInput.trim() !== ''
          ? parsedEvaluatorId
          : undefined,
      evaluationStatus:
        showEvaluationStatus && evaluationStatusInput
          ? (evaluationStatusInput as EvaluationStatusFilter)
          : undefined,
    }
  }, [
    userIdInput,
    caseIdInput,
    startDate,
    endDate,
    stateInput,
    patientPluginInput,
    evaluatorPluginInput,
    evaluatorIdInput,
    evaluationStatusInput,
    showEvaluationStatus,
  ])

  const hasActiveFilters =
    filters.userId !== undefined ||
    filters.caseId !== undefined ||
    filters.startDate !== undefined ||
    filters.endDate !== undefined ||
    filters.state !== undefined ||
    filters.patientPlugin !== undefined ||
    filters.evaluatorPlugin !== undefined ||
    filters.evaluatorUserId !== undefined ||
    filters.evaluationStatus !== undefined

  const clearFilters = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const key of [
        'userId',
        'caseId',
        'startDate',
        'endDate',
        'state',
        'patientPlugin',
        'evaluatorPlugin',
        'evalStatus',
        'evaluatorId',
      ]) {
        next.delete(key)
      }
      return next
    })
  }

  const caseTitleById = useMemo(() => {
    const map = new Map<number, string>()
    for (const c of filterOptions?.cases ?? []) map.set(c.id, c.title)
    return map
  }, [filterOptions])

  const evaluatorLabelById = useMemo(() => {
    const map = new Map<number, string>()
    for (const e of filterOptions?.evaluators ?? []) map.set(e.id, e.label)
    return map
  }, [filterOptions])

  const activeFilterChips: ActiveFilterChip[] = useMemo(() => {
    const chips: ActiveFilterChip[] = []
    if (filters.userId !== undefined) {
      chips.push({
        key: 'userId',
        label: `User #${filters.userId}`,
        onRemove: () => setFilterParam('userId', ''),
      })
    }
    if (filters.caseId !== undefined) {
      chips.push({
        key: 'caseId',
        label: `Case: ${caseTitleById.get(filters.caseId) ?? `#${filters.caseId}`}`,
        onRemove: () => setFilterParam('caseId', ''),
      })
    }
    if (filters.startDate !== undefined) {
      chips.push({
        key: 'startDate',
        label: `From: ${filters.startDate}`,
        onRemove: () => setFilterParam('startDate', ''),
      })
    }
    if (filters.endDate !== undefined) {
      chips.push({
        key: 'endDate',
        label: `Until: ${filters.endDate}`,
        onRemove: () => setFilterParam('endDate', ''),
      })
    }
    if (filters.state !== undefined) {
      chips.push({
        key: 'state',
        label: `State: ${filters.state}`,
        onRemove: () => setFilterParam('state', ''),
      })
    }
    if (filters.patientPlugin !== undefined) {
      chips.push({
        key: 'patientPlugin',
        label: `Patient plugin: ${filters.patientPlugin}`,
        onRemove: () => setFilterParam('patientPlugin', ''),
      })
    }
    if (filters.evaluatorPlugin !== undefined) {
      chips.push({
        key: 'evaluatorPlugin',
        label: `Evaluator plugin: ${filters.evaluatorPlugin}`,
        onRemove: () => setFilterParam('evaluatorPlugin', ''),
      })
    }
    if (filters.evaluationStatus !== undefined) {
      const optionLabel =
        EVALUATION_STATUS_OPTIONS.find((o) => o.value === filters.evaluationStatus)?.label ??
        filters.evaluationStatus
      chips.push({
        key: 'evalStatus',
        label: `Status: ${optionLabel}`,
        onRemove: () => setFilterParam('evalStatus', ''),
      })
    }
    if (filters.evaluatorUserId !== undefined) {
      chips.push({
        key: 'evaluatorId',
        label: `Evaluator: ${evaluatorLabelById.get(filters.evaluatorUserId) ?? `#${filters.evaluatorUserId}`}`,
        onRemove: () => setFilterParam('evaluatorId', ''),
      })
    }
    return chips
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, caseTitleById, evaluatorLabelById])

  // Any filter change re-queries from the first page -- a filtered result set has a
  // different total, so an old `skip` could point past the end of it.
  useEffect(() => {
    setSkip(0)
  }, [
    filters.userId,
    filters.caseId,
    filters.startDate,
    filters.endDate,
    filters.state,
    filters.patientPlugin,
    filters.evaluatorPlugin,
    filters.evaluatorUserId,
    filters.evaluationStatus,
  ])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAdminSessions(skip, limit, filters)
        if (!cancelled) setSessionsData(data)
      } catch (e) {
        console.error('Failed to fetch sessions:', e)
        if (!cancelled) setError('Failed to load session logs')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    limit,
    skip,
    filters.userId,
    filters.caseId,
    filters.startDate,
    filters.endDate,
    filters.state,
    filters.patientPlugin,
    filters.evaluatorPlugin,
    filters.evaluatorUserId,
    filters.evaluationStatus,
  ])

  // Filter-dropdown options load once; not worth re-fetching on every filter change.
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const options = await fetchSessionFilterOptions()
        if (!cancelled) setFilterOptions(options)
      } catch (e) {
        // Non-fatal: filter dropdowns just render empty, raw filtering still works via URL.
        console.error('Failed to fetch session filter options:', e)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!showEvaluationStatus || !sessionsData || sessionsData.sessions.length === 0) return
    let cancelled = false
    const load = async () => {
      try {
        const statuses = await fetchSessionEvaluationStatuses(
          sessionsData.sessions.map((s) => s.id)
        )
        if (!cancelled) {
          setStatusesById(new Map(statuses.map((row) => [row.session_id, row])))
        }
      } catch (e) {
        // Non-fatal: the table still renders without the status column/sort.
        console.error('Failed to fetch session evaluation statuses:', e)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [showEvaluationStatus, sessionsData])

  const rows = useMemo(() => {
    const sessions = sessionsData?.sessions ?? []
    if (!showEvaluationStatus) return sessions
    // Sort client-side over the already-fetched page; this does not attempt to keep a
    // stable rank order across separate pagination pages.
    return sessions.slice().sort((a, b) => {
      const rankA = evaluationChipFor(statusesById.get(a.id)).rank
      const rankB = evaluationChipFor(statusesById.get(b.id)).rank
      if (rankA !== rankB) return rankA - rankB
      return new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
    })
  }, [sessionsData, showEvaluationStatus, statusesById])

  const total = sessionsData?.total ?? 0
  const rangeStart = total === 0 ? 0 : skip + 1
  const rangeEnd = Math.min(skip + limit, total)
  const canGoPrevious = skip > 0
  const canGoNext = skip + limit < total

  const filterBar = (
    <div className="flex flex-col gap-2 border-b pb-3 text-sm">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">User ID</span>
          <input
            type="number"
            inputMode="numeric"
            value={userIdInput}
            onChange={(event) => setFilterParam('userId', event.target.value)}
            className="w-24 rounded border border-gray-300 px-2 py-1"
            placeholder="Any"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Case</span>
          <select
            value={caseIdInput}
            onChange={(event) => setFilterParam('caseId', event.target.value)}
            className="w-48 rounded border border-gray-300 px-2 py-1"
          >
            <option value="">Any</option>
            {(filterOptions?.cases ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">State</span>
          <select
            value={stateInput}
            onChange={(event) => setFilterParam('state', event.target.value)}
            className="w-32 rounded border border-gray-300 px-2 py-1"
          >
            <option value="">Any</option>
            {SESSION_STATE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Patient plugin</span>
          <select
            value={patientPluginInput}
            onChange={(event) => setFilterParam('patientPlugin', event.target.value)}
            className="w-40 rounded border border-gray-300 px-2 py-1"
          >
            <option value="">Any</option>
            {(filterOptions?.patient_plugins ?? []).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Evaluator plugin</span>
          <select
            value={evaluatorPluginInput}
            onChange={(event) => setFilterParam('evaluatorPlugin', event.target.value)}
            className="w-40 rounded border border-gray-300 px-2 py-1"
          >
            <option value="">Any</option>
            {(filterOptions?.evaluator_plugins ?? []).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        {showEvaluationStatus && (
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-600">Evaluation status</span>
            <select
              value={evaluationStatusInput}
              onChange={(event) => setFilterParam('evalStatus', event.target.value)}
              className="w-40 rounded border border-gray-300 px-2 py-1"
            >
              <option value="">Any</option>
              {EVALUATION_STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {showEvaluationStatus && (
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-600">Evaluator</span>
            <select
              value={evaluatorIdInput}
              onChange={(event) => setFilterParam('evaluatorId', event.target.value)}
              className="w-44 rounded border border-gray-300 px-2 py-1"
            >
              <option value="">Any</option>
              {(filterOptions?.evaluators ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Started from</span>
          <input
            type="date"
            value={startDate}
            onChange={(event) => setFilterParam('startDate', event.target.value)}
            className="rounded border border-gray-300 px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Started until</span>
          <input
            type="date"
            value={endDate}
            onChange={(event) => setFilterParam('endDate', event.target.value)}
            className="rounded border border-gray-300 px-2 py-1"
          />
        </label>
      </div>
      {activeFilterChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {activeFilterChips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1 rounded-full border border-apex-200 bg-apex-50 px-2 py-0.5 text-xs font-medium text-apex-900"
            >
              {chip.label}
              <button
                type="button"
                onClick={chip.onRemove}
                aria-label={`Remove filter: ${chip.label}`}
                className="text-apex-600 hover:text-apex-900"
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={clearFilters}
            className="text-xs font-medium text-apex-600 hover:underline"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  )

  const pagination = total > 0 && (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-sm text-gray-600">
      <span>
        Showing {rangeStart}–{rangeEnd} of {total}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!canGoPrevious}
          onClick={() => setSkip((current) => Math.max(0, current - limit))}
          className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          disabled={!canGoNext}
          onClick={() => setSkip((current) => current + limit)}
          className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )

  if (loading) {
    return (
      <div className="flex h-full flex-col gap-3">
        {filterBar}
        <p className="text-gray-500 py-8 text-center">Loading sessions…</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="flex h-full flex-col gap-3">
        {filterBar}
        <p className="text-red-600 py-8 text-center">{error}</p>
      </div>
    )
  }
  if (!sessionsData || sessionsData.sessions.length === 0) {
    return (
      <div className="flex h-full flex-col gap-3">
        {filterBar}
        <p className="text-gray-500 py-8 text-center">
          {hasActiveFilters ? 'No sessions match these filters' : 'No sessions found'}
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-3">
      {filterBar}
      <div className="flex-1 overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 font-medium">Session ID</th>
            <th className="text-left py-2 font-medium">User</th>
            <th className="text-left py-2 font-medium">Case</th>
            <th className="text-left py-2 font-medium">Started</th>
            <th className="text-left py-2 font-medium">State</th>
            {showEvaluationStatus && (
              <th className="text-left py-2 font-medium">Evaluation status</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const chip = showEvaluationStatus ? evaluationChipFor(statusesById.get(s.id)) : null
            return (
              <tr
                key={s.id}
                onClick={() => onRowClick(s)}
                className={cn(
                  'border-b cursor-pointer transition-colors',
                  selectedSessionId === s.id ? 'bg-apex-50' : 'hover:bg-gray-50'
                )}
              >
                <td className="py-2">{s.id}</td>
                <td className="py-2">{formatSessionUserLabel(s)}</td>
                <td className="py-2">{s.case_title?.trim() || `Case #${s.case_id}`}</td>
                <td className="py-2">{formatDateTimeInUserTimeZone(s.started_at)}</td>
                <td className="py-2">{s.state}</td>
                {showEvaluationStatus && chip && (
                  <td className="py-2">
                    <span
                      className={cn(
                        'inline-block rounded-full border px-2 py-0.5 text-xs font-medium',
                        CHIP_CLASSNAMES[chip.label]
                      )}
                    >
                      {chip.label}
                    </span>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>
      {pagination}
    </div>
  )
}
