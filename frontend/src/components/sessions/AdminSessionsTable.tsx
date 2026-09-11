/**
 * Shared, real (non-anonymized) session list table backed by `fetchAdminSessions`.
 *
 * @remarks
 * Extracted from Admin.tsx's Sessions tab so both the Admin "Session Logs" tab and the
 * Research "Sessions" tab render the same rows from the same data source, each
 * supplying its own row-click behavior (open an inline detail panel vs navigate to the
 * evaluation workspace).
 */
import { useEffect, useMemo, useState } from 'react'
import { fetchAdminSessions, type AdminSessionListResponse } from '@/api/admin.api'
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

export interface AdminSessionsTableProps {
  /** Called when a row is clicked; receives the full session row. */
  onRowClick: (session: SessionDetailDTO) => void
  /** Row id considered "selected" for highlighting (optional). */
  selectedSessionId?: number | null
  /** Page size for the underlying `fetchAdminSessions` call. Defaults to 50. */
  limit?: number
  /**
   * Shows a per-row evaluation/annotation status chip and defaults the sort order to
   * surface sessions needing attention first.
   *
   * @remarks
   * Only meaningful for the Research "Sessions" tab's review workflow; Admin's own
   * Sessions tab is general session management and isn't about review status, so it
   * leaves this off (default `false`) rather than forking the component.
   */
  showEvaluationStatus?: boolean
}

/**
 * Loads and renders the real-session table (id, user, case, started) used by both
 * Admin's Session Logs tab and Research's Sessions tab.
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
  const [sessionsData, setSessionsData] = useState<AdminSessionListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusesById, setStatusesById] = useState<Map<number, SessionEvaluationStatusDTO>>(
    new Map()
  )

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAdminSessions(0, limit)
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
  }, [limit])

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

  if (loading) {
    return <p className="text-gray-500 py-8 text-center">Loading sessions…</p>
  }
  if (error) {
    return <p className="text-red-600 py-8 text-center">{error}</p>
  }
  if (!sessionsData || sessionsData.sessions.length === 0) {
    return <p className="text-gray-500 py-8 text-center">No sessions found</p>
  }

  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 font-medium">Session ID</th>
            <th className="text-left py-2 font-medium">User</th>
            <th className="text-left py-2 font-medium">Case ID</th>
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
                <td className="py-2">{s.case_id}</td>
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
  )
}
