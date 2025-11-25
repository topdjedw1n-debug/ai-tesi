'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { AdminSidebar } from './AdminSidebar'
import { AdminHeader } from './AdminHeader'
import { AdminBreadcrumbs } from './AdminBreadcrumbs'

interface AdminLayoutProps {
  children: React.ReactNode
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // Check if user is admin
    const isAdmin = localStorage.getItem('is_admin')
    const adminUser = localStorage.getItem('admin_user')

    // Allow access to login page
    if (pathname === '/admin/login') {
      return
    }

    // Redirect to login if not admin
    if (!isAdmin || !adminUser) {
      router.push('/admin/login')
    }
  }, [pathname, router])

  // Don't render layout for login page
  if (pathname === '/admin/login') {
    return <>{children}</>
  }

  return (
    <div className="h-screen flex overflow-hidden bg-gray-900">
      {/* Sidebar */}
      <AdminSidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />

      {/* Main content */}
      <div className="flex flex-col w-0 flex-1 overflow-hidden">
        {/* Header */}
        <AdminHeader setSidebarOpen={setSidebarOpen} />

        {/* Page content */}
        <main className="flex-1 relative overflow-y-auto focus:outline-none bg-gray-900">
          <div className="py-6">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8">
              <AdminBreadcrumbs />
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
