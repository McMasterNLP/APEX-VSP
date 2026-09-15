import { RatioValueCell } from './RatioValueCell'
import type { SpanClassificationMetrics } from '@/types/researchEvaluation'

/**
 * Per-label precision/recall/F1 table plus micro/macro summary rows for one validation run's
 * span-classification results.
 *
 * @remarks
 * Only the `span_classification` metric family is computed today (Item 3A), so this is the
 * only results table this pass builds — no picker implying other metric families exist. The
 * macro row's footnote lists labels excluded from the macro average (those without a
 * `computed` F1, e.g. no reference support) so a reader never mistakes "excluded" for "scored
 * as zero" — matching how Item 3A's own metric engine computes the macro average.
 */
export function ValidationResultsTable({ metrics }: { metrics: SpanClassificationMetrics }) {
  const excludedFromMacro = metrics.per_label.filter((label) => label.f1.status !== 'computed')

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Label</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Support</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Predicted</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">TP</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">FP</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">FN</th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Precision</th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">Recall</th>
              <th className="px-3 py-2 text-left font-medium text-gray-600">F1</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {metrics.per_label.map((label) => (
              <tr key={label.label}>
                <td className="px-3 py-2 font-medium text-gray-900">{label.label}</td>
                <td className="px-3 py-2 text-right text-gray-700">{label.support}</td>
                <td className="px-3 py-2 text-right text-gray-700">{label.predicted_count}</td>
                <td className="px-3 py-2 text-right text-gray-700">{label.true_positives}</td>
                <td className="px-3 py-2 text-right text-gray-700">{label.false_positives}</td>
                <td className="px-3 py-2 text-right text-gray-700">{label.false_negatives}</td>
                <td className="px-3 py-2"><RatioValueCell ratio={label.precision} /></td>
                <td className="px-3 py-2"><RatioValueCell ratio={label.recall} /></td>
                <td className="px-3 py-2"><RatioValueCell ratio={label.f1} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot className="divide-y divide-gray-100 border-t-2 border-gray-300 bg-gray-50 font-medium">
            <tr>
              <td className="px-3 py-2 text-gray-900" colSpan={2}>
                Micro average
              </td>
              <td className="px-3 py-2" />
              <td className="px-3 py-2 text-right text-gray-700">{metrics.micro.true_positives}</td>
              <td className="px-3 py-2 text-right text-gray-700">{metrics.micro.false_positives}</td>
              <td className="px-3 py-2 text-right text-gray-700">{metrics.micro.false_negatives}</td>
              <td className="px-3 py-2"><RatioValueCell ratio={metrics.micro.precision} /></td>
              <td className="px-3 py-2"><RatioValueCell ratio={metrics.micro.recall} /></td>
              <td className="px-3 py-2"><RatioValueCell ratio={metrics.micro.f1} /></td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-gray-900" colSpan={2}>
                Macro average
                <span className="ml-1 font-normal text-gray-500">
                  ({metrics.macro.labels_included} label
                  {metrics.macro.labels_included === 1 ? '' : 's'} included)
                </span>
              </td>
              <td className="px-3 py-2" />
              <td className="px-3 py-2 text-right text-gray-700">{metrics.macro.true_positives}</td>
              <td className="px-3 py-2 text-right text-gray-700">{metrics.macro.false_positives}</td>
              <td className="px-3 py-2 text-right text-gray-700">{metrics.macro.false_negatives}</td>
              <td className="px-3 py-2"><RatioValueCell ratio={metrics.macro.precision} /></td>
              <td className="px-3 py-2"><RatioValueCell ratio={metrics.macro.recall} /></td>
              <td className="px-3 py-2"><RatioValueCell ratio={metrics.macro.f1} /></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {excludedFromMacro.length > 0 && (
        <p className="text-xs text-gray-600">
          Excluded from the macro average (no computed F1):{' '}
          {excludedFromMacro
            .map((label) => `${label.label} (${label.f1.status.replaceAll('_', ' ')})`)
            .join(', ')}
          .
        </p>
      )}

      <p className="text-xs text-gray-500">
        Matching policy: {metrics.matching_policy_identifier} v{metrics.matching_policy_version} ·
        Metric implementation: {metrics.metric_implementation_version}
      </p>
    </div>
  )
}
