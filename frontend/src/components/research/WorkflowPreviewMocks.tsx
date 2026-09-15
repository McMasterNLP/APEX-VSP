/**
 * Small, static illustrative "mockup" previews used on the Research Overview page and
 * the Workflow Guide -- stylized panels that suggest what each feature looks like in a
 * compact browser-window frame, without embedding real chart/data libraries or
 * screenshots. Purely decorative; not backed by live data.
 */
import type { ReactNode } from 'react'

/**
 * Wraps a preview in a small window-chrome frame (traffic-light dots + title bar) so it
 * reads as a screenshot preview rather than loose page content.
 *
 * @param title - Text shown in the window's title bar
 * @param children - The mock UI content
 * @returns A compact, fixed-width framed preview
 */
function MockWindowFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[280px] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center gap-1.5 border-b border-gray-200 bg-gray-50 px-3 py-1.5">
        <span className="h-2 w-2 rounded-full bg-red-300" />
        <span className="h-2 w-2 rounded-full bg-amber-300" />
        <span className="h-2 w-2 rounded-full bg-emerald-300" />
        <span className="ml-2 truncate text-[10px] font-medium text-gray-400">{title}</span>
      </div>
      <div className="p-3">{children}</div>
    </div>
  )
}

/** Score-trends line chart, illustrated with plain divs (no chart library). */
export function MockAnalyticsPreview() {
  const bars = [40, 55, 48, 62, 58, 70, 66]
  return (
    <MockWindowFrame title="Score Trends">
      <div className="flex h-20 items-end gap-1.5">
        {bars.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-t bg-gradient-to-t from-apex-500 to-apex-300"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400">
        <span>7-day rolling</span>
        <span className="font-medium text-emerald-600">+12%</span>
      </div>
    </MockWindowFrame>
  )
}

/** Span-level correction: a transcript line with one span highlighted and flagged. */
export function MockSpanCorrectionPreview() {
  return (
    <MockWindowFrame title="Review & Annotate">
      <p className="text-[11px] leading-relaxed text-gray-700">
        "I understand this is difficult news to hear, and{' '}
        <span className="relative rounded bg-amber-200/70 px-0.5 ring-1 ring-amber-400">
          I know exactly how you feel
        </span>
        ."
      </p>
      <div className="mt-2 flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-2 py-1">
        <span className="text-[10px] font-medium text-amber-900">Empathy · flagged</span>
        <span className="rounded bg-apex-600 px-1.5 py-0.5 text-[9px] font-semibold text-white">
          Correct
        </span>
      </div>
    </MockWindowFrame>
  )
}

/** Sessions filter bar with a couple of dropdown pills and a status chip. */
export function MockFilterBarPreview() {
  return (
    <MockWindowFrame title="Evaluate Sessions">
      <div className="flex flex-wrap gap-1.5">
        <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[9px] text-gray-600">Case ▾</span>
        <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[9px] text-gray-600">Plugin ▾</span>
        <span className="rounded border border-apex-300 bg-apex-50 px-1.5 py-0.5 text-[9px] text-apex-800">Status ▾</span>
      </div>
      <div className="mt-2 space-y-1">
        <div className="flex items-center justify-between rounded border border-gray-100 px-1.5 py-1">
          <span className="text-[9px] text-gray-600">Session #382</span>
          <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[8px] font-medium text-amber-900">Needs review</span>
        </div>
        <div className="flex items-center justify-between rounded border border-gray-100 px-1.5 py-1">
          <span className="text-[9px] text-gray-600">Session #379</span>
          <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[8px] font-medium text-emerald-900">Locked</span>
        </div>
      </div>
    </MockWindowFrame>
  )
}

/** "Run evaluator" trigger with a couple of past-run rows underneath. */
export function MockRunEvaluatorPreview() {
  return (
    <MockWindowFrame title="Run & Compare">
      <div className="flex items-center justify-between rounded-md bg-apex-600 px-2 py-1.5">
        <span className="text-[10px] font-medium text-white">Run rubric_v2</span>
        <span className="text-[9px] text-apex-100">▶</span>
      </div>
      <div className="mt-2 space-y-1 text-[9px] text-gray-500">
        <div className="flex justify-between">
          <span>Run #a1b2c3d4</span>
          <span className="text-gray-400">2m ago</span>
        </div>
        <div className="flex justify-between">
          <span>Run #f8e7d6c5</span>
          <span className="text-gray-400">1d ago</span>
        </div>
      </div>
    </MockWindowFrame>
  )
}

/** Validation dashboard: a headline metric plus a transcript-mismatch warning banner. */
export function MockValidationPreview() {
  return (
    <MockWindowFrame title="Validate">
      <div className="flex items-baseline gap-1.5">
        <span className="text-lg font-bold text-gray-900">94%</span>
        <span className="text-[9px] text-gray-500">agreement</span>
      </div>
      <div className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[9px] text-amber-900">
        ⚠ Transcript hash mismatch -- re-run before submitting
      </div>
    </MockWindowFrame>
  )
}

/** Export tab: a small grid of format buttons. */
export function MockExportPreview() {
  const formats = ['Full JSON', 'Framework JSON', 'Projection', 'Tabular ZIP']
  return (
    <MockWindowFrame title="Export">
      <div className="grid grid-cols-2 gap-1.5">
        {formats.map((f) => (
          <div
            key={f}
            className="rounded border border-gray-200 px-1.5 py-1 text-center text-[9px] text-gray-600"
          >
            {f}
          </div>
        ))}
      </div>
    </MockWindowFrame>
  )
}
