'use client'

import { FormEvent, useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { adminApiClient, ProductionCase } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'
import { productionStatus } from '@/lib/production-status'

function statusClass(status: string) {
  if (['released', 'passed', 'completed', 'ready', 'delivered'].includes(status)) {
    return 'bg-green-50 text-green-800 border-green-200'
  }
  if (['blocked', 'failed', 'failed_quality'].includes(status)) {
    return 'bg-red-50 text-red-700 border-red-200'
  }
  if (['needs_review', 'warning', 'no_data'].includes(status)) {
    return 'bg-amber-50 text-amber-800 border-amber-200'
  }
  return 'bg-white text-gray-700 border-gray-200'
}

export default function ProductionCasesPage() {
  const pathname = usePathname()
  const caseBasePath = pathname?.startsWith('/dashboard/')
    ? '/dashboard/production-cases'
    : '/admin/production-cases'
  const operatorView = pathname?.startsWith('/dashboard/')
  const [loadError, setLoadError] = useState(false)
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
      setLoadError(false)
      const data = await adminApiClient.getProductionCases({ per_page: 50 })
      setCases(data.cases)
      setTotal(data.total)
    } catch (error) {
      console.error('Failed to load production cases:', error)
      setLoadError(true)
      toast.error('Не вдалося завантажити роботи для перевірки')
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
      toast.error('Вкажіть правильний номер роботи')
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
      toast.success('Роботу додано до перевірки')
      setForm({
        document_id: '',
        deadline_at: '',
        citation_style: 'apa',
        requirements_text: '',
      })
      await loadCases()
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося додати роботу до перевірки')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Перевірка та видача</h1>
        <p className="mt-1 text-sm text-gray-500">
          Тут зберігаються перевірки кожної роботи й дозвіл отримати фінальний файл.
        </p>
      </div>

      {operatorView ? (
        <p className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
          Справа створюється автоматично під час першого запуску написання.
          <Link href="/dashboard" className="ml-1 text-primary-700 underline">Відкрити мої роботи</Link>
        </p>
      ) : <form
        onSubmit={handleCreate}
        className="rounded-lg border border-gray-200 bg-white p-4"
        data-testid="create-production-case-form"
      >
        <h2 className="text-lg font-semibold text-gray-900">Додати наявну роботу до перевірки</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
          <label className="text-sm text-gray-600">
            Номер роботи
            <input
              value={form.document_id}
              onChange={(event) => setForm({ ...form, document_id: event.target.value })}
              className="mt-1 w-full rounded border border-gray-300 bg-gray-50 px-3 py-2 text-gray-900"
              inputMode="numeric"
              required
            />
          </label>
          <label className="text-sm text-gray-600">
            Дедлайн
            <input
              type="datetime-local"
              value={form.deadline_at}
              onChange={(event) => setForm({ ...form, deadline_at: event.target.value })}
              className="mt-1 w-full rounded border border-gray-300 bg-gray-50 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-600">
            Стиль цитування
            <input
              value={form.citation_style}
              onChange={(event) => setForm({ ...form, citation_style: event.target.value })}
              className="mt-1 w-full rounded border border-gray-300 bg-gray-50 px-3 py-2 text-gray-900"
            />
          </label>
          <label className="text-sm text-gray-600 md:col-span-4">
            Вимоги
            <textarea
              value={form.requirements_text}
              onChange={(event) => setForm({ ...form, requirements_text: event.target.value })}
              className="mt-1 h-24 w-full rounded border border-gray-300 bg-gray-50 px-3 py-2 text-gray-900"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={creating}
          className="mt-4 rounded bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
        >
          {creating ? 'Додаємо…' : 'Додати роботу'}
        </button>
      </form>}

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : loadError ? (
        <div role="alert" className="rounded border border-amber-200 p-4">
          <p>Список не завантажився. Збережені роботи не змінено.</p>
          <button onClick={loadCases} className="mt-2 text-primary-700 underline">Оновити список</button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-4 py-3 text-sm text-gray-600">
            {total.toLocaleString()} робіт
          </div>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Робота
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Перевірки
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Огляд змісту
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Видача
                </th>
                {!operatorView && <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                  Хвилини огляду
                </th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {cases.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`${caseBasePath}/${item.id}`}
                      className="font-medium text-gray-900 hover:text-primary-700"
                    >
                      #{item.id} · {item.document?.title || `Робота ${item.document_id}`}
                    </Link>
                    <p className="mt-1 text-xs text-gray-500">
                      {item.client_email || `Обліковий запис ${item.client_user_id}`}
                      {item.executor_version === 2 && <span className="block">{item.generation_status_label} · {item.warnings_count || 0} попереджень</span>}
                    </p>
                  </td>
                  {[
                    ['qa', item.qa_status],
                    ['editorial', item.editorial_status],
                    ['release', item.release_status],
                  ].map(([key, status]) => (
                    <td key={key} className="px-4 py-3">
                      <span className={`inline-flex rounded border px-2 py-1 text-xs ${statusClass(status)}`}>
                        {productionStatus(status)}
                      </span>
                    </td>
                  ))}
                  {!operatorView && <td className="px-4 py-3 text-right text-sm text-gray-700">
                    {item.human_minutes_used.toLocaleString()}
                  </td>}
                </tr>
              ))}
              {cases.length === 0 && (
                <tr>
                  <td colSpan={operatorView ? 4 : 5} className="px-4 py-10 text-center text-sm text-gray-500">
                    Список поки порожній. Робота з’явиться тут після підтвердження умов і запуску написання.
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
