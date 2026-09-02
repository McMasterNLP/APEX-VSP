import type {
  AnnotationPolicyDescriptor,
  DecisionRevisionRecord,
  DimensionRating,
  ProjectedRelation,
  ResearchFinding,
  ReviewablePrediction,
  SpanAnnotation,
  TurnLabel,
  TypedCorrection,
} from '@/types/researchEvaluation'
import { ReviewControls } from './ReviewControls'

const humanize = (value: string) => value.replaceAll('_', ' ')

function predictionSummary(prediction: ReviewablePrediction): string {
  const original = prediction.original_prediction
  switch (original.projection_type) {
    case 'span_annotation': {
      const span = original as SpanAnnotation
      return `Turn ${span.turn_number}: ${span.label} — “${span.quoted_text}”`
    }
    case 'turn_label': {
      const label = original as TurnLabel
      return `Turn ${label.turn_number}: ${label.label} — ${label.dimension ?? label.subtype ?? 'labeled'}`
    }
    case 'relation': {
      const relation = original as ProjectedRelation
      return `${relation.relation_type}: ${relation.source_annotation_id} → ${relation.target_annotation_id}`
    }
    case 'dimension_rating': {
      const rating = original as DimensionRating
      return `${rating.dimension_identifier}: ${rating.score_status === 'available' ? `${rating.score} / ${rating.scale_maximum}` : humanize(rating.score_status)}`
    }
    case 'finding': {
      const finding = original as ResearchFinding
      return `${humanize(finding.finding_type)}: ${finding.description}`
    }
  }
}

export function PredictionReviewCard({
  prediction,
  policy,
  transcriptTurnNumbers,
  currentDecision,
  disabled,
  onSave,
}: {
  prediction: ReviewablePrediction
  policy: AnnotationPolicyDescriptor
  transcriptTurnNumbers: number[]
  currentDecision: DecisionRevisionRecord | null
  disabled: boolean
  onSave: (
    decision: 'confirmed' | 'rejected' | 'corrected' | 'insufficient_evidence',
    correction: TypedCorrection | null,
    reviewerNote: string
  ) => Promise<void>
}) {
  const state = currentDecision?.decision ?? 'unreviewed'
  return (
    <article aria-labelledby={`prediction-${prediction.prediction_id}`} className="space-y-4 rounded-lg border border-gray-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-600">Model prediction · {humanize(prediction.projection_type)}</p>
          <h6 id={`prediction-${prediction.prediction_id}`} className="mt-1 font-semibold text-gray-950">
            {predictionSummary(prediction)}
          </h6>
        </div>
        <span aria-label={`Human decision: ${humanize(state)}`} className="rounded-full border border-gray-300 px-2 py-1 text-xs font-semibold capitalize">
          Human decision: {humanize(state)}
        </span>
      </div>
      {currentDecision?.correction && (
        <details className="rounded-md bg-indigo-50 p-2 text-sm">
          <summary className="cursor-pointer font-medium">Effective human correction</summary>
          <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(currentDecision.correction, null, 2)}</pre>
        </details>
      )}
      <ReviewControls
        prediction={prediction}
        policy={policy}
        transcriptTurnNumbers={transcriptTurnNumbers}
        currentDecision={currentDecision}
        disabled={disabled}
        onSave={onSave}
      />
    </article>
  )
}
