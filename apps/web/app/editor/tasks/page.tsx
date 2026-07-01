'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { adminApiClient, EditorTask } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

export default function EditorTasksPage() {
  const [tasks, setTasks] = useState<EditorTask[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await adminApiClient.getEditorTasks({ per_page: 50 })
        if (mounted) setTasks(data.tasks)
      } catch (error) {
        console.error('Failed to load editor tasks:', error)
        toast.error('Failed to load editor tasks')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [])

  return (
    <main className="min-h-screen bg-gray-950 px-6 py-8 text-gray-100">
      <div className="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Editor Tasks</h1>
          <p className="mt-1 text-sm text-gray-400">
            Assigned findings that need focused editorial work.
          </p>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <LoadingSpinner />
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-800 bg-gray-900">
            <table className="min-w-full divide-y divide-gray-800">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs uppercase text-gray-500">
                    Finding
                  </th>
                  <th className="px-4 py-3 text-left text-xs uppercase text-gray-500">
                    Source
                  </th>
                  <th className="px-4 py-3 text-left text-xs uppercase text-gray-500">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs uppercase text-gray-500">
                    Minutes
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {tasks.map((task) => (
                  <tr key={task.id} className="hover:bg-gray-800">
                    <td className="px-4 py-3">
                      <Link
                        href={`/editor/tasks/${task.id}`}
                        className="font-medium text-white hover:text-primary-300"
                      >
                        {task.title}
                      </Link>
                      <p className="mt-1 text-xs text-gray-500">
                        {task.document_title || `Document ${task.document_id}`}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">
                      {task.source_gate || 'manual'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">{task.status}</td>
                    <td className="px-4 py-3 text-right text-sm text-gray-300">
                      {task.minutes_spent}
                    </td>
                  </tr>
                ))}
                {tasks.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-10 text-center text-sm text-gray-500">
                      No assigned editor tasks.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  )
}
