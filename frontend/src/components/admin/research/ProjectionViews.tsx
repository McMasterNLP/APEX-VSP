import type {
  DimensionRating,
  GlobalMetric,
  ProjectedRelation,
  ResearchFinding,
  ResearchLimitation,
  SpanAnnotation,
} from '@/types/researchEvaluation'

const humanize = (value: string) => value.replaceAll('_', ' ')

export function RelationsView({
  relations,
  spans,
}: {
  relations: ProjectedRelation[]
  spans: SpanAnnotation[]
}) {
  const byId = new Map(spans.map((span) => [span.prediction_id, span]))
  if (relations.length === 0) return <p className="text-sm text-gray-600">No relations were produced.</p>
  return (
    <ul className="space-y-2">
      {relations.map((relation) => {
        const source = byId.get(relation.source_annotation_id)
        const target = byId.get(relation.target_annotation_id)
        return (
          <li key={relation.relation_id} className="rounded-md border border-gray-200 p-3 text-sm">
            <span className="font-medium">{humanize(relation.relation_type)}</span>
            <span className="block text-gray-700">
              {source ? `Turn ${source.turn_number}: ${source.label}` : relation.source_annotation_id}
              {' → '}
              {target ? `Turn ${target.turn_number}: ${target.label}` : relation.target_annotation_id}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export function DimensionRatingsView({
  ratings,
  onEvidenceTurn,
}: {
  ratings: DimensionRating[]
  onEvidenceTurn: (turn: number) => void
}) {
  if (ratings.length === 0) return <p className="text-sm text-gray-600">No dimension ratings were produced.</p>
  const groups = new Map<string, DimensionRating[]>()
  for (const rating of ratings) {
    const group = rating.domain_identifier ?? 'ungrouped'
    groups.set(group, [...(groups.get(group) ?? []), rating])
  }
  return (
    <div className="space-y-4">
      {[...groups].map(([domain, items]) => (
        <section key={domain} aria-labelledby={`rating-domain-${domain}`}>
          <h6 id={`rating-domain-${domain}`} className="mb-2 text-sm font-semibold capitalize text-gray-900">
            {humanize(domain)}
          </h6>
          <div className="grid gap-3 lg:grid-cols-2">
            {items.map((rating) => (
              <article key={rating.rating_id} className="rounded-md border border-gray-200 p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium capitalize text-gray-950">
                    {humanize(rating.dimension_identifier)}
                  </p>
                  <span className="whitespace-nowrap rounded-full border border-gray-300 px-2 py-0.5 text-xs font-semibold">
                    {rating.score_status === 'available'
                      ? `${rating.score} / ${rating.scale_maximum}`
                      : humanize(rating.score_status)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-600">Assessability: {humanize(rating.assessability)}</p>
                <p className="mt-2 text-sm text-gray-700">{rating.rationale}</p>
                {rating.evidence_turns.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1" aria-label="Evidence turns">
                    {rating.evidence_turns.map((turn) => (
                      <button
                        key={turn}
                        type="button"
                        onClick={() => onEvidenceTurn(turn)}
                        className="rounded border border-indigo-300 px-2 py-1 text-xs text-indigo-800 outline-none hover:bg-indigo-50 focus:ring-2 focus:ring-indigo-600"
                      >
                        Evidence turn {turn}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export function GlobalMetricsView({ metrics }: { metrics: GlobalMetric[] }) {
  if (metrics.length === 0) return <p className="text-sm text-gray-600">No global metrics were produced.</p>
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric) => (
        <article key={metric.metric_id} className="rounded-md border border-gray-200 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-600">{humanize(metric.metric_name)}</p>
          <p className="mt-1 text-xl font-semibold text-gray-950">
            {metric.value_status === 'available' ? metric.value : 'Unavailable'}
            {metric.value_status === 'available' && (
              <span className="ml-1 text-xs font-normal text-gray-500">{metric.unit_or_scale}</span>
            )}
          </p>
          <p className="mt-2 text-xs text-gray-600">{metric.comparability_statement}</p>
          <p className="mt-1 text-xs text-gray-500">Source: {metric.source_label}</p>
        </article>
      ))}
    </div>
  )
}

export function FindingsView({
  findings,
  onEvidenceTurn,
}: {
  findings: ResearchFinding[]
  onEvidenceTurn: (turn: number) => void
}) {
  if (findings.length === 0) return <p className="text-sm text-gray-600">No narrative findings were produced.</p>
  return (
    <ul className="space-y-2">
      {findings.map((finding) => (
        <li key={finding.finding_id} className="rounded-md border border-gray-200 p-3 text-sm">
          <p className="font-medium capitalize text-gray-950">{humanize(finding.finding_type)}</p>
          <p className="mt-1 whitespace-pre-wrap text-gray-700">{finding.description}</p>
          {finding.evidence_turns.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {finding.evidence_turns.map((turn) => (
                <button
                  key={turn}
                  type="button"
                  onClick={() => onEvidenceTurn(turn)}
                  className="rounded border border-indigo-300 px-2 py-1 text-xs text-indigo-800 outline-none focus:ring-2 focus:ring-indigo-600"
                >
                  Evidence turn {turn}
                </button>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}

export function LimitationsView({ limitations }: { limitations: ResearchLimitation[] }) {
  if (limitations.length === 0) return <p className="text-sm text-gray-600">No limitations were declared.</p>
  return (
    <ul className="space-y-2">
      {limitations.map((limitation) => (
        <li key={limitation.limitation_id} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          <p className="font-medium">{humanize(limitation.code)}</p>
          <p className="mt-1">{limitation.description}</p>
          <p className="mt-1 text-xs">Scope: {limitation.severity_or_scope} · Affects {limitation.affected_outputs.join(', ') || 'unspecified outputs'}</p>
        </li>
      ))}
    </ul>
  )
}
