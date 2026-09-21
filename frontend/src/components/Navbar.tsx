/**
 * Top navigation bar: branding, optional developer docs link (admin), user chip, and logout.
 */
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Button } from './ui/button'
import { LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import apexLogo from '@/assets/apex-capstone-logo.png'

/**
 * Renders the authenticated header or `null` when logged out.
 *
 * @remarks
 * Mobile layout toggles `mobileMenuOpen` for a collapsible drawer with the same links/actions.
 *
 * @returns Navbar JSX or null
 */
export const Navbar = () => {
  const { user, logout, isAuthenticated } = useAuthStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  if (!isAuthenticated) return null

  return (
    <nav className="border-b bg-white shadow-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center">
            <Link to="/dashboard" className="flex items-center gap-3.5 text-gray-900">
              <img src={apexLogo} alt="APEX logo" className="h-11 w-11 rounded-xl object-cover shadow-sm" />
              <div className="flex flex-col justify-center gap-0.5 leading-tight">
                <span className="brand-font text-xl font-bold tracking-[0.22em] text-apex-700">
                  APEX
                </span>
                <span className="text-[9px] font-medium uppercase tracking-[0.18em] text-gray-500">
                  AI Patient Experience Simulator
                </span>
              </div>
            </Link>
          </div>

          <div className="hidden md:block">
            <div className="ml-4 flex items-center space-x-6">
              <div className="flex items-center gap-4">
                <Link
                  to="/docs/user-guide"
                  className="text-sm font-medium text-gray-700 hover:text-apex-700"
                >
                  User guide
                </Link>
                {user?.role === 'admin' && (
                  <>
                    <Link
                      to="/docs/admin-guide"
                      className="text-sm font-medium text-gray-700 hover:text-apex-700"
                    >
                      Admin guide
                    </Link>
                    <Link
                      to="/docs/developer-onboarding"
                      className="text-sm font-medium text-gray-700 hover:text-apex-700"
                    >
                      Onboarding
                    </Link>
                    <Link
                      to="/docs/plugin-developer-guide"
                      className="text-sm font-medium text-gray-700 hover:text-apex-700"
                    >
                      Plugin guide
                    </Link>
                  </>
                )}
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-700">
                  {user?.full_name || user?.email}
                </span>
                <span className="rounded-full bg-apex-100 px-2.5 py-0.5 text-xs font-medium text-apex-800">
                  {user?.role && user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                </span>
                <Button variant="default" size="sm" onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Logout
                </Button>
              </div>
            </div>
          </div>

          <div className="md:hidden">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              <Menu className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="border-t md:hidden">
            <div className="space-y-1 px-2 pb-3 pt-2">
              <div className="px-3 py-2 text-sm text-gray-700">
                {user?.full_name || user?.email}
              </div>
              <Link
                to="/docs/user-guide"
                className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md"
                onClick={() => setMobileMenuOpen(false)}
              >
                User guide
              </Link>
              {user?.role === 'admin' && (
                <>
                  <Link
                    to="/docs/admin-guide"
                    className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Admin guide
                  </Link>
                  <Link
                    to="/docs/developer-onboarding"
                    className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Onboarding
                  </Link>
                  <Link
                    to="/docs/plugin-developer-guide"
                    className="block px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Plugin guide
                  </Link>
                </>
              )}
              <div className="px-3 py-2">
                <span className="rounded-full bg-apex-100 px-2.5 py-0.5 text-xs font-medium text-apex-800">
                  {user?.role}
                </span>
              </div>
              <Button
                variant="default"
                className="w-full justify-start"
                onClick={logout}
              >
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </Button>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}
