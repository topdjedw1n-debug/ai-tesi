'use client';

import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

type Phase0ReadinessPayload = {
  test_contour: {
    country: string;
    university_context: string;
    language: string;
    work_type: string;
    sanity_run_size: string;
    target_full_run_size: string;
    citation_style: string;
  };
  detector_access: {
    plagiarism_checker: string;
    plagiarism_checker_kind: string;
    plagiarism_threshold: string;
    ai_detector: string;
    ai_risk_threshold: string;
    turnitin_ai_access: string;
    proxy_detector: string;
    detector_limitations: string;
    evidence_owner: string;
    evidence_date: string;
  };
  human_minutes_budget: {
    price_band: string;
    estimated_ai_generation_cost: string;
    estimated_detector_cost: string;
    estimated_editor_cost: string;
    estimated_total_cost: string;
    human_written_comparison_cost: string;
    manager_setup_budget: string;
    editor_review_budget: string;
    editing_remediation_budget: string;
    detector_rerun_budget: string;
    delivery_prep_budget: string;
    total_human_minutes_budget: string;
    cost_source: string;
    budget_source: string;
  };
  citation_gate_state: {
    provenance_ledger_enabled: string;
    citation_verification_enabled: string;
    citation_verification_policy: string;
    crossref_access: string;
    openalex_access: string;
    semantic_scholar_access: string;
    arxiv_access: string;
    target_environment_evidence: string;
    known_blind_spots: string;
  };
  ownership: {
    manager: string;
    editor: string;
    release_decision_owner: string;
    detector_evidence_owner: string;
  };
  remediation_plan: {
    pre_delivery_detector_fail: string;
    post_delivery_failure: string;
    max_extra_minutes: string;
    client_delivery_policy: string;
  };
};

type Criterion = {
  key: string;
  label: string;
  passed: boolean;
};

const STRICT_REMEDIATION = {
  pre_delivery_detector_fail:
    'Do not deliver. Run editor remediation or regenerate flagged sections, re-check GPTZero/plagiarism, and release only after manager approval.',
  post_delivery_failure:
    'Open an editor escalation, rewrite failed sections, re-run checks, and record the final decision in the production case.',
  max_extra_minutes:
    'Track extra work during RUN-001; if expected total cost exceeds target margin, mark economics as failed.',
  client_delivery_policy:
    'Client receives only manager-approved final delivery. Failed detector/citation evidence blocks delivery.',
};

const EDITOR_LOOP_REMEDIATION = {
  pre_delivery_detector_fail:
    'Send flagged sections to editor, revise for source use and academic style, then re-check GPTZero/plagiarism before manager release.',
  post_delivery_failure:
    'Offer one focused revision cycle tied to the failed criterion; if the second check fails, escalate to rewrite/refund decision.',
  max_extra_minutes:
    'Track extra editor minutes separately from baseline production cost.',
  client_delivery_policy:
    'Delivery is allowed after release approval; revision promise is limited to detector/citation failures recorded in evidence.',
};

const REWRITE_REFUND_REMEDIATION = {
  pre_delivery_detector_fail:
    'Hold delivery and choose the cheaper path: editor remediation or regenerate affected sections, then re-check.',
  post_delivery_failure:
    'If client/university rejects, provide rewrite first; if rewrite is not economically viable, approve partial/full refund per manager decision.',
  max_extra_minutes:
    'Stop remediation when expected total cost exceeds target margin.',
  client_delivery_policy:
    'No public promise of bypassing detectors. Commercial promise is managed rewrite/refund handling after evidence review.',
};

const REMEDIATION_OPTIONS: Array<{
  title: string;
  description: string;
  plan: Phase0ReadinessPayload['remediation_plan'];
}> = [
  {
    title: 'Strict internal gate',
    description: STRICT_REMEDIATION.client_delivery_policy,
    plan: STRICT_REMEDIATION,
  },
  {
    title: 'Editor revision loop',
    description:
      'Send flagged sections to editor, re-check, then manager decides.',
    plan: EDITOR_LOOP_REMEDIATION,
  },
  {
    title: 'Rewrite/refund fallback',
    description:
      'Rewrite first; refund only if rewrite is not economically viable.',
    plan: REWRITE_REFUND_REMEDIATION,
  },
];

function blankPayload(): Phase0ReadinessPayload {
  return {
    test_contour: {
      country: 'Italy',
      university_context: '',
      language: 'Italian',
      work_type: 'bachelor thesis',
      sanity_run_size: '20 pages',
      target_full_run_size: '60-70 pages',
      citation_style: 'to be confirmed per order',
    },
    detector_access: {
      plagiarism_checker: 'To be added after next edits and agreement',
      plagiarism_checker_kind: 'post-edit agreement',
      plagiarism_threshold: 'To be set after next edits and agreement',
      ai_detector: 'GPTZero',
      ai_risk_threshold: '< 20%',
      turnitin_ai_access: 'No direct access',
      proxy_detector: 'GPTZero',
      detector_limitations:
        'GPTZero is a proxy signal, not Turnitin AI or an exact university detector.',
      evidence_owner: '',
      evidence_date: new Date().toISOString().slice(0, 10),
    },
    human_minutes_budget: {
      price_band: 'EUR 100-200',
      estimated_ai_generation_cost: '',
      estimated_detector_cost: '',
      estimated_editor_cost: '',
      estimated_total_cost: '',
      human_written_comparison_cost: '',
      manager_setup_budget: '',
      editor_review_budget: '',
      editing_remediation_budget: '',
      detector_rerun_budget: '',
      delivery_prep_budget: '',
      total_human_minutes_budget: '',
      cost_source: '',
      budget_source: '',
    },
    citation_gate_state: {
      provenance_ledger_enabled: 'true',
      citation_verification_enabled: 'false',
      citation_verification_policy: 'mark_only',
      crossref_access: 'CONFIRMED from local machine on 2026-06-30',
      openalex_access: 'CONFIRMED from local machine on 2026-06-30',
      semantic_scholar_access: 'Key present locally, HTTP 403 on 2026-06-30',
      arxiv_access: 'CONFIRMED from local machine on 2026-06-30',
      target_environment_evidence:
        'Local smoke check recorded; production/preprod target environment pending before live delivery.',
      known_blind_spots:
        'GPTZero is only a proxy. Plagiarism checker is pending after next edits and agreement.',
    },
    ownership: {
      manager: '',
      editor: '',
      release_decision_owner: '',
      detector_evidence_owner: '',
    },
    remediation_plan: STRICT_REMEDIATION,
  };
}

function unresolved(value: string) {
  const normalized = value.trim().toLowerCase();
  return (
    normalized.length === 0 ||
    normalized.startsWith('to be ') ||
    normalized.startsWith('pending ') ||
    ['not confirmed', 'not set', 'not selected'].includes(normalized)
  );
}

function hasValue(value: string) {
  return !unresolved(value);
}

function preparePayload(input: Phase0ReadinessPayload) {
  const manager = input.ownership.manager.trim();
  const editor =
    input.ownership.editor.trim() ||
    'Assigned after the sanity-run draft is ready';
  const evidenceOwner =
    input.ownership.detector_evidence_owner.trim() || manager;
  const releaseOwner = input.ownership.release_decision_owner.trim() || manager;

  return {
    ...input,
    detector_access: {
      ...input.detector_access,
      plagiarism_checker:
        input.detector_access.plagiarism_checker ||
        'To be added after next edits and agreement',
      plagiarism_checker_kind:
        input.detector_access.plagiarism_checker_kind || 'post-edit agreement',
      plagiarism_threshold:
        input.detector_access.plagiarism_threshold ||
        'To be set after next edits and agreement',
      ai_detector: 'GPTZero',
      turnitin_ai_access: 'No direct access',
      proxy_detector: 'GPTZero',
      detector_limitations:
        input.detector_access.detector_limitations ||
        'GPTZero is a proxy signal, not Turnitin AI or an exact university detector.',
      evidence_owner: evidenceOwner,
    },
    human_minutes_budget: {
      ...input.human_minutes_budget,
      budget_source:
        input.human_minutes_budget.budget_source ||
        input.human_minutes_budget.cost_source,
    },
    ownership: {
      manager,
      editor,
      release_decision_owner: releaseOwner,
      detector_evidence_owner: evidenceOwner,
    },
    remediation_plan: {
      ...STRICT_REMEDIATION,
      ...input.remediation_plan,
    },
  };
}

function computeCriteria(payload: Phase0ReadinessPayload): Criterion[] {
  const prepared = preparePayload(payload);
  return [
    {
      key: 'context',
      label: 'Контур першого тесту',
      passed: hasValue(prepared.test_contour.university_context),
    },
    {
      key: 'gptzero',
      label: 'GPTZero threshold',
      passed: hasValue(prepared.detector_access.ai_risk_threshold),
    },
    {
      key: 'cost',
      label: 'Собівартість одного прогону',
      passed:
        hasValue(prepared.human_minutes_budget.estimated_total_cost) &&
        hasValue(prepared.human_minutes_budget.cost_source),
    },
    {
      key: 'owner',
      label: 'Відповідальний за RUN-001',
      passed: hasValue(prepared.ownership.manager),
    },
    {
      key: 'remediation',
      label: 'Що робимо, якщо перевірка падає',
      passed:
        hasValue(prepared.remediation_plan.pre_delivery_detector_fail) &&
        hasValue(prepared.remediation_plan.client_delivery_policy),
    },
  ];
}

function fieldClasses() {
  return 'mt-1 w-full rounded border border-gray-600 bg-gray-950 px-3 py-2 text-sm text-white outline-none transition focus:border-primary-500 focus:ring-1 focus:ring-primary-500';
}

function TextField({
  label,
  value,
  onChange,
  multiline = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  placeholder?: string;
}) {
  const common = {
    value,
    placeholder,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange(event.target.value),
  };

  return (
    <label className="block text-sm text-gray-300">
      {label}
      {multiline ? (
        <textarea
          {...common}
          className={`${fieldClasses()} min-h-[92px] resize-y`}
        />
      ) : (
        <input {...common} className={fieldClasses()} />
      )}
    </label>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <h2 className="text-base font-semibold text-white">{title}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

export default function Phase0ReadinessPage() {
  const [payload, setPayload] = useState<Phase0ReadinessPayload>(blankPayload);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [markdown, setMarkdown] = useState('');
  const [artifactPath, setArtifactPath] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const localCriteria = useMemo(() => computeCriteria(payload), [payload]);
  const activeCriteria = criteria.length ? criteria : localCriteria;
  const readyCount = activeCriteria.filter((item) => item.passed).length;
  const isReady = readyCount === activeCriteria.length;

  const updateSection = <SectionName extends keyof Phase0ReadinessPayload>(
    section: SectionName,
    key: keyof Phase0ReadinessPayload[SectionName],
    value: string
  ) => {
    setPayload((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [key]: value,
      },
    }));
    setCriteria([]);
  };

  const loadRecord = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/phase0-readiness', {
        cache: 'no-store',
      });
      if (!response.ok) throw new Error('Failed to load Phase 0 readiness');
      const data = await response.json();
      setPayload(
        preparePayload({ ...blankPayload(), ...(data.payload || {}) })
      );
      setCriteria(data.criteria || []);
      setMarkdown(data.markdown || '');
      setArtifactPath(data.path || '');
    } catch (error) {
      console.error('Failed to load Phase 0 readiness:', error);
      toast.error('Failed to load Phase 0 readiness');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecord();
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      const nextPayload = preparePayload(payload);
      const response = await fetch('/api/admin/phase0-readiness', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nextPayload),
      });
      if (!response.ok) throw new Error('Failed to save Phase 0 readiness');
      const data = await response.json();
      setPayload(data.payload);
      setCriteria(data.criteria || []);
      setMarkdown(data.markdown || '');
      setArtifactPath(data.path || artifactPath);
      toast.success(
        data.status === 'READY FOR PHASE 1 SANITY RUN' ? 'Ready' : 'Saved'
      );
    } catch (error) {
      console.error('Failed to save Phase 0 readiness:', error);
      toast.error('Failed to save Phase 0 readiness');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Phase 0 Quick Setup</h1>
          <p className="mt-1 max-w-3xl text-sm text-gray-400">
            Менеджер заповнює тільки рішення для першого sanity run. GPTZero,
            Turnitin status, plagiarism pending, citation smoke і remediation
            defaults записуються автоматично.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={loadRecord}>
            Reload
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save setup'}
          </Button>
        </div>
      </div>

      <div
        className={`rounded-lg border p-4 ${
          isReady
            ? 'border-green-700 bg-green-950/30'
            : 'border-yellow-700 bg-yellow-950/30'
        }`}
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">
              Sanity-run readiness
            </p>
            <p className="mt-1 text-xl font-semibold text-white">
              {isReady ? 'Ready to create RUN-001' : 'Needs a few inputs'}
            </p>
          </div>
          <div className="rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-200">
            {readyCount} / {activeCriteria.length}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-5">
          {activeCriteria.map((criterion) => (
            <div
              key={criterion.key}
              className="rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm"
            >
              <span
                className={
                  criterion.passed ? 'text-green-200' : 'text-yellow-100'
                }
              >
                {criterion.passed ? 'OK' : 'Needed'}
              </span>
              <p className="mt-1 text-gray-300">{criterion.label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="1. Перший тест">
          <TextField
            label="Університет або реальний контекст замовлення"
            value={payload.test_contour.university_context}
            onChange={(value) =>
              updateSection('test_contour', 'university_context', value)
            }
            placeholder="Напр. Italy / University of Bologna / бакалаврська"
          />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <TextField
              label="Мова"
              value={payload.test_contour.language}
              onChange={(value) =>
                updateSection('test_contour', 'language', value)
              }
            />
            <TextField
              label="Citation style"
              value={payload.test_contour.citation_style}
              onChange={(value) =>
                updateSection('test_contour', 'citation_style', value)
              }
            />
          </div>
        </Card>

        <Card title="2. Детектор">
          <div className="rounded border border-gray-700 bg-gray-900 p-3 text-sm text-gray-300">
            Turnitin AI: no direct access. AI proxy: GPTZero. Plagiarism checker
            буде додано після наступних правок і узгодження.
          </div>
          <TextField
            label="GPTZero pass threshold"
            value={payload.detector_access.ai_risk_threshold}
            onChange={(value) =>
              updateSection('detector_access', 'ai_risk_threshold', value)
            }
            placeholder="Рекомендація: < 20%"
          />
        </Card>

        <Card title="3. Собівартість">
          <TextField
            label="Estimated total cost"
            value={payload.human_minutes_budget.estimated_total_cost}
            onChange={(value) =>
              updateSection(
                'human_minutes_budget',
                'estimated_total_cost',
                value
              )
            }
            placeholder="Напр. EUR 20-40"
          />
          <TextField
            label="Cost source"
            value={payload.human_minutes_budget.cost_source}
            onChange={(value) =>
              updateSection('human_minutes_budget', 'cost_source', value)
            }
            multiline
            placeholder="Напр. token estimate + GPTZero + editor spot-check"
          />
          <TextField
            label="Human-written comparison cost"
            value={payload.human_minutes_budget.human_written_comparison_cost}
            onChange={(value) =>
              updateSection(
                'human_minutes_budget',
                'human_written_comparison_cost',
                value
              )
            }
            placeholder="Напр. EUR 120-180"
          />
        </Card>

        <Card title="4. Хто відповідає">
          <TextField
            label="Owner RUN-001"
            value={payload.ownership.manager}
            onChange={(value) => updateSection('ownership', 'manager', value)}
            placeholder="Ім'я менеджера або ваше ім'я"
          />
          <TextField
            label="Editor / reviewer"
            value={payload.ownership.editor}
            onChange={(value) => updateSection('ownership', 'editor', value)}
            placeholder="Можна залишити default: assigned after draft"
          />
        </Card>
      </div>

      <Card title="5. Якщо перевірка падає">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {REMEDIATION_OPTIONS.map(({ title, description, plan }) => (
            <button
              key={title}
              type="button"
              onClick={() =>
                setPayload((current) => ({
                  ...current,
                  remediation_plan: plan,
                }))
              }
              className="rounded border border-gray-700 bg-gray-900 p-3 text-left text-sm text-gray-300 hover:border-primary-500"
            >
              <span className="font-medium text-white">{title}</span>
              <span className="mt-2 block">{description}</span>
            </button>
          ))}
        </div>
        <p className="text-sm text-gray-400">
          Default для Phase 1: Strict internal gate. Це означає: якщо GPTZero,
          plagiarism або citation evidence падає, роботу не видаємо до правок і
          повторної перевірки.
        </p>
      </Card>

      <section className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-white">
              Canonical record
            </h2>
            <p className="mt-1 text-sm text-gray-400">
              {artifactPath || 'docs/PHASE0_READINESS_RECORD.md'}
            </p>
          </div>
          <Link
            href="/admin/production-cases"
            className="inline-flex h-10 items-center justify-center rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200"
          >
            Open production cases
          </Link>
        </div>
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-gray-300">
            Show generated readiness record
          </summary>
          <pre className="mt-3 max-h-80 overflow-auto rounded border border-gray-700 bg-gray-950 p-4 text-xs text-gray-200">
            {markdown || 'Save setup to generate the canonical record.'}
          </pre>
        </details>
      </section>
    </div>
  );
}
