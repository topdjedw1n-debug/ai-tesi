import type { ReleaseGate } from '@/lib/api/admin';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Чернетка',
  not_started: 'Ще не почато',
  queued: 'У черзі',
  generating: 'Генерується',
  running: 'Виконується',
  completed: 'Завершено',
  passed: 'Пройдено',
  failed: 'Потребує виправлення',
  failed_quality: 'Перевірку не пройдено',
  needs_review: 'Очікує перевірки',
  in_progress: 'Триває перевірка',
  warning: 'Потребує уваги',
  unchecked: 'Не перевірено',
  no_data: 'Немає результату',
  blocked: 'Видачу заблоковано',
  not_ready: 'Ще не готово',
  released: 'Дозволено до видачі',
  ready: 'Файл готовий менеджеру',
  delivered: 'Файл готовий менеджеру',
  overridden: 'Погоджено з поясненням',
  cancelled: 'Скасовано',
};

export function productionStatus(value: string | null | undefined): string {
  return STATUS_LABELS[value ?? ''] ?? 'Стан уточнюється';
}

const GATE_LABELS: Record<string, string> = {
  generation_contract: 'Відповідність погодженому завданню',
  citation_verification: 'Перевірка цитат',
  claim_support: 'Підкріпленість тверджень',
  section_quality: 'Якість розділів',
  plagiarism_proxy: 'Compilatio: збіги тексту',
  ai_detection_proxy: 'Compilatio: показник AI',
  editorial_review: 'Огляд змісту',
  delivery_package: 'Фінальний DOCX',
  source_availability: 'Академічні джерела',
};

export function gateLabel(key: string): string {
  return GATE_LABELS[key] ?? 'Додаткова перевірка';
}

export function gateDetail(gate: ReleaseGate): string {
  const passed = gate.status === 'passed' || gate.status === 'overridden';
  if (['plagiarism_proxy', 'ai_detection_proxy'].includes(gate.gate_key)) {
    const percent = gate.evidence?.result_percent;
    if (typeof percent === 'number') {
      return `${percent}% у Compilatio. ${
        passed
          ? 'Звіт підтверджений для поточного DOCX.'
          : 'Видачу заблоковано: перевірте показник, звіт і відповідність поточному файлу.'
      }`;
    }
    return 'Завантажте DOCX для Compilatio, прикріпіть звіт і внесіть результат. Допустимо до 10% включно.';
  }
  const details: Record<string, [string, string]> = {
    generation_contract: [
      'Роботу створено за погодженими умовами.',
      'Умови та поточний результат не підтверджені. Перевірте завдання перед новою спробою.',
    ],
    citation_verification: [
      'Цитати пройшли перевірку.',
      'Перевірка цитат відсутня або виявила проблему. Потрібне виправлення перед видачею.',
    ],
    claim_support: [
      'Твердження пройшли перевірку опори на джерела.',
      'Підкріпленість тверджень ще не підтверджена. Перед видачею потрібно усунути причину.',
    ],
    section_quality: [
      'Розділи пройшли обов’язкові перевірки.',
      'Є непройдені або відсутні перевірки розділів. Видача недоступна.',
    ],
    editorial_review: [
      'Менеджер прийняв зміст без переписування.',
      'Прочитайте фінальний DOCX і збережіть рішення щодо змісту, обсягу та оформлення.',
    ],
    delivery_package: [
      'Фінальний DOCX збережений і доступний для перевірки.',
      'Фінальний DOCX ще не готовий або змінився. Не використовуйте попередній файл.',
    ],
    source_availability: [
      'Пакет академічних джерел пройшов перевірку.',
      'Потрібно виправити автоматичний добір або перевірку джерел. PDF необов’язкові.',
    ],
  };
  return (
    details[gate.gate_key]?.[passed ? 0 : 1] ??
    'Перегляньте результат цієї перевірки перед видачею.'
  );
}
