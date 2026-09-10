/**
 * Evaluation workspace for one session: evaluator checklist, saved runs, and annotation authoring.
 *
 * @remarks
 * Entry point for the Item 1/2A/2B evaluation workflow, reached from Research's
 * "Evaluate Sessions" tab. Renders session context (transcript orientation) plus
 * {@link ResearchEvaluationPanel}, which internally renders `AnnotationSetWorkspace`
 * once a run and annotation set are selected. Uses ordinary full-page scroll; no
 * embedded-panel scroll workaround like the old Admin Sessions tab needed.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchAdminSessionDetail, type AdminSessionDetailResponse } from '@/api/admin.api'
import { ResearchEvaluationPanel } from '@/components/admin/research/ResearchEvaluationPanel'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTimeInUserTimeZone } from '@/lib/dateTime'

/** Prefer full name, then email; fallback to numeric id (admin API adds user_* from users table). */
function formatSessionUserLabel(s: {
  user_id: number
  user_full_name?: string | null
  user_email?: string | null
}): string {
  const name = s.user_full_name?.trim()
  if (name) return name
  const email = s.user_email?.trim()
  if (email) return email
  return `User #${s.user_id}`
}

/**
 * Loads session context and renders the evaluation/annotation workspace for it.
 *
 * @returns Full page layout (Navbar/Sidebar shell, session header, transcript, evaluation panel)
 */
export function ResearchEvaluationSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [detail, setDetail] = useState<AdminSessionDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchAdminSessionDetail(sessionId)
        if (!cancelled) setDetail(data)
      } catch (e) {
        console.error('Failed to fetch session detail:', e)
        if (!cancelled) setError('Failed to load session detail')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [sessionId])

  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 overflow-y-auto md:ml-64">
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            <nav className="mb-4 text-sm text-gray-500">
              <Link to="/research" className="hover:underline">
                Research
              </Link>
              {' / '}
              <span className="text-gray-900">Evaluate Session {sessionId}</span>
            </nav>

            {loading && (
              <Card>
                <CardContent className="py-12 text-center text-gray-500">
                  Loading session…
                </CardContent>
              </Card>
            )}

            {!loading && error && (
              <Card>
                <CardContent className="py-8 text-center text-red-600">{error}</CardContent>
              </Card>
            )}

            {!loading && !error && detail && (
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Session {detail.session.id} – Evaluation Workspace</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {formatSessionUserLabel(detail.session)} · State: {detail.session.state}
                    </p>
                  </CardHeader>
                  <CardContent>
                    <h4 className="font-medium mb-3">Transcript</h4>
                    <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3 bg-gray-50">
                      {detail.session.turns.length === 0 ? (
                        <p className="text-gray-500 text-sm">No turns</p>
                      ) : (
                        detail.session.turns.map((t) => (
                          <div key={t.id} className="text-sm">
                            <span className="font-medium text-gray-700">
                              Turn {t.turn_number} ({t.role})
                            </span>
                            <span className="text-gray-500 ml-2 text-xs">
                              {formatDateTimeInUserTimeZone(t.timestamp)}
                            </span>
                            <p className="mt-1 text-gray-900">{t.text}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </CardContent>
                </Card>

                <ResearchEvaluationPanel
                  sessionId={detail.session.id}
                  sessionState={detail.session.state}
                />
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
