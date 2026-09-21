/**
 * Admin "Usage" tab: today's global usage against the daily caps, plus a
 * 14-day trend chart, so admins can see whether the shared EACL-reviewer
 * deployment is trending toward its limits before reviewers hit a 429.
 */
import { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { MetricCard } from '@/components/MetricCard'
import { fetchAdminUsage, type UsageAdminDTO } from '@/api/usage.api'
import { MessageSquare, Mic, FlaskConical } from 'lucide-react'

const CATEGORY_ICON = {
  chat_turn: MessageSquare,
  audio: Mic,
  live_evaluation: FlaskConical,
} as const

const TREND_LINE_COLORS: Record<string, string> = {
  chat_turn: '#0ea5a4', // apex teal
  audio: '#f97316', // orange
  live_evaluation: '#8b5cf6', // purple
}

const TREND_LINE_LABELS: Record<string, string> = {
  chat_turn: 'Chat turns',
  audio: 'Audio',
  live_evaluation: 'Live evaluations',
}

/**
 * Fetches and renders the admin usage dashboard content.
 *
 * @remarks
 * Self-contained (owns its own fetch/loading/error state) so it drops
 * straight into `Admin.tsx`'s tab switch the same way other tab bodies do.
 */
export function AdminUsagePanel() {
  const [data, setData] = useState<UsageAdminDTO | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchAdminUsage(14)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load usage data.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <p className="text-sm text-gray-500">Loading usage…</p>
  }

  if (error || !data) {
    return <p className="text-sm text-destructive">{error ?? 'No usage data available.'}</p>
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {data.categories.map((row) => {
          const Icon = CATEGORY_ICON[row.category]
          const percent = row.globalLimit > 0 ? Math.round((row.globalCount / row.globalLimit) * 100) : 0
          return (
            <MetricCard
              key={row.category}
              title={row.label}
              value={`${row.globalCount} / ${row.globalLimit}`}
              icon={Icon}
              description={`${percent}% of today's shared limit used`}
            />
          )
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Daily usage trend</CardTitle>
          <CardDescription>
            Metered events per day across all users, last {data.trend.length} days. Resets at midnight UTC.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer>
              <LineChart data={data.trend} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <RechartsTooltip />
                <Legend formatter={(value) => TREND_LINE_LABELS[value] ?? value} />
                {(['chat_turn', 'audio', 'live_evaluation'] as const).map((category) => (
                  <Line
                    key={category}
                    type="monotone"
                    dataKey={category}
                    name={category}
                    stroke={TREND_LINE_COLORS[category]}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
