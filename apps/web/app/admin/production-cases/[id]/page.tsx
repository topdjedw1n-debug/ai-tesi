'use client'

import { useEffect, useMemo, useState } from 'react'
import { useParams, usePathname } from 'next/navigation'
import Link from 'next/link'
import {
  adminApiClient,
  ProductionCase,
  ReleaseGate,
} from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import { ReleaseEvidenceForms } from '@/components/production/ReleaseEvidenceForms'
import toast from 'react-hot-toast'
import { gateDetail, gateLabel, productionStatus } from '@/lib/production-status'
import { downloadDocumentDocx } from '@/lib/download'

function gateTone(gate: ReleaseGate) {
  if (gate.status === 'passed' || gate.status === 'overridden') return 'border-green-200 bg-green-50'
  if (gate.status === 'failed') return 'border-red-200 bg-red-50'
  if (gate.status === 'warning' || gate.status === 'unchecked') return 'border-amber-200 bg-amber-50'
  return 'border-gray-200 bg-white'
}

export default function ProductionCaseDetailPage() {
  const params = useParams()
  const operatorView = usePathname()?.startsWith('/dashboard/')
  const caseId = Number(params.id)
  const [productionCase, setProductionCase] = useState<ProductionCase | null>(null)
  const [gates, setGates] = useState<ReleaseGate[]>([])
  const [loading, setLoading] = useState(true)
  const [isReleasing, setIsReleasing] = useState(false)
  const [isDownloadingReview, setIsDownloadingReview] = useState(false)
  const [isDownloadingFinal, setIsDownloadingFinal] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [isRetryingReview, setIsRetryingReview] = useState(false)
  const [reviewAttemptId, setReviewAttemptId] = useState<string | null>(null)

  const blockers = useMemo(
    () =>
      gates.filter(
        (gate) =>
          gate.blocking &&
          ['failed', 'no_data', 'unchecked', 'warning'].includes(gate.status) &&
          !gate.override_reason
      ),
    [gates]
  )

  const load = async () => {
    try {
      setLoading(true)
      setLoadError(false)
      // Show current gate decisions before reading the saved case status.
      const gateData = await adminApiClient.getReleaseGates(caseId)
      const caseData = await adminApiClient.getProductionCase(caseId)
      setProductionCase(caseData)
      setGates(gateData)
    } catch (error) {
      console.error('Failed to load production case:', error)
      setLoadError(true)
      toast.error('Не вдалося завантажити перевірки роботи')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (Number.isFinite(caseId)) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId])

  const handleRelease = async () => {
    try {
      setIsReleasing(true)
      await adminApiClient.releaseProductionCase(caseId, 'Approved from manager console after reviewing the bound DOCX evidence')
      toast.success('Файл готовий менеджеру')
      await load()
    } catch (error: any) {
      toast.error(error?.message || 'Видачу заблоковано')
    } finally {
      setIsReleasing(false)
    }
  }

  const handleReviewRetry = async () => {
    const attemptId = reviewAttemptId ?? crypto.randomUUID()
    setReviewAttemptId(attemptId)
    setIsRetryingReview(true)
    try {
      const result = await adminApiClient.retryAcademicReview(caseId, attemptId)
      if (result.status !== 'pending') setReviewAttemptId(null)
      if (result.status === 'passed') toast.success('Академічну перевірку пройдено')
      else toast(result.reason || 'Перевірка завершилася із зауваженнями')
      await load()
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося отримати результат перевірки')
    } finally {
      setIsRetryingReview(false)
    }
  }

  const handleInternalReviewDownload = async () => {
    const documentId = productionCase?.document?.id
    if (!documentId || !productionCase?.document?.docx_path) return
    try {
      setIsDownloadingReview(true)
      const response = await adminApiClient.getInternalReviewDownload(documentId)
      if (!response.download_url) {
        throw new Error('Посилання на DOCX ще не готове')
      }
      const apiOrigin = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const downloadUrl = new URL(response.download_url, apiOrigin).toString()
      window.open(downloadUrl, '_blank', 'noopener')
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося отримати DOCX для перевірки')
    } finally {
      setIsDownloadingReview(false)
    }
  }

  const handleFinalDownload = async () => {
    if (!productionCase?.document) return
    setIsDownloadingFinal(true)
    try {
      await downloadDocumentDocx(productionCase.document.id)
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося отримати перевірений DOCX')
      await load()
    } finally {
      setIsDownloadingFinal(false)
    }
  }

  const handleOverride = async (gate: ReleaseGate) => {
    const reason = window.prompt(`${gateLabel(gate.gate_key)}. Поясніть адміністративний виняток:`)
    if (!reason) return
    try {
      await adminApiClient.overrideReleaseGate(caseId, gate.gate_key, reason)
      toast.success('Виняток збережено')
      await load()
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося зберегти виняток')
    }
  }

  if (loading && !productionCase) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  if (loadError || !productionCase) return (
    <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p>Перевірки не завантажились. Збережені дані роботи не змінено.</p>
      <Button onClick={load} className="mt-3">Оновити перевірки</Button>
    </div>
  )

  const warningGroups = (productionCase.generation_warnings || []).reduce<Record<string, NonNullable<typeof productionCase.generation_warnings>>>((groups, item) => {
    const label = item.section_label || "Зауваження";
    (groups[label] ||= []).push(item);
    return groups;
  }, {});

  const needsGenerationRetry = operatorView &&
    ['failed', 'failed_quality'].includes(productionCase.document?.status || '') &&
    !productionCase.document?.artifact_bindings?.docx

  return (
    <div className="space-y-6">
      {!needsGenerationRetry && <Link href={operatorView ? `/dashboard/documents/${productionCase.document_id}` : '/admin/production-cases'} className="text-sm text-primary-700 underline">
        {operatorView ? '← До роботи та стану генерації' : '← До списку перевірок'}
      </Link>}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-serif text-gray-900">
            Перевірка та видача · №{productionCase.document_id}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {productionCase.document?.title || `Робота ${productionCase.document_id}`}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            onClick={handleInternalReviewDownload}
            disabled={
              isDownloadingReview ||
              !productionCase.document?.docx_path ||
              !productionCase.document?.artifact_bindings?.docx
            }
            data-testid="internal-review-download"
          >
            {isDownloadingReview
              ? 'Готуємо DOCX…'
              : 'DOCX для Compilatio'}
          </Button>
          {productionCase.release_status === 'released' && !blockers.length ? (
            <Button onClick={handleFinalDownload} disabled={isDownloadingFinal}>
              {isDownloadingFinal ? 'Готуємо файл…' : 'Завантажити перевірений DOCX'}
            </Button>
          ) : (
            <Button onClick={handleRelease} disabled={isReleasing || !gates.length || blockers.length > 0}>
              {isReleasing ? 'Перевіряємо…' : 'Дозволити видачу'}
            </Button>
          )}
        </div>
      </div>

      {!!productionCase.generation_warnings?.length && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4" aria-labelledby="generation-warnings-heading">
          <h2 id="generation-warnings-heading" className="text-lg font-semibold text-amber-900">{productionCase.generation_warnings.length} попереджень</h2>
          <p className="mt-2 text-sm text-amber-900">Ці зауваження не зупиняють підготовку DOCX. Перегляньте їх перед перевіркою та видачею роботи.</p>
          {Object.entries(warningGroups).map(([label, warnings]) => (
            <div key={label} className="mt-4">
              <h3 className="font-medium text-amber-950">{label}</h3>
          <ul className="mt-3 space-y-3 text-sm text-amber-950">
            {warnings.map(warning => (
              <li key={warning.id}>
                <p>{warning.message_uk || warning.reason}</p>
                {warning.detail && <p className="mt-1">{warning.detail}</p>}
                {warning.details?.map((detail, index) => <p key={`detail-${index}`} className="mt-1">{detail}</p>)}
                {warning.references?.map((reference, index) => (
                  <p key={index} className="mt-1">{reference.title ? `${reference.authors?.join('; ') || ''}. ${reference.title}${reference.year ? ` (${reference.year})` : ''}. Потребує перевірки.` : 'Бібліографічні дані потребують уточнення.'}</p>
                ))}
                {Object.entries(warning.checks || {}).map(([check, finding]) => (
                  <p key={check} className="mt-1">{({ grammar: 'Мова', plagiarism: 'Збіги тексту', ai_detection: 'Оцінка ШІ' } as Record<string, string>)[check] || 'Перевірка'}: {finding.reason || 'Є зауваження або перевірка недоступна.'}</p>
                ))}
              </li>
            ))}
          </ul>
            </div>
          ))}
        </section>
      )}

      {needsGenerationRetry && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4" aria-labelledby="generation-stopped-heading">
          <h2 id="generation-stopped-heading" className="text-lg font-semibold text-amber-900">Попереднє написання зупинилося</h2>
          <p className="mt-2 text-sm text-amber-900">
            Готового DOCX ще немає. Відкрийте роботу, перегляньте причину зупинки й після її усунення підтвердьте нову спробу. Перевірка у Compilatio починається після готового файла.
          </p>
          <Link href={`/dashboard/documents/${productionCase.document_id}`} className="mt-3 inline-flex rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
            Перейти до нової спроби
          </Link>
        </section>
      )}

      {blockers.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Видача поки недоступна: {blockers.map((gate) => gateLabel(gate.gate_key)).join(', ')}.
        </div>
      )}

      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-gray-900">Один файл для перевірки та видачі</h2>
        {productionCase.document?.artifact_bindings?.docx ? (
          <div className="mt-2 text-xs text-gray-600">
            <p className="text-sm">Спочатку завантажте DOCX для Compilatio. Після перевірок можна отримати той самий файл для видачі. Відправлення клієнту залишається у звичайному процесі агенції.</p>
            <details className="mt-3">
              <summary className="cursor-pointer">Технічний відбиток файла</summary>
              <p className="mt-2 break-all font-mono" data-testid="docx-fingerprint">
                SHA-256: {productionCase.document.artifact_bindings.docx.fingerprint_sha256}
              </p>
            </details>
          </div>
        ) : (
          <p className="mt-2 text-sm text-amber-800">
            Зафіксований DOCX ще не готовий.
          </p>
        )}
      </section>

      {productionCase.document?.artifact_bindings?.docx && (
        <ReleaseEvidenceForms
          key={productionCase.document.artifact_bindings.docx.fingerprint_sha256}
          caseId={caseId}
          fingerprint={productionCase.document.artifact_bindings.docx.fingerprint_sha256}
          gates={gates}
          targetPages={productionCase.document.target_pages}
          onSaved={load}
        />
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[
          ['Написання', productionCase.generation_status],
          ['Перевірки', gates.length && !blockers.length ? 'passed' : blockers.some((gate) => gate.status === 'failed') ? 'failed' : 'needs_review'],
          ['Огляд змісту', productionCase.editorial_status],
          ['Видача', blockers.length ? 'blocked' : productionCase.release_status === 'released' ? 'ready' : productionCase.release_status],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs uppercase text-gray-500">{label}</p>
            <p className="mt-2 text-lg font-semibold text-gray-900">{productionStatus(value)}</p>
          </div>
        ))}
      </div>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Результати перевірок</h2>
          <p className="mt-1 text-sm text-gray-500">
            Усі обов’язкові перевірки мають бути пройдені для поточного DOCX. Зміна файла потребує нових доказів.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {gates.map((gate) => {
            return (
              <div key={gate.gate_key} className={`rounded-lg border p-4 ${gateTone(gate)}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-gray-900">{gateLabel(gate.gate_key)}</h3>
                    <p className="mt-1 text-sm text-gray-600">{gateDetail(gate)}</p>
                  </div>
                  <span className="rounded bg-gray-50 px-2 py-1 text-xs text-gray-700">
                    {productionStatus(gate.status)}
                  </span>
                </div>
                <p className="mt-3 text-xs text-gray-500">
                  {gate.blocking ? 'Обов’язкова перевірка' : 'Інформація для огляду'}
                </p>
                {gate.gate_key === 'academic_quality' && gate.evidence?.retry_allowed === true && (
                  <div className="mt-3">
                    <p className="mb-2 text-xs text-gray-500">Повторна перевірка готового тексту потребує нового виклику AI.</p>
                    <Button onClick={handleReviewRetry} disabled={isRetryingReview}>
                      {isRetryingReview ? 'Перевірка триває…' : 'Повторити AI-перевірку'}
                    </Button>
                  </div>
                )}
                {!operatorView && gate.evidence && Object.keys(gate.evidence).length > 0 && (
                  <dl className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-600 sm:grid-cols-2">
                    {Object.entries(gate.evidence)
                      .filter(([key]) =>
                        [
                          'detector_name',
                          'result_percent',
                          'decision',
                          'checked_at',
                          'report_id',
                          'threshold_percent',
                          'no_rewrite_confirmed',
                          'artifact_format',
                          'artifact_identifier',
                          'binding_status',
                        ].includes(key)
                      )
                      .map(([key, value]) => (
                        <div key={key}>
                          <dt className="text-gray-500">{key}</dt>
                          <dd className="break-words text-gray-700">{String(value)}</dd>
                        </div>
                      ))}
                  </dl>
                )}
                {gate.override_reason && (
                  <p className="mt-2 text-xs text-green-800">
                    Пояснення винятку: {gate.override_reason}
                  </p>
                )}
                {!operatorView && gate.override_allowed && gate.status !== 'overridden' && (
                  <button
                    type="button"
                    onClick={() => handleOverride(gate)}
                    className="mt-3 text-sm text-primary-700 hover:text-primary-800"
                  >
                    Адміністративний виняток з поясненням
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {!operatorView && <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-gray-900">Витрати на підготовку</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase text-gray-500">Хвилини огляду</p>
            <p className="mt-1 text-gray-900">{productionCase.human_minutes_used}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-gray-500">Вартість</p>
            <p className="mt-1 text-gray-900">€{(productionCase.cost_cents / 100).toFixed(2)}</p>
          </div>
          <div>
            <p className="text-xs uppercase text-gray-500">Витрати AI</p>
            <p className="mt-1 text-gray-900">
              €{((productionCase.ai_cost_eur_cents ?? 0) / 100).toFixed(2)}
            </p>
            <p className="text-xs text-gray-500">
              {(productionCase.ai_total_tokens ?? 0).toLocaleString()} токенів
            </p>
          </div>
          <div>
            <p className="text-xs uppercase text-gray-500">Обліковий запис</p>
            <p className="mt-1 text-gray-900">{productionCase.client_email || 'Не вказано'}</p>
          </div>
        </div>
      </section>}
    </div>
  )
}
