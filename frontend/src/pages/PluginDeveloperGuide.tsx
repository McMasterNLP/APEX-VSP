/**
 * Long-form admin documentation for plugin architecture and registration.
 */
import { Link } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/store/authStore'
import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

/** In-page table of contents anchors and searchable keywords (space-separated topics). */
const DOC_NAV = [
  {
    id: 'overview',
    label: 'Overview',
    keywords:
      'introduction overview apex plugin guide extend patient evaluator metrics environment configuration research session',
  },
  {
    id: 'architecture',
    label: 'Plugin Architecture',
    keywords:
      'architecture pipeline dialogue clinician patient model evaluator feedback response scoring metrics analytics dashboard protocol registry load_plugins',
  },
  {
    id: 'plugin-types',
    label: 'Plugin Types',
    keywords: 'plugin types patientmodel evaluator metricsplugin protocol interface class',
  },
  {
    id: 'patient-model',
    label: 'PatientModel Plugins',
    keywords: 'patient model patientmodel generate_response state conversation history spikes simulate utterance',
  },
  {
    id: 'evaluator',
    label: 'Evaluator Plugins',
    keywords: 'evaluator evaluate feedbackresponse scores strengths improvement spikes empathy framework metadata',
  },
  {
    id: 'research-evaluator',
    label: 'Research Evaluator Plugins',
    keywords:
      'research evaluator adapter registry live execution provider openai gemini availability experimental ace-ct apex baseline hybrid researcher pseudonymized identity redaction evaluate sessions run compare',
  },
  {
    id: 'metrics',
    label: 'Metrics Plugins',
    keywords: 'metrics metricsplugin compute dictionary research export analytics session metrics_json generate_feedback',
  },
  {
    id: 'registration',
    label: 'Plugin Registration',
    keywords: 'registration register pluginregistry configuration settings module path classname environment case session frozen',
  },
  {
    id: 'testing',
    label: 'Testing Plugins',
    keywords: 'testing pytest tests plugins mock dialogue_service scoring_service registry session lru_cache',
  },
  {
    id: 'best-practices',
    label: 'Best Practices',
    keywords: 'best practices stateless repository scoring service dialogue validation',
  },
  {
    id: 'plugin-registry-workflow',
    label: 'Plugin Registry & Promotions',
    keywords:
      'plugin registry lifecycle stage draft experimental under_review promoted deprecated retired promotion request review approve reject withdraw registryservice plugin_registrations',
  },
] as const

function docSectionVisible(keywords: string, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const b = keywords.toLowerCase()
  return q
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => b.includes(w))
}

/**
 * Scrollable developer guide with section anchors and prose blocks.
 *
 * @remarks
 * Scrolls to top on mount for predictable deep-link behavior.
 *
 * @returns Documentation layout
 */
export const PluginDeveloperGuide = () => {
  const { user } = useAuthStore()
  const [docSearch, setDocSearch] = useState('')

  const navSections = useMemo(
    () => DOC_NAV.filter((s) => docSectionVisible(s.keywords, docSearch)),
    [docSearch]
  )
  const anySectionVisible = useMemo(
    () => DOC_NAV.some((s) => docSectionVisible(s.keywords, docSearch)),
    [docSearch]
  )

  useEffect(() => {
    // On mount, scroll to top
    window.scrollTo(0, 0)
  }, [])

  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 overflow-y-auto md:ml-64 bg-gray-50">
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            <nav className="mb-4 text-sm text-gray-500">
              Dashboard /{' '}
              {user?.role === 'admin' && (
                <>
                  <span className="text-gray-900">Developer Docs</span>
                </>
              )}
              {!user?.role && <span className="text-gray-900">Developer Docs</span>}
            </nav>

            <div className="flex flex-col gap-8 lg:flex-row">
              {/* Left sidebar navigation */}
              <aside className="lg:w-64 lg:flex-shrink-0">
                <div className="sticky top-24 hidden lg:block">
                  <h2 className="text-sm font-semibold text-gray-700 mb-3">
                    On this page
                  </h2>
                  <nav className="space-y-1 text-sm">
                    {navSections.map((section) => (
                      <button
                        key={section.id}
                        type="button"
                        onClick={() => {
                          const el = document.getElementById(section.id)
                          if (el) {
                            el.scrollIntoView({ behavior: 'smooth', block: 'start' })
                          }
                        }}
                        className="block w-full rounded-md px-2 py-1 text-left text-gray-700 hover:bg-apex-50 hover:text-apex-700"
                      >
                        {section.label}
                      </button>
                    ))}
                  </nav>
                  {docSearch.trim() && navSections.length === 0 && (
                    <p className="mt-2 text-xs text-gray-500">No sections match this search.</p>
                  )}
                </div>
              </aside>

              {/* Main content */}
              <article className="flex-1">
                <header className="mb-6">
                  <h1 className="text-3xl font-bold text-gray-900 mb-2">APEX Plugin Developer Guide</h1>
                  <p className="text-gray-600 max-w-2xl mb-4">
                    This guide explains how to extend APEX by writing and registering your own
                    <span className="font-semibold"> PatientModel</span>,{' '}
                    <span className="font-semibold">Evaluator</span>, and{' '}
                    <span className="font-semibold">MetricsPlugin</span> implementations.
                  </p>
                  <div className="max-w-md">
                    <label htmlFor="doc-search" className="sr-only">
                      Search this guide
                    </label>
                    <Input
                      id="doc-search"
                      type="search"
                      placeholder="Filter sections by keyword…"
                      value={docSearch}
                      onChange={(e) => setDocSearch(e.target.value)}
                      className="bg-white"
                    />
                    <p className="mt-1.5 text-xs text-gray-500">
                      Type one or more words; sections that match all words stay visible.
                    </p>
                  </div>
                </header>

                {docSearch.trim() && !anySectionVisible && (
                  <p className="mb-6 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    No sections match &quot;{docSearch.trim()}&quot;. Clear the search box to see the full guide.
                  </p>
                )}

                {/* 1. Introduction / Overview */}
                <section
                  id="overview"
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[0].keywords, docSearch) && 'hidden')}
                >
                  <h2 className="text-xl font-semibold mt-2 mb-3">Introduction</h2>
                  <p className="text-gray-700 mb-3">
                    APEX allows researchers and developers to extend the system by implementing plugins.
                    Defaults come from settings (for example, environment variables); cases can override
                    plugins for new sessions. At session creation, resolved plugin ids are frozen on the
                    session row so dialogue and scoring use that configuration for reproducibility. You can
                    swap the patient model, evaluator, or metrics without modifying core application code
                    beyond registration and config.
                  </p>
                </section>

                {/* 2. Plugin Architecture */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[1].keywords, docSearch) && 'hidden')}
                  id="architecture"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Plugin Architecture</h2>
                  <p className="text-gray-700 mb-4">
                    APEX uses a pipeline architecture where each stage can be swapped via plugins.
                    The evaluation pipeline flows as follows:
                  </p>
                  <div className="rounded-lg border border-gray-200 bg-gray-900 p-5 text-sm font-mono text-gray-100 overflow-x-auto mb-4">
                    <div className="space-y-1">
                      <div className="text-indigo-300">Clinician Message</div>
                      <div className="text-gray-500">{'  →'} <span className="text-amber-300">Patient Model Plugin</span> <span className="text-gray-500">(generates patient response)</span></div>
                      <div className="text-gray-500">{'  →'} <span className="text-gray-300">Conversation</span> <span className="text-gray-500">(multi-turn dialogue)</span></div>
                      <div className="text-gray-500">{'  →'} <span className="text-emerald-300">Evaluator Plugin</span> <span className="text-gray-500">(scores communication, produces feedback)</span></div>
                      <div className="text-gray-500">{'  →'} <span className="text-gray-300">Feedback + Scores</span> <span className="text-gray-500">(FeedbackResponse)</span></div>
                      <div className="text-gray-500">{'  →'} <span className="text-purple-300">Metrics Plugins</span> <span className="text-gray-500">(compute research analytics)</span></div>
                      <div className="text-gray-500">{'  →'} <span className="text-gray-300">Analytics Dashboard</span></div>
                    </div>
                  </div>
                  <p className="text-gray-700">
                    Each plugin type implements a specific protocol (interface) and is configured via
                    environment variables using{' '}
                    <span className="font-mono text-sm">module.path:ClassName</span> format. Plugins are
                    resolved at session creation time and frozen on the session record, ensuring
                    reproducible results for research.
                  </p>
                </section>

                {/* 3. Plugin Types Overview */}
                <section className="mb-6" id="plugin-types">
                  <h2 className="text-xl font-semibold mt-8 mb-3">Plugin Types</h2>
                  <div className="space-y-4">
                    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                      <h3 className="font-semibold text-amber-900">Patient Model Plugin</h3>
                      <p className="text-sm text-amber-800 mt-1">
                        Generates simulated patient responses during training conversations. The plugin
                        receives the full conversation state (case context, session metadata, conversation
                        history) and returns the next patient utterance as a string.
                      </p>
                      <p className="text-xs text-amber-700 mt-2 font-mono">
                        Protocol: PatientModel.generate_response(state, clinician_input) → str
                      </p>
                    </div>
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                      <h3 className="font-semibold text-emerald-900">Evaluator Plugin</h3>
                      <p className="text-sm text-emerald-800 mt-1">
                        Scores clinician communication after a session ends and produces structured
                        feedback including numeric scores, text feedback, strengths, areas for
                        improvement, and optional framework-specific data (e.g. SPIKES coverage).
                      </p>
                      <p className="text-xs text-emerald-700 mt-2 font-mono">
                        Protocol: Evaluator.evaluate(db, session_id) → FeedbackResponse
                      </p>
                    </div>
                    <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
                      <h3 className="font-semibold text-purple-900">Metrics Plugin</h3>
                      <p className="text-sm text-purple-800 mt-1">
                        Computes additional analytics metrics for research dashboards and data exports.
                        Multiple metrics plugins can run in parallel, each producing a dictionary of
                        computed values from the session data.
                      </p>
                      <p className="text-xs text-purple-700 mt-2 font-mono">
                        Protocol: MetricsPlugin.compute(db, session_id) → dict[str, Any]
                      </p>
                    </div>
                    <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
                      <h3 className="font-semibold text-indigo-900">Research Evaluator Plugin</h3>
                      <p className="text-sm text-indigo-800 mt-1">
                        A separate, admin/researcher-only evaluator used on the Evaluate Sessions{' '}
                        <span className="font-semibold">Run &amp; Compare</span> and{' '}
                        <span className="font-semibold">Saved Runs</span> tabs. Statically registered
                        (not settings-driven) and operates on an identity-free transcript.
                      </p>
                      <p className="text-xs text-indigo-700 mt-2 font-mono">
                        Protocol: ResearchResultAdapter.build_native_result / .project(...)
                      </p>
                    </div>
                  </div>
                </section>

                {/* 4. PatientModel Plugins */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[3].keywords, docSearch) && 'hidden')}
                  id="patient-model"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">PatientModel Plugins</h2>
                  <p className="text-gray-700 mb-3">
                    Implement the <span className="font-mono">PatientModel</span> protocol: an async
                    method <span className="font-mono">generate_response(state, clinician_input)</span>{' '}
                    that returns the simulated patient response as a string.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Example</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`from typing import Any


class MyPatientModel:
    async def generate_response(self, state: Any, clinician_input: str) -> str:
        # Use state.case, state.session, state.conversation_history as needed.
        # Return the next patient utterance.
        return "I'm not sure how to feel about that."`}</code>
                  </pre>

                  <h3 className="text-lg font-medium mt-6 mb-2">Expected behavior</h3>
                  <ul className="list-disc pl-6 text-gray-700 space-y-1">
                    <li>
                      <span className="font-mono">state</span> is provided by the dialogue service and
                      typically has <span className="font-mono">case</span>,{' '}
                      <span className="font-mono">session</span>, and{' '}
                      <span className="font-mono">conversation_history</span>.
                    </li>
                    <li>
                      Your method should return a single string: the next patient turn. Keep responses
                      appropriate for the clinical context and, if relevant, the current SPIKES stage.
                    </li>
                  </ul>
                </section>

                {/* 3. Evaluator Plugins */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[4].keywords, docSearch) && 'hidden')}
                  id="evaluator"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Evaluator Plugins</h2>
                  <p className="text-gray-700 mb-3">
                    Implement the <span className="font-mono">Evaluator</span> protocol: an async method{' '}
                    <span className="font-mono">evaluate(db, session_id)</span> that returns a{' '}
                    <span className="font-mono">FeedbackResponse</span>.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Example</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`from sqlalchemy.orm import Session
from domain.models.sessions import FeedbackResponse


class MyEvaluator:
    async def evaluate(self, db: Session, session_id: int) -> FeedbackResponse:
        # Load session/turns from db, compute scores and text feedback.
        return FeedbackResponse(
            empathy_score=75.0,
            overall_score=80.0,
            strengths="Clear structure.",
            areas_for_improvement="More empathy phrases.",
            suggested_responses=[],
            timeline_events=[],
        )`}</code>
                  </pre>

                  <h3 className="text-lg font-medium mt-6 mb-2">Expected return type</h3>
                  <p className="text-gray-700 mb-3">
                    <span className="font-mono">FeedbackResponse</span> (or a compatible type) with at
                    least empathy score, overall score, and optional strengths / areas for improvement,
                    suggested responses, and timeline events as defined in the domain model.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Complete evaluator example</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`from sqlalchemy.orm import Session
from domain.models.sessions import FeedbackResponse
from repositories.session_repo import SessionRepository


class MyCustomEvaluator:
    """Custom evaluator with SPIKES + empathy scoring."""

    name = "my_custom_evaluator"
    version = "1.0.0"

    async def evaluate(self, db: Session, session_id: int) -> FeedbackResponse:
        repo = SessionRepository(db)
        session = repo.get(session_id)
        turns = repo.get_turns(session_id)

        # Implement your scoring logic here
        empathy_score = self._score_empathy(turns)
        spikes_score = self._score_spikes(turns)

        return FeedbackResponse(
            session_id=session_id,
            empathy_score=empathy_score,
            overall_score=(empathy_score + spikes_score) / 2,
            spikes_completion_score=spikes_score,
            strengths="Good use of open questions.",
            areas_for_improvement="Consider more reflective listening.",
            evaluator_meta={
                "name": self.name,
                "version": self.version,
                "framework": "SPIKES + Empathy",
            },
        )

    def _score_empathy(self, turns):
        # Your empathy scoring implementation
        return 75.0

    def _score_spikes(self, turns):
        # Your SPIKES scoring implementation
        return 80.0`}</code>
                  </pre>
                  <p className="text-gray-700 text-sm">
                    Include <span className="font-mono">evaluator_meta</span> in your response to provide
                    the UI with display context — the Feedback page will show the evaluator name and
                    framework to trainees.
                  </p>
                </section>

                {/* 3b. Research Evaluator Plugins */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[5].keywords, docSearch) && 'hidden')}
                  id="research-evaluator"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Research Evaluator Plugins</h2>
                  <p className="text-gray-700 mb-3">
                    These are a different, separate thing from the trainee-facing{' '}
                    <span className="font-mono">Evaluator</span> plugins above. Research evaluators back
                    the <span className="font-mono">Run &amp; Compare</span> and{' '}
                    <span className="font-mono">Saved Runs</span> tabs on a session&apos;s{' '}
                    <span className="font-mono">Evaluate Sessions</span> workspace (admin + researcher
                    roles only) — they never touch trainee-facing feedback, and are never auto-run on
                    session close.
                  </p>

                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 mb-4">
                    <h4 className="font-semibold text-gray-900 mb-2">
                      Why this is kept separate from the trainee Evaluator (by design, not an oversight)
                    </h4>
                    <ul className="list-disc pl-5 text-sm text-gray-700 space-y-2">
                      <li>
                        <span className="font-semibold">Identity boundary.</span> A research evaluator
                        structurally cannot receive a <span className="font-mono">session_id</span> or a
                        DB handle — only an identity-stripped{' '}
                        <span className="font-mono">ResearchAdapterContext</span>. That is what makes the
                        &quot;researchers see transcripts, never real trainee identity&quot; guarantee an
                        enforced property of the protocol, not just a convention. Merging the two
                        interfaces would mean either the research side gains a path back to identity, or
                        the trainee side loses access to session state it needs (history lookups, timeline
                        events, direct writes) — a bad trade either way.
                      </li>
                      <li>
                        <span className="font-semibold">Different stability contracts.</span> Research
                        evaluators are meant to stay fixed and citable once registered (see the roadmap
                        note below); the trainee evaluator has no such constraint and should be free to
                        iterate quickly. Combining them would force one side&apos;s stability requirement
                        onto the other.
                      </li>
                      <li>
                        <span className="font-semibold">Different blast radius.</span> A trainee-evaluator
                        bug affects a live trainee, immediately. A research-evaluator bug affects one
                        offline comparison run. Keeping the code paths separate keeps a change made for one
                        context from carrying operational risk for the other.
                      </li>
                      <li>
                        <span className="font-semibold">If you want one underlying model for both:</span>{' '}
                        share the core scoring/rubric logic as a plain function or module, and write two
                        thin wrappers on top of it — one implementing <span className="font-mono">Evaluator</span>,
                        one implementing <span className="font-mono">ResearchResultAdapter</span>. That avoids
                        duplicating the actual scoring logic without merging the two protocols or their
                        registration paths.
                      </li>
                    </ul>
                  </div>

                  <h3 className="text-lg font-medium mt-6 mb-2">Explicit static registry, not dynamic discovery</h3>
                  <p className="text-gray-700 mb-3">
                    Unlike <span className="font-mono">PatientModel</span> / <span className="font-mono">Evaluator</span>{' '}
                    / <span className="font-mono">MetricsPlugin</span>, research evaluators are not
                    resolved from a settings string at runtime. They implement the{' '}
                    <span className="font-mono">ResearchResultAdapter</span> protocol (
                    <span className="font-mono">services/research_adapters/base.py</span>:{' '}
                    <span className="font-mono">build_native_result</span> and{' '}
                    <span className="font-mono">project</span>) and are registered explicitly, by hand, in{' '}
                    <span className="font-mono">services/research_adapters/defaults.py</span>&apos;s{' '}
                    <span className="font-mono">build_default_research_adapter_registry()</span> via{' '}
                    <span className="font-mono">ResearchAdapterRegistration(...)</span>. There is no{' '}
                    <span className="font-mono">PLUGIN_MODULES</span>-style loader for these — add the
                    adapter class, then add one registration call.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Identity-free by construction</h3>
                  <p className="text-gray-700 mb-3">
                    Adapters never see a session id or a trainee. They receive a{' '}
                    <span className="font-mono">ResearchAdapterContext</span> — a canonical, already
                    identity-stripped transcript (<span className="font-mono">transcript_hash</span>,{' '}
                    <span className="font-mono">transcript_turns</span>) plus the evaluator/framework
                    identifiers. This is what keeps the researcher-role redaction guarantee intact even as
                    new evaluators are added: there is nothing identity-bearing to accidentally leak.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Live model execution is opt-in and gated</h3>
                  <p className="text-gray-700 mb-3">
                    If your adapter calls an LLM (currently OpenAI or Gemini, via{' '}
                    <span className="font-mono">evaluator_llm_adapter_factory.py</span>), set{' '}
                    <span className="font-mono">requires_live_execution=True</span> and declare{' '}
                    <span className="font-mono">supported_providers</span> /{' '}
                    <span className="font-mono">default_provider</span> on the registration — the registry
                    validates these are consistent at startup. Two independent server flags then gate
                    whether a live evaluator is selectable at all in the UI:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 space-y-1 mb-3">
                    <li>
                      <span className="font-mono">settings.research_allow_live_evaluations</span> (
                      <span className="font-mono">research_allow_live_evaluations</span> in{' '}
                      <span className="font-mono">.env</span>, default <span className="font-mono">false</span>) —
                      must be on for any live (OpenAI/Gemini-backed) research evaluator to be selectable.
                    </li>
                    <li>
                      <span className="font-mono">settings.ace_ct_allow_experimental_rubric</span> (default{' '}
                      <span className="font-mono">false</span>) — an additional gate for evaluators marked{' '}
                      <span className="font-mono">experimental=True</span> on their registration.
                    </li>
                  </ul>
                  <p className="text-gray-700 mb-3">
                    Offline evaluators (<span className="font-mono">requires_live_execution=False</span>,
                    e.g. the APEX baseline / hybrid v1 / hybrid v2 research adapters) are always{' '}
                    <span className="font-mono">available</span> regardless of these flags. The UI also
                    requires a human to tick &quot;Explicitly allow live model execution for this run&quot;
                    per run, on top of the server flag, before a live evaluator actually calls out.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Minimal registration example</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`registry.register(
    ResearchAdapterRegistration(
        evaluator_identifier="my_research_evaluator",
        display_name="My Research Evaluator",
        evaluator_version="1.0.0",
        evaluator_type="my_research_evaluator",
        framework=my_framework_metadata,
        adapter=MyResearchAdapter(),
        requires_live_execution=False,  # or True + supported_providers/default_provider
        default_selected=False,
    )
)`}</code>
                  </pre>
                  <p className="text-gray-700 text-sm mb-6">
                    See the built-in <span className="font-mono">ApexResearchAdapter</span> and{' '}
                    <span className="font-mono">ACECTResearchAdapter</span> (
                    <span className="font-mono">services/research_adapters/</span>) for complete examples,
                    and the <Link to="/docs/research-workflow-guide" className="text-apex-700 hover:underline">
                      Research workflow guide
                    </Link>{' '}
                    for how these evaluators surface end-to-end for researchers running Evaluate Sessions.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Adding a new research evaluator today (developer task)</h3>
                  <p className="text-gray-700 mb-3">
                    There is no self-serve path yet &mdash; a researcher with a new evaluator idea needs a
                    developer to make a code change and restart the backend. In order:
                  </p>
                  <ol className="list-decimal pl-6 text-gray-700 space-y-1 mb-3">
                    <li>Implement the scoring logic (a new <span className="font-mono">ScoringService</span> compute
                      method, or reuse an existing LLM adapter with a different prompt/rubric).</li>
                    <li>Write a <span className="font-mono">ResearchResultAdapter</span> mapping that output onto
                      the shared <span className="font-mono">ResearchProjection</span> schema.</li>
                    <li>Add an <span className="font-mono">EvaluatorDefinition</span> entry in{' '}
                      <span className="font-mono">evaluator_comparison_service.py</span>.</li>
                    <li>Add a dispatch branch in <span className="font-mono">EvaluatorComparisonService._compute</span>
                      /<span className="font-mono">_run_one</span> (currently a hardcoded per-identifier chain, not
                      itself a registry &mdash; see the roadmap note below).</li>
                    <li>Register it in <span className="font-mono">research_adapters/defaults.py</span> via{' '}
                      <span className="font-mono">ResearchAdapterRegistration(...)</span>.</li>
                    <li>If it calls a live model, set <span className="font-mono">requires_live_execution=True</span>,
                      declare <span className="font-mono">supported_providers</span>/
                      <span className="font-mono">default_provider</span>, and mark{' '}
                      <span className="font-mono">experimental=True</span> with a warning string if it hasn&apos;t
                      been validated yet (see the ACE-CT-inspired evaluator for the pattern).</li>
                  </ol>
                  <p className="text-gray-700 text-sm mb-3">
                    This is deliberately reviewed and code-level, not dynamically discoverable &mdash; the research
                    contract depends on the registered evaluator set being fixed and citable, not swappable at
                    runtime.
                  </p>

                  <div className="rounded-lg border border-sky-200 bg-sky-50 p-4">
                    <h4 className="font-semibold text-sky-900 mb-2">Roadmap: lowering this bar for researchers</h4>
                    <ul className="list-disc pl-5 text-sm text-sky-900 space-y-2">
                      <li>
                        <span className="font-semibold">Soon &mdash; registry-fy the dispatch step.</span> Replace step
                        4&apos;s hardcoded if/elif chain with a per-definition registered compute function, mirroring
                        the <span className="font-mono">MatchingPolicyRegistry</span> pattern already used for
                        Item 3A (&quot;write one function, register it, zero changes to existing calculation
                        code&quot;). Doesn&apos;t add a new capability by itself, but every future evaluator addition
                        stops touching shared dispatch code.
                      </li>
                      <li>
                        <span className="font-semibold">Soon &mdash; prompt/rubric-only variants.</span> For the two
                        LLM-backed evaluator types (hybrid, ACE-CT-inspired-style), add a lighter registration path
                        that only needs a new (prompt_version, rubric config) entry against an existing adapter
                        &mdash; not a whole new adapter class &mdash; when a researcher just wants to try a different
                        prompt or rubric weighting.
                      </li>
                      <li>
                        <span className="font-semibold">Medium &mdash; declarative evaluator definitions.</span> A
                        small reviewed YAML/JSON spec (provider, prompt template, rubric dimensions, versioning) that
                        a researcher without deep backend experience can draft themselves and hand to a developer for
                        a quick review-and-merge, instead of hand-writing the Python registration boilerplate above.
                      </li>
                      <li>
                        <span className="font-semibold">Later &mdash; sandboxed preview tier.</span> Let an
                        unregistered/unreviewed evaluator config run in Run &amp; Compare preview only (never
                        Saved Runs, never counted as citable/reproducible), so researchers can experiment before the
                        formal registration step instead of needing it upfront.
                      </li>
                    </ul>
                  </div>
                </section>

                {/* 4. Metrics Plugins */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[6].keywords, docSearch) && 'hidden')}
                  id="metrics"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Metrics Plugins</h2>
                  <p className="text-gray-700 mb-3">
                    Implement the <span className="font-mono">MetricsPlugin</span> protocol: a synchronous
                    method <span className="font-mono">compute(db, session_id)</span> that returns a
                    dictionary of metrics.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Example</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`from typing import Any
from sqlalchemy.orm import Session


class MyMetricsPlugin:
    def compute(self, db: Session, session_id: int) -> dict[str, Any]:
        # Compute custom metrics from session/turns.
        return {
            "custom_metric_a": 42,
            "custom_metric_b": "value",
        }`}</code>
                  </pre>

                  <p className="text-gray-700">
                    When <span className="font-mono text-sm">ScoringService.generate_feedback</span> runs (for
                    example on session close), after the evaluator finishes the backend runs each plugin in
                    the session&apos;s frozen <span className="font-mono text-sm">metrics_plugins</span>,
                    calls <span className="font-mono text-sm">compute(db, session_id)</span>, and stores one
                    JSON object on <span className="font-mono text-sm">sessions.metrics_json</span> (API field{' '}
                    <span className="font-mono text-sm">metrics_json</span>): keys are plugin ids, values are
                    each <span className="font-mono text-sm">compute</span> return dict. Metrics plugins are not
                    run if code bypasses <span className="font-mono text-sm">generate_feedback</span>. See{' '}
                    <span className="font-mono text-sm">docs/plugin_architecture.md</span> for the full contract.
                  </p>
                </section>

                {/* 5. Plugin Registration */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[7].keywords, docSearch) && 'hidden')}
                  id="registration"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Plugin Registration</h2>
                  <p className="text-gray-700 mb-3">
                    <span className="font-semibold">1. Code registration (import time).</span> Each plugin module
                    calls <span className="font-mono text-sm">PluginRegistry.register_*</span> when imported.
                    Startup imports the list in{' '}
                    <span className="font-mono text-sm">plugins/load_plugins.py</span> (
                    <span className="font-mono text-sm">PLUGIN_MODULES</span>); add your module there.
                  </p>
                  <p className="text-gray-700 mb-3">
                    <span className="font-semibold">2. Configuration (which plugin runs).</span> Resolution is
                    typically case override → settings default at session creation; the session row stores the
                    frozen ids.
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 space-y-1 mb-3">
                    <li>
                      <span className="font-semibold">Patient model:</span>{' '}
                      <span className="font-mono">patient_model_plugin</span> in settings and/or on the case.
                      Dialogue loads using <span className="font-mono">session.patient_model_plugin</span>{' '}
                      (fallback: <span className="font-mono">settings.patient_model_plugin</span>).
                    </li>
                    <li>
                      <span className="font-semibold">Evaluator:</span>{' '}
                      <span className="font-mono">evaluator_plugin</span> on case/settings → frozen{' '}
                      <span className="font-mono">session.evaluator_plugin</span> for scoring.
                    </li>
                    <li>
                      <span className="font-semibold">Metrics (list):</span>{' '}
                      <span className="font-mono">metrics_plugins</span> on case/settings → frozen{' '}
                      <span className="font-mono">session.metrics_plugins</span> (JSON array text) for scoring.
                    </li>
                  </ul>

                  <h3 className="text-lg font-medium mt-6 mb-2">Example plugin path</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`plugins.patient_models.default_llm_patient:DefaultLLMPatientModel`}</code>
                  </pre>

                  <p className="text-gray-700">
                    The format is always <span className="font-mono">module.path:ClassName</span>. The
                    module must be importable (for example, under <span className="font-mono">backend/src</span>{' '}
                    or on <span className="font-mono">PYTHONPATH</span>), and the class must implement the
                    corresponding interface.
                  </p>
                  <p className="text-gray-700 mt-3">
                    This code-time registration is separate from &mdash; and unaffected by &mdash; the
                    DB-backed lifecycle registry described in{' '}
                    <span className="font-mono">Plugin Registry &amp; Promotions</span> below. That registry
                    tracks the same plugins as rows for maturity/audit purposes; it never changes which
                    plugin a session actually runs.
                  </p>
                </section>

                {/* 6. Testing Plugins */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[8].keywords, docSearch) && 'hidden')}
                  id="testing"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Testing Plugins</h2>
                  <ul className="list-disc pl-6 text-gray-700 space-y-1 mb-3">
                    <li>
                      <span className="font-semibold">Location:</span> Add tests under{' '}
                      <span className="font-mono">backend/tests/plugins/</span> and{' '}
                      <span className="font-mono">backend/tests/services/</span> for integration coverage.
                    </li>
                    <li>
                      <span className="font-semibold">Patterns:</span> Dialogue resolves the patient model from
                      the session and <span className="font-mono">PluginRegistry</span> (not{' '}
                      <span className="font-mono">get_patient_model()</span> alone). Prefer registering a dummy
                      class and setting <span className="font-mono">session.patient_model_plugin</span>, or patch{' '}
                      <span className="font-mono">_instantiate_patient_model</span> in{' '}
                      <span className="font-mono">dialogue_service</span>. For scoring, exercise{' '}
                      <span className="font-mono">ScoringService.generate_feedback</span> with frozen evaluator /
                      metrics on the session. Clear <span className="font-mono">lru_cache</span> on{' '}
                      <span className="font-mono">get_patient_model</span>, <span className="font-mono">get_evaluator</span>,{' '}
                      <span className="font-mono">get_metrics_plugins</span> in{' '}
                      <span className="font-mono">core/plugin_manager</span> only when tests hit those
                      settings-based entry points directly.
                    </li>
                    <li>
                      <span className="font-semibold">Interfaces:</span> Prefer testing against the public
                      interface (for example, <span className="font-mono">generate_response</span>,{' '}
                      <span className="font-mono">evaluate</span>, <span className="font-mono">compute</span>)
                      so that refactors preserve behavior.
                    </li>
                  </ul>
                </section>

                {/* 7. Best Practices */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[9].keywords, docSearch) && 'hidden')}
                  id="best-practices"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Best Practices</h2>
                  <ul className="list-disc pl-6 text-gray-700 space-y-2">
                    <li>
                      <span className="font-semibold">Keep plugins stateless where possible:</span> Rely on{' '}
                      <span className="font-mono">state</span>, <span className="font-mono">db</span>, and{' '}
                      <span className="font-mono">session_id</span> for input. Avoid global mutable state so
                      that plugins are safe under concurrency and caching.
                    </li>
                    <li>
                      <span className="font-semibold">Reuse services where possible:</span> Use existing
                      repositories and services (for example,{' '}
                      <span className="font-mono">ScoringService</span>, session / turn repos) inside your
                      plugin to stay consistent with the rest of the system and avoid duplicating logic.
                    </li>
                    <li>
                      <span className="font-semibold">Avoid modifying core services:</span> Extend behavior via
                      new plugins or new classes that implement the interfaces; do not change{' '}
                      <span className="font-mono">DialogueService</span> or{' '}
                      <span className="font-mono">ScoringService</span> internals to suit a single plugin.
                    </li>
                    <li>
                      <span className="font-semibold">Validate configuration early:</span> Use the same{' '}
                      <span className="font-mono">module.path:ClassName</span> format as the defaults. Invalid
                      paths cause errors at startup or first use, which is intentional so misconfiguration is
                      caught quickly.
                    </li>
                  </ul>
                </section>

                {/* 8. Plugin Registry & Promotions */}
                <section
                  className={cn('mb-6', !docSectionVisible(DOC_NAV[10].keywords, docSearch) && 'hidden')}
                  id="plugin-registry-workflow"
                >
                  <h2 className="text-xl font-semibold mt-8 mb-3">Plugin Registry &amp; Promotions</h2>
                  <p className="text-gray-700 mb-3">
                    Alongside the code-time registration above, APEX keeps a{' '}
                    <span className="font-mono">plugin_registrations</span> table &mdash; one row per plugin
                    (evaluator, patient model, or metrics) &mdash; that tracks maturity and provides an audit
                    trail. This is additive: it does not replace{' '}
                    <span className="font-mono">PluginRegistry</span> /{' '}
                    <span className="font-mono">PLUGIN_MODULES</span>, and it never changes which plugin a
                    session actually runs. Think of it as a catalog and governance layer on top of the
                    plugins that already exist in code.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Plugin kinds</h3>
                  <p className="text-gray-700 mb-3">
                    Every registration has a <span className="font-mono">plugin_kind</span> of{' '}
                    <span className="font-mono">evaluator</span>, <span className="font-mono">patient_model</span>,
                    or <span className="font-mono">metrics</span> &mdash; the same three plugin types described
                    earlier in this guide. (This is the plugin registry&apos;s three <em>kinds</em>; it&apos;s
                    a different count from however many individual evaluator plugins happen to be registered.)
                  </p>
                  <p className="text-gray-700 mb-3">
                    <span className="font-semibold">Note on <span className="font-mono">evaluator</span> rows
                    specifically:</span> both the trainee-facing{' '}
                    <Link to="/docs/plugin-developer-guide#evaluator" className="text-apex-700 hover:underline">
                      Evaluator plugin
                    </Link>{' '}
                    and the{' '}
                    <Link to="/docs/plugin-developer-guide#research-evaluator" className="text-apex-700 hover:underline">
                      Research Evaluator plugin
                    </Link>{' '}
                    get tracked as <span className="font-mono">plugin_kind=&quot;evaluator&quot;</span> rows
                    here &mdash; that&apos;s what &quot;unified&quot; means in this registry. It is{' '}
                    <span className="font-semibold">only</span> a shared identity/lifecycle tracking layer:
                    the two remain separate systems with separate protocols, separate registration paths, and
                    (intentionally) separate access to trainee identity. See &quot;Why this is kept
                    separate&quot; in the Research Evaluator Plugins section above for the reasoning.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Lifecycle stages</h3>
                  <p className="text-gray-700 mb-3">
                    Each registration moves through six stages, in order:
                  </p>
                  <ol className="list-decimal pl-6 text-gray-700 space-y-1 mb-3">
                    <li><span className="font-mono">draft</span> &mdash; newly registered, not yet reviewed.</li>
                    <li><span className="font-mono">experimental</span> &mdash; usable for exploration, not yet vetted.</li>
                    <li><span className="font-mono">under_review</span> &mdash; a promotion request is pending review.</li>
                    <li><span className="font-mono">promoted</span> &mdash; reviewed and approved for broader use.</li>
                    <li><span className="font-mono">deprecated</span> &mdash; still usable, but on its way out.</li>
                    <li><span className="font-mono">retired</span> &mdash; no longer intended for use.</li>
                  </ol>
                  <p className="text-gray-700 mb-3">
                    Registrations seeded directly by a migration (for example the built-in{' '}
                    <span className="font-mono">DefaultLLMPatientModel</span> and{' '}
                    <span className="font-mono">ApexMetrics</span>) start life already at{' '}
                    <span className="font-mono">promoted</span>, since they&apos;re the existing defaults, not
                    new candidates.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">Promotion request/review workflow</h3>
                  <p className="text-gray-700 mb-3">
                    Moving a registration forward a stage is a request-then-decision flow, not a direct
                    field edit, so there&apos;s always an audit trail of who asked for what and who approved
                    it:
                  </p>
                  <ol className="list-decimal pl-6 text-gray-700 space-y-1 mb-3">
                    <li>
                      A researcher or admin opens a promotion request on a registration, naming the{' '}
                      <span className="font-mono">requested_stage</span> and optional notes.
                    </li>
                    <li>
                      Only one <span className="font-mono">pending</span> request can exist per registration
                      at a time &mdash; enforced with a partial unique DB index, not just app-level checks.
                    </li>
                    <li>
                      An admin approves (moving the registration to the requested stage) or rejects the
                      request, each with optional review notes.
                    </li>
                    <li>
                      The original requester can withdraw their own pending request instead of waiting on a
                      decision.
                    </li>
                  </ol>
                  <p className="text-gray-700 mb-3">
                    Approving a request that targets <span className="font-mono">promoted</span> or{' '}
                    <span className="font-mono">deprecated</span> routes through the same{' '}
                    <span className="font-mono">RegistryService.promote()</span> /{' '}
                    <span className="font-mono">.deprecate()</span> methods used elsewhere, so those two
                    transitions stay consistent everywhere they happen.
                  </p>

                  <h3 className="text-lg font-medium mt-6 mb-2">API endpoints</h3>
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-md text-sm overflow-x-auto mb-3">
                    <code>{`GET  /v1/research/plugin-registrations
GET  /v1/research/plugin-registrations/{id}

POST /v1/research/plugin-registrations/{id}/promotion-requests
GET  /v1/research/plugin-registrations/{id}/promotion-requests
GET  /v1/research/promotion-requests
GET  /v1/research/promotion-requests/{id}
POST /v1/research/promotion-requests/{id}/approve   (admin only)
POST /v1/research/promotion-requests/{id}/reject    (admin only)
POST /v1/research/promotion-requests/{id}/withdraw  (admin or the original requester)`}</code>
                  </pre>

                  <h3 className="text-lg font-medium mt-6 mb-2">Where to see this in the UI</h3>
                  <p className="text-gray-700">
                    The <span className="font-semibold">Plugin Registry</span> tab on the Research page lists
                    every registration with its kind and stage, lets a researcher or admin file a promotion
                    request, and shows the promotion-request queue with admin approve/reject actions and
                    requester withdraw &mdash; no direct API calls needed for day-to-day use.
                  </p>
                </section>
              </article>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

