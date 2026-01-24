'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { adminApiClient, UserDetails } from '@/lib/api/admin'
import { UserDetails as UserDetailsComponent } from '@/components/admin/users/UserDetails'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

export default function AdminUserDetailsPage() {
  const router = useRouter()
  const params = useParams()
  const userId = Number(params.id)
  const [user, setUser] = useState<UserDetails | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchUserDetails = useCallback(async () => {
    try {
      setIsLoading(true)
      const [userData, documentsData, paymentsData] = await Promise.all([
        adminApiClient.getUser(userId),
        adminApiClient.getUserDocuments(userId, 1, 5).catch(() => ({ documents: [] })),
        adminApiClient.getUserPayments(userId, 1, 5).catch(() => ({ payments: [] })),
      ])

      // Merge documents and payments into user data
      setUser({
        ...userData,
        documents: documentsData.documents || [],
        payments: paymentsData.payments || [],
      })
    } catch (error: any) {
      console.error('Failed to fetch user details:', error)
      toast.error('Failed to load user details')
      router.push('/admin/users')
    } finally {
      setIsLoading(false)
    }
  }, [userId, router])

  useEffect(() => {
    if (userId) {
      fetchUserDetails()
    }
  }, [userId, fetchUserDetails])

  const handleBlock = async () => {
    if (!user) return

    try {
      await adminApiClient.blockUser(user.id)
      toast.success('User blocked successfully')
      fetchUserDetails()
    } catch (error: any) {
      toast.error('Failed to block user')
    }
  }

  const handleUnblock = async () => {
    if (!user) return

    try {
      await adminApiClient.unblockUser(user.id)
      toast.success('User unblocked successfully')
      fetchUserDetails()
    } catch (error: any) {
      toast.error('Failed to unblock user')
    }
  }

  const handleDelete = async () => {
    if (!user) return

    if (!confirm(`Are you sure you want to delete user ${user.email}? This action cannot be undone.`)) {
      return
    }

    try {
      await adminApiClient.deleteUser(user.id)
      toast.success('User deleted successfully')
      router.push('/admin/users')
    } catch (error: any) {
      toast.error('Failed to delete user')
    }
  }

  const handleMakeAdmin = async () => {
    if (!user) return

    if (!confirm(`Are you sure you want to make ${user.email} an admin?`)) {
      return
    }

    try {
      await adminApiClient.makeAdmin(user.id, true, false)
      toast.success('User is now an admin')
      fetchUserDetails()
    } catch (error: any) {
      toast.error('Failed to make user admin')
    }
  }

  const handleSendEmail = () => {
    // Email modal feature deferred to post-MVP phase
    toast('Email functionality coming soon', { icon: 'ℹ️' })
  }

  const handleViewDocuments = () => {
    if (user) {
      router.push(`/admin/users/${user.id}?tab=documents`)
    }
  }

  const handleViewPayments = () => {
    if (user) {
      router.push(`/admin/users/${user.id}?tab=payments`)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <p className="text-sm text-red-800">User not found</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push('/admin/users')}
            className="text-sm text-gray-400 hover:text-gray-300 mb-2"
          >
            ← Back to Users
          </button>
          <h1 className="text-2xl font-bold text-white">User Details</h1>
        </div>
      </div>

      <UserDetailsComponent
        user={user}
        onBlock={handleBlock}
        onUnblock={handleUnblock}
        onDelete={handleDelete}
        onMakeAdmin={handleMakeAdmin}
        onSendEmail={handleSendEmail}
        onViewDocuments={handleViewDocuments}
        onViewPayments={handleViewPayments}
      />
    </div>
  )
}
