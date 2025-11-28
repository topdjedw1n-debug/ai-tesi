'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DocumentsList } from '@/components/dashboard/DocumentsList'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'
import { Suspense } from 'react'

export default function DocumentsPage() {
  const router = useRouter()

  useEffect(() => {
    // Check if user is authenticated
    const token = getAccessToken()
    if (!token) {
      toast.error('Please sign in to view documents')
      router.push('/')
      return
    }
  }, [router])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Documents</h1>
          <p className="mt-1 text-sm text-gray-500">
            View and manage all your generated documents
          </p>
        </div>

        <Suspense fallback={<LoadingSpinner />}>
          <DocumentsList />
        </Suspense>
      </div>
    </DashboardLayout>
  )
}
