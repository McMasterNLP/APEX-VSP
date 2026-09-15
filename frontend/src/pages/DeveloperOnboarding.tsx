/**
 * Short onboarding for developers: repo setup, team workflow, plugins.
 */
import { Link } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import { Sidebar } from '@/components/Sidebar'
import { useAuthStore } from '@/store/authStore'

/**
 * Skimmable developer onboarding (admin).
 */
export const DeveloperOnboarding = () => {
  const { user } = useAuthStore()

  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <main className="flex-1 overflow-y-auto md:ml-64 bg-gray-50">
          <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
            <nav className="mb-4 text-sm text-gray-500">
              {user?.role === 'admin' && <span className="text-gray-900">Developer onboarding</span>}
              {!user?.role && <span className="text-gray-900">Developer onboarding</span>}
            </nav>

            <h1 className="text-3xl font-bold text-gray-900 mb-2">Developer onboarding</h1>
            <p className="text-gray-600 mb-8">
              Quick start for the capstone repo. For plugin APIs and examples, see the{' '}
              <Link to="/docs/plugin-developer-guide" className="text-apex-700 font-medium hover:underline">
                Plugin developer guide
              </Link>
              . For the research evaluation workflow (admin/researcher roles), see the{' '}
              <Link to="/docs/research-workflow-guide" className="text-apex-700 font-medium hover:underline">
                Research workflow guide
              </Link>
              .
            </p>

            <section className="mb-10">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">1. Repo setup</h2>
              <ul className="list-disc pl-5 space-y-2 text-gray-700 text-sm leading-relaxed">
                <li>
                  <span className="font-medium">Clone:</span>{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">git clone</code> your fork or
                  team remote, then <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">cd</code> into
                  the project root.
                </li>
                <li>
                  <span className="font-medium">Backend:</span> from <code className="text-xs">backend/</code>,
                  install deps (Poetry: <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">poetry install</code>
                  ) and follow <code className="text-xs">backend/README.md</code> for env vars and DB.
                </li>
                <li>
                  <span className="font-medium">Frontend:</span> from <code className="text-xs">frontend/</code>,{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">npm install</code> (or pnpm/yarn per
                  team), copy <code className="text-xs">.env.example</code> if present, then{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">npm run dev</code>.
                </li>
                <li>
                  <span className="font-medium">Run:</span> start API and Vite dev server; open the app URL from the
                  frontend README. Log in with a seeded or invited user to hit protected routes.
                </li>
              </ul>
            </section>

            <section className="mb-10">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">2. How we work in a team</h2>
              <ul className="list-disc pl-5 space-y-2 text-gray-700 text-sm leading-relaxed">
                <li>
                  <span className="font-medium">Branches:</span> use short-lived{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">feature/…</code> branches off{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">main</code>; open PRs for review
                  instead of pushing straight to main.
                </li>
                <li>
                  <span className="font-medium">Plugins:</span> add code under{' '}
                  <code className="text-xs">backend/src/plugins/</code> (patient_models, evaluators, metrics).
                  Register the module in <code className="text-xs">plugins/load_plugins.py</code> (
                  <code className="text-xs">PLUGIN_MODULES</code>) so it loads at startup.
                </li>
                <li>
                  <span className="font-medium">Tests:</span> run{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">pytest</code> from{' '}
                  <code className="text-xs">backend/</code>; add cases next to related code under{' '}
                  <code className="text-xs">backend/tests/</code>. For UI, use the team&apos;s lint/test script in{' '}
                  <code className="text-xs">frontend/package.json</code>.
                </li>
              </ul>
            </section>

            <section className="mb-10">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">3. Plugin integration (quick)</h2>
              <ul className="list-disc pl-5 space-y-2 text-gray-700 text-sm leading-relaxed">
                <li>
                  <span className="font-medium">Where:</span>{' '}
                  <code className="text-xs">backend/src/plugins/…</code> + protocols in{' '}
                  <code className="text-xs">backend/src/interfaces/</code>.
                </li>
                <li>
                  <span className="font-medium">Register:</span> in your module, call{' '}
                  <code className="text-xs">PluginRegistry.register_*</code> with a stable{' '}
                  <code className="text-xs">name</code> (usually <code className="text-xs">module:Class</code>).
                  Append the module to <code className="text-xs">PLUGIN_MODULES</code>.
                </li>
                <li>
                  <span className="font-medium">Configure:</span> set{' '}
                  <code className="text-xs">patient_model_plugin</code>,{' '}
                  <code className="text-xs">evaluator_plugin</code>, or{' '}
                  <code className="text-xs">metrics_plugins</code> in settings / <code className="text-xs">.env</code>{' '}
                  (see root README and <code className="text-xs">docs/plugin_architecture.md</code>).
                </li>
                <li>
                  <span className="font-medium">Test:</span> unit-test the plugin class; use service tests or mocks
                  for session create and feedback where your plugin is selected.
                </li>
              </ul>
            </section>

            <section className="mb-10">
              <h2 className="text-xl font-semibold text-gray-900 mb-3">4. Roles &amp; research evaluation</h2>
              <ul className="list-disc pl-5 space-y-2 text-gray-700 text-sm leading-relaxed">
                <li>
                  <span className="font-medium">Roles:</span> <code className="text-xs">trainee</code> only
                  sees their own sessions and feedback; <code className="text-xs">admin</code> and{' '}
                  <code className="text-xs">researcher</code> can both reach the Research area and its
                  Evaluate Sessions workspace. Researchers see real transcripts (needed for evaluation) but
                  trainee identity is pseudonymized for them &mdash; admins see real trainee names.
                </li>
                <li>
                  <span className="font-medium">Evaluate Sessions:</span> under Research, this is where
                  admins/researchers filter sessions (case, state, plugin, evaluation status, evaluator) and
                  open a session&apos;s <span className="font-medium">Run &amp; Compare</span> (ephemeral
                  preview) and <span className="font-medium">Saved Runs</span> (persisted, append-only)
                  tabs. Walk through it once via the{' '}
                  <Link to="/docs/research-workflow-guide" className="text-apex-700 font-medium hover:underline">
                    Research workflow guide
                  </Link>
                  .
                </li>
                <li>
                  <span className="font-medium">Live model evaluators:</span> OpenAI/Gemini-backed research
                  evaluators are off by default locally &mdash; set{' '}
                  <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">research_allow_live_evaluations=true</code>{' '}
                  (and <code className="rounded bg-gray-200 px-1.5 py-0.5 text-xs">ace_ct_allow_experimental_rubric=true</code>{' '}
                  for the experimental ACE-CT-inspired one) in <code className="text-xs">backend/.env</code> and
                  restart the backend. This is separate from having{' '}
                  <code className="text-xs">openai_api_key</code> / <code className="text-xs">gemini_api_key</code>{' '}
                  configured, which is required just to boot the backend.
                </li>
                <li>
                  <span className="font-medium">Adding a research evaluator:</span> unlike the dynamic
                  plugin types above, research evaluators are registered explicitly in{' '}
                  <code className="text-xs">services/research_adapters/defaults.py</code> &mdash; see the{' '}
                  <Link to="/docs/plugin-developer-guide" className="text-apex-700 font-medium hover:underline">
                    Plugin developer guide
                  </Link>
                  &apos;s &quot;Research Evaluator Plugins&quot; section.
                </li>
              </ul>
            </section>
          </div>
        </main>
      </div>
    </div>
  )
}
