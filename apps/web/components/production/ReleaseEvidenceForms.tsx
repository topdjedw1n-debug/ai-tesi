'use client';

import { FormEvent, useEffect, useState } from 'react';
import {
  adminApiClient,
  ContentReviewPayload,
  DetectorReport,
  ReleaseGate,
} from '@/lib/api/admin';
import toast from 'react-hot-toast';
import { gateDetail } from '@/lib/production-status';

const fieldClass =
  'mt-1 w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900';
const buttonClass =
  'rounded bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50';
const detectorLabels: Record<string, string> = {
  plagiarism_proxy: 'Збіги тексту (similarity)',
  ai_detection_proxy: 'Показник AI',
};

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'Не вдалося зберегти перевірку. Спробуйте ще раз.';
}

function localDateTime(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function DetectorResultForm({
  caseId,
  fingerprint,
  gateKey,
  reports,
  onSaved,
}: {
  caseId: number;
  fingerprint: string;
  gateKey: string;
  reports: DetectorReport[];
  onSaved: () => Promise<void>;
}) {
  const [percent, setPercent] = useState('');
  const [reportId, setReportId] = useState('');
  const [checkedAt, setCheckedAt] = useState(localDateTime);
  const [confirmed, setConfirmed] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const overThreshold = percent !== '' && Number(percent) > 10;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      saving ||
      !confirmed ||
      !reportId ||
      percent.trim() === '' ||
      !Number.isFinite(Number(percent))
    )
      return;
    setSaving(true);
    setError('');
    try {
      const result = await adminApiClient.recordDetectorResult(
        caseId,
        gateKey,
        {
          detector_name: 'Compilatio',
          result_percent: Number(percent),
          decision: rejected ? 'failed' : 'passed',
          artifact_format: 'docx',
          artifact_fingerprint_sha256: fingerprint,
          report_id: Number(reportId),
          report_matches_artifact: true,
          checked_at: new Date(checkedAt).toISOString(),
          reason:
            reason.trim() ||
            'Менеджер підтвердив звіт Compilatio для цього DOCX.',
        }
      );
      toast.success(
        result.status === 'passed'
          ? 'Перевірку збережено'
          : 'Результат збережено. Видачу заблоковано.'
      );
      await onSaved();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  };
  return (
    <form
      onSubmit={submit}
      aria-label={detectorLabels[gateKey]}
      className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
    >
      <h3 className="font-semibold text-gray-900">{detectorLabels[gateKey]}</h3>
      <label className="block text-sm text-gray-600">
        Результат, %
        <input
          type="number"
          min={0}
          max={100}
          step="any"
          required
          value={percent}
          onChange={(event) => setPercent(event.target.value)}
          className={fieldClass}
        />
      </label>
      <p
        className={
          overThreshold ? 'text-sm text-red-700' : 'text-sm text-gray-600'
        }
      >
        {overThreshold
          ? 'Понад 10%: результат збережеться як неприйнятний. Видати роботу не можна.'
          : 'Допустимо до 10% включно. Рішення обчислює система.'}
      </p>
      <label className="block text-sm text-gray-600">
        Збережений звіт Compilatio
        <select
          required
          value={reportId}
          onChange={(event) => setReportId(event.target.value)}
          className={fieldClass}
        >
          <option value="">Виберіть прикріплений звіт</option>
          {reports.map((report) => (
            <option key={report.id} value={report.id}>
              {report.filename}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm text-gray-600">
        Коли проведено перевірку
        <input
          type="datetime-local"
          required
          value={checkedAt}
          onChange={(event) => setCheckedAt(event.target.value)}
          className={fieldClass}
        />
      </label>
      <label className="flex items-start gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          required
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
          className="mt-1"
        />
        Звіт і відсоток стосуються саме DOCX, завантаженого з цієї роботи.
      </label>
      <label className="flex items-start gap-2 text-sm text-gray-600">
        <input
          type="checkbox"
          checked={rejected}
          onChange={(event) => setRejected(event.target.checked)}
          className="mt-1"
        />
        Відхилити результат з іншої причини
      </label>
      {rejected && (
        <label className="block text-sm text-gray-600">
          Причина відхилення
          <textarea
            required
            minLength={10}
            maxLength={2000}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={fieldClass}
          />
        </label>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={saving || !confirmed || !reportId || !percent}
        className={buttonClass}
      >
        {saving ? 'Зберігаємо…' : 'Зберегти результат'}
      </button>
    </form>
  );
}

export function ReleaseEvidenceForms({
  caseId,
  fingerprint,
  gates,
  targetPages,
  onSaved,
}: {
  caseId: number;
  fingerprint: string;
  gates: ReleaseGate[];
  targetPages?: number;
  onSaved: () => Promise<void>;
}) {
  const [reports, setReports] = useState<DetectorReport[]>([]);
  const [reportsError, setReportsError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [decision, setDecision] = useState<
    ContentReviewPayload['decision'] | ''
  >('');
  const [reason, setReason] = useState('');
  const [pageCount, setPageCount] = useState('');
  const [savingReview, setSavingReview] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const review = gates.find((gate) => gate.gate_key === 'editorial_review');
  const rewritten = review?.evidence?.decision === 'rewritten';

  useEffect(() => {
    let active = true;
    adminApiClient
      .listDetectorReports(caseId)
      .then((data) => {
        if (active)
          setReports((current) => [
            ...current,
            ...data.filter(
              (report) =>
                report.artifact_fingerprint_sha256 === fingerprint &&
                !current.some((item) => item.id === report.id)
            ),
          ]);
      })
      .catch((error) => {
        if (active) setReportsError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [caseId, fingerprint]);

  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || uploading) return;
    const uploadForm = event.currentTarget;
    setUploading(true);
    setReportsError('');
    try {
      const report = await adminApiClient.uploadDetectorReport(
        caseId,
        fingerprint,
        file
      );
      setReports((current) => [report, ...current]);
      setFile(null);
      uploadForm.reset();
      toast.success('Звіт прикріплено. Внесіть результати нижче.');
    } catch (error) {
      setReportsError(errorMessage(error));
    } finally {
      setUploading(false);
    }
  };
  const downloadReport = async (report: DetectorReport) => {
    try {
      const blob = await adminApiClient.downloadDetectorReport(
        caseId,
        report.id
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = report.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setReportsError(errorMessage(error));
    }
  };
  const saveReview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      !decision ||
      savingReview ||
      rewritten ||
      (decision === 'accepted' && !pageCount)
    )
      return;
    setSavingReview(true);
    setReviewError('');
    try {
      await adminApiClient.recordContentReview(caseId, {
        artifact_fingerprint_sha256: fingerprint,
        decision,
        reason,
        ...(pageCount ? { reviewed_page_count: Number(pageCount) } : {}),
      });
      toast.success('Огляд роботи збережено');
      await onSaved();
    } catch (error) {
      setReviewError(errorMessage(error));
    } finally {
      setSavingReview(false);
    }
  };
  return (
    <section className="space-y-4" aria-label="Перевірка фінального DOCX">
      <form
        onSubmit={upload}
        className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
      >
        <h2 className="text-lg font-semibold text-gray-900">
          Звіти Compilatio
        </h2>
        <p className="text-sm text-gray-600">
          Завантажте DOCX для перевірки, проведіть Compilatio та прикріпіть
          звіт. Один звіт можна використати для обох показників.
        </p>
        <label className="block text-sm text-gray-600">
          Файл звіту (PDF, PNG або JPEG, до 20 МБ)
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            required
            className={fieldClass}
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <button
          type="submit"
          disabled={!file || uploading}
          className={buttonClass}
        >
          {uploading ? 'Прикріплюємо…' : 'Прикріпити звіт'}
        </button>
        {reportsError && (
          <p role="alert" className="text-sm text-red-700">
            {reportsError}
          </p>
        )}
        {reports.length > 0 && (
          <ul className="space-y-2 text-sm text-gray-600">
            {reports.map((report) => (
              <li key={report.id}>
                <button
                  type="button"
                  onClick={() => downloadReport(report)}
                  className="text-primary-700 underline"
                >
                  {report.filename}
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>
      <div className="grid gap-4 lg:grid-cols-2">
        {Object.keys(detectorLabels).map((gateKey) => (
          <DetectorResultForm
            key={gateKey}
            caseId={caseId}
            fingerprint={fingerprint}
            gateKey={gateKey}
            reports={reports}
            onSaved={onSaved}
          />
        ))}
      </div>
      <form
        onSubmit={saveReview}
        aria-label="Огляд змісту"
        className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
      >
        <h2 className="text-lg font-semibold text-gray-900">
          Огляд змісту менеджером
        </h2>
        <p className="text-sm text-gray-600">
          Перевірте тему, структуру, джерела й цитати, мову, обсяг та
          оформлення. Прийняття означає, що зміст не довелося переписувати.
        </p>
        <p className="text-sm text-gray-600">
          Відкрийте саме цей DOCX у Word або LibreOffice та звірте обсяг із
          завданням
          {targetPages ? ` (${targetPages} сторінок)` : ''}. Рахуйте сторінки
          після оформлення; лічильник слів на сайті не замінює цієї перевірки.
        </p>
        {review && (
          <p className="text-sm text-gray-700">{gateDetail(review)}</p>
        )}
        {review?.evidence?.reviewed_page_count && (
          <p className="text-sm text-gray-600">
            В останньому огляді: {review.evidence.reviewed_page_count} сторінок
            у DOCX.
          </p>
        )}
        {rewritten ? (
          <p role="alert" className="text-sm text-red-700">
            Зафіксовано переписування. Цей результат не можна прийняти повторною
            галочкою.
          </p>
        ) : (
          <>
            <label className="block text-sm text-gray-600">
              Фактична кількість сторінок у DOCX
              <input
                type="number"
                min={1}
                max={1000}
                step={1}
                required={decision === 'accepted'}
                value={pageCount}
                onChange={(event) => setPageCount(event.target.value)}
                className={fieldClass}
              />
            </label>
            <label className="block text-sm text-gray-600">
              Рішення щодо змісту
              <select
                required
                value={decision}
                onChange={(event) =>
                  setDecision(event.target.value as typeof decision)
                }
                className={fieldClass}
              >
                <option value="">Виберіть після перегляду роботи</option>
                <option value="accepted">
                  Робота відповідає завданню, зміст не переписували
                </option>
                <option value="rejected">
                  Робота непридатна, потрібне виправлення системи
                </option>
                <option value="rewritten">
                  Знадобилося переписування змісту людиною
                </option>
              </select>
            </label>
            {decision && decision !== 'accepted' && (
              <label className="block text-sm text-gray-600">
                Що не так із роботою
                <textarea
                  required
                  minLength={10}
                  maxLength={2000}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  className={fieldClass}
                />
              </label>
            )}
            <button
              type="submit"
              disabled={
                !decision ||
                savingReview ||
                (decision === 'accepted' && !pageCount)
              }
              className={buttonClass}
            >
              {savingReview ? 'Зберігаємо…' : 'Зберегти огляд'}
            </button>
          </>
        )}
        {reviewError && (
          <p role="alert" className="text-sm text-red-700">
            {reviewError}
          </p>
        )}
      </form>
    </section>
  );
}
