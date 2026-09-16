/**
 * Role-filtered left navigation for primary app sections (desktop + mobile slide-over).
 */
import { Link, useLocation, type Location } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { LayoutDashboard, FileText, Shield, BarChart3, Menu, LineChart, ClipboardList, ClipboardCheck, FlaskConical, Puzzle, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * Renders sidebar links filtered by the current user's role.
 *
 * @remarks
 * `collapsed` hides the panel on small screens; a floating control can reopen it.
 * The `navigation` list is filtered to items whose `roles` includes the active role (default trainee).
 *
 * @returns Sidebar JSX or null when logged out
 */
export const Sidebar = () => {
  const { user, isAuthenticated } = useAuthStore()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  if (!isAuthenticated) return null

  const navigation = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: LayoutDashboard,
      roles: ['trainee', 'admin', 'researcher'],
      isActive: (loc: Location) => loc.pathname === '/dashboard',
    },
    {
      name: 'Sessions',
      href: '/sessions',
      icon: ClipboardList,
      roles: ['trainee', 'admin', 'researcher'],
      isActive: (loc: Location) => loc.pathname === '/sessions' || loc.pathname.startsWith('/sessions/'),
    },
    {
      name: 'Cases',
      href: '/cases',
      icon: FileText,
      roles: ['trainee', 'admin', 'researcher'],
      isActive: (loc: Location) => loc.pathname === '/cases' || loc.pathname.startsWith('/case/'),
    },
    {
      name: 'Analytics',
      href: '/analytics',
      icon: LineChart,
      roles: ['trainee', 'admin', 'researcher'],
    },
  ].filter((item) => item.roles.includes(user?.role || 'trainee'))

  const researchOverviewIsActive = (loc: Location) =>
    loc.pathname === '/research' &&
    !['?tab=analytics', '?tab=evaluate', '?tab=registry', '?tab=import'].includes(loc.search)

  const researchSubNavigation = [
    {
      name: 'Analytics',
      href: '/research?tab=analytics',
      icon: BarChart3,
      isActive: (loc: Location) =>
        loc.pathname === '/research' && loc.search === '?tab=analytics',
    },
    {
      name: 'Evaluate Sessions',
      href: '/research?tab=evaluate',
      icon: ClipboardCheck,
      isActive: (loc: Location) => loc.pathname === '/research' && loc.search === '?tab=evaluate',
    },
    {
      name: 'Plugin Registry',
      href: '/research?tab=registry',
      icon: Puzzle,
      isActive: (loc: Location) => loc.pathname === '/research' && loc.search === '?tab=registry',
    },
    {
      name: 'Import Sessions',
      href: '/research?tab=import',
      icon: Sparkles,
      isActive: (loc: Location) => loc.pathname === '/research' && loc.search === '?tab=import',
    },
  ]

  const adminNavigation = [
    {
      name: 'Admin',
      href: '/admin',
      icon: Shield,
      roles: ['admin'],
      isActive: (loc: Location) => loc.pathname === '/admin' || loc.pathname.startsWith('/admin/'),
    },
  ].filter((item) => item.roles.includes(user?.role || 'trainee'))

  const showResearch = ['admin', 'researcher'].includes(user?.role || 'trainee')

  return (
    <div
      className={cn(
        'fixed left-0 top-16 z-40 h-[calc(100vh-4rem)] w-64 border-r bg-white transition-transform md:translate-x-0',
        collapsed ? '-translate-x-full' : 'translate-x-0'
      )}
    >
      <div className="flex h-full flex-col">
        <div className="flex h-16 items-center justify-between border-b px-4 md:hidden">
          <span className="text-sm font-semibold">Navigation</span>
          <button
            onClick={() => setCollapsed(true)}
            className="p-2 rounded-md hover:bg-apex-50"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-2 py-4">
          {navigation.map((item) => {
            const isActive = item.isActive
              ? item.isActive(location)
              : location.pathname === item.href.split('#')[0]
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'group flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-apex-100 text-apex-900'
                    : 'text-gray-700 hover:bg-apex-50 hover:text-apex-900'
                )}
              >
                <item.icon
                  className={cn(
                    'h-5 w-5 shrink-0',
                    isActive
                      ? 'text-apex-900'
                      : 'text-gray-600 group-hover:text-apex-900'
                  )}
                />
                <span>{item.name}</span>
              </Link>
            )
          })}

          {showResearch && (
            <div className="pt-4">
              {/*
                "Research" is a real link to the Overview tab (not just a section label) so
                it's pressable like every other top-level item, with Analytics and Evaluate
                Sessions nested as sub-links directly beneath it -- one click away from
                anywhere in the app, and visually a child of Research rather than a sibling.
              */}
              <Link
                to="/research"
                className={cn(
                  'group flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  researchOverviewIsActive(location)
                    ? 'bg-emerald-100 text-emerald-900'
                    : 'text-gray-700 hover:bg-emerald-50 hover:text-emerald-900'
                )}
              >
                <FlaskConical
                  className={cn(
                    'h-5 w-5 shrink-0',
                    researchOverviewIsActive(location)
                      ? 'text-emerald-900'
                      : 'text-gray-600 group-hover:text-emerald-900'
                  )}
                />
                <span>Research</span>
              </Link>
              <div className="mt-1 ml-5 space-y-1 border-l border-gray-200 pl-3">
                {researchSubNavigation.map((item) => {
                  const isActive = item.isActive(location)
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={cn(
                        'group flex items-center space-x-3 rounded-lg py-2 pl-3 pr-3 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-emerald-100 text-emerald-900'
                          : 'text-gray-700 hover:bg-emerald-50 hover:text-emerald-900'
                      )}
                    >
                      <item.icon
                        className={cn(
                          'h-4 w-4 shrink-0',
                          isActive
                            ? 'text-emerald-900'
                            : 'text-gray-600 group-hover:text-emerald-900'
                        )}
                      />
                      <span>{item.name}</span>
                    </Link>
                  )
                })}
              </div>
            </div>
          )}

          {adminNavigation.length > 0 && (
            <div className={cn(showResearch ? 'pt-3' : 'pt-4', 'space-y-1')}>
              {adminNavigation.map((item) => {
                const isActive = item.isActive(location)
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={cn(
                      'group flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-emerald-100 text-emerald-900'
                        : 'text-gray-700 hover:bg-emerald-50 hover:text-emerald-900'
                    )}
                  >
                    <item.icon
                      className={cn(
                        'h-5 w-5 shrink-0',
                        isActive
                          ? 'text-emerald-900'
                          : 'text-gray-600 group-hover:text-emerald-900'
                      )}
                    />
                    <span>{item.name}</span>
                  </Link>
                )
              })}
            </div>
          )}
        </nav>
      </div>

      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          className="fixed left-0 top-20 z-50 rounded-r-md border-r border-t border-b bg-white p-2 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}
    </div>
  )
}
