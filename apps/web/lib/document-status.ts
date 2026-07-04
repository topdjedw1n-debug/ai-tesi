/**
 * Single source of truth for document status display.
 * To support a new backend status, add one entry here — every list and
 * detail page reads from this map.
 */

export interface StatusConfig {
  label: string
  badgeClass: string
}

export const DOCUMENT_STATUS: Record<string, StatusConfig> = {
  draft: { label: 'Чернетка', badgeClass: 'bg-gray-100 text-gray-800' },
  generating: { label: 'Генерується', badgeClass: 'bg-primary-100 text-primary-800' },
  payment_pending: { label: 'Очікує оплату', badgeClass: 'bg-amber-100 text-amber-800' },
  outline_generated: { label: 'План готовий', badgeClass: 'bg-primary-100 text-primary-800' },
  sections_generated: { label: 'Розділи готові', badgeClass: 'bg-amber-100 text-amber-800' },
  completed: { label: 'Готово', badgeClass: 'bg-green-100 text-green-800' },
  failed: { label: 'Не пройшла перевірку', badgeClass: 'bg-red-100 text-red-800' },
  pending: { label: 'В черзі', badgeClass: 'bg-gray-100 text-gray-800' },
  queued: { label: 'В черзі', badgeClass: 'bg-gray-100 text-gray-800' },
  running: { label: 'Генерується', badgeClass: 'bg-primary-100 text-primary-800' },
}

const UNKNOWN_STATUS: StatusConfig = {
  label: 'Невідомий статус',
  badgeClass: 'bg-gray-100 text-gray-800',
}

export function documentStatus(status: string | undefined | null): StatusConfig {
  return (status && DOCUMENT_STATUS[status]) || UNKNOWN_STATUS
}
