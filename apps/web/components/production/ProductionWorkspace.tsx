'use client'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { useAuth } from '@/components/providers/AuthProvider'

export function ProductionWorkspace({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return (
    <DashboardLayout>
      {user?.can_access_production ? (
        <div className="text-gray-900">{children}</div>
      ) : (
        <p>Доступ до перевірки та видачі робіт ще не налаштований для цього облікового запису.</p>
      )}
    </DashboardLayout>
  )
}
