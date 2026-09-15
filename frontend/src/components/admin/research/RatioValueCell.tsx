import { Info } from 'lucide-react'
import type { RatioResult, RatioStatus } from '@/types/researchEvaluation'

/** Human label for each non-computed {@link RatioStatus}. */
const STATUS_LABEL: Record<Exclude<RatioStatus, 'computed'>, string> = {
  ineligible: 'Ineligible',
  no_reference_support: 'No reference support',
  no_predicted_support: 'No predicted support',
}

/** Renders an exact fraction string (e.g. "2/3", "1", "0") as a decimal for readability. */
function fractionToDecimal(value: string): string {
  const [numerator, denominator] = value.split('/')
  const n = Number(numerator)
  const d = denominator !== undefined ? Number(denominator) : 1
  if (!Number.isFinite(n) || !Number.isFinite(d) || d === 0) return value
  return (n / d).toFixed(3)
}

/**
 * Renders one precision/recall/F1 cell, distinguishing a real computed value from every
 * "not available" status.
 *
 * @remarks
 * This is the single highest-risk-of-silent-bug part of Item 3B: `ineligible`,
 * `no_reference_support`, and `no_predicted_support` must never look like a computed
 * score of zero to someone skimming the table. A computed value renders as plain text
 * (the fraction plus a decimal); every other status renders with a distinct amber
 * "not available" pill carrying its reason as both a `title` tooltip and a visible
 * caption (the underlying `note`, when present) — never blank, never a bare "0".
 */
export function RatioValueCell({ ratio }: { ratio: RatioResult }) {
  if (ratio.status === 'computed') {
    if (ratio.value === null) return null
    return (
      <span className="whitespace-nowrap font-mono text-sm text-gray-900">
        {ratio.value}{' '}
        <span className="text-xs text-gray-500">({fractionToDecimal(ratio.value)})</span>
      </span>
    )
  }

  const label = STATUS_LABEL[ratio.status]
  return (
    <span
      className="inline-flex max-w-[12rem] flex-col gap-0.5"
      data-testid="ratio-not-available"
    >
      <span
        title={ratio.note ?? label}
        className="inline-flex w-fit items-center gap-1 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-800"
      >
        <Info className="h-3 w-3" aria-hidden="true" />
        N/A &middot; {label}
      </span>
      {ratio.note && <span className="text-[11px] leading-tight text-gray-500">{ratio.note}</span>}
    </span>
  )
}
