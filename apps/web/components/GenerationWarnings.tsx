'use client'

import { useEffect, useState } from 'react'
import { apiClient, API_ENDPOINTS } from '@/lib/api'

export interface GenerationWarning {
  id?: number
  code?: string
  severity?: string
  stage?: string
  section_index?: number | null
  section_label?: string
  message_uk?: string
  detail?: string
  created_at?: string
}

// What the manager can do about a warning; the executor keeps writing.
const GUIDANCE: Record<string, string> = {
  catalogue_unavailable:
    'Каталог не відповів: джерела дібрано з інших каталогів. Якщо їх замало, спробуйте пізніше або зверніться до власника.',
  plan_material_gap: 'Розділ буде написано з того, що є в пакеті.',
  source_full_text_unavailable:
    'Відкрийте посилання в браузері й збережіть PDF: його можна додати до нової роботи з тим самим брифом як джерело.',
}

function groupBySection(warnings: GenerationWarning[]): Array<[string, GenerationWarning[]]> {
  const groups = new Map<string, GenerationWarning[]>()
  for (const warning of warnings) {
    const label = warning.section_label || (warning.section_index ? `Розділ ${warning.section_index}` : 'Загальні зауваження')
    groups.set(label, [...(groups.get(label) || []), warning])
  }
  return Array.from(groups.entries())
}

export function WarningList({ warnings }: { warnings?: GenerationWarning[] | null }) {
  if (!warnings?.length) return null
  return (
    <section className="rounded-md border border-amber-200 bg-amber-50 p-4" aria-labelledby="generation-warnings-heading">
      <h3 id="generation-warnings-heading" className="font-medium text-amber-900">{warnings.length} попереджень</h3>
      <p className="mt-1 text-sm text-amber-900">Ці зауваження не зупиняють написання. Перегляньте їх перед перевіркою роботи.</p>
      {groupBySection(warnings).map(([label, items]) => (
        <div key={label} className="mt-3">
          <h4 className="text-sm font-medium text-amber-950">{label}</h4>
          <ul className="mt-2 space-y-2 text-sm text-amber-950">
            {items.map((warning, index) => (
              <li key={warning.id ?? `${label}-${index}`}>
                <p>{warning.message_uk || warning.code}</p>
                {warning.detail && <p className="mt-1 text-amber-800">{warning.detail}</p>}
                {warning.code && GUIDANCE[warning.code] && <p className="mt-1 text-amber-800">{GUIDANCE[warning.code]}</p>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}

/** Warnings of the latest run of a finished work, read once from the job status. */
export function GenerationWarnings({ documentId }: { documentId: number }) {
  const [warnings, setWarnings] = useState<GenerationWarning[]>([])
  useEffect(() => {
    let disposed = false
    apiClient
      .get<{ warnings?: GenerationWarning[] } | null>(API_ENDPOINTS.JOBS.FOR_DOCUMENT(documentId))
      .then((job) => { if (!disposed) setWarnings(job?.warnings || []) })
      .catch(() => { if (!disposed) setWarnings([]) })
    return () => { disposed = true }
  }, [documentId])
  return <WarningList warnings={warnings} />
}
