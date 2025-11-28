'use client'

import { useEffect, useState } from 'react'
import { adminApiClient, PricingSettings, AISettings, LimitSettings, MaintenanceSettings } from '@/lib/api/admin'
import { PricingSettingsForm } from '@/components/admin/settings/PricingSettingsForm'
import { AISettingsForm } from '@/components/admin/settings/AISettingsForm'
import { LimitSettingsForm } from '@/components/admin/settings/LimitSettingsForm'
import { MaintenanceSettingsForm } from '@/components/admin/settings/MaintenanceSettingsForm'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ConfirmDialog } from '@/components/admin/ui/ConfirmDialog'
import toast from 'react-hot-toast'

type SettingsTab = 'pricing' | 'ai' | 'limits' | 'maintenance'

export default function AdminSettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('pricing')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [pricingSettings, setPricingSettings] = useState<PricingSettings | null>(null)
  const [aiSettings, setAISettings] = useState<AISettings | null>(null)
  const [limitSettings, setLimitSettings] = useState<LimitSettings | null>(null)
  const [maintenanceSettings, setMaintenanceSettings] = useState<MaintenanceSettings | null>(null)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [pendingSave, setPendingSave] = useState<(() => Promise<void>) | null>(null)
  const [confirmMessage, setConfirmMessage] = useState('')

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      setIsLoading(true)
      const allSettings = await adminApiClient.getAllSettings()

      // Extract settings by category
      // allSettings is a dict: { "pricing": {...}, "ai": {...}, ... }
      const pricing = allSettings.pricing || {}
      if (pricing['pricing.price_per_page'] !== undefined || pricing['price_per_page'] !== undefined) {
        setPricingSettings({
          price_per_page: pricing['pricing.price_per_page'] || pricing['price_per_page'] || 0.5,
          min_pages: pricing['pricing.min_pages'] || pricing['min_pages'] || 3,
          max_pages: pricing['pricing.max_pages'] || pricing['max_pages'] || 200,
          currencies: pricing['pricing.currencies'] || pricing['currencies'] || ['EUR'],
        })
      }

      const ai = allSettings.ai || {}
      if (ai['ai.default_provider'] !== undefined || ai['default_provider'] !== undefined) {
        setAISettings({
          default_provider: ai['ai.default_provider'] || ai['default_provider'] || 'openai',
          default_model: ai['ai.default_model'] || ai['default_model'] || 'gpt-4',
          fallback_models: ai['ai.fallback_models'] || ai['fallback_models'] || [],
          max_retries: ai['ai.max_retries'] || ai['max_retries'] || 3,
          timeout_seconds: ai['ai.timeout_seconds'] || ai['timeout_seconds'] || 300,
          temperature_default: ai['ai.temperature_default'] || ai['temperature_default'] || 0.7,
        })
      }

      const limits = allSettings.limits || {}
      if (limits['limits.max_concurrent_generations'] !== undefined || limits['max_concurrent_generations'] !== undefined) {
        setLimitSettings({
          max_concurrent_generations: limits['limits.max_concurrent_generations'] || limits['max_concurrent_generations'] || 5,
          max_documents_per_user: limits['limits.max_documents_per_user'] || limits['max_documents_per_user'] || 100,
          max_pages_per_document: limits['limits.max_pages_per_document'] || limits['max_pages_per_document'] || 200,
          daily_token_limit: limits['limits.daily_token_limit'] || limits['daily_token_limit'] || null,
        })
      }

      const maintenance = allSettings.maintenance || {}
      if (maintenance['maintenance.enabled'] !== undefined || maintenance['enabled'] !== undefined) {
        setMaintenanceSettings({
          enabled: maintenance['maintenance.enabled'] || maintenance['enabled'] || false,
          message: maintenance['maintenance.message'] || maintenance['message'] || 'System maintenance in progress',
          allowed_ips: maintenance['maintenance.allowed_ips'] || maintenance['allowed_ips'] || [],
          estimated_end_time: maintenance['maintenance.estimated_end_time'] || maintenance['estimated_end_time'] || null,
        })
      }
    } catch (error: any) {
      console.error('Failed to fetch settings:', error)
      toast.error('Failed to load settings')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSavePricing = async (settings: PricingSettings) => {
    setConfirmMessage('Are you sure you want to update pricing settings? This will affect all future document generation pricing.')
    setPendingSave(() => async () => {
      try {
        setIsSaving(true)
        await adminApiClient.updatePricingSettings(settings)
        toast.success('Pricing settings updated successfully')
        await fetchSettings()
      } catch (error: any) {
        console.error('Failed to update pricing settings:', error)
        toast.error('Failed to update pricing settings')
        throw error
      } finally {
        setIsSaving(false)
      }
    })
    setConfirmDialogOpen(true)
  }

  const handleSaveAI = async (settings: AISettings) => {
    setConfirmMessage('Are you sure you want to update AI settings? This will affect all future document generation.')
    setPendingSave(() => async () => {
      try {
        setIsSaving(true)
        await adminApiClient.updateAISettings(settings)
        toast.success('AI settings updated successfully')
        await fetchSettings()
      } catch (error: any) {
        console.error('Failed to update AI settings:', error)
        toast.error('Failed to update AI settings')
        throw error
      } finally {
        setIsSaving(false)
      }
    })
    setConfirmDialogOpen(true)
  }

  const handleSaveLimits = async (settings: LimitSettings) => {
    setConfirmMessage('Are you sure you want to update limit settings? This will affect user limits and system capacity.')
    setPendingSave(() => async () => {
      try {
        setIsSaving(true)
        await adminApiClient.updateLimitSettings(settings)
        toast.success('Limit settings updated successfully')
        await fetchSettings()
      } catch (error: any) {
        console.error('Failed to update limit settings:', error)
        toast.error('Failed to update limit settings')
        throw error
      } finally {
        setIsSaving(false)
      }
    })
    setConfirmDialogOpen(true)
  }

  const handleSaveMaintenance = async (settings: MaintenanceSettings) => {
    if (settings.enabled) {
      setConfirmMessage('⚠️ WARNING: Enabling maintenance mode will block all non-admin users from accessing the platform. Are you sure?')
    } else {
      setConfirmMessage('Are you sure you want to update maintenance settings?')
    }
    setPendingSave(() => async () => {
      try {
        setIsSaving(true)
        await adminApiClient.updateMaintenanceSettings(settings)
        toast.success(settings.enabled ? 'Maintenance mode enabled' : 'Maintenance settings updated successfully')
        await fetchSettings()
      } catch (error: any) {
        console.error('Failed to update maintenance settings:', error)
        toast.error('Failed to update maintenance settings')
        throw error
      } finally {
        setIsSaving(false)
      }
    })
    setConfirmDialogOpen(true)
  }

  const handleConfirmSave = async () => {
    if (pendingSave) {
      await pendingSave()
      setPendingSave(null)
      setConfirmDialogOpen(false)
    }
  }

  const tabs = [
    { id: 'pricing' as const, label: 'Pricing', icon: '💰' },
    { id: 'ai' as const, label: 'AI Settings', icon: '🤖' },
    { id: 'limits' as const, label: 'Limits', icon: '🔒' },
    { id: 'maintenance' as const, label: 'Maintenance', icon: '🔧' },
  ]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">System Settings</h1>
        <p className="mt-1 text-sm text-gray-400">
          Manage platform configuration and settings
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-700">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'pricing' && (
          <PricingSettingsForm
            initialSettings={pricingSettings || undefined}
            onSave={handleSavePricing}
            isLoading={isSaving}
          />
        )}

        {activeTab === 'ai' && (
          <AISettingsForm
            initialSettings={aiSettings || undefined}
            onSave={handleSaveAI}
            isLoading={isSaving}
          />
        )}

        {activeTab === 'limits' && (
          <LimitSettingsForm
            initialSettings={limitSettings ? { ...limitSettings, daily_token_limit: limitSettings.daily_token_limit ?? null } : undefined}
            onSave={handleSaveLimits}
            isLoading={isSaving}
          />
        )}

        {activeTab === 'maintenance' && (
          <MaintenanceSettingsForm
            initialSettings={maintenanceSettings ? { ...maintenanceSettings, estimated_end_time: maintenanceSettings.estimated_end_time ?? null } : undefined}
            onSave={handleSaveMaintenance}
            isLoading={isSaving}
          />
        )}
      </div>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmDialogOpen}
        setOpen={setConfirmDialogOpen}
        title="Confirm Settings Update"
        description={confirmMessage}
        onConfirm={handleConfirmSave}
        confirmButtonText="Confirm"
        confirmButtonColor="blue"
        isLoading={isSaving}
      />
    </div>
  )
}
