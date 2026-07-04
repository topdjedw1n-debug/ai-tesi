'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { PaymentForm } from '@/components/payment/PaymentForm'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import { isUserPaymentFlowEnabled } from '@/lib/feature-flags'
import {
  INTAKE_FIELDS,
  IntakeField,
  IntakeFormValues,
  buildDocumentPayload,
  intakeDefaults,
  validateIntake,
} from '@/lib/intake-fields'
import toast from 'react-hot-toast'

interface CreateDocumentFormProps {
  onSuccess?: (documentId: number) => void
}

type FormStep = 'form' | 'payment'

const inputClass =
  'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm'

function IntakeInput({
  field,
  value,
  error,
  onChange,
}: {
  field: IntakeField
  value: string | number
  error?: string
  onChange: (key: string, value: string) => void
}) {
  const testId = `document-${field.key}-input`
  const common = {
    id: field.key,
    'data-testid': testId,
    value: String(value ?? ''),
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
    ) => onChange(field.key, e.target.value),
  }

  return (
    <div className={field.half ? '' : 'sm:col-span-2'}>
      <label htmlFor={field.key} className="block text-sm font-medium text-gray-700">
        {field.label}
        {field.required ? ' *' : ''}
        {field.hint && <span className="font-normal text-gray-500"> — {field.hint}</span>}
      </label>

      {field.type === 'textarea' && (
        <textarea
          {...common}
          rows={field.rows ?? 3}
          placeholder={field.placeholder}
          className={inputClass}
        />
      )}
      {field.type === 'select' && (
        <select {...common} className={inputClass}>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
      {(field.type === 'text' || field.type === 'number' || field.type === 'date') && (
        <input
          {...common}
          type={field.type}
          min={field.min}
          max={field.max}
          placeholder={field.placeholder}
          className={inputClass}
        />
      )}

      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  )
}

export function CreateDocumentForm({ onSuccess }: CreateDocumentFormProps) {
  const router = useRouter()
  const [values, setValues] = useState<IntakeFormValues>(intakeDefaults)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [currentStep, setCurrentStep] = useState<FormStep>('form')
  const [isCreating, setIsCreating] = useState(false)
  const [createdDocumentId, setCreatedDocumentId] = useState<number | null>(null)

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => {
      if (!prev[key]) return prev
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const validationErrors = validateIntake(values)
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      return
    }

    const token = getAccessToken()
    if (!token) {
      toast.error('Увійдіть, щоб створити роботу')
      return
    }

    setIsCreating(true)
    try {
      const payload = buildDocumentPayload(values)
      const document = await apiClient.post(API_ENDPOINTS.DOCUMENTS.CREATE, payload, {
        headers: { Authorization: `Bearer ${token}` },
      })

      setCreatedDocumentId(document.id)

      if (!isUserPaymentFlowEnabled) {
        // Internal MVP: one action for the manager — create the draft and
        // immediately kick off generation, then land on the document page
        // where live progress is shown.
        try {
          await apiClient.post(
            API_ENDPOINTS.GENERATE.FULL,
            { document_id: document.id },
            { headers: { Authorization: `Bearer ${token}` } }
          )
          toast.success('Роботу створено — генерація пішла')
        } catch (genError: any) {
          // The draft was created but generation didn't start (e.g. daily
          // limit or page cap). Surface the reason; the document page has a
          // "Generate" button to retry.
          toast.error(
            genError?.message ||
              'Роботу створено, але генерація не стартувала. Відкрий роботу і спробуй ще раз.'
          )
        }
        onSuccess?.(document.id)
        router.push(`/dashboard/documents/${document.id}`)
        return
      }

      setCurrentStep('payment')
      toast.success('Роботу створено. Далі — оплата.')
    } catch (error: any) {
      console.error('Error creating document:', error)
      toast.error(error.message || 'Не вдалося створити роботу. Спробуй ще раз.')
    } finally {
      setIsCreating(false)
    }
  }

  if (currentStep === 'payment' && createdDocumentId) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="mb-4">
          <h2 className="text-lg font-medium text-gray-900">Потрібна оплата</h2>
          <p className="mt-1 text-sm text-gray-500">
            Заверши оплату, щоб стартувала генерація
          </p>
        </div>

        <PaymentForm
          documentId={createdDocumentId}
          pages={Number(values.pages) || 10}
          onCancel={() => {
            setCurrentStep('form')
            setCreatedDocumentId(null)
          }}
        />
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-6">
        <h2 className="text-lg font-medium text-gray-900" data-testid="create-document-title">
          Нова робота
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Заповни вимоги так, як їх прислав клієнт, і натисни «Згенерувати» — далі
          система все зробить сама.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        data-testid="create-document-form"
      >
        {INTAKE_FIELDS.map((field) => (
          <IntakeInput
            key={field.key}
            field={field}
            value={values[field.key]}
            error={errors[field.key]}
            onChange={handleChange}
          />
        ))}

        <div className="sm:col-span-2 flex justify-end">
          <Button type="submit" disabled={isCreating} data-testid="create-document-submit">
            {isCreating ? (
              <>
                <LoadingSpinner className="mr-2 h-4 w-4" />
                Створюємо…
              </>
            ) : (
              'Згенерувати роботу'
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
