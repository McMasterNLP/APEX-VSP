/**
 * Role-filtered left navigation for primary app sections (desktop + mobile slide-over).
 */
import { Link, useLocation, type Location } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { LayoutDashboard, FileText, Shield, BarChart3, Menu, LineChart, ClipboardList } from 'lucide-react'
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

  const adminNavigation = [
    {
      name: 'Research',
      href: '/research',
      icon: BarChart3,
      roles: ['admin', 'researcher'],
      isActive: (loc: Location) => loc.pathname === '/research' || loc.pathname.startsWith('/research/'),
    },
    {
      name: 'Admin',
      href: '/admin',
      icon: Shield,
      roles: ['admin'],
      isActive: (loc: Location) => loc.pathname === '/admin' || loc.pathname.startsWith('/admin/'),
    },
  ].filter((item) => item.roles.includes(user?.role || 'trainee'))

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

          {adminNavigation.length > 0 && (
            <div className="pt-4">
              <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                {user?.role === 'admin' ? 'Admin' : 'Research'}
              </div>
              <div className="space-y-1">
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
