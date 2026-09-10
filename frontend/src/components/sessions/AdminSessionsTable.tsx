/**
 * Shared, real (non-anonymized) session list table backed by `fetchAdminSessions`.
 *
 * @remarks
 * Extracted from Admin.tsx's Sessions tab so both the Admin "Session Logs" tab and the
 * Research "Evaluate Sessions" tab render the same rows from the same data source, each
 * supplying its own row-click behavior (open an inline detail panel vs navigate to the
 * evaluation workspace).
 */
import { useEffect, useState } from 'react'
import { fetchAdminSessions, type AdminSessionListResponse } from '@/api/admin.api'
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

export interface AdminSessionsTableProps {
  /** Called when a row is clicked; receives the full session row. */
  onRowClick: (session: SessionDetailDTO) => void
  /** Row id considered "selected" for highlighting (optional). */
  selectedSessionId?: number | null
  /** Page size for the underlying `fetchAdminSessions` call. Defaults to 50. */
  limit?: number
}

/**
 * Loads and renders the real-session table (id, user, case, started) used by both
 * Admin's Session Logs tab and Research's Evaluate Sessions tab.
 *
 * @param props - Row-click handler, optional selected id, and page size
 * @returns Table card content (loading/error/empty states included)
 */
export function AdminSessionsTable({ onRowClick, selectedSessionId, limit = 50 }: AdminSessionsTableProps) {
  const [sessionsData, setSessionsData] = useState<AdminSessionListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
          </tr>
        </thead>
        <tbody>
          {sessionsData.sessions.map((s) => (
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
