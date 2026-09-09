'use client';

import { useEffect, useRef, useState } from 'react';
import { apiClient, API_ENDPOINTS } from '@/lib/api';

export interface GenerationStop {
  code: string;
  message_uk: string;
  next_action: 'retry_now' | 'retry_after_owner' | 'contact_owner';
  next_action_label: string;
  retryable: boolean;
}

export interface GenerationJob {
  job_id: number;
  status: string;
  status_label?: string | null;
  executor_version?: number | null;
  progress: number;
  stage_label?: string | null;
  sections_done?: number;
  sections_total?: number;
  last_signal?: string | null;
  cost_cents_so_far?: number;
  tokens_so_far?: number;
  warnings_count?: number;
  heartbeat_at?: string | null;
  started_at?: string | null;
  observed_at?: string | null;
  error_message?: string | null;
  stop?: GenerationStop | null;
}

export function GenerationProgress({ documentId, onComplete, onError, onCancelled, onOwnerAction, active = true }: {
  documentId: number;
  onComplete?: () => void;
  onError?: (error: string) => void;
  onOwnerAction?: () => void;
  onCancelled?: () => void;
  active?: boolean;
}) {
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [ownerMessage, setOwnerMessage] = useState(false);
  const [checkedAt, setCheckedAt] = useState(Date.now);
  const receivedAt = useRef(Date.now());
  const callbacks = useRef({ onComplete, onError, onCancelled });
  callbacks.current = { onComplete, onError, onCancelled };
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let notified = false;
    setJob(null);
    setOwnerMessage(false);
    const poll = async () => {
      let terminal = false;
      try {
        const current = await apiClient.get<GenerationJob | null>(API_ENDPOINTS.JOBS.FOR_DOCUMENT(documentId));
        if (disposed) return;
        receivedAt.current = Date.now();
        setUnavailable(false);
        setJob(current);
        if (current) {
          terminal = ['completed', 'failed', 'cancelled', 'failed_quality'].includes(current.status);
          if (terminal && !notified) {
            notified = true;
            if (current.status === 'completed') callbacks.current.onComplete?.();
            else if (current.status === 'cancelled') callbacks.current.onCancelled?.();
            else callbacks.current.onError?.(current.stop?.message_uk || current.error_message || 'Написання зупинено.');
          }
        }
      } catch {
        if (!disposed) setUnavailable(true);
      }
      if (!disposed) setCheckedAt(Date.now());
      if (!disposed && active && !terminal) timer = setTimeout(poll, 3000);
    };
    poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [documentId, active]);
  const terminal = !!job && ['completed', 'failed', 'cancelled', 'failed_quality'].includes(job.status);
  const stale = job?.status === 'running' && job.observed_at &&
    Date.parse(job.observed_at) + Math.max(0, checkedAt - receivedAt.current) - Date.parse(job.heartbeat_at || job.started_at || job.observed_at) > 300000;
  return (
    <section className="rounded-lg bg-white p-6 shadow" aria-label="Хід генерації">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Хід генерації</h3>
        <span>{job?.status_label || 'Оновлюємо стан…'}</span>
      </div>
      {unavailable && <p role="status" className="mb-3 text-amber-700">Не вдалося оновити стан. Останній відомий прогрес збережено; перевіряємо зв’язок.</p>}
      {stale && <div className="mb-3 text-amber-800" role="status"><p>Виконавець не відповідає.</p><button onClick={() => setOwnerMessage(true)} className="mt-2 underline">Звернутися до власника</button></div>}
      {job?.stage_label && <p className="font-medium">{job.stage_label}</p>}
      {!!job?.sections_total && <p>Розділів збережено: {job.sections_done || 0} із {job.sections_total}</p>}
      {job?.last_signal && <p className="mt-2 text-sm text-gray-600">{job.last_signal}</p>}
      {job && (!terminal || job.status === 'completed') && <div className="my-4">
        <div role="progressbar" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100} className="h-2.5 rounded-full bg-gray-200">
          <div className="h-2.5 rounded-full bg-primary-500" style={{ width: `${job.progress}%` }} />
        </div><p className="mt-1 text-sm">{job.progress}%</p>
      </div>}
      {job?.executor_version === 2 && <p className="mt-3 text-sm text-gray-600">
        {(job.tokens_so_far || 0).toLocaleString('uk-UA')} токенів · ${((job.cost_cents_so_far || 0) / 100).toFixed(2)} · {job.warnings_count || 0} попереджень
      </p>}
      {job?.stop && <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
        <p>{job.stop.message_uk}</p>
        {job.stop.next_action !== 'retry_now' && !ownerMessage && <button onClick={() => { setOwnerMessage(true); onOwnerAction?.(); }} className="mt-2 underline">{job.stop.next_action_label}</button>}
      </div>}
      {ownerMessage && <p role="status" className="mt-3">Передайте власнику номер роботи №{documentId} та запуску №{job?.job_id} для відновлення доступу.</p>}
      {job?.status === 'completed' && <p className="mt-4 rounded-md bg-green-50 p-3 text-green-800">DOCX готовий. Завантажте його для Compilatio й внесіть результат у справу.</p>}
      {!job?.executor_version && job?.error_message && <p className="mt-4 text-sm text-amber-800">{job.error_message}</p>}
    </section>
  );
}
