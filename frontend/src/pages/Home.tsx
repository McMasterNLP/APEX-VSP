/**
 * Marketing landing for the APEX research platform; redirects authenticated users to the dashboard.
 */
import { Link, Navigate } from 'react-router-dom'
import { useAuthGate } from '@/hooks/useAuthGate'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { MessageSquare, BarChart3, Puzzle, ArrowRight, Microscope, ShieldCheck } from 'lucide-react'

/** Static hero visual: conversation + structured evaluation output. No live data. */
function HeroConversationMock() {
  return (
    <div
      className="relative mx-auto w-full rounded-3xl border border-gray-300/90 bg-white shadow-[0_8px_30px_rgba(15,23,42,0.08),0_32px_64px_-16px_rgba(15,23,42,0.18)] ring-1 ring-gray-950/[0.06]"
      aria-hidden
    >
      {/* Window chrome */}
      <div className="flex items-center gap-2 rounded-t-3xl border-b border-gray-200 bg-gray-100 px-5 py-3.5">
        <span className="flex gap-1.5">
          <span className="h-3 w-3 rounded-full bg-gray-400" />
          <span className="h-3 w-3 rounded-full bg-gray-300" />
          <span className="h-3 w-3 rounded-full bg-gray-300" />
        </span>
        <span className="flex-1 truncate px-2 text-center text-xs font-semibold tracking-wide text-gray-500 uppercase">
          APEX · Session ID #A-2049 · Scenario: Breaking bad news
        </span>
      </div>

      <div className="space-y-5 p-6 sm:p-8">
        {/* Simulated Patient */}
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-slate-400" />
            Simulated Patient
          </p>
          <div className="flex justify-start">
            <div className="max-w-[90%] rounded-2xl rounded-tl-sm border border-slate-300 bg-slate-100 px-5 py-3.5 text-[0.9375rem] leading-relaxed text-gray-950 shadow-sm">
              I&apos;m worried about what the scan might show. Can you walk me through what happens next?
            </div>
          </div>
        </div>

        {/* Clinician Response */}
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-600" />
            Clinician Response
          </p>
          <div className="flex justify-end">
            <div className="max-w-[90%] rounded-2xl rounded-tr-sm border border-emerald-700/30 bg-emerald-50 px-5 py-3.5 text-[0.9375rem] leading-relaxed text-gray-950 shadow-sm">
              I understand this is unsettling. I&apos;ll explain the results in plain language, then we&apos;ll
              discuss options together.
            </div>
          </div>
        </div>

        {/* Evaluation Output */}
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-teal-600" />
            Evaluation Output
          </p>
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
            {/* Headline score */}
            <div className="mb-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700">SPIKES Score</p>
                <p className="text-xs text-gray-600 mt-0.5">Primary framework metric</p>
              </div>
              <span className="text-3xl font-bold tabular-nums text-emerald-800">8.4<span className="text-base font-medium text-emerald-600">/10</span></span>
            </div>

            {/* Secondary metrics */}
            <div className="space-y-3.5">
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-medium text-gray-700">Empathy</span>
                  <span className="font-semibold tabular-nums text-gray-900">7.9 / 10</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
                  <div className="h-full w-[79%] rounded-full bg-emerald-600" />
                </div>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between text-sm">
                  <span className="font-medium text-gray-700">Clarity</span>
                  <span className="font-semibold tabular-nums text-gray-900">8.8 / 10</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
                  <div className="h-full w-[88%] rounded-full bg-teal-600" />
                </div>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <span className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700">AFCE aligned</span>
                <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">Empathic opportunity: addressed</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export const Home = () => {
  const gate = useAuthGate()

  if (gate === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center text-gray-500">
        Loading...
      </div>
    )
  }

  if (gate === 'authed') {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 via-white to-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">

        {/* ── Hero ──────────────────────────────────────────────────── */}
        <section className="mb-24 lg:mb-32">
          <div className="grid items-start gap-14 lg:grid-cols-[1fr_1.15fr] lg:gap-16">

            {/* Left: copy */}
            <div className="order-2 text-center lg:order-1 lg:text-left lg:pt-6">
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 shadow-sm">
                <Microscope className="h-3.5 w-3.5 text-emerald-700" aria-hidden />
                APEX — Clinical Research Platform
              </div>

              <h1 className="text-balance text-4xl font-bold tracking-tight text-gray-950 sm:text-5xl xl:text-[3rem] xl:leading-[1.07]">
                Clinical communication research with AI-simulated patients
              </h1>

              <p className="mx-auto mt-5 max-w-lg text-lg leading-relaxed text-gray-600 lg:mx-0">
                Run controlled simulated interactions, score sessions against validated frameworks, and generate
                structured outputs designed for downstream analysis and reproducible experimentation.
              </p>

              {/* Credibility indicators */}
              <ul className="mt-7 flex flex-wrap justify-center gap-2 lg:justify-start" aria-label="Platform properties">
                <li className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm">
                  Supports SPIKES and AFCE frameworks
                </li>
                <li className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm">
                  Reproducible experimental workflows
                </li>
                <li className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm">
                  Structured, analysis-ready outputs
                </li>
              </ul>

              {/* CTAs */}
              <div className="mt-9 flex flex-wrap justify-center gap-3 lg:justify-start">
                <Link to="/login">
                  <Button
                    size="lg"
                    className="h-11 rounded-lg bg-emerald-700 px-7 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800"
                  >
                    Start a simulated session
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
                <Link to="/login">
                  <Button
                    size="lg"
                    variant="outline"
                    className="h-11 rounded-lg border-gray-300 px-7 text-sm font-medium text-gray-800 shadow-sm hover:bg-gray-50"
                  >
                    View sample output
                  </Button>
                </Link>
              </div>
              <p className="mt-3 text-xs text-gray-500 text-center lg:text-left">
                Begin with a predefined clinical scenario
              </p>
            </div>

            {/* Right: mock */}
            <div className="order-1 lg:order-2">
              <HeroConversationMock />
            </div>
          </div>
        </section>

        {/* ── Feature cards ─────────────────────────────────────────── */}
        <section className="mb-24" aria-labelledby="features-heading">
          <h2 id="features-heading" className="sr-only">Platform capabilities</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <Card className="border-gray-200 bg-white shadow-sm">
              <CardHeader>
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-100">
                  <MessageSquare className="h-5 w-5 text-emerald-700" />
                </div>
                <CardTitle className="text-base font-semibold text-gray-950">
                  Simulated clinical dialogue
                </CardTitle>
                <CardDescription className="text-sm leading-relaxed text-gray-600">
                  Generate controlled doctor–patient interactions with configurable AI patients.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-gray-200 bg-white shadow-sm">
              <CardHeader>
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-100">
                  <BarChart3 className="h-5 w-5 text-emerald-700" />
                </div>
                <CardTitle className="text-base font-semibold text-gray-950">
                  Framework-aligned evaluation
                </CardTitle>
                <CardDescription className="text-sm leading-relaxed text-gray-600">
                  Score communication using validated frameworks such as SPIKES and AFCE.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-gray-200 bg-white shadow-sm">
              <CardHeader>
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-amber-100">
                  <ShieldCheck className="h-5 w-5 text-amber-700" />
                </div>
                <CardTitle className="text-base font-semibold text-gray-950">
                  Human-validated evaluators
                </CardTitle>
                <CardDescription className="text-sm leading-relaxed text-gray-600">
                  Reviewers confirm, correct, and annotate every evaluator prediction, then
                  validate the evaluator against that human judgment -- not a black box.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-gray-200 bg-white shadow-sm">
              <CardHeader>
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-purple-100">
                  <Puzzle className="h-5 w-5 text-purple-700" />
                </div>
                <CardTitle className="text-base font-semibold text-gray-950">
                  Modular research stack
                </CardTitle>
                <CardDescription className="text-sm leading-relaxed text-gray-600">
                  Integrate models, evaluators, and export structured datasets for analysis.
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </section>

        {/* ── What you get from each session ───────────────────────── */}
        <section className="mb-24 rounded-2xl border border-gray-200 bg-white px-8 py-12 shadow-sm" aria-labelledby="outputs-heading">
          <div className="mb-10 text-center">
            <h2 id="outputs-heading" className="text-2xl font-bold tracking-tight text-gray-950 sm:text-3xl">
              What you get from each session
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-base text-gray-500">
              Every session produces three concrete, reusable outputs.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-3">

            {/* 01: Conversation transcript */}
            <div className="flex flex-col gap-4 rounded-xl bg-gray-50 p-5">
              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">01</p>
                <h3 className="text-sm font-semibold text-gray-950">Conversation transcript</h3>
              </div>
              <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-4 font-mono text-[11px] leading-relaxed text-gray-700 shadow-sm">
                <p><span className="font-semibold text-slate-500">[P]</span> I&apos;m worried about what the scan might show.</p>
                <p><span className="font-semibold text-emerald-700">[C]</span> I understand. I&apos;ll explain the results clearly.</p>
                <p><span className="font-semibold text-slate-500">[P]</span> Will I need treatment straight away?</p>
                <p><span className="font-semibold text-emerald-700">[C]</span> That depends on what we find. Let&apos;s go through it step by step.</p>
                <p className="text-gray-400">— turn 3 of 12 · scenario: breaking bad news</p>
              </div>
            </div>

            {/* 02: Structured evaluation */}
            <div className="flex flex-col gap-4 rounded-xl bg-gray-50 p-5">
              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">02</p>
                <h3 className="text-sm font-semibold text-gray-950">Structured evaluation</h3>
              </div>
              <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">SPIKES score</span>
                  <span className="text-xl font-bold tabular-nums text-emerald-800">8.4<span className="text-xs font-medium text-gray-500"> / 10</span></span>
                </div>
                <div className="space-y-2.5">
                  {[
                    { label: 'Empathy', value: '7.9', pct: '79%', color: 'bg-emerald-600' },
                    { label: 'Clarity', value: '8.8', pct: '88%', color: 'bg-teal-600' },
                  ].map(({ label, value, pct, color }) => (
                    <div key={label} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-700">{label}</span>
                        <span className="font-semibold tabular-nums text-gray-900">{value}</span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                        <div className={`h-full rounded-full ${color}`} style={{ width: pct }} />
                      </div>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-[11px] text-gray-400">Frameworks: SPIKES · AFCE</p>
              </div>
            </div>

            {/* 03: Exportable dataset */}
            <div className="flex flex-col gap-4 rounded-xl bg-gray-50 p-5">
              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">03</p>
                <h3 className="text-sm font-semibold text-gray-950">Exportable dataset</h3>
              </div>
              <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                <table className="w-full min-w-[320px] text-[11px] tabular-nums">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50">
                      {['session_id', 'spikes', 'empathy', 'transcript_id'].map((col) => (
                        <th key={col} className="whitespace-nowrap px-3 py-2 text-left font-semibold text-gray-500">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 font-mono">
                    <tr>
                      <td className="px-3 py-2 text-gray-700">A-2049</td>
                      <td className="px-3 py-2 text-emerald-800 font-semibold">8.4</td>
                      <td className="px-3 py-2 text-emerald-700">7.9</td>
                      <td className="px-3 py-2 text-gray-400">tx-0831</td>
                    </tr>
                    <tr className="bg-gray-50/60">
                      <td className="px-3 py-2 text-gray-700">A-2050</td>
                      <td className="px-3 py-2 text-emerald-800 font-semibold">7.1</td>
                      <td className="px-3 py-2 text-emerald-700">6.8</td>
                      <td className="px-3 py-2 text-gray-400">tx-0832</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 text-gray-700">A-2051</td>
                      <td className="px-3 py-2 text-emerald-800 font-semibold">9.0</td>
                      <td className="px-3 py-2 text-emerald-700">8.5</td>
                      <td className="px-3 py-2 text-gray-400">tx-0833</td>
                    </tr>
                  </tbody>
                </table>
                <p className="border-t border-gray-100 px-3 py-2 text-[10px] text-gray-400">CSV · JSON · analysis-ready</p>
              </div>
            </div>

          </div>
        </section>

        {/* ── Bottom CTA ────────────────────────────────────────────── */}
        <section>
          <div className="rounded-2xl border border-emerald-800 bg-emerald-700 px-8 py-12 text-center shadow-sm">
            <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Run structured clinical communication studies
            </h2>
              <p className="mx-auto mt-4 max-w-xl text-base text-emerald-100">
              Simulate interactions, evaluate communication, and generate analysis-ready outputs.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link to="/login">
                <Button
                  size="lg"
                  className="h-11 rounded-lg bg-white px-8 text-sm font-semibold text-emerald-800 shadow-sm hover:bg-emerald-50"
                >
                  Start a session
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
        </section>

      </div>
    </div>
  )
}
