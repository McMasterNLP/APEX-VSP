import { useState } from 'react'
import type { ResearchEvaluationEnvelope } from '@/types/researchEvaluation'

export function ProvenanceView({ envelope }: { envelope: ResearchEvaluationEnvelope }) {
  const [copied, setCopied] = useState(false)
  const hash = envelope.transcript.canonical_transcript_hash
  const copyHash = async () => {
    try {
      await navigator.clipboard.writeText(hash)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <dl className="grid gap-x-4 gap-y-2 rounded-md bg-gray-50 p-3 text-sm sm:grid-cols-[max-content_1fr]">
      <dt className="font-medium">Evaluator</dt><dd>{envelope.evaluator.display_name} v{envelope.evaluator.version}</dd>
      <dt className="font-medium">Framework</dt><dd>{envelope.framework.display_name} v{envelope.framework.version}</dd>
      <dt className="font-medium">Adapter</dt><dd>{envelope.adapter.identifier} v{envelope.adapter.version}</dd>
      <dt className="font-medium">Validation</dt><dd>{envelope.framework.validation_status.replaceAll('_', ' ')}</dd>
      <dt className="font-medium">Provider / model</dt>
      <dd>{envelope.evaluator.provider ?? 'offline'}{envelope.evaluator.model_identifier ? ` / ${envelope.evaluator.model_identifier}` : ''}</dd>
      <dt className="font-medium">Execution</dt><dd>{envelope.run.execution_mode} · {envelope.run.runtime_ms.toFixed(1)} ms</dd>
      <dt className="font-medium">Transcript hash</dt>
      <dd className="flex min-w-0 items-center gap-2">
        <code title={hash} className="truncate">{hash.slice(0, 12)}…{hash.slice(-8)}</code>
        <button
          type="button"
          onClick={() => void copyHash()}
          className="rounded border border-gray-300 px-2 py-1 text-xs outline-none focus:ring-2 focus:ring-indigo-600"
          aria-label="Copy full transcript hash"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </dd>
      <dt className="font-medium">Run ID</dt><dd className="break-all font-mono text-xs">{envelope.run.run_id}</dd>
    </dl>
  )
}
