/**
 * Trainee-facing guide to the core product loop: dashboard, cases, sessions,
 * feedback, analytics, and usage limits.
 *
 * @remarks
 * Same visual language as `ResearchWorkflowGuide.tsx` (hero header, searchable
 * step timeline) so the guide pages read as one family, not three separately
 * designed docs. Deliberately skips that page's illustrative mock-UI previews
 * to stay quick to build/verify -- the step descriptions link straight to the
 * real pages instead.
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
  LayoutDashboard,
  FileText,
  MessageSquare,
  HeartHandshake,
  LineChart,
  Gauge,
} from 'lucide-react'

const STEPS = [
  {
    id: 'dashboard',
    icon: LayoutDashboard,
    title: 'Dashboard',
    keywords: 'dashboard home active sessions completed sessions start new session stats',
    body: (
      <p className="text-gray-700">
        Your{' '}
        <Link to="/dashboard" className="text-apex-700 font-medium hover:underline">
          Dashboard
        </Link>{' '}
        is the landing page after login: your active and recently completed sessions, quick
        stats on your own SPIKES-stage coverage, and a shortcut to start a new session on any
        case.
      </p>
    ),
  },
  {
    id: 'cases',
    icon: FileText,
    title: 'Cases',
    keywords: 'cases case library browse category difficulty start session',
    body: (
      <p className="text-gray-700">
        <Link to="/cases" className="text-apex-700 font-medium hover:underline">
          Cases
        </Link>{' '}
        lists every training scenario available to you -- title, category, and a short
        description of the situation. Opening one shows the full case background and a
        single button to start a session against it.
      </p>
    ),
  },
  {
    id: 'sessions',
    icon: MessageSquare,
    title: 'Running a session',
    keywords: 'session chat conversation text audio voice tone spikes stage end session',
    body: (
      <>
        <p className="text-gray-700 mb-3">
          Inside a session you can respond by typing or recording audio -- either is
          transcribed and analyzed for tone the same way. A live SPIKES-stage tracker shows
          which stage of the breaking-bad-news framework the conversation has reached.
        </p>
        <p className="text-gray-700">
          Ending a session locks the transcript and immediately triggers scoring -- you land on
          your Feedback view for that session right after.
        </p>
      </>
    ),
  },
  {
    id: 'feedback',
    icon: HeartHandshake,
    title: 'Feedback',
    keywords: 'feedback empathy score communication score spikes completion overall score',
    body: (
      <p className="text-gray-700">
        Every completed session gets an Empathy score, a Communication score, a SPIKES
        completion score, and an Overall score, plus written strengths and areas for
        improvement. You can reopen any past session from{' '}
        <Link to="/sessions" className="text-apex-700 font-medium hover:underline">
          My Sessions
        </Link>{' '}
        to revisit its transcript and feedback together.
      </p>
    ),
  },
  {
    id: 'analytics',
    icon: LineChart,
    title: 'Analytics',
    keywords: 'analytics trends performance over time progress',
    body: (
      <p className="text-gray-700">
        <Link to="/analytics" className="text-apex-700 font-medium hover:underline">
          Analytics
        </Link>{' '}
        charts your own performance across sessions over time, so you can see whether empathy,
        communication, and SPIKES completion are trending the way you'd expect session to
        session, not just within one conversation.
      </p>
    ),
  },
  {
    id: 'usage',
    icon: Gauge,
    title: 'Usage limits',
    keywords: 'usage limits daily cap chat turns audio live evaluation rate limit',
    body: (
      <p className="text-gray-700">
        <Link to="/usage" className="text-apex-700 font-medium hover:underline">
          Usage
        </Link>{' '}
        shows today's count against your daily limits on chat turns and audio requests --
        this is a shared deployment, so those limits keep it available for everyone. Counters
        reset at midnight UTC.
      </p>
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
 * Step-timeline walkthrough of the core trainee-facing product loop.
 *
 * @returns Guide page layout
 */
export const UserGuide = () => {
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
              <Link to="/dashboard" className="hover:text-apex-700">
                Dashboard
              </Link>{' '}
              / <span className="text-gray-900">User Guide</span>
            </nav>

            <div className="mb-8 overflow-hidden rounded-2xl bg-gradient-to-br from-apex-700 via-apex-600 to-emerald-600 px-8 py-10 text-white shadow-sm">
              <div className="flex items-center gap-2 text-apex-100">
                <BookOpen className="h-5 w-5" />
                <span className="text-sm font-semibold uppercase tracking-wide">User guide</span>
              </div>
              <h1 className="mt-3 text-3xl font-bold">Dashboard, cases, sessions, feedback</h1>
              <p className="mt-2 max-w-xl text-apex-50">
                Six things to know, start to finish -- jump to any of them below.
              </p>
              <div className="mt-5 max-w-sm">
                <label htmlFor="user-guide-search" className="sr-only">
                  Search this guide
                </label>
                <Input
                  id="user-guide-search"
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
              <Link to="/dashboard">
                <Button size="sm">Go to Dashboard</Button>
              </Link>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
