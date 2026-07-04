'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { CreateDocumentForm } from '@/components/dashboard/CreateDocumentForm'
import { getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'

export default function NewDocumentPage() {
  const router = useRouter()

  useEffect(() => {
    const token = getAccessToken()
    if (!token) {
      toast.error('Увійдіть, щоб створити роботу')
      router.push('/')
    }
  }, [router])

  return (
    <DashboardLayout>
      <div className="max-w-3xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Нова робота</h1>
          <p className="mt-1 text-sm text-gray-500">
            Тема, обсяг і вимоги — цього достатньо, щоб запустити генерацію
          </p>
        </div>
        <CreateDocumentForm />
      </div>
    </DashboardLayout>
  )
}
