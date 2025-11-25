'use client'

import { useState, useEffect } from 'react'
import { WrenchScrewdriverIcon } from '@heroicons/react/24/outline'

interface MaintenanceSettings {
  enabled: boolean
  message: string
  allowed_ips: string[]
  estimated_end_time: string | null
}

interface MaintenanceSettingsFormProps {
  initialSettings?: MaintenanceSettings
  onSave: (settings: MaintenanceSettings) => Promise<void>
  isLoading?: boolean
}

export function MaintenanceSettingsForm({
  initialSettings,
  onSave,
  isLoading = false,
}: MaintenanceSettingsFormProps) {
  const [enabled, setEnabled] = useState(initialSettings?.enabled || false)
  const [message, setMessage] = useState(
    initialSettings?.message || 'System maintenance in progress'
  )
  const [allowedIPs, setAllowedIPs] = useState<string[]>(
    initialSettings?.allowed_ips || []
  )
  const [estimatedEndTime, setEstimatedEndTime] = useState<string>(
    initialSettings?.estimated_end_time || ''
  )
  const [newIP, setNewIP] = useState('')

  useEffect(() => {
    if (initialSettings) {
      setEnabled(initialSettings.enabled)
      setMessage(initialSettings.message || 'System maintenance in progress')
      setAllowedIPs(initialSettings.allowed_ips || [])
      setEstimatedEndTime(initialSettings.estimated_end_time || '')
    }
  }, [initialSettings])

  const handleAddIP = () => {
    if (newIP && !allowedIPs.includes(newIP)) {
      setAllowedIPs([...allowedIPs, newIP])
      setNewIP('')
    }
  }

  const handleRemoveIP = (ip: string) => {
    setAllowedIPs(allowedIPs.filter((i) => i !== ip))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (enabled && !message.trim()) {
      alert('Maintenance message is required when maintenance mode is enabled')
      return
    }

    await onSave({
      enabled,
      message: message.trim(),
      allowed_ips: allowedIPs,
      estimated_end_time: estimatedEndTime || null,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <WrenchScrewdriverIcon className="h-5 w-5 mr-2" />
          Maintenance Mode
        </h3>

        <div className="space-y-4">
          {/* Enable Maintenance Mode */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="maintenance_enabled"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-600 rounded bg-gray-700"
              disabled={isLoading}
            />
            <label htmlFor="maintenance_enabled" className="ml-2 text-sm font-medium text-white">
              Enable Maintenance Mode
            </label>
          </div>

          {enabled && (
            <>
              {/* Maintenance Message */}
              <div>
                <label htmlFor="maintenance_message" className="block text-sm font-medium text-gray-300 mb-1">
                  Maintenance Message
                </label>
                <textarea
                  id="maintenance_message"
                  rows={3}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  required={enabled}
                  disabled={isLoading}
                  placeholder="System maintenance in progress"
                />
                <p className="mt-1 text-sm text-gray-400">
                  This message will be displayed to users during maintenance
                </p>
              </div>

              {/* Allowed IPs */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Allowed IP Addresses (Admin Access During Maintenance)
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {allowedIPs.map((ip) => (
                    <span
                      key={ip}
                      className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-600 text-white"
                    >
                      {ip}
                      <button
                        type="button"
                        onClick={() => handleRemoveIP(ip)}
                        className="ml-2 text-white hover:text-red-300"
                        disabled={isLoading}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newIP}
                    onChange={(e) => setNewIP(e.target.value)}
                    placeholder="Add IP address (e.g., 192.168.1.1)"
                    className="flex-1 px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={handleAddIP}
                    className="px-4 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-50"
                    disabled={isLoading || !newIP}
                  >
                    Add
                  </button>
                </div>
                <p className="mt-1 text-sm text-gray-400">
                  IP addresses that will have access during maintenance (leave empty to allow all admin IPs)
                </p>
              </div>

              {/* Estimated End Time */}
              <div>
                <label
                  htmlFor="estimated_end_time"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Estimated End Time (Optional)
                </label>
                <input
                  type="datetime-local"
                  id="estimated_end_time"
                  value={estimatedEndTime}
                  onChange={(e) => setEstimatedEndTime(e.target.value)}
                  className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  disabled={isLoading}
                />
                <p className="mt-1 text-sm text-gray-400">
                  Optional: When maintenance is expected to complete
                </p>
              </div>
            </>
          )}
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="submit"
            className={`px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 ${
              enabled
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
            disabled={isLoading}
          >
            {isLoading ? 'Saving...' : enabled ? 'Enable Maintenance Mode' : 'Save Settings'}
          </button>
        </div>
      </div>
    </form>
  )
}
