/**
 * Intake form config — the single place that defines what the manager
 * fills in on "Нова робота".
 *
 * To add/remove/change a field, edit ONLY this array. Fields with `core`
 * map straight to Document API columns; everything else is serialized
 * into `additional_requirements` as labeled lines, so no backend change
 * is ever needed for a new intake field.
 */

export type IntakeFieldType = 'text' | 'textarea' | 'number' | 'select' | 'date'

export interface IntakeField {
  /** Unique key; also used for form state and data-testid */
  key: string
  label: string
  /** Small helper text after the label */
  hint?: string
  type: IntakeFieldType
  required?: boolean
  placeholder?: string
  options?: Array<{ value: string; label: string }>
  /** Maps to a Document API column instead of additional_requirements */
  core?: 'title' | 'topic' | 'language' | 'pages'
  /** Line label used when serializing into additional_requirements */
  requirementsLabel?: string
  defaultValue?: string | number
  rows?: number
  min?: number
  max?: number
  /** Render at half width (pairs of half-width fields share a row) */
  half?: boolean
}

export const INTAKE_FIELDS: IntakeField[] = [
  {
    key: 'topic',
    label: 'Тема роботи',
    type: 'textarea',
    required: true,
    core: 'topic',
    rows: 2,
    placeholder:
      'Напр.: Цифровий маркетинг у B2B-сегменті: стратегії та інструменти',
  },
  {
    key: 'pages',
    label: 'Обсяг',
    hint: 'сторінок',
    type: 'number',
    required: true,
    core: 'pages',
    defaultValue: 45,
    min: 3,
    max: 400,
    half: true,
  },
  {
    key: 'language',
    label: 'Мова роботи',
    type: 'select',
    required: true,
    core: 'language',
    defaultValue: 'it',
    options: [
      { value: 'it', label: 'Італійська' },
      { value: 'uk', label: 'Українська' },
      { value: 'en', label: 'Англійська' },
      { value: 'de', label: 'Німецька' },
      { value: 'fr', label: 'Французька' },
      { value: 'es', label: 'Іспанська' },
    ],
    half: true,
  },
  {
    key: 'workType',
    label: 'Тип роботи',
    type: 'select',
    requirementsLabel: 'Тип роботи',
    defaultValue: 'Дипломна (бакалавр)',
    options: [
      { value: 'Дипломна (бакалавр)', label: 'Дипломна (бакалавр)' },
      { value: 'Магістерська', label: 'Магістерська' },
      { value: 'Курсова', label: 'Курсова' },
      { value: 'Реферат', label: 'Реферат' },
      { value: 'Есе', label: 'Есе' },
    ],
    half: true,
  },
  {
    key: 'citationStyle',
    label: 'Стиль цитування',
    type: 'select',
    requirementsLabel: 'Citation style',
    defaultValue: 'APA',
    options: [
      { value: 'APA', label: 'APA' },
      { value: 'MLA', label: 'MLA' },
      { value: 'Chicago', label: 'Chicago' },
      { value: 'Harvard', label: 'Harvard' },
      { value: 'ДСТУ 8302:2015', label: 'ДСТУ 8302:2015' },
      { value: 'інший — у вимогах', label: 'Інший (описано у вимогах)' },
    ],
    half: true,
  },
  {
    key: 'deadline',
    label: 'Дедлайн',
    hint: 'опційно',
    type: 'date',
    requirementsLabel: 'Deadline',
    half: true,
  },
  {
    key: 'requirements',
    label: 'Вимоги',
    hint: 'встав як є — з листа клієнта чи методички',
    type: 'textarea',
    rows: 6,
    placeholder:
      'Університет, факультет, побажання наукового керівника, обов’язкові розділи, кількість і свіжість джерел, особливі вимоги до вступу/висновків…',
  },
]

export type IntakeFormValues = Record<string, string | number>

export function intakeDefaults(): IntakeFormValues {
  const values: IntakeFormValues = {}
  for (const field of INTAKE_FIELDS) {
    values[field.key] = field.defaultValue ?? ''
  }
  return values
}

/**
 * Split form values into the Document API payload + the serialized
 * requirements text. Non-core fields become labeled lines; the freeform
 * `requirements` field is appended verbatim at the end.
 */
export function buildDocumentPayload(values: IntakeFormValues): {
  title: string
  topic: string
  language: string
  target_pages: number
  additional_requirements: string
} {
  const topic = String(values.topic ?? '').trim()
  const lines: string[] = ['[Manager intake]']

  for (const field of INTAKE_FIELDS) {
    if (field.core || !field.requirementsLabel) continue
    const raw = String(values[field.key] ?? '').trim()
    lines.push(`${field.requirementsLabel}: ${raw || 'not specified'}`)
  }

  const freeform = String(values.requirements ?? '').trim()
  if (freeform) {
    lines.push('', '[Additional requirements]', freeform)
  }

  return {
    title: topic.length > 500 ? `${topic.slice(0, 497)}…` : topic,
    topic,
    language: String(values.language || 'it'),
    target_pages: Number(values.pages) || 0,
    additional_requirements: lines.join('\n'),
  }
}

/** Field-level validation; returns a map key -> error message (Ukrainian). */
export function validateIntake(values: IntakeFormValues): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const field of INTAKE_FIELDS) {
    const raw = String(values[field.key] ?? '').trim()
    if (field.required && !raw) {
      errors[field.key] = 'Обов’язкове поле'
      continue
    }
    if (field.key === 'topic' && raw && raw.length < 10) {
      errors[field.key] = 'Тема закоротка — потрібно щонайменше 10 символів'
    }
    if (field.type === 'number' && raw) {
      const num = Number(raw)
      if (Number.isNaN(num)) {
        errors[field.key] = 'Має бути число'
      } else if (field.min !== undefined && num < field.min) {
        errors[field.key] = `Мінімум ${field.min}`
      } else if (field.max !== undefined && num > field.max) {
        errors[field.key] = `Максимум ${field.max}`
      }
    }
  }
  return errors
}
