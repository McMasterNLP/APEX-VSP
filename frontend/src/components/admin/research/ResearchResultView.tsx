import { useState, type ReactNode } from 'react'
import type {
  ResearchEvaluationEnvelope,
  ResearchTranscriptTurn,
} from '@/types/researchEvaluation'
import { FrameworkNativeView } from './FrameworkNativeView'
import {
  DimensionRatingsView,
  FindingsView,
  GlobalMetricsView,
  LimitationsView,
  RelationsView,
} from './ProjectionViews'
import { ProvenanceView } from './ProvenanceView'
import { TranscriptAnnotationView } from './TranscriptAnnotationView'

const statusStyles: Record<string, string> = {
  success: 'bg-emerald-100 text-emerald-900',
  failed: 'bg-red-100 text-red-900',
  refused: 'bg-amber-100 text-amber-950',
}

function ResultSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="space-y-2">
      <h6 className="text-sm font-semibold text-gray-950">{title}</h6>
      {children}
    </section>
  )
}

export function ResearchResultView({
  envelope,
  transcriptTurns,
}: {
  envelope: ResearchEvaluationEnvelope
  transcriptTurns: ResearchTranscriptTurn[]
}) {
  const [focusedTurn, setFocusedTurn] = useState<number | null>(null)
  const outputs = envelope.capabilities.outputs

  return (
    <article className="space-y-5 rounded-lg border border-gray-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h5 className="font-semibold text-gray-950">{envelope.evaluator.display_name}</h5>
          <p className="text-xs text-gray-600">{envelope.framework.framework_statement}</p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusStyles[envelope.status] ?? 'bg-gray-100 text-gray-900'}`}>
          Status: {envelope.status}
        </span>
      </div>

      {envelope.warnings.length > 0 && (
        <ul aria-label="Evaluation warnings" className="space-y-1 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          {envelope.warnings.map((warning) => <li key={warning}>Warning: {warning}</li>)}
        </ul>
      )}
      {envelope.error && <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{envelope.error.message}</p>}

      <ResultSection title="Provenance"><ProvenanceView envelope={envelope} /></ResultSection>

      {envelope.status === 'success' && (
        <>
          {(outputs.character_spans || outputs.turn_labels) && (
            <ResultSection title="Annotated transcript">
              <TranscriptAnnotationView
                turns={transcriptTurns}
                spans={outputs.character_spans ? envelope.projection.spans : []}
                turnLabels={outputs.turn_labels ? envelope.projection.turn_labels : []}
                focusedTurn={focusedTurn}
              />
            </ResultSection>
          )}
          {outputs.relations && (
            <ResultSection title="Relations">
              <RelationsView relations={envelope.projection.relations} spans={envelope.projection.spans} />
            </ResultSection>
          )}
          {outputs.dimension_ratings && (
            <ResultSection title="Dimension ratings">
              <DimensionRatingsView ratings={envelope.projection.dimension_ratings} onEvidenceTurn={setFocusedTurn} />
            </ResultSection>
          )}
          {outputs.global_metrics && (
            <ResultSection title="Global metrics"><GlobalMetricsView metrics={envelope.projection.global_metrics} /></ResultSection>
          )}
          {outputs.narrative_findings && (
            <ResultSection title="Findings">
              <FindingsView findings={envelope.projection.findings} onEvidenceTurn={setFocusedTurn} />
            </ResultSection>
          )}
          <ResultSection title="Limitations"><LimitationsView limitations={envelope.projection.limitations} /></ResultSection>
          {outputs.framework_native_view && (
            <ResultSection title="Framework-native result"><FrameworkNativeView result={envelope.framework_result} /></ResultSection>
          )}
        </>
      )}
    </article>
  )
}
