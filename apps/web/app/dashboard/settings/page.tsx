'use client'

import { useState } from 'react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { useAuth } from '@/components/providers/AuthProvider'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    // TODO: Implement settings save
    setTimeout(() => {
      setSaving(false)
      toast.success('Налаштування збережено')
    }, 1000)
  }

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Налаштування</h1>
          <p className="mt-1 text-sm text-gray-500">
            Керуйте налаштуваннями свого акаунта
          </p>
        </div>

        {/* Preferences Section */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Уподобання</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Мова інтерфейсу
              </label>
              <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500">
                <option>Українська</option>
                <option>English</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Тема
              </label>
              <select className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500">
                <option>Світла</option>
                <option>Темна</option>
                <option>Системна</option>
              </select>
            </div>
            <div className="pt-4">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? 'Збереження...' : 'Зберегти зміни'}
              </Button>
            </div>
          </div>
        </div>

        {/* Account Section */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Акаунт</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div>
              <p className="text-sm text-gray-600 mb-4">
                Email: <span className="font-medium">{user?.email}</span>
              </p>
            </div>
            <div>
              <Button 
                variant="outline" 
                onClick={async () => {
                  await logout()
                  toast.success('Ви вийшли з акаунта')
                }}
              >
                Вийти з акаунта
              </Button>
            </div>
          </div>
        </div>

        {/* API Settings Section */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">API Налаштування</h2>
          </div>
          <div className="px-6 py-5">
            <p className="text-sm text-gray-600">
              Тут ви зможете налаштувати параметри AI моделей та інші опції генерації.
              Функціонал розробляється.
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

