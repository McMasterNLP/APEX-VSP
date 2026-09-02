import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  completeResearchAnnotationSet,
  createResearchAnnotationSet,
  downloadResearchAnnotationExport,
  fetchResearchAnnotationSet,
  fetchSavedResearchRun,
  fetchSavedResearchRuns,
  reopenResearchAnnotationSet,
  saveResearchEvaluationRun,
  saveResearchReviewDecision,
} from '@/api/research.api'
import type {
  AnnotationSetRecord,
  EvaluationRunRecord,
  EvaluationRunSummary,
} from '@/types/researchEvaluation'
import { apiGet, apiPost, apiPut } from '@/test/authTestMocks'

const mockedGet = vi.mocked(apiGet)
const mockedPost = vi.mocked(apiPost)
const mockedPut = vi.mocked(apiPut)

const runRecord = { run_uuid: 'run-uuid' } as EvaluationRunRecord
const runSummary = { run_uuid: 'run-uuid' } as EvaluationRunSummary
const annotationSet = { annotation_set_uuid: 'set-uuid', revision: 3 } as AnnotationSetRecord

describe('research annotation API client', () => {
  beforeEach(() => {
    mockedGet.mockReset()
    mockedPost.mockReset()
    mockedPut.mockReset()
  })

  it('lists, saves, and loads immutable evaluation runs', async () => {
    mockedGet.mockResolvedValueOnce({ data: [runSummary] })
    expect(await fetchSavedResearchRuns(42)).toEqual([runSummary])
    expect(mockedGet).toHaveBeenLastCalledWith('/v1/research/sessions/42/evaluation-runs')

    mockedPost.mockResolvedValueOnce({ data: runRecord })
    expect(
      await saveResearchEvaluationRun(42, {
        evaluator_identifier: 'baseline',
        allow_live: false,
      })
    ).toBe(runRecord)
    expect(mockedPost).toHaveBeenLastCalledWith(
      '/v1/research/sessions/42/evaluation-runs',
      { evaluator_identifier: 'baseline', allow_live: false }
    )

    mockedGet.mockResolvedValueOnce({ data: runRecord })
    expect(await fetchSavedResearchRun('run/uuid')).toBe(runRecord)
    expect(mockedGet).toHaveBeenLastCalledWith('/v1/research/evaluation-runs/run%2Fuuid')
  })

  it('creates, refreshes, and saves revision-guarded decisions', async () => {
    mockedPost.mockResolvedValueOnce({ data: annotationSet })
    await createResearchAnnotationSet('run-uuid', {
      guideline_identifier: 'guide',
      guideline_version: '1.0',
    })
    expect(mockedPost).toHaveBeenLastCalledWith(
      '/v1/research/evaluation-runs/run-uuid/annotation-sets',
      { guideline_identifier: 'guide', guideline_version: '1.0' }
    )

    mockedGet.mockResolvedValueOnce({ data: annotationSet })
    expect(await fetchResearchAnnotationSet('set-uuid')).toBe(annotationSet)

    mockedPut.mockResolvedValueOnce({ data: annotationSet })
    await saveResearchReviewDecision('set-uuid', 'span_123', {
      expected_set_revision: 2,
      expected_decision_revision: 1,
      decision: 'rejected',
    })
    expect(mockedPut).toHaveBeenLastCalledWith(
      '/v1/research/annotation-sets/set-uuid/decisions/span_123',
      {
        expected_set_revision: 2,
        expected_decision_revision: 1,
        decision: 'rejected',
      }
    )
  })

  it('completes, reopens, and requests only sanitized UI exports', async () => {
    mockedPost.mockResolvedValue({ data: annotationSet })
    await completeResearchAnnotationSet('set-uuid', 3)
    expect(mockedPost).toHaveBeenLastCalledWith(
      '/v1/research/annotation-sets/set-uuid/complete',
      { expected_set_revision: 3 }
    )
    await reopenResearchAnnotationSet('set-uuid', 4, 'Expert second pass')
    expect(mockedPost).toHaveBeenLastCalledWith(
      '/v1/research/annotation-sets/set-uuid/reopen',
      { expected_set_revision: 4, reason: 'Expert second pass' }
    )

    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:annotation'),
      revokeObjectURL: vi.fn(),
    })
    mockedPost.mockResolvedValueOnce({ data: new Blob(['{}']) })
    await downloadResearchAnnotationExport('set-uuid', 'audit_history')
    expect(mockedPost).toHaveBeenLastCalledWith(
      '/v1/research/annotation-sets/set-uuid/exports',
      { profile: 'audit_history', include_transcript_content: false },
      { responseType: 'blob' }
    )
  })
})
