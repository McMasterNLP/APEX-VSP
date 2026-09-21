/**
 * User-facing usage page: today's counts against the daily per-user and
 * shared deployment caps, for the three metered actions (chat turns, audio,
 * live evaluations).
 */
import { useEffect, useState } from 'react'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fetchMyUsage, type CategoryUsageDTO } from '@/api/usage.api'
import { MessageSquare, Mic, FlaskConical, Gauge } from 'lucide-react'

const CATEGORY_ICON: Record<CategoryUsageDTO['category'], typeof MessageSquare> = {
  chat_turn: MessageSquare,
  audio: Mic,
  live_evaluation: FlaskConical,
}

/**
 * Formats a UTC ISO instant as a short local time string for the "resets at" note.
 *
 * @param isoUtc - UTC ISO-8601 timestamp
 * @returns Locale-formatted date/time string
 */
function formatResetTime(isoUtc: string): string {
  try {
    return new Date(isoUtc).toLocaleString(undefined, {
      weekday: 'short',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return isoUtc
  }
}

/**
 * One category's usage bar: shows the user's own count against their daily
 * limit, plus a smaller note on the shared deployment-wide cap.
 *
 * @param props.usage - Category usage row from `/v1/usage/me`
 */
function UsageCategoryCard({ usage }: { usage: CategoryUsageDTO }) {
  const Icon = CATEGORY_ICON[usage.category]
  const percent = usage.userLimit > 0 ? Math.min(100, Math.round((usage.userCount / usage.userLimit) * 100)) : 0
  const nearLimit = percent >= 80

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium capitalize">{usage.label}</CardTitle>
        <Icon className="h-4 w-4 text-gray-500" />
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between">
          <div className="text-2xl font-bold">
            {usage.userCount}
            <span className="text-base font-normal text-gray-400"> / {usage.userLimit}</span>
          </div>
          <span className={nearLimit ? 'text-xs font-medium text-amber-600' : 'text-xs text-gray-400'}>
            {usage.userRemaining} left today
          </span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className={`h-full rounded-full transition-all ${nearLimit ? 'bg-amber-500' : 'bg-apex-500'}`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Renders the "Usage" page: per-category usage cards plus a note on when
 * today's counters reset (midnight UTC).
 */
export const Usage = () => {
  const [usage, setUsage] = useState<Awaited<ReturnType<typeof fetchMyUsage>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchMyUsage()
      .then((data) => {
        if (!cancelled) setUsage(data)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load usage right now.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="fixed inset-0 overflow-hidden flex flex-col bg-white">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 min-h-0 overflow-y-auto md:ml-64">
          <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center gap-3">
            <div className="rounded-lg border border-gray-200 bg-white p-2">
              <Gauge className="h-5 w-5 text-gray-700" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Usage</h1>
              <p className="mt-1 text-gray-600">
                Daily limits on metered actions, so this deployment stays available for everyone.
              </p>
            </div>
          </div>

          {loading ? (
            <p className="text-sm text-gray-500">Loading usage…</p>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : usage ? (
            <>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {usage.categories.map((row) => (
                  <UsageCategoryCard key={row.category} usage={row} />
                ))}
              </div>
              <p className="mt-6 text-sm text-gray-500">
                Counters reset at midnight UTC (next reset: {formatResetTime(usage.resetsAt)}).
              </p>
            </>
          ) : null}
          </div>
        </main>
      </div>
    </div>
  )
}
