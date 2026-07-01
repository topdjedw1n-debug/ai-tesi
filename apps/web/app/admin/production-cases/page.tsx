'use client'

import { FormEvent, useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { adminApiClient, ProductionCase } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

function statusClass(status: string) {
  if (['released', 'passed', 'completed', 'delivered'].includes(status)) {
    return 'bg-green-900/40 text-green-200 border-green-700'
  }
  if (['blocked', 'failed', 'failed_quality'].includes(status)) {
    return 'bg-red-900/40 text-red-200 border-red-700'
  }
  if (['needs_review', 'warning', 'no_data'].includes(status)) {
    return 'bg-yellow-900/40 text-yellow-100 border-yellow-700'
  }
  return 'bg-gray-800 text-gray-200 border-gray-700'
}

export default function ProductionCasesPage() {
  const [cases, setCases] = useState<ProductionCase[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [total, setTotal] = useState(0)
  const [form, setForm] = useState({
    document_id: '',
    deadline_at: '',
    citation_style: 'apa',
    requirements_text: '',
  })

  const loadCases = useCallback(async () => {
    try {
      setLoading(true)
      const data = await adminApiClient.getProductionCases({ per_page: 50 })
      setCases(data.cases)
      setTotal(data.total)
    } catch (error) {
      console.error('Failed to load production cases:', error)
      toast.error('Failed to load production cases')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCases()
  }, [loadCases])

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const documentId = Number(form.document_id)
    if (!Number.isFinite(documentId) || documentId <= 0) {
      toast.error('Enter a valid document ID')
      return
    }
    try {
      setCreating(true)
      await adminApiClient.createProductionCase({
        document_id: documentId,
        deadline_at: form.deadline_at ? new Date(form.deadline_at).toISOString() : undefined,
        citation_style: form.citation_style || undefined,
        requirements_text: form.requirements_text || undefined,
      })
      toast.success('Production case created')
      setForm({
        document_id: '',
        deadline_at: '',
        citation_style: 'apa',
        requirements_text: '',
      })
      await loadCases()
    } catch (error: any) {
      toast.error(error?.message || 'Failed to create production case')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Production Cases</h1>
        <p className="mt-1 text-sm text-gray-400">
          Internal QA-first control surface for manager release decisions.
        </p>
      </div>

      <form
        onSubmit={handleCreate}
        className="rounded-lg border border-gray-700 bg-gray-800 p-4"
        data-testid="create-production-case-form"
      >
        <h2 className="text-lg font-semibold text-white">Create production case</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
          <label className="text-sm text-gray-300">
            Document ID
            <input
              value={form.document_id}
              onChange={(event) => setForm({ ...form, document_id: event.target.value })}
              className="mt-1 w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 text-white"
              inputMode="numeric"
              required
            />
          </label>
          <label className="text-sm text-gray-300">
            Deadline
            <input
              type="datetime-local"
              value={form.deadline_at}
              onChange={(event) => setForm({ ...form, deadline_at: event.target.value })}
              className="mt-1 w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 text-white"
            />
          </label>
          <label className="text-sm text-gray-300">
            Citation style
            <input
              value={form.citation_style}
              onChange={(event) => setForm({ ...form, citation_style: event.target.value })}
              className="mt-1 w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 text-white"
            />
          </label>
          <label className="text-sm text-gray-300 md:col-span-4">
            Requirements
            <textarea
              value={form.requirements_text}
              onChange={(event) => setForm({ ...form, requirements_text: event.target.value })}
              className="mt-1 h-24 w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 text-white"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={creating}
          className="mt-4 rounded bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
        >
          {creating ? 'Creating...' : 'Create case'}
        </button>
      </form>

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-700 bg-gray-800">
          <div className="border-b border-gray-700 px-4 py-3 text-sm text-gray-300">
            {total.toLocaleString()} case(s)
          </div>
          <table className="min-w-full divide-y divide-gray-700">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400">
                  Case
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400">
                  QA
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400">
                  Editorial
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400">
                  Release
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-400">
                  Human minutes
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {cases.map((item) => (
                <tr key={item.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/production-cases/${item.id}`}
                      className="font-medium text-white hover:text-primary-300"
                    >
                      #{item.id} · {item.document?.title || `Document ${item.document_id}`}
                    </Link>
                    <p className="mt-1 text-xs text-gray-400">
                      {item.client_email || `Client ${item.client_user_id}`}
                    </p>
                  </td>
                  {[
                    ['qa', item.qa_status],
                    ['editorial', item.editorial_status],
                    ['release', item.release_status],
                  ].map(([key, status]) => (
                    <td key={key} className="px-4 py-3">
                      <span className={`inline-flex rounded border px-2 py-1 text-xs ${statusClass(status)}`}>
                        {status}
                      </span>
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right text-sm text-gray-200">
                    {item.human_minutes_used.toLocaleString()}
                  </td>
                </tr>
              ))}
              {cases.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-400">
                    No production cases yet. Create one from an existing document above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
