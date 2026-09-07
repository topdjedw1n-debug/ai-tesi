'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { apiClient, API_ENDPOINTS } from '@/lib/api';
import { generationStopGuidance } from '@/lib/generation-status';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';

interface GenerationProgressProps {
  documentId: number;
  onComplete?: () => void;
  onError?: (error: string) => void;
  active?: boolean;
}

interface ProgressState {
  status:
    | 'queued'
    | 'running'
    | 'retrying'
    | 'completed'
    | 'failed'
    | 'cancelled';
  progress: number;
  currentSection?: string;
  estimatedTime?: string;
  error?: string;
}

export function GenerationProgress({
  documentId,
  onComplete,
  onError,
  active = true,
}: GenerationProgressProps) {
  const [progressState, setProgressState] = useState<ProgressState>({
    status: 'queued',
    progress: 0,
  });
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const callbacks = useRef({ onComplete, onError });
  const terminalNotified = useRef(false);
  useEffect(() => {
    callbacks.current = { onComplete, onError };
  }, [onComplete, onError]);

  const applyMessage = useCallback(
    (message: Record<string, any>) => {
      // A user can have several documents; the socket is user-scoped.
      if (message.document_id != null && message.document_id !== documentId)
        return;
      // Handle different message types
      if (message.type === 'job_started') {
        setProgressState({
          status: 'running',
          progress: message.progress || 0,
          currentSection: message.current_section,
          estimatedTime: message.estimated_time,
        });
      } else if (message.type === 'job_completed') {
        setProgressState({
          status: 'completed',
          progress: 100,
        });
        if (!terminalNotified.current) {
          terminalNotified.current = true;
          callbacks.current.onComplete?.();
        }
      } else if (message.type === 'job_failed') {
        const errorMsg = message.error || 'Причину зупинки ще не записано';
        setProgressState({
          status: message.status === 'cancelled' ? 'cancelled' : 'failed',
          progress: message.progress || 0,
          error: errorMsg,
        });
        if (!terminalNotified.current) {
          terminalNotified.current = true;
          callbacks.current.onError?.(errorMsg);
        }
      } else if (message.type === 'job_retrying') {
        setProgressState((current) => ({
          ...current,
          status: 'retrying',
          progress: message.progress ?? current.progress,
          currentSection: undefined,
          estimatedTime: undefined,
          error: undefined,
        }));
      } else if (message.type === 'progress_update') {
        setProgressState((current) => ({
          status: 'running',
          progress: message.preserve_live_progress
            ? Math.max(current.progress, message.progress ?? 0)
            : message.progress_percentage ?? message.progress ?? 0,
          currentSection: message.persisted_poll
            ? current.currentSection
            : message.current_section,
          estimatedTime: message.persisted_poll
            ? current.estimatedTime
            : message.estimated_time,
        }));
      }
    },
    [documentId]
  );

  const {
    isConnected,
    isConnecting,
    error: wsError,
  } = useWebSocket({
    documentId,
    enabled: active,
    onMessage: applyMessage,
  });
  const connected = useRef(isConnected);
  connected.current = isConnected;

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    terminalNotified.current = false;
    const poll = async () => {
      let terminal = false;
      try {
        const job = await apiClient.get<{
          job_id: number;
          document_id: number;
          status: string;
          progress: number;
          attempt_count: number;
          error_message: string | null;
        } | null>(API_ENDPOINTS.JOBS.FOR_DOCUMENT(documentId));
        if (stopped) return;
        setStatusUnavailable(false);
        if (job) {
          terminal = ['completed', 'failed', 'cancelled'].includes(job.status);
          // A request started before the terminal socket event may return late.
          if (terminalNotified.current && !terminal) return;
          const type =
            job.status === 'completed'
              ? 'job_completed'
              : terminal
                ? 'job_failed'
                : job.status === 'queued' && job.attempt_count > 0
                  ? 'job_retrying'
                  : job.status === 'running'
                    ? 'progress_update'
                    : 'job_started';
          if (job.status === 'queued' && !job.attempt_count) {
            setProgressState({ status: 'queued', progress: job.progress });
          } else {
            applyMessage({
              ...job,
              type,
              error: job.error_message,
              persisted_poll: true,
              preserve_live_progress: connected.current,
            });
          }
        }
      } catch {
        if (!stopped) setStatusUnavailable(true);
      }
      if (!stopped && active && !terminal) timer = setTimeout(poll, 3000);
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [documentId, active, applyMessage]);

  const getStatusColor = () => {
    switch (progressState.status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
      case 'cancelled':
        return 'bg-red-500';
      case 'running':
        return 'bg-primary-500';
      case 'retrying':
        return 'bg-amber-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getStatusIcon = () => {
    switch (progressState.status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'failed':
      case 'cancelled':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />;
      case 'running':
        return <ClockIcon className="h-5 w-5 animate-spin text-primary-500" />;
      case 'retrying':
        return <ClockIcon className="h-5 w-5 text-amber-500" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusText = () => {
    switch (progressState.status) {
      case 'queued':
        return 'В черзі';
      case 'running':
        return 'Генерується…';
      case 'retrying':
        return 'Повторна спроба';
      case 'completed':
        return 'Написання завершено';
      case 'cancelled':
        return 'Скасовано';
      case 'failed':
        return 'Не вдалося';
      default:
        return 'Невідомо';
    }
  };

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">Хід генерації</h3>
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="text-sm font-medium text-gray-700">
              {getStatusText()}
            </span>
          </div>
        </div>

        {/* Connection Status */}
        {isConnecting && (
          <div className="mb-2 text-xs text-gray-500">Підключаємось…</div>
        )}
        {!isConnected && !isConnecting && wsError && (
          <p className="mb-2 text-xs text-amber-700">
            Прямий зв’язок втрачено. Перевіряємо збережений стан; це не означає
            зупинку генерації.
          </p>
        )}
        {statusUnavailable && (
          <p role="status" className="text-sm text-amber-700">
            Не вдалося оновити стан. Останній відомий прогрес збережено;
            перевіряємо зв’язок.
          </p>
        )}
        {isConnected && (
          <div className="mb-2 text-xs text-green-500">Наживо</div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="h-2.5 w-full rounded-full bg-gray-200">
          <div
            className={`h-2.5 rounded-full transition-all duration-300 ${getStatusColor()}`}
            style={{ width: `${progressState.progress}%` }}
          />
        </div>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {progressState.progress}%
          </span>
          {progressState.estimatedTime && (
            <span className="text-sm text-gray-500">
              Орієнтовно лишилось: {progressState.estimatedTime}
            </span>
          )}
        </div>
      </div>

      {/* Current Section */}
      {progressState.currentSection && (
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            Поточний етап:{' '}
            <span className="font-medium">{progressState.currentSection}</span>
          </p>
        </div>
      )}

      {/* Error Message */}
      {progressState.error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3">
          <div className="flex items-start">
            <ExclamationTriangleIcon className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
            <div className="ml-2">
              <p className="text-sm font-medium text-red-800">
                Помилка генерації
              </p>
              <p className="mt-1 text-sm text-red-700">
                {generationStopGuidance(progressState.error)}
              </p>
              <details className="mt-2 text-xs text-red-700">
                <summary className="cursor-pointer">
                  Технічна причина для діагностики
                </summary>
                <p className="mt-1 break-words">{progressState.error}</p>
              </details>
            </div>
          </div>
        </div>
      )}

      {/* Status Details */}
      {progressState.status === 'retrying' && (
        <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Система автоматично відновить цю спробу. Завершені розділи
          зберігаються; повторно натискати запуск не потрібно.
        </p>
      )}
      {progressState.status === 'completed' && (
        <div className="mt-4 rounded-md border border-green-200 bg-green-50 p-3">
          <div className="flex items-center">
            <CheckCircleIcon className="h-5 w-5 text-green-500" />
            <p className="ml-2 text-sm font-medium text-green-800">
              DOCX готовий до перевірки. Перейдіть до «Перевірка та видача», щоб
              провести Compilatio й оцінити зміст.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
