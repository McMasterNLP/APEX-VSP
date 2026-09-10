import type { FrameworkNativeResult } from '@/types/researchEvaluation'

const humanize = (value: string) => value.replaceAll('_', ' ')

export function FrameworkNativeView({ result }: { result: FrameworkNativeResult | null | undefined }) {
  if (!result) return <p className="text-sm text-gray-600">No framework-specific data is available.</p>

  switch (result.native_type) {
    case 'apex_feedback':
      return (
        <div className="space-y-3 text-sm">
          <p className="rounded-md border border-indigo-200 bg-indigo-50 p-3 font-medium text-indigo-950">
            {result.framework_statement}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border p-3">
              <p className="font-medium">Opportunity / elicitation / response</p>
              <p className="mt-1 text-gray-700">
                {result.eo_spans.length} opportunities · {result.elicitation_spans.length} elicitations · {result.response_spans.length} responses
              </p>
              <p className="mt-1 text-gray-700">{result.missed_opportunities.length} missed opportunities</p>
            </div>
            <div className="rounded-md border p-3">
              <p className="font-medium">SPIKES coverage</p>
              <p className="mt-1 text-gray-700">{Math.round(result.spikes_coverage.percent * 100)}% · {result.spikes_coverage.covered.join(', ') || 'No stages'}</p>
            </div>
          </div>
          <details className="rounded-md border p-3">
            <summary className="cursor-pointer font-medium outline-none focus:ring-2 focus:ring-indigo-600">Structured native result</summary>
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words bg-gray-950 p-3 text-xs text-gray-50">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )
    case 'ace_ct_inspired':
      return (
        <div className="space-y-3 text-sm">
          <p className="rounded-md border border-red-300 bg-red-50 p-3 font-semibold text-red-950">
            Experimental · Unvalidated · Non-official · Not a reproduction of the confidential manuscript’s trained models
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {result.framework_results.domain_scores.map((domain) => (
              <div key={domain.domain} className="rounded-md border p-3">
                <p className="font-medium capitalize">{humanize(domain.domain)}</p>
                <p className="mt-1 text-gray-700">
                  {domain.mean_score == null ? 'Unavailable' : `${domain.mean_score.toFixed(2)} / 5`}
                </p>
                <p className="text-xs text-gray-500">{domain.scored_dimension_count} scored dimensions</p>
              </div>
            ))}
          </div>
          <p className="text-gray-700">
            {result.framework_results.dimension_results.length} dimensions · {result.framework_results.assessability_counts.scored} scored · {result.framework_results.assessability_counts.insufficient_evidence} insufficient evidence
          </p>
          <details className="rounded-md border p-3">
            <summary className="cursor-pointer font-medium outline-none focus:ring-2 focus:ring-indigo-600">Structured native result</summary>
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words bg-gray-950 p-3 text-xs text-gray-50">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )
    case 'versioned_extension':
      return (
        <div className="rounded-md border p-3 text-sm">
          <p className="font-medium">{result.extension_identifier} v{result.extension_schema_version}</p>
          <p className="mt-1 text-gray-600">Validated versioned extension with {result.fields.length} bounded fields.</p>
        </div>
      )
  }
}
