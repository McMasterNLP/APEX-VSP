import { useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { getHomeRouteForRole } from '@/lib/roleRoutes'
import type { ReactNode } from 'react'

interface ProtectedRouteProps {
  children: ReactNode
  allowedRoles?: ('admin' | 'trainee' | 'researcher')[]
}

export const ProtectedRoute = ({
  children,
  allowedRoles,
}: ProtectedRouteProps) => {
  const { isAuthenticated, user, loading } = useAuthStore()
  const refreshProfile = useAuthStore((s) => s.refreshProfile)

  useEffect(() => {
    if (loading || !isAuthenticated || user) return
    void refreshProfile()
  }, [loading, isAuthenticated, user, refreshProfile])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (allowedRoles && allowedRoles.length > 0 && user?.role && !allowedRoles.includes(user.role)) {
    return <Navigate to={getHomeRouteForRole(user.role)} replace />
  }

  return <>{children}</>
}
