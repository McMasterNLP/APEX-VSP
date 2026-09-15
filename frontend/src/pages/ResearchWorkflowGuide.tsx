/**
 * Researcher-facing guide to the session evaluation/annotation/validation pipeline
 * (the Evaluate Sessions workflow).
 *
 * @remarks
 * Deliberately NOT styled like `PluginDeveloperGuide.tsx` (a left-rail table-of-contents
 * over dense prose) -- that page is admin-only technical reference; this one is a
 * product walkthrough for researchers, so it reads as a numbered step timeline with a
 * hero header, matching the Research Overview tab's visual language instead.
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
  ClipboardCheck,
  PlayCircle,
  ClipboardEdit,
  ShieldCheck,
  Download,
  Lock as LockIcon,
} from 'lucide-react'
import {
  MockFilterBarPreview,
  MockRunEvaluatorPreview,
  MockSpanCorrectionPreview,
  MockValidationPreview,
  MockExportPreview,
} from '@/components/research/WorkflowPreviewMocks'

/** One step in the workflow timeline: an id (anchor), icon, title, and searchable keywords. */
const STEPS = [
  {
    id: 'finding-sessions',
    icon: ClipboardCheck,
    title: 'Find a session',
    keywords:
      'finding sessions evaluate sessions tab filter case patient plugin evaluator plugin state status chip needs review in review locked no runs yet',
    body: (
      <>
        <p className="text-gray-700 mb-3">
          The{' '}
          <Link to="/research?tab=evaluate" className="text-apex-700 font-medium hover:underline">
            Evaluate Sessions
          </Link>{' '}
          tab lists real (non-anonymized) sessions available for evaluation. Filter by case,
          state, patient/evaluator plugin, evaluation status, or evaluator to narrow it down --
          filters live in the URL, so a filtered view can be bookmarked or shared.
        </p>
        <p className="text-gray-700">
          The status chip tells you where a session stands:{' '}
          <span className="font-medium">No runs yet</span> &rarr;{' '}
          <span className="font-medium">Needs review</span> &rarr;{' '}
          <span className="font-medium">In review</span> &rarr;{' '}
          <span className="font-medium">Locked</span>.
        </p>
        <div className="mt-3">
          <MockFilterBarPreview />
        </div>
      </>
    ),
  },
  {
    id: 'running-evaluations',
    icon: PlayCircle,
    title: 'Run an evaluation',
    keywords:
      'run compare evaluator plugin evaluation run immutable transcript hash reproducibility saved runs',
    body: (
      <>
        <p className="text-gray-700 mb-3">
          Opening a session lands on its <span className="font-medium">Overview</span> tab. From{' '}
          <span className="font-medium">Run &amp; Compare</span>, execute a registered evaluator
          plugin against the session's transcript.
        </p>
        <p className="text-gray-700">
          Each execution creates an <span className="font-medium">immutable evaluation run</span>{' '}
          -- the transcript snapshot, evaluator identity/version, and every prediction are frozen
          and can never be edited, only superseded by a new run. Past runs are listed under{' '}
          <span className="font-medium">Saved Runs</span> for comparison.
        </p>
        <div className="mt-3">
          <MockRunEvaluatorPreview />
        </div>
      </>
    ),
  },
  {
    id: 'annotating',
    icon: ClipboardEdit,
    title: 'Review & annotate',
    keywords:
      'review annotate annotation set correct prediction span boundaries rating correction coverage declaration lock locking reviewer note',
    body: (
      <>
        <p className="text-gray-700 mb-3">
          On <span className="font-medium">Review &amp; Annotate</span>, go through an evaluation
          run's predictions and accept or correct each one -- click{' '}
          <span className="font-medium">Correct prediction</span> to flag a span label as wrong or
          enter a corrected rating (span boundaries themselves can't be moved). Not every
          prediction type is correctable -- relation and global-metric predictions, for example,
          aren't, and that's expected.
        </p>
        <p className="text-gray-700">
          A <span className="font-medium">coverage declaration</span> records how thoroughly you
          reviewed the eligible predictions, and <span className="font-medium">locking</span> the
          annotation set marks it complete (a locked set can still be reopened).
        </p>
        <div className="mt-3">
          <MockSpanCorrectionPreview />
        </div>
      </>
    ),
  },
  {
    id: 'validating',
    icon: ShieldCheck,
    title: 'Validate the result',
    keywords:
      'validate validation run engine dashboard archive unarchive transcript hash mismatch exhaustive coverage',
    body: (
      <>
        <p className="text-gray-700 mb-3">
          The <span className="font-medium">Validate</span> tab runs the validation engine and
          surfaces agreement metrics, warnings, and framework-level checks. If the transcript has
          changed since the evaluation run was created, a transcript-hash mismatch warning appears
          before you can submit -- catching stale comparisons before they happen.
        </p>
        <p className="text-gray-700">
          Superseded validation runs can be archived (hidden from the default list, never
          deleted) -- toggle "Show archived runs" to bring them back into view.
        </p>
        <div className="mt-3">
          <MockValidationPreview />
        </div>
      </>
    ),
  },
  {
    id: 'exporting',
    icon: Download,
    title: 'Export',
    keywords: 'export full json framework native projection tabular zip download csv',
    body: (
      <>
        <p className="text-gray-700">
          The <span className="font-medium">Export</span> tab produces four preview formats --{' '}
          <span className="font-medium">Full JSON</span>,{' '}
          <span className="font-medium">Framework-native JSON</span>,{' '}
          <span className="font-medium">Projection JSON</span>, and{' '}
          <span className="font-medium">Tabular ZIP</span> -- plus saved-run/review and validation
          exports. Raw transcript content is never included; you get predictions, corrections, and
          metadata for downstream analysis.
        </p>
        <div className="mt-3">
          <MockExportPreview />
        </div>
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
 * Step-timeline walkthrough of the Evaluate Sessions workflow, for admins and researchers.
 *
 * @returns Guide page layout
 */
export const ResearchWorkflowGuide = () => {
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
              <Link to="/research" className="hover:text-apex-700">
                Research
              </Link>{' '}
              / <span className="text-gray-900">Workflow Guide</span>
            </nav>

            <div className="mb-8 overflow-hidden rounded-2xl bg-gradient-to-br from-apex-700 via-apex-600 to-emerald-600 px-8 py-10 text-white shadow-sm">
              <div className="flex items-center gap-2 text-apex-100">
                <BookOpen className="h-5 w-5" />
                <span className="text-sm font-semibold uppercase tracking-wide">Workflow guide</span>
              </div>
              <h1 className="mt-3 text-3xl font-bold">Find, evaluate, annotate, validate, export</h1>
              <p className="mt-2 max-w-xl text-apex-50">
                Five steps, start to finish -- jump to any of them below.
              </p>
              <div className="mt-5 max-w-sm">
                <label htmlFor="workflow-search" className="sr-only">
                  Search this guide
                </label>
                <Input
                  id="workflow-search"
                  type="search"
                  placeholder="Search steps by keyword…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-white/95 text-gray-900"
                />
              </div>
            </div>

            {/* Step quick-nav pills */}
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

            {/* Step timeline */}
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
                          Step {index + 1}
                        </p>
                        <h2 className="mt-0.5 text-lg font-semibold text-gray-900">{step.title}</h2>
                        <div className="mt-2 text-sm leading-relaxed">{step.body}</div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>

            {/* Access & privacy */}
            <Card className="mt-6">
              <CardContent className="py-6">
                <div className="mb-3 flex items-center gap-2">
                  <LockIcon className="h-5 w-5 text-apex-600" />
                  <h2 className="text-lg font-semibold text-gray-900">Access &amp; privacy</h2>
                </div>
                <p className="text-gray-700 mb-4">
                  Admins and researchers see the same sessions and the same real transcripts --
                  the pipeline needs the real transcript to score and review against. What differs
                  is trainee identity:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="text-left px-4 py-2 font-semibold text-gray-700">Role</th>
                        <th className="text-left px-4 py-2 font-semibold text-gray-700">Session transcript</th>
                        <th className="text-left px-4 py-2 font-semibold text-gray-700">Trainee name / email</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                      <tr>
                        <td className="px-4 py-2 font-medium text-gray-900">Admin</td>
                        <td className="px-4 py-2 text-gray-700">Real, full access</td>
                        <td className="px-4 py-2 text-gray-700">Real name and email</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2 font-medium text-gray-900">Researcher</td>
                        <td className="px-4 py-2 text-gray-700">Real, full access</td>
                        <td className="px-4 py-2 text-gray-700">
                          Pseudonymous reference (e.g. <span className="font-mono text-xs">participant_a1b2c3d4…</span>)
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="text-gray-700 mt-4">
                  This is separate from the fully anonymized data on the{' '}
                  <Link to="/research?tab=analytics" className="text-apex-700 font-medium hover:underline">
                    Analytics
                  </Link>{' '}
                  tab, which aggregates and hashes session data for fairness auditing rather than
                  per-session review.
                </p>
              </CardContent>
            </Card>

            <div className="mt-8 flex justify-center">
              <Link to="/research?tab=evaluate">
                <Button size="sm">Go to Evaluate Sessions</Button>
              </Link>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
