/**
 * Root router: public routes, role-protected trainee/admin pages, and login redirect.
 */
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, matchPath, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useAuthStore } from './store/authStore'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { Signup } from './pages/Signup'
import { Dashboard } from './pages/Dashboard'
import { Cases } from './pages/Cases'
import { CaseDetail } from './pages/CaseDetail'
import { Feedback } from './pages/Feedback'
import { Sessions } from './pages/Sessions'
import { SessionDetailPage } from './pages/SessionDetailPage'
import { Analytics } from './pages/Analytics'
import { Admin } from './pages/Admin'
import { Research } from './pages/Research'
import { ResearchSessions } from './pages/ResearchSessions'
import { ResearchEvaluationSessionPage } from './pages/ResearchEvaluationSessionPage'
import { AdminResearchSessionPage } from './pages/AdminResearchSessionPage'
import { PluginDeveloperGuide } from './pages/PluginDeveloperGuide'
import { DeveloperOnboarding } from './pages/DeveloperOnboarding'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuthGate } from './hooks/useAuthGate'
import { getHomeRouteForRole } from './lib/roleRoutes'
import apexLogo from './assets/apex-capstone-logo.png'

const ROUTE_TITLES: Array<{ path: string; screenName: string }> = [
  { path: '/', screenName: 'Home' },
  { path: '/login', screenName: 'Login' },
  { path: '/signup', screenName: 'Sign Up' },
  { path: '/dashboard', screenName: 'Dashboard' },
  { path: '/case/:caseId', screenName: 'Case Details' },
  { path: '/feedback/:sessionId', screenName: 'Feedback' },
  { path: '/sessions', screenName: 'My Sessions' },
  { path: '/sessions/:sessionId', screenName: 'Session Details' },
  { path: '/admin', screenName: 'Admin Dashboard' },
  { path: '/research', screenName: 'Research' },
  { path: '/docs/plugin-developer-guide', screenName: 'Plugin Developer Guide' },
]

const getScreenName = (pathname: string) =>
  ROUTE_TITLES.find(({ path }) => matchPath({ path, end: true }, pathname))?.screenName ?? 'App'

const BrandingManager = () => {
  const location = useLocation()

  useEffect(() => {
    document.title = `APEX | ${getScreenName(location.pathname)}`

    let favicon = document.querySelector("link[rel='icon']") as HTMLLinkElement | null
    if (!favicon) {
      favicon = document.createElement('link')
      favicon.rel = 'icon'
      document.head.appendChild(favicon)
    }

    favicon.type = 'image/png'
    favicon.href = apexLogo
  }, [location.pathname])

  return null
}

/**
 * Renders the login page or redirects authenticated users to the dashboard.
 *
 * @remarks
 * Prevents logged-in users from seeing `/login` again.
 *
 * @returns Login screen or a client-side redirect
 */
const LoginRoute = () => {
  const gate = useAuthGate()
  const user = useAuthStore((s) => s.user)

  if (gate === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center text-gray-500">
        Loading...
      </div>
    )
  }

  if (gate === 'authed') {
    return <Navigate to={getHomeRouteForRole(user?.role)} replace />
  }
  return <Login />
}

/**
 * Application route tree with {@link ProtectedRoute} wrappers for auth and roles.
 *
 * @returns Browser router wrapping all page routes
 */
function App() {
  const initialize = useAuthStore((s) => s.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <BrowserRouter>
      <BrandingManager />
      <Toaster position="top-center" richColors />
      <Routes>
        {/* Public */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<LoginRoute />} />
        <Route path="/signup" element={<Signup />} />

        {/* Shared: admin + trainee */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute allowedRoles={['admin', 'trainee', 'researcher']}>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/case/:caseId"
          element={
            <ProtectedRoute allowedRoles={['admin', 'trainee', 'researcher']}>
              <CaseDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/feedback/:sessionId"
          element={
            <ProtectedRoute allowedRoles={['admin', 'trainee', 'researcher']}>
              <Feedback />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sessions"
          element={
            <ProtectedRoute>
              <Sessions />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases"
          element={
            <ProtectedRoute allowedRoles={['admin', 'trainee', 'researcher']}>
              <Cases />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sessions/:sessionId"
          element={
            <ProtectedRoute>
              <SessionDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedRoute allowedRoles={['admin', 'trainee', 'researcher']}>
              <Analytics />
            </ProtectedRoute>
          }
        />

        {/* Admin routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <Admin />
            </ProtectedRoute>
          }
        />
        <Route
          path="/research"
          element={
            <ProtectedRoute allowedRoles={['admin', 'researcher']}>
              <Research />
            </ProtectedRoute>
          }
        />
        <Route
          path="/research/sessions"
          element={
            <ProtectedRoute allowedRoles={['admin', 'researcher']}>
              <ResearchSessions />
            </ProtectedRoute>
          }
        />
        <Route
          path="/research/evaluate/:sessionId"
          element={
            <ProtectedRoute allowedRoles={['admin', 'researcher']}>
              <ResearchEvaluationSessionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/sessions/:sessionId"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <AdminResearchSessionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/docs/plugin-developer-guide"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <PluginDeveloperGuide />
            </ProtectedRoute>
          }
        />
        <Route
          path="/docs/developer-onboarding"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <DeveloperOnboarding />
            </ProtectedRoute>
          }
        />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
