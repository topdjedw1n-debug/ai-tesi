export interface GenerationRecovery {
  executor_version?: number
  stop?: { message_uk: string; retryable: boolean; next_action: string; next_action_label: string } | null
  reason_code?: string
  allowed_actions: Array<'resume' | 'new_version'>
  expected_fingerprint: string
}

const REASON_GUIDANCE: Record<string, string> = {
  recording_storage_unavailable: 'Не вдалося зберегти запис відповіді. Після відновлення сховища можна продовжити зі збереженого прогресу.',
  provider_temporarily_unavailable: 'Зовнішній сервіс тимчасово недоступний. Збережені джерела й завершені розділи можна використати при продовженні.',
  review_temporarily_unavailable: 'Рецензент тимчасово недоступний. Потрібно повторити перевірку; завершений текст збережено.',
  provider_access_required: 'Потрібно відновити доступ або поповнити баланс AI-сервісу, а потім підтвердити продовження.',
  review_input_invalid: 'Вхід перевірки відсутній або перевищує її місткість. Потрібне виправлення причини перед новим запуском.',
  source_coverage_gap: 'Джерела не покривають потрібну вимогу. Перегляньте записану прогалину перед новим запуском.',
  plan_requirements_unmet: 'План не виконує погоджені вимоги. Потрібно виправити вказану причину.',
  academic_content_rejected: 'Робота не пройшла змістовну перевірку. Зауваження збережені; автоматичного переписування немає.',
  artifact_temporarily_unavailable: 'Файл не вдалося сформувати або зберегти. Продовження повторить експорт зі збереженого тексту.',
  contract_or_profile_mismatch: 'Змінилися вимоги або версія генератора. Збережений результат потребує окремого рішення.',
  checkpoint_integrity_error: 'Цілісність збережених матеріалів не підтверджена. Потрібна технічна перевірка.',
  cancelled_by_user: 'Запуск скасовано. Продовження потребує нового підтвердження платної дії.',
  legacy_unknown: 'Стара спроба не має підтвердженої сумісності для продовження. Її історію збережено.',
}

export function generationStopGuidance(reasonCode?: string): string {
  return REASON_GUIDANCE[reasonCode || ''] || 'Роботу зупинено. Причина потребує діагностики; доступні дії визначає система.'
}
