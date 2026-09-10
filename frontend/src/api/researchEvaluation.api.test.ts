import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  downloadResearchEvaluationExport,
  fetchResearchEvaluatorDescriptors,
  runResearchEvaluations,
} from '@/api/research.api'
import { apiGet, apiPost } from '@/test/authTestMocks'
import type {
  ResearchEvaluationEnvelope,
  ResearchEvaluatorDescriptorsResponse,
} from '@/types/researchEvaluation'

const mockedGet = vi.mocked(apiGet)
const mockedPost = vi.mocked(apiPost)

describe('research evaluation API', () => {
  beforeEach(() => {
    mockedGet.mockReset()
    mockedPost.mockReset()
  })

  it('loads evaluator descriptors from the admin research registry', async () => {
    const payload: ResearchEvaluatorDescriptorsResponse = {
      schema_version: '1.0',
      evaluators: [],
    }
    mockedGet.mockResolvedValue({ data: payload })
    await expect(fetchResearchEvaluatorDescriptors()).resolves.toEqual(payload)
    expect(mockedGet).toHaveBeenCalledWith('/v1/research/evaluators')
  })

  it('posts an explicit non-live run request', async () => {
    mockedPost.mockResolvedValue({
      data: {
        schema_version: '1.0',
        transcript: {},
        transcript_turns: [],
        results: [],
      },
    })
    await runResearchEvaluations(42, {
      evaluator_identifiers: ['baseline'],
      allow_live: false,
    })
    expect(mockedPost).toHaveBeenCalledWith('/v1/research/sessions/42/evaluations', {
      evaluator_identifiers: ['baseline'],
      allow_live: false,
    })
  })

  it('posts existing envelopes for a sanitized tabular export', async () => {
    const createObjectURL = vi.fn(() => 'blob:research')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const blob = new Blob(['zip'], { type: 'application/zip' })
    mockedPost.mockResolvedValue({ data: blob })
    const envelopes = [{ schema_version: '1.0' }] as ResearchEvaluationEnvelope[]

    await downloadResearchEvaluationExport(7, 'tabular', envelopes)

    expect(mockedPost).toHaveBeenCalledWith(
      '/v1/research/sessions/7/evaluation-exports',
      { profile: 'tabular', envelopes, include_transcript_content: false },
      { responseType: 'blob' }
    )
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:research')
  })
})
