'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { adminApiClient, UserDetails } from '@/lib/api/admin'
import { UsersTable } from '@/components/admin/users/UsersTable'
import { UserFilters } from '@/components/admin/users/UserFilters'
import { BulkActions } from '@/components/admin/users/BulkActions'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

export default function AdminUsersPage() {
  const router = useRouter()
  const [users, setUsers] = useState<UserDetails[]>([])
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(10)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [sortColumn, setSortColumn] = useState<string | undefined>()
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    fetchUsers()
  }, [page, perPage, search, status])

  const fetchUsers = async () => {
    try {
      setIsLoading(true)
      const params: any = {
        page,
        per_page: perPage,
      }
      if (search) params.search = search
      if (status !== 'all') params.status = status

      const response = await adminApiClient.getUsers(params)
      setUsers(response.users)
      setTotal(response.total)
    } catch (error: any) {
      console.error('Failed to fetch users:', error)
      toast.error('Failed to load users')
    } finally {
      setIsLoading(false)
    }
  }

  const handleUserClick = (user: UserDetails) => {
    router.push(`/admin/users/${user.id}`)
  }

  const handleBlock = async (user: UserDetails) => {
    try {
      await adminApiClient.blockUser(user.id)
      toast.success('User blocked successfully')
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to block user')
    }
  }

  const handleUnblock = async (user: UserDetails) => {
    try {
      await adminApiClient.unblockUser(user.id)
      toast.success('User unblocked successfully')
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to unblock user')
    }
  }

  const handleDelete = async (user: UserDetails) => {
    if (!confirm(`Are you sure you want to delete user ${user.email}? This action cannot be undone.`)) {
      return
    }

    try {
      await adminApiClient.deleteUser(user.id)
      toast.success('User deleted successfully')
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to delete user')
    }
  }

  const handleMakeAdmin = async (user: UserDetails) => {
    if (!confirm(`Are you sure you want to make ${user.email} an admin?`)) {
      return
    }

    try {
      await adminApiClient.makeAdmin(user.id, true, false)
      toast.success('User is now an admin')
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to make user admin')
    }
  }

  const handleSendEmail = (user: UserDetails) => {
    // Email modal feature deferred to post-MVP phase
    toast('Email functionality coming soon', { icon: 'ℹ️' })
  }

  const handleBulkBlock = async () => {
    if (selectedRows.size === 0) return

    if (!confirm(`Are you sure you want to block ${selectedRows.size} user(s)?`)) {
      return
    }

    try {
      await adminApiClient.bulkUserAction(Array.from(selectedRows), 'block')
      toast.success(`${selectedRows.size} user(s) blocked successfully`)
      setSelectedRows(new Set())
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to block users')
    }
  }

  const handleBulkUnblock = async () => {
    if (selectedRows.size === 0) return

    if (!confirm(`Are you sure you want to unblock ${selectedRows.size} user(s)?`)) {
      return
    }

    try {
      await adminApiClient.bulkUserAction(Array.from(selectedRows), 'unblock')
      toast.success(`${selectedRows.size} user(s) unblocked successfully`)
      setSelectedRows(new Set())
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to unblock users')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedRows.size === 0) return

    if (!confirm(`Are you sure you want to delete ${selectedRows.size} user(s)? This action cannot be undone.`)) {
      return
    }

    try {
      await adminApiClient.bulkUserAction(Array.from(selectedRows), 'delete')
      toast.success(`${selectedRows.size} user(s) deleted successfully`)
      setSelectedRows(new Set())
      fetchUsers()
    } catch (error: any) {
      toast.error('Failed to delete users')
    }
  }

  const handleSort = (column: string, direction: 'asc' | 'desc') => {
    setSortColumn(column)
    setSortDirection(direction)
    // Frontend sorting (backend sorting deferred to post-MVP)
  }

  const handleResetFilters = () => {
    setSearch('')
    setStatus('all')
    setPage(1)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Users Management</h1>
        <p className="mt-1 text-sm text-gray-400">
          Manage platform users, view details, and perform actions
        </p>
      </div>

      {/* Filters */}
      <UserFilters
        search={search}
        status={status}
        onSearchChange={setSearch}
        onStatusChange={setStatus}
        onReset={handleResetFilters}
      />

      {/* Bulk Actions */}
      {selectedRows.size > 0 && (
        <BulkActions
          selectedCount={selectedRows.size}
          onBulkBlock={handleBulkBlock}
          onBulkUnblock={handleBulkUnblock}
          onBulkDelete={handleBulkDelete}
        />
      )}

      {/* Users Table */}
      <UsersTable
        users={users}
        onUserClick={handleUserClick}
        onBlock={handleBlock}
        onUnblock={handleUnblock}
        onDelete={handleDelete}
        onMakeAdmin={handleMakeAdmin}
        onSendEmail={handleSendEmail}
        selectable={true}
        selectedRows={selectedRows}
        onSelectionChange={(selected) => setSelectedRows(new Set(Array.from(selected).map(Number)))}
        loading={isLoading}
      />

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of {total} users
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => setPage(page - 1)}
              disabled={page === 1}
              className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page >= Math.ceil(total / perPage)}
              className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
