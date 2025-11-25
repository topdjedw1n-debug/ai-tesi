'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Bars3Icon, BellIcon } from '@heroicons/react/24/outline'
import { adminApiClient, AdminUser } from '@/lib/api/admin'
import { clearTokens } from '@/lib/api'
import toast from 'react-hot-toast'

interface AdminHeaderProps {
  setSidebarOpen: (open: boolean) => void
}

export function AdminHeader({ setSidebarOpen }: AdminHeaderProps) {
  const router = useRouter()
  const [adminUser, setAdminUser] = useState<AdminUser | null>(null)
  const [showUserMenu, setShowUserMenu] = useState(false)

  useEffect(() => {
    // Load admin user from localStorage
    const adminData = localStorage.getItem('admin_user')
    if (adminData) {
      try {
        setAdminUser(JSON.parse(adminData))
      } catch (error) {
        console.error('Failed to parse admin user data:', error)
      }
    }
  }, [])

  const handleLogout = async () => {
    try {
      await adminApiClient.logout()
      clearTokens()
      localStorage.removeItem('admin_user')
      localStorage.removeItem('is_admin')
      toast.success('Logged out successfully')
      router.push('/admin/login')
    } catch (error: any) {
      console.error('Logout failed:', error)
      // Clear tokens anyway
      clearTokens()
      localStorage.removeItem('admin_user')
      localStorage.removeItem('is_admin')
      router.push('/admin/login')
    }
  }

  return (
    <>
      {/* Mobile header */}
      <div className="md:hidden pl-1 pt-1 sm:pl-3 sm:pt-3 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center justify-between h-16 px-4">
          <button
            type="button"
            className="-ml-0.5 -mt-0.5 h-12 w-12 inline-flex items-center justify-center rounded-md text-gray-400 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
            onClick={() => setSidebarOpen(true)}
          >
            <span className="sr-only">Open sidebar</span>
            <Bars3Icon className="h-6 w-6" />
          </button>

          <div className="flex items-center space-x-4">
            {/* Notifications */}
            <button
              type="button"
              className="relative inline-flex items-center p-2 text-gray-400 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md"
            >
              <span className="sr-only">View notifications</span>
              <BellIcon className="h-6 w-6" />
              {/* Badge for notifications */}
              <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-red-400 ring-2 ring-gray-800" />
            </button>

            {/* User menu */}
            <div className="relative">
              <button
                type="button"
                className="flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center">
                  <span className="text-white text-xs font-bold">
                    {adminUser?.email?.charAt(0).toUpperCase() || 'A'}
                  </span>
                </div>
                <span className="ml-2 text-gray-300 text-sm font-medium hidden sm:block">
                  {adminUser?.email || 'Admin'}
                </span>
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 rounded-md shadow-lg bg-gray-800 ring-1 ring-black ring-opacity-5 z-50">
                  <div className="py-1">
                    <div className="px-4 py-2 text-sm text-gray-300 border-b border-gray-700">
                      <div className="font-medium">{adminUser?.email}</div>
                      <div className="text-xs text-gray-500">
                        {adminUser?.is_super_admin ? 'Super Admin' : 'Admin'}
                      </div>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
                    >
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Desktop header */}
      <div className="hidden md:flex md:flex-shrink-0 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center justify-between h-16 w-full px-6">
          <div className="flex items-center">
            <h1 className="text-lg font-semibold text-white">Admin Panel</h1>
          </div>

          <div className="flex items-center space-x-4">
            {/* Notifications */}
            <button
              type="button"
              className="relative inline-flex items-center p-2 text-gray-400 hover:text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md"
            >
              <span className="sr-only">View notifications</span>
              <BellIcon className="h-6 w-6" />
              {/* Badge for notifications */}
              <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-red-400 ring-2 ring-gray-800" />
            </button>

            {/* User menu */}
            <div className="relative">
              <button
                type="button"
                className="flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center">
                  <span className="text-white text-xs font-bold">
                    {adminUser?.email?.charAt(0).toUpperCase() || 'A'}
                  </span>
                </div>
                <span className="ml-2 text-gray-300 text-sm font-medium">
                  {adminUser?.email || 'Admin'}
                </span>
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 rounded-md shadow-lg bg-gray-800 ring-1 ring-black ring-opacity-5 z-50">
                  <div className="py-1">
                    <div className="px-4 py-2 text-sm text-gray-300 border-b border-gray-700">
                      <div className="font-medium">{adminUser?.email}</div>
                      <div className="text-xs text-gray-500">
                        {adminUser?.is_super_admin ? 'Super Admin' : 'Admin'}
                      </div>
                    </div>
                    <button
                      onClick={handleLogout}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
                    >
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
