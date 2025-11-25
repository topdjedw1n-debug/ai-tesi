'use client'

import { useState } from 'react'
import { UserDetails as UserDetailsType } from '@/lib/api/admin'
import { format } from 'date-fns'
import {
  LockClosedIcon,
  LockOpenIcon,
  TrashIcon,
  UserPlusIcon,
  EnvelopeIcon,
  DocumentTextIcon,
  CreditCardIcon,
  UserIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface UserDetailsProps {
  user: UserDetailsType
  onBlock?: () => void
  onUnblock?: () => void
  onDelete?: () => void
  onMakeAdmin?: () => void
  onSendEmail?: () => void
  onViewDocuments?: () => void
  onViewPayments?: () => void
}

export function UserDetails({
  user,
  onBlock,
  onUnblock,
  onDelete,
  onMakeAdmin,
  onSendEmail,
  onViewDocuments,
  onViewPayments,
}: UserDetailsProps) {
  const [activeTab, setActiveTab] = useState<'profile' | 'documents' | 'payments'>('profile')

  const getStatusBadge = () => {
    if (user.status === 'blocked') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-900 text-red-200">
          Blocked
        </span>
      )
    }
    if (user.status === 'deleted') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-900 text-gray-200">
          Deleted
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-900 text-green-200">
        Active
      </span>
    )
  }

  return (
    <div className="bg-gray-800 rounded-lg shadow">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="h-12 w-12 rounded-full bg-blue-500 flex items-center justify-center">
              <UserIcon className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">{user.email}</h2>
              <p className="text-sm text-gray-400">User ID: {user.id}</p>
            </div>
            {getStatusBadge()}
          </div>
          <div className="flex space-x-2">
            {user.status === 'active' && onBlock && (
              <button
                onClick={onBlock}
                className="inline-flex items-center px-3 py-2 border border-gray-600 rounded-md text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600"
              >
                <LockClosedIcon className="h-4 w-4 mr-2" />
                Block
              </button>
            )}
            {user.status === 'blocked' && onUnblock && (
              <button
                onClick={onUnblock}
                className="inline-flex items-center px-3 py-2 border border-gray-600 rounded-md text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600"
              >
                <LockOpenIcon className="h-4 w-4 mr-2" />
                Unblock
              </button>
            )}
            {!user.is_admin && onMakeAdmin && (
              <button
                onClick={onMakeAdmin}
                className="inline-flex items-center px-3 py-2 border border-gray-600 rounded-md text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600"
              >
                <UserPlusIcon className="h-4 w-4 mr-2" />
                Make Admin
              </button>
            )}
            {onSendEmail && (
              <button
                onClick={onSendEmail}
                className="inline-flex items-center px-3 py-2 border border-gray-600 rounded-md text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600"
              >
                <EnvelopeIcon className="h-4 w-4 mr-2" />
                Send Email
              </button>
            )}
            {onDelete && (
              <button
                onClick={onDelete}
                className="inline-flex items-center px-3 py-2 border border-red-600 rounded-md text-sm font-medium text-red-400 bg-gray-700 hover:bg-gray-600"
              >
                <TrashIcon className="h-4 w-4 mr-2" />
                Delete
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-700">
        <nav className="flex space-x-8 px-6" aria-label="Tabs">
          {[
            { id: 'profile', label: 'Profile', icon: UserIcon },
            { id: 'documents', label: 'Documents', icon: DocumentTextIcon },
            { id: 'payments', label: 'Payments', icon: CreditCardIcon },
          ].map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
              >
                <Icon className="h-5 w-5 mr-2" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="px-6 py-4">
        {activeTab === 'profile' && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Email</h3>
              <p className="text-white">{user.email}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Name</h3>
              <p className="text-white">{user.name || '—'}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Registered</h3>
              <p className="text-white">
                {format(new Date(user.registered_at), 'MMM dd, yyyy HH:mm')}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Last Login</h3>
              <p className="text-white">
                {user.last_login
                  ? format(new Date(user.last_login), 'MMM dd, yyyy HH:mm')
                  : 'Never'}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Role</h3>
              <p className="text-white">
                {user.is_admin ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-900 text-blue-200">
                    Admin
                  </span>
                ) : (
                  'User'
                )}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Documents Count</h3>
              <p className="text-white">{user.documents_count || 0}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Total Spent</h3>
              <p className="text-white">€{user.total_spent?.toFixed(2) || '0.00'}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Total Refunds</h3>
              <p className="text-white">{user.total_refunds || 0}</p>
            </div>
          </div>
        )}

        {activeTab === 'documents' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-white">Documents ({user.documents_count || 0})</h3>
              {onViewDocuments && (
                <button
                  onClick={onViewDocuments}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  View All →
                </button>
              )}
            </div>
            {user.documents && user.documents.length > 0 ? (
              <div className="space-y-2">
                {user.documents.slice(0, 5).map((doc: any) => (
                  <div
                    key={doc.id}
                    className="bg-gray-700 rounded p-3 flex items-center justify-between"
                  >
                    <div>
                      <p className="text-white font-medium">{doc.title || 'Untitled'}</p>
                      <p className="text-sm text-gray-400">
                        {doc.status} • {doc.created_at ? format(new Date(doc.created_at), 'MMM dd, yyyy') : '—'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400">No documents found</p>
            )}
          </div>
        )}

        {activeTab === 'payments' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-white">Payments</h3>
              {onViewPayments && (
                <button
                  onClick={onViewPayments}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  View All →
                </button>
              )}
            </div>
            {user.payments && user.payments.length > 0 ? (
              <div className="space-y-2">
                {user.payments.slice(0, 5).map((payment: any) => (
                  <div
                    key={payment.id}
                    className="bg-gray-700 rounded p-3 flex items-center justify-between"
                  >
                    <div>
                      <p className="text-white font-medium">
                        €{payment.amount?.toFixed(2) || '0.00'}
                      </p>
                      <p className="text-sm text-gray-400">
                        {payment.status} • {payment.created_at ? format(new Date(payment.created_at), 'MMM dd, yyyy') : '—'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400">No payments found</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
