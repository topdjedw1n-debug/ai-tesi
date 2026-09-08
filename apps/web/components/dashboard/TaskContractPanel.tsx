'use client'

import { ReactNode, useCallback, useEffect, useState, useRef } from 'react'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'
import { GenerationRecovery, generationStopGuidance } from '@/lib/generation-status'

interface TaskContractRule {
  key: string
  value: unknown
  source: string
  status: 'explicit' | 'assumed' | 'confirmed' | string
  note?: string
}

interface TaskContract {
  version: number
  document_id: number
  basis: string
  basis_label: string
  rules: TaskContractRule[]
  assumptions: TaskContractRule[]
  confirmation_required: boolean
  sha256: string
  confirmed: boolean
  confirmed_at: string | null
}

interface CostEstimate {
  estimated_cost_usd: number
  estimated_total_tokens?: number
  currency?: string
}

interface TaskContractPanelProps {
  documentId: number
  targetPages: number
  provider: string
  model: string
  refreshKey?: number
  retry?: boolean
  onGenerationStarted?: () => void
  children?: ReactNode
}

const RULE_LABELS: Record<string, string> = {
  topic: 'Тема',
  language: 'Мова',
  target_pages: 'Обсяг',
  citation_style: 'Стиль цитування',
  work_type: 'Тип роботи',
  structure: 'Структура',
  sources_policy: 'Політика джерел',
}

const WORK_TYPE_LABELS: Record<string, string> = {
  tesi_triennale: 'Дипломна (бакалавр)',
  tesi_magistrale: 'Магістерська',
  report: 'Курсова',
  essay: 'Есе / реферат',
  diploma: 'Дипломна',
}

const LANGUAGE_LABELS: Record<string, string> = {
  it: 'Італійська',
  uk: 'Українська',
  en: 'Англійська',
  de: 'Німецька',
  fr: 'Французька',
  es: 'Іспанська',
}

const SOURCE_LABELS: Record<string, string> = {
  intake: 'введено менеджером',
  methodology: 'з методички',
  system_default: 'стандартне правило системи',
}

function formatRuleValue(rule: TaskContractRule): string {
  if (rule.key === 'language' && typeof rule.value === 'string') {
    return LANGUAGE_LABELS[rule.value] ?? rule.value
  }
  if (rule.key === 'citation_style' && typeof rule.value === 'string') {
    return rule.value.toUpperCase()
  }
  if (rule.key === 'work_type' && typeof rule.value === 'string') {
    return WORK_TYPE_LABELS[rule.value] ?? rule.value
  }
  if (rule.key === 'target_pages') return `${String(rule.value)} сторінок`
  if (rule.key === 'structure') {
    return rule.value === 'university_methodology'
      ? 'За завантаженою методичкою'
      : 'Стандартна академічна структура для обраного типу роботи'
  }
  if (
    rule.key === 'sources_policy' &&
    rule.value &&
    typeof rule.value === 'object'
  ) {
    const policy = rule.value as {
      mode?: string
      mandatory_files?: string[]
      supplementary_files?: string[]
    }
    if (policy.mode === 'auto') return 'Автоматичний пошук академічних джерел'
    const mandatory = policy.mandatory_files?.length ?? 0
    const supplementary = policy.supplementary_files?.length ?? 0
    return `Завантажені + автоматично знайдені · обов’язкових ${mandatory} · додаткових ${supplementary}`
  }
  return String(rule.value ?? '—')
}

function RuleStatus({ rule }: { rule: TaskContractRule }) {
  const assumed = rule.status === 'assumed'
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        assumed
          ? 'bg-amber-100 text-amber-800'
          : 'bg-green-100 text-green-800'
      }`}
    >
      {assumed ? 'Припущення' : 'Явно задано'}
    </span>
  )
}

export function TaskContractPanel({
  documentId,
  targetPages,
  provider,
  model,
  refreshKey = 0,
  retry = false,
  onGenerationStarted,
  children,
}: TaskContractPanelProps) {
  const [contract, setContract] = useState<TaskContract | null>(null)
  const [cost, setCost] = useState<CostEstimate | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  const [causeResolved, setCauseResolved] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [recovery, setRecovery] = useState<GenerationRecovery | null>(null)
  const [replacementReason, setReplacementReason] = useState('')
  const intent = useRef<{ fingerprint: string; id: string } | null>(null)
  const resuming = retry && !!recovery?.allowed_actions.includes('resume')
  const replacing = retry && !!recovery?.allowed_actions.includes('new_version')
  const recoveryReady = !retry || !!recovery && (resuming || replacing) && (!replacing || replacementReason.trim().length >= 3)

  const loadContract = useCallback(async () => {
    setIsLoading(true)
    setLoadFailed(false)
    setAcknowledged(false)
    setCauseResolved(false)
    try {
      const [contractResponse, costResponse, jobResponse] = await Promise.all([
        apiClient.get<TaskContract>(
          API_ENDPOINTS.DOCUMENTS.TASK_CONTRACT(documentId)
        ),
        apiClient
          .get<CostEstimate>(
            API_ENDPOINTS.GENERATE.ESTIMATE_COST({
              provider,
              model,
              targetPages,
              includeRag: true,
              includeHumanization: false,
            })
          )
          .catch((error) => {
            console.error('Failed to load cost estimate:', error)
            return null
          }),
        retry ? apiClient.get<GenerationRecovery | null>(`${API_ENDPOINTS.GENERATE.FULL}/${documentId}/recovery`) : Promise.resolve(null),
      ])
      setRecovery(jobResponse || null)
      setContract(contractResponse)
      setCost(costResponse)
    } catch (error) {
      console.error('Failed to load task contract:', error)
      setContract(null)
      setCost(null)
      setLoadFailed(true)
    } finally {
      setIsLoading(false)
    }
  }, [documentId, model, provider, targetPages, retry])

  useEffect(() => {
    loadContract()
  }, [loadContract, refreshKey])

  const handleConfirmAndStart = async () => {
    if (!contract || !acknowledged || isStarting || !recoveryReady || (retry && !causeResolved)) return
    setIsStarting(true)
    let confirmed = contract.confirmed
    try {
      if (!confirmed && !resuming) {
        await apiClient.post(
          API_ENDPOINTS.DOCUMENTS.CONFIRM_TASK_CONTRACT(documentId)
        )
        confirmed = true
        setContract((current) =>
          current ? { ...current, confirmed: true } : current
        )
      }
      const fingerprint = recovery?.expected_fingerprint || 'initial'
      if (!intent.current || intent.current.fingerprint !== fingerprint) {
        intent.current = { fingerprint, id: crypto.randomUUID() }
      }
      if (resuming && recovery) {
        await apiClient.post(API_ENDPOINTS.GENERATE.FULL + '/' + documentId + '/resume', {
          intent_id: intent.current.id,
          expected_fingerprint: recovery.expected_fingerprint,
          confirm_paid: true,
          confirm_access_restored: causeResolved,
        })
      } else {
        await apiClient.post(API_ENDPOINTS.GENERATE.FULL, {
          document_id: documentId,
          intent_id: intent.current.id,
          ...(replacing && recovery ? {
            mode: 'new_version',
            confirm_replace: true,
            expected_fingerprint: recovery.expected_fingerprint,
            replacement_reason: replacementReason.trim(),
          } : {}),
        })
      }
      toast.success(resuming ? 'Продовження підтверджено — збережені матеріали використає система' : 'Умови підтверджено — написання почалось')
      onGenerationStarted?.()
    } catch (error: any) {
      toast.error(
        error?.message ||
          (confirmed
            ? 'Умови підтверджено, але початок написання не підтверджений. Оновіть сторінку й перевірте стан перед новим запуском.'
            : 'Не вдалося підтвердити умови роботи')
      )
      setAcknowledged(false)
      setCauseResolved(false)
    } finally {
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-lg bg-white p-6 shadow" data-testid="task-contract-loading">
        <div className="flex h-28 items-center justify-center">
          <LoadingSpinner />
        </div>
      </div>
    )
  }

  if (loadFailed || !contract) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <h2 className="font-semibold text-red-900">Контракт не завантажився</h2>
        <p className="mt-1 text-sm text-red-700">
          Генерація недоступна, доки правила роботи не можна перевірити.
        </p>
        <Button className="mt-4" variant="outline" onClick={loadContract}>
          Спробувати ще раз
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6" data-testid="task-contract-flow">
      <section
        className="rounded-lg bg-white p-6 shadow"
        aria-labelledby="task-contract-heading"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="task-contract-heading" className="text-lg font-semibold text-gray-900">
              Контракт роботи
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Перевір, що саме система вважатиме завданням перед початком написання.
            </p>
          </div>
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
              contract.basis === 'university_methodology'
                ? 'bg-green-100 text-green-800'
                : 'bg-amber-100 text-amber-800'
            }`}
          >
            {contract.basis === 'university_methodology'
              ? 'На основі методички'
              : 'Стандартні академічні правила'}
          </span>
        </div>

        {contract.assumptions.length > 0 && (
          <div className="mt-4 flex gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
            <p>
              Методички немає, тому система позначила припущення. Перевір їх особливо уважно.
            </p>
          </div>
        )}

        <dl className="mt-4 divide-y divide-gray-100">
          {contract.rules.map((rule) => (
            <div key={rule.key} className="grid gap-2 py-3 sm:grid-cols-[11rem_1fr_auto] sm:items-start">
              <dt className="text-sm font-medium text-gray-700">
                {RULE_LABELS[rule.key] ?? rule.key}
              </dt>
              <dd className="text-sm text-gray-900">
                <p>{formatRuleValue(rule)}</p>
                <p className="mt-0.5 text-xs text-gray-500">
                  {SOURCE_LABELS[rule.source] ?? rule.source}
                </p>
              </dd>
              <dd><RuleStatus rule={rule} /></dd>
            </div>
          ))}
        </dl>
      </section>

      {children}

      <section className="rounded-lg bg-white p-6 shadow" aria-labelledby="generation-start-heading">
        <h2 id="generation-start-heading" className="text-lg font-semibold text-gray-900">
          {resuming ? 'Продовжити з місця зупинки' : retry ? 'Почати заново після виправлення причини' : 'Перевірка перед запуском'}
        </h2>

        {retry ? (
          <label className="mt-4 flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <input type="checkbox" checked={causeResolved} onChange={(event) => setCauseResolved(event.target.checked)} className="mt-1" />
            <span>{resuming ? 'Причину зупинки усунуто. Я підтверджую платне продовження зі збереженими джерелами й завершеними розділами.' : 'Причину зупинки усунуто. Я підтверджую нову платну генерацію із заміною попередніх робочих матеріалів і перевірок. Історія спроб і витрат збережеться.'}</span>
          </label>
        ) : (
          <p className="mt-3 text-sm text-gray-600">До натискання кнопки нижче написання не починається. Справа для перевірок створиться автоматично разом із першим запуском.</p>
        )}

        {retry && <p className="mt-3 text-sm text-gray-700">{generationStopGuidance(recovery?.reason_code)}</p>}
        {retry && !recovery && <p className="mt-3 text-sm text-amber-700">Не вдалося підтвердити доступні дії. Оновіть стан перед запуском.</p>}
        {replacing && (
          <label className="mt-4 block text-sm text-gray-700">
            Причина нового запуску
            <textarea value={replacementReason} onChange={(event) => setReplacementReason(event.target.value)} maxLength={500} className="mt-1 block w-full rounded-md border border-gray-300 p-2" />
          </label>
        )}
        {resuming && <p className="mt-3 text-sm text-gray-600">Продовження використовує готові частини. Сума нижче — оцінка повного написання; остаточні витрати залежать від фактичних звернень до сервісів.</p>}
        <div className="mt-4 rounded-lg bg-gray-50 p-4">
          <p className="text-sm font-medium text-gray-700">Орієнтовна вартість повної генерації</p>
          {cost ? (
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-2xl font-semibold text-gray-900">
                ${cost.estimated_cost_usd.toFixed(2)}
              </span>
              {typeof cost.estimated_total_tokens === 'number' && (
                <span className="text-sm text-gray-500">
                  близько {cost.estimated_total_tokens.toLocaleString('uk-UA')} токенів
                </span>
              )}
            </div>
          ) : (
            <p className="mt-1 text-sm text-amber-700">
              Оцінка тимчасово недоступна. Це не змінює ліміти запуску.
            </p>
          )}
        </div>

        <label className="mt-5 flex items-start gap-3 rounded-md border border-gray-200 p-4 text-sm text-gray-800">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
            className="mt-0.5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            data-testid="task-contract-confirmation"
          />
          <span>
            Я перевірив(ла) тему, тип роботи, обсяг, правила та джерела й підтверджую цей контракт.
          </span>
        </label>

        {contract.confirmed && (
          <p className="mt-3 flex items-center gap-2 text-sm text-green-700">
            <CheckCircleIcon className="h-5 w-5" aria-hidden="true" />
            Поточну версію контракту вже було підтверджено.
          </p>
        )}

        <div className="mt-5 flex justify-end">
          <Button
            onClick={handleConfirmAndStart}
            disabled={!acknowledged || isStarting || !recoveryReady || (retry && !causeResolved)}
            data-testid="confirm-and-start-button"
          >
            {isStarting && <LoadingSpinner size="sm" className="mr-2" />}
            {isStarting ? 'Запускаємо…' : resuming ? 'Підтвердити продовження' : retry ? 'Почати заново' : 'Підтвердити і запустити'}
          </Button>
        </div>
      </section>
    </div>
  )
}
