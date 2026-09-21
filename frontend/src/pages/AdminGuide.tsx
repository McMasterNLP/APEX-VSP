/**
 * Admin-facing guide to the admin console: overview, users, session logs,
 * analytics, usage dashboard, case management, and plugins.
 *
 * @remarks
 * Same shell as `UserGuide.tsx` / `ResearchWorkflowGuide.tsx`. Deliberately
 * doesn't re-cover the Evaluate/Review/Validate pipeline -- that's the
 * Research Workflow Guide's job, and it's linked from the last step here
 * instead of duplicated.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  BookOpen,
  BarChart3,
  Users,
  MessageSquare,
  TrendingUp,
  Gauge,
  FileText,
  Puzzle,
  FlaskConical,
} from 'lucide-react'

const STEPS = [
  {
    id: 'overview',
    icon: BarChart3,
    title: 'Overview',
    keywords: 'overview kpi metrics recent sessions total users cases active',
    body: (
      <p className="text-gray-700">
        The{' '}
        <Link to="/admin" className="text-apex-700 font-medium hover:underline">
          Admin
        </Link>{' '}
        console opens on Overview: platform-wide KPI tiles (users, cases, active/completed
        sessions, average scores) and a feed of the most recent sessions across every trainee.
      </p>
    ),
  },
  {
    id: 'users',
    icon: Users,
    title: 'User Management',
    keywords: 'users user management role trainee admin researcher promote',
    body: (
      <p className="text-gray-700">
        The Users tab lists every account on the platform and lets you change a user's role
        between trainee, admin, and researcher. Role changes take effect on that user's next
        request -- no re-login required on their end.
      </p>
    ),
  },
  {
    id: 'sessions',
    icon: MessageSquare,
    title: 'Session Logs',
    keywords: 'session logs sessions transcripts filter case evaluator status',
    body: (
      <p className="text-gray-700">
        Session Logs shows every session on the platform, not just your own, with filters by
        case, evaluator, and state. Opening one shows the full transcript, metadata, and (if
        scored) feedback -- the same detail a trainee sees on their own session, with the
        trainee's real identity attached.
      </p>
    ),
  },
  {
    id: 'analytics',
    icon: TrendingUp,
    title: 'Analytics',
    keywords: 'analytics aggregate cohort case stats performance trends',
    body: (
      <p className="text-gray-700">
        The Analytics tab aggregates cohort-wide performance: average scores by month, session
        completion by case, and a breakdown of case categories -- the platform-wide counterpart
        to a trainee's own personal Analytics page.
      </p>
    ),
  },
  {
    id: 'usage',
    icon: Gauge,
    title: 'Usage',
    keywords: 'usage dashboard trend daily limits global chat turns audio live evaluation',
    body: (
      <p className="text-gray-700">
        The Usage tab shows today's platform-wide count against the daily guardrail limits for
        chat turns, audio requests, and live evaluator runs, plus a 14-day trend chart -- useful
        for spotting whether the shared deployment is trending toward a cap before it happens.
      </p>
    ),
  },
  {
    id: 'cases',
    icon: FileText,
    title: 'Case Management',
    keywords: 'case management create edit delete case patient model evaluator plugin',
    body: (
      <p className="text-gray-700">
        Case Management is where training scenarios are authored: title, background, the
        patient and evaluator plugins to use, and the expected SPIKES flow. Cases created or
        edited here are immediately available to every trainee.
      </p>
    ),
  },
  {
    id: 'plugins',
    icon: Puzzle,
    title: 'Plugins',
    keywords: 'plugins registry evaluator patient model metrics installed lifecycle stage',
    body: (
      <>
        <p className="text-gray-700 mb-3">
          The Plugins tab lists every installed patient-model, evaluator, and metrics plugin,
          plus the Plugin Registry's lifecycle stage for each (draft, experimental, under
          review, promoted, deprecated, retired).
        </p>
        <p className="text-gray-700">
          For the full evaluator run / review / annotate / validate pipeline built on top of
          these plugins, see the{' '}
          <Link
            to="/docs/research-workflow-guide"
            className="inline-flex items-center gap-1 text-apex-700 font-medium hover:underline"
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Research Workflow Guide
          </Link>
          .
        </p>
      </>
    ),
  },
] as const

function stepMatches(keywords: string, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const b = keywords.toLowerCase()
  return q
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => b.includes(w))
}

/**
 * Step-timeline walkthrough of the admin console.
 *
 * @returns Guide page layout
 */
export const AdminGuide = () => {
  const [search, setSearch] = useState('')
  const visibleSteps = STEPS.filter((s) => stepMatches(s.keywords, search))

  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 overflow-y-auto md:ml-64 bg-gray-50">
          <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
            <nav className="mb-4 text-sm text-gray-500">
              <Link to="/admin" className="hover:text-apex-700">
                Admin
              </Link>{' '}
              / <span className="text-gray-900">Admin Guide</span>
            </nav>

            <div className="mb-8 overflow-hidden rounded-2xl bg-gradient-to-br from-apex-700 via-apex-600 to-emerald-600 px-8 py-10 text-white shadow-sm">
              <div className="flex items-center gap-2 text-apex-100">
                <BookOpen className="h-5 w-5" />
                <span className="text-sm font-semibold uppercase tracking-wide">Admin guide</span>
              </div>
              <h1 className="mt-3 text-3xl font-bold">Overview, users, sessions, cases, plugins</h1>
              <p className="mt-2 max-w-xl text-apex-50">
                Seven things to know, start to finish -- jump to any of them below.
              </p>
              <div className="mt-5 max-w-sm">
                <label htmlFor="admin-guide-search" className="sr-only">
                  Search this guide
                </label>
                <Input
                  id="admin-guide-search"
                  type="search"
                  placeholder="Search by keyword…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-white/95 text-gray-900"
                />
              </div>
            </div>

            <div className="mb-8 flex flex-wrap gap-2">
              {STEPS.map((step, index) => {
                const disabled = !stepMatches(step.keywords, search)
                return (
                  <button
                    key={step.id}
                    type="button"
                    disabled={disabled}
                    onClick={() => {
                      const el = document.getElementById(step.id)
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
                    }}
                    className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-apex-300 hover:text-apex-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-apex-100 text-xs font-semibold text-apex-800">
                      {index + 1}
                    </span>
                    {step.title}
                  </button>
                )
              })}
            </div>

            {search.trim() && visibleSteps.length === 0 && (
              <p className="mb-6 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                No steps match &quot;{search.trim()}&quot;. Clear the search box to see the full guide.
              </p>
            )}

            <div className="space-y-4">
              {STEPS.map((step, index) => {
                const Icon = step.icon
                const visible = stepMatches(step.keywords, search)
                return (
                  <Card key={step.id} id={step.id} className={visible ? '' : 'hidden'}>
                    <CardContent className="flex gap-4 py-6">
                      <div className="flex flex-col items-center">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-apex-100 text-apex-800">
                          <Icon className="h-5 w-5" />
                        </div>
                        {index < STEPS.length - 1 && (
                          <div className="mt-2 w-px flex-1 bg-gray-200" aria-hidden="true" />
                        )}
                      </div>
                      <div className="flex-1 pb-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-apex-600">
                          {index + 1}
                        </p>
                        <h2 className="mt-0.5 text-lg font-semibold text-gray-900">{step.title}</h2>
                        <div className="mt-2 text-sm leading-relaxed">{step.body}</div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>

            <div className="mt-8 flex justify-center">
              <Link to="/admin">
                <Button size="sm">Go to Admin console</Button>
              </Link>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
