/**
 * Plugin Registry tab: the unified plugin registry (Phase 1-2) and its promotion
 * request/review workflow (Phase 4), surfaced in the UI for the first time.
 *
 * @remarks
 * Two sections: a filterable table of all registered plugins (evaluator, patient_model,
 * metrics) with a "Request stage change" action per row, and a promotion-requests queue
 * (defaults to pending) with approve/reject (admin-only) and withdraw (requester-only)
 * actions. Everything here is additive on top of the existing evaluator/session flows --
 * no plugin's actual behavior changes from anything on this page.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTimeInUserTimeZone } from '@/lib/dateTime'
import {
  approvePromotionRequest,
  createPromotionRequest,
  fetchPluginRegistrations,
  fetchPromotionRequests,
  linkPluginRegistration,
  rejectPromotionRequest,
  withdrawPromotionRequest,
} from '@/api/pluginRegistry.api'
import { getResearchApiMessage } from '@/api/research.api'
import {
  isNotYetPromoted,
  nextStage,
  STAGE_ORDER,
  type PluginKind,
  type PluginRegistration,
  type PluginStage,
  type PromotionRequest,
  type PromotionRequestStatus,
} from '@/types/pluginRegistry'

const KIND_OPTIONS: Array<{ value: PluginKind | ''; label: string }> = [
  { value: '', label: 'All kinds' },
  { value: 'evaluator', label: 'Evaluator' },
  { value: 'patient_model', label: 'Patient model' },
  { value: 'metrics', label: 'Metrics' },
]

const STAGE_OPTIONS: Array<{ value: PluginStage | ''; label: string }> = [
  { value: '', label: 'All stages' },
  ...STAGE_ORDER.map((stage) => ({ value: stage, label: stage.replaceAll('_', ' ') })),
]

const STAGE_BADGE_CLASSES: Record<PluginStage, string> = {
  draft: 'bg-gray-100 text-gray-700',
  experimental: 'bg-sky-100 text-sky-800',
  under_review: 'bg-amber-100 text-amber-800',
  promoted: 'bg-emerald-100 text-emerald-800',
  deprecated: 'bg-orange-100 text-orange-800',
  retired: 'bg-gray-200 text-gray-500',
}

function StageBadge({ stage }: { stage: PluginStage }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${STAGE_BADGE_CLASSES[stage]}`}
    >
      {stage.replaceAll('_', ' ')}
    </span>
  )
}

/**
 * Soft-enforcement indicator: the registry stage doesn't block selection or
 * execution anywhere in the app today, so this is a visible warning, not a
 * gate. Shown wherever a not-yet-promoted plugin's stage appears.
 */
function NotYetPromotedWarning() {
  return (
    <span
      title="This plugin's registry stage means it hasn't been reviewed/approved yet. It may still be fully wired up and usable elsewhere in the app -- the registry stage doesn't block that."
      className="ml-1 inline-block rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
    >
      not yet promoted
    </span>
  )
}

/** True when a registration's metadata marks it as the Research Evaluator adapter
 * side of a linked pair (set by the seed migration; see plugin_registry_service.py). */
function isResearchAdapterSide(reg: PluginRegistration): boolean {
  const meta = reg.metadata as Record<string, unknown> | null
  return Boolean(meta && typeof meta === 'object' && meta.research_adapter === true)
}

/**
 * Groups registrations so a linked pair renders adjacently (trainee side first,
 * research-adapter side second) instead of wherever alphabetical identifier
 * sort happens to put them. Unlinked rows -- or a link whose partner isn't in
 * the current filtered set -- render alone. Preserves the incoming (kind,
 * identifier) order as the group order, so this only pulls a partner up next
 * to its pair rather than re-sorting everything.
 */
function groupByLink(regs: PluginRegistration[]): PluginRegistration[][] {
  const byId = new Map(regs.map((r) => [r.id, r]))
  const consumed = new Set<number>()
  const groups: PluginRegistration[][] = []
  for (const reg of regs) {
    if (consumed.has(reg.id)) continue
    const partner = reg.linked_registration_id ? byId.get(reg.linked_registration_id) : undefined
    if (partner && !consumed.has(partner.id)) {
      const ordered = isResearchAdapterSide(reg) && !isResearchAdapterSide(partner)
        ? [partner, reg]
        : [reg, partner]
      groups.push(ordered)
      consumed.add(reg.id)
      consumed.add(partner.id)
    } else {
      groups.push([reg])
      consumed.add(reg.id)
    }
  }
  return groups
}

function StatusBadge({ status }: { status: PromotionRequestStatus }) {
  const classes: Record<PromotionRequestStatus, string> = {
    pending: 'bg-amber-100 text-amber-800',
    approved: 'bg-emerald-100 text-emerald-800',
    rejected: 'bg-red-100 text-red-800',
    withdrawn: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${classes[status]}`}>
      {status}
    </span>
  )
}

export function PluginRegistryTab() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  const [registrations, setRegistrations] = useState<PluginRegistration[]>([])
  const [loadingRegistrations, setLoadingRegistrations] = useState(true)
  const [kindFilter, setKindFilter] = useState<PluginKind | ''>('')
  const [stageFilter, setStageFilter] = useState<PluginStage | ''>('')

  const [requests, setRequests] = useState<PromotionRequest[]>([])
  const [loadingRequests, setLoadingRequests] = useState(true)
  const [requestStatusFilter, setRequestStatusFilter] = useState<PromotionRequestStatus | ''>(
    'pending'
  )

  const [error, setError] = useState<string | null>(null)
  const [actingRequestId, setActingRequestId] = useState<number | null>(null)

  const [requestTarget, setRequestTarget] = useState<PluginRegistration | null>(null)
  const [requestedStage, setRequestedStage] = useState<PluginStage | ''>('')
  const [requestNotes, setRequestNotes] = useState('')
  // Keyed by request id so notes typed for one row's decision never leak onto another
  // row's approve/reject action.
  const [reviewNotesByRequest, setReviewNotesByRequest] = useState<Record<number, string>>({})
  const [submittingRequest, setSubmittingRequest] = useState(false)

  const [linkTarget, setLinkTarget] = useState<PluginRegistration | null>(null)
  const [linkChoice, setLinkChoice] = useState<number | ''>('')
  const [submittingLink, setSubmittingLink] = useState(false)

  const loadRegistrations = useCallback(async () => {
    setLoadingRegistrations(true)
    try {
      const { registrations: rows } = await fetchPluginRegistrations({
        pluginKind: kindFilter || undefined,
        stage: stageFilter || undefined,
      })
      setRegistrations(rows)
      setError(null)
    } catch (err) {
      setError(getResearchApiMessage(err, 'Failed to load the plugin registry.'))
    } finally {
      setLoadingRegistrations(false)
    }
  }, [kindFilter, stageFilter])

  const loadRequests = useCallback(async () => {
    setLoadingRequests(true)
    try {
      const { requests: rows } = await fetchPromotionRequests(requestStatusFilter || undefined)
      setRequests(rows)
      setError(null)
    } catch (err) {
      setError(getResearchApiMessage(err, 'Failed to load promotion requests.'))
    } finally {
      setLoadingRequests(false)
    }
  }, [requestStatusFilter])

  useEffect(() => {
    void loadRegistrations()
  }, [loadRegistrations])

  useEffect(() => {
    void loadRequests()
  }, [loadRequests])

  const openRequestDialog = (registration: PluginRegistration) => {
    setRequestTarget(registration)
    setRequestedStage(nextStage(registration.stage) ?? '')
    setRequestNotes('')
  }

  const submitPromotionRequest = async () => {
    if (!requestTarget || !requestedStage) return
    setSubmittingRequest(true)
    try {
      await createPromotionRequest(requestTarget.id, requestedStage, requestNotes || undefined)
      setRequestTarget(null)
      await loadRequests()
    } catch (err) {
      setError(getResearchApiMessage(err, 'Failed to submit the promotion request.'))
    } finally {
      setSubmittingRequest(false)
    }
  }

  const registrationGroups = useMemo(() => groupByLink(registrations), [registrations])

  const openLinkDialog = (registration: PluginRegistration) => {
    setLinkTarget(registration)
    setLinkChoice(registration.linked_registration_id ?? '')
  }

  const submitLink = async () => {
    if (!linkTarget) return
    setSubmittingLink(true)
    try {
      await linkPluginRegistration(linkTarget.id, linkChoice === '' ? null : linkChoice)
      setLinkTarget(null)
      await loadRegistrations()
    } catch (err) {
      setError(getResearchApiMessage(err, 'Failed to update the link.'))
    } finally {
      setSubmittingLink(false)
    }
  }

  const act = async (
    requestId: number,
    action: (id: number, notes?: string) => Promise<PromotionRequest>
  ) => {
    setActingRequestId(requestId)
    try {
      await action(requestId, reviewNotesByRequest[requestId] || undefined)
      setReviewNotesByRequest((prev) => {
        const next = { ...prev }
        delete next[requestId]
        return next
      })
      await Promise.all([loadRequests(), loadRegistrations()])
    } catch (err) {
      setError(getResearchApiMessage(err, 'That action could not be completed.'))
    } finally {
      setActingRequestId(null)
    }
  }

  return (
    <section aria-labelledby="plugin-registry-heading" className="space-y-6">
      <div>
        <h2 id="plugin-registry-heading" className="text-lg font-semibold text-gray-950">
          Plugin Registry
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Every registered evaluator, patient model, and metrics plugin, and its lifecycle
          stage. Requesting a stage change here doesn&apos;t change anything by itself -- an
          admin has to approve it in the queue below. Linked pairs (the same underlying
          model&apos;s trainee wrapper and Research Evaluator adapter) are shown together,
          tinted, with a role tag -- linking is purely informational and doesn&apos;t merge
          their stages or history.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm font-medium text-red-700">
          {error}
        </p>
      )}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>Registered plugins</CardTitle>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filter by plugin kind"
              className="rounded border border-gray-300 px-2 py-1 text-sm"
              value={kindFilter}
              onChange={(event) => setKindFilter(event.target.value as PluginKind | '')}
            >
              {KIND_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by stage"
              className="rounded border border-gray-300 px-2 py-1 text-sm"
              value={stageFilter}
              onChange={(event) => setStageFilter(event.target.value as PluginStage | '')}
            >
              {STAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {loadingRegistrations ? (
            <p className="py-6 text-center text-sm text-gray-500">Loading…</p>
          ) : registrations.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-500">
              No registered plugins match this filter.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                    <th className="py-2 pr-4">Kind</th>
                    <th className="py-2 pr-4">Identifier</th>
                    <th className="py-2 pr-4">Display name</th>
                    <th className="py-2 pr-4">Version</th>
                    <th className="py-2 pr-4">Stage</th>
                    <th className="py-2 pr-4">Linked to</th>
                    <th className="py-2 pr-4" />
                  </tr>
                </thead>
                <tbody>
                  {registrationGroups.map((group, groupIndex) => {
                    const isPair = group.length === 2
                    return group.map((reg, rowInGroup) => {
                      const partner = isPair ? group[1 - rowInGroup] : undefined
                      const roleLabel = isPair
                        ? isResearchAdapterSide(reg)
                          ? 'research adapter'
                          : 'trainee'
                        : null
                      return (
                        <tr
                          key={reg.id}
                          className={
                            isPair
                              ? `bg-indigo-50/50 ${rowInGroup === 0 ? 'border-t border-indigo-100' : 'border-b border-indigo-100'}`
                              : `border-b border-gray-100 ${groupIndex > 0 ? '' : ''}`
                          }
                        >
                          <td className="py-2 pr-4 text-gray-700">
                            {rowInGroup === 0 ? reg.plugin_kind : ''}
                          </td>
                          <td className="py-2 pr-4 font-mono text-xs text-gray-900">
                            {isPair && (
                              <span className="mr-1 text-indigo-400" aria-hidden="true">
                                {rowInGroup === 0 ? '⛓' : '⤷'}
                              </span>
                            )}
                            {reg.identifier}
                            {roleLabel && (
                              <span className="ml-1.5 rounded bg-indigo-100 px-1 py-0.5 text-[10px] font-sans font-medium normal-case text-indigo-700">
                                {roleLabel}
                              </span>
                            )}
                          </td>
                          <td className="py-2 pr-4 text-gray-900">{reg.display_name}</td>
                          <td className="py-2 pr-4 text-gray-600">{reg.version}</td>
                          <td className="py-2 pr-4">
                            <StageBadge stage={reg.stage} />
                            {isNotYetPromoted(reg.stage) && <NotYetPromotedWarning />}
                          </td>
                          <td className="py-2 pr-4 text-xs text-gray-600">
                            {partner ? (
                              <span className="font-mono text-indigo-700">
                                same model as {partner.identifier}
                              </span>
                            ) : reg.linked_registration_id ? (
                              <span className="text-gray-400">#{reg.linked_registration_id}</span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="py-2 pr-4">
                            <div className="flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => openRequestDialog(reg)}
                              >
                                Request stage change
                              </Button>
                              {isAdmin && (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => openLinkDialog(reg)}
                                >
                                  {reg.linked_registration_id ? 'Edit link' : 'Link'}
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>Promotion requests</CardTitle>
          <select
            aria-label="Filter by request status"
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={requestStatusFilter}
            onChange={(event) =>
              setRequestStatusFilter(event.target.value as PromotionRequestStatus | '')
            }
          >
            <option value="pending">Pending (review queue)</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="withdrawn">Withdrawn</option>
            <option value="">All</option>
          </select>
        </CardHeader>
        <CardContent>
          {loadingRequests ? (
            <p className="py-6 text-center text-sm text-gray-500">Loading…</p>
          ) : requests.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-500">
              No promotion requests match this filter.
            </p>
          ) : (
            <ul className="space-y-2">
              {requests.map((req) => {
                const registration = registrations.find((r) => r.id === req.registration_id)
                const isOwnRequest = req.requested_by_user_id === user?.id
                const acting = actingRequestId === req.id
                return (
                  <li key={req.id} className="rounded-md bg-gray-50 p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <span className="font-medium text-gray-900">
                          {registration?.identifier ?? `registration #${req.registration_id}`}
                        </span>
                        <span className="ml-2 text-gray-600">
                          → <StageBadge stage={req.requested_stage} />
                        </span>
                        <StatusBadge status={req.status} />
                        <span className="ml-2 text-xs text-gray-500">
                          {formatDateTimeInUserTimeZone(req.created_at)}
                        </span>
                      </div>
                      {req.status === 'pending' && (
                        <div className="flex flex-wrap items-center gap-2">
                          {isAdmin && (
                            <>
                              <Button
                                type="button"
                                size="sm"
                                variant="success"
                                disabled={acting}
                                onClick={() => void act(req.id, approvePromotionRequest)}
                              >
                                Approve
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="destructive"
                                disabled={acting}
                                onClick={() => void act(req.id, rejectPromotionRequest)}
                              >
                                Reject
                              </Button>
                            </>
                          )}
                          {isOwnRequest && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={acting}
                              onClick={() =>
                                void act(req.id, (id) => withdrawPromotionRequest(id))
                              }
                            >
                              Withdraw
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                    {req.request_notes && (
                      <p className="mt-1 text-xs text-gray-600">
                        <span className="font-medium">Request notes:</span> {req.request_notes}
                      </p>
                    )}
                    {req.review_notes && (
                      <p className="mt-1 text-xs text-gray-600">
                        <span className="font-medium">Review notes:</span> {req.review_notes}
                      </p>
                    )}
                    {req.status === 'pending' && isAdmin && (
                      <Textarea
                        aria-label={`Review notes for request ${req.id}`}
                        placeholder="Optional notes for this decision…"
                        className="mt-2 text-xs"
                        rows={2}
                        value={reviewNotesByRequest[req.id] ?? ''}
                        onChange={(event) =>
                          setReviewNotesByRequest((prev) => ({
                            ...prev,
                            [req.id]: event.target.value,
                          }))
                        }
                      />
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Dialog open={requestTarget !== null} onOpenChange={(open) => !open && setRequestTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request a stage change</DialogTitle>
            <DialogDescription>
              {requestTarget && (
                <>
                  <span className="font-mono">{requestTarget.identifier}</span> is currently{' '}
                  <StageBadge stage={requestTarget.stage} />. This only records the request --
                  an admin still has to approve it before the stage actually changes.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block text-sm text-gray-700">
              Requested stage
              <select
                aria-label="Requested stage"
                className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5"
                value={requestedStage}
                onChange={(event) => setRequestedStage(event.target.value as PluginStage)}
              >
                <option value="" disabled>
                  Choose a stage…
                </option>
                {STAGE_ORDER.filter((stage) => stage !== requestTarget?.stage).map((stage) => (
                  <option key={stage} value={stage}>
                    {stage.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm text-gray-700">
              Notes (optional)
              <Textarea
                aria-label="Request notes"
                className="mt-1"
                rows={3}
                value={requestNotes}
                onChange={(event) => setRequestNotes(event.target.value)}
              />
            </label>
            <Button
              type="button"
              disabled={!requestedStage || submittingRequest}
              onClick={() => void submitPromotionRequest()}
            >
              {submittingRequest ? 'Submitting…' : 'Submit request'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={linkTarget !== null} onOpenChange={(open) => !open && setLinkTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Link to another registration</DialogTitle>
            <DialogDescription>
              {linkTarget && (
                <>
                  Mark <span className="font-mono">{linkTarget.identifier}</span> as the same
                  underlying model as another {linkTarget.plugin_kind} registration on a
                  different surface (e.g. a trainee Evaluator wrapper and its Research Evaluator
                  adapter counterpart). Purely informational -- this never changes either
                  registration&apos;s stage or which code path runs. Linking is symmetric: the
                  other registration will show this link too.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block text-sm text-gray-700">
              Linked registration
              <select
                aria-label="Linked registration"
                className="mt-1 block w-full rounded border border-gray-300 px-2 py-1.5"
                value={linkChoice}
                onChange={(event) =>
                  setLinkChoice(event.target.value === '' ? '' : Number(event.target.value))
                }
              >
                <option value="">None (unlinked)</option>
                {registrations
                  .filter(
                    (r) => linkTarget && r.id !== linkTarget.id && r.plugin_kind === linkTarget.plugin_kind
                  )
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.identifier} ({r.display_name})
                    </option>
                  ))}
              </select>
            </label>
            <Button type="button" disabled={submittingLink} onClick={() => void submitLink()}>
              {submittingLink ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  )
}
