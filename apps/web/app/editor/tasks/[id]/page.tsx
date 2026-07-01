'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { adminApiClient, EditorTask } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'

export default function EditorTaskDetailPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = Number(params.id)
  const [task, setTask] = useState<EditorTask | null>(null)
  const [loading, setLoading] = useState(true)
  const [notes, setNotes] = useState('')
  const [minutes, setMinutes] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await adminApiClient.getEditorTask(taskId)
        if (!mounted) return
        setTask(data)
        setNotes(data.resolution_notes || '')
        setMinutes(data.minutes_spent || 0)
      } catch (error) {
        console.error('Failed to load editor task:', error)
        toast.error('Failed to load editor task')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    if (Number.isFinite(taskId)) load()
    return () => {
      mounted = false
    }
  }, [taskId])

  const handleResolve = async (event: FormEvent) => {
    event.preventDefault()
    try {
      setSubmitting(true)
      const updated = await adminApiClient.resolveEditorTask(taskId, {
        resolution_notes: notes,
        minutes_spent: minutes,
        status: 'resolved',
      })
      setTask(updated)
      toast.success('Task resolved')
    } catch (error: any) {
      toast.error(error?.message || 'Failed to resolve task')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !task) {
    return (
      <main className="min-h-screen bg-gray-950 px-6 py-8 text-gray-100">
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner />
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-gray-950 px-6 py-8 text-gray-100">
      <div className="mx-auto max-w-3xl space-y-6">
        <button
          type="button"
          onClick={() => router.push('/editor/tasks')}
          className="text-sm text-gray-400 hover:text-white"
        >
          Back to tasks
        </button>

        <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-white">{task.title}</h1>
              <p className="mt-1 text-sm text-gray-400">
                {task.document_title || `Document ${task.document_id}`}
                {task.section_title ? ` · ${task.section_title}` : ''}
              </p>
            </div>
            <span className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-300">
              {task.status}
            </span>
          </div>

          <div className="mt-6 space-y-3 text-sm text-gray-300">
            <p>
              <span className="text-gray-500">Source:</span> {task.source_gate || 'manual'}
            </p>
            {task.description && <p>{task.description}</p>}
          </div>
        </section>

        <form onSubmit={handleResolve} className="rounded-lg border border-gray-800 bg-gray-900 p-6">
          <h2 className="text-lg font-medium text-white">Resolve task</h2>
          <label className="mt-4 block text-sm text-gray-300">
            Resolution notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="mt-2 h-32 w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-white"
              required
            />
          </label>
          <label className="mt-4 block text-sm text-gray-300">
            Minutes spent
            <input
              type="number"
              min={0}
              value={minutes}
              onChange={(event) => setMinutes(Number(event.target.value))}
              className="mt-2 w-40 rounded border border-gray-700 bg-gray-950 px-3 py-2 text-white"
            />
          </label>
          <div className="mt-5">
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : 'Resolve'}
            </Button>
          </div>
        </form>
      </div>
    </main>
  )
}
