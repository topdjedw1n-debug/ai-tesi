import { promises as fs } from 'fs';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

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

const REPO_ROOT = path.resolve(process.cwd(), '..', '..');
const READINESS_PATH = path.join(
  REPO_ROOT,
  'docs',
  'PHASE0_READINESS_RECORD.md'
);
const API_ENV_PATH = path.join(REPO_ROOT, 'apps', 'api', '.env');

function forbiddenInProduction() {
  return (
    process.env.NODE_ENV === 'production' &&
    process.env.PHASE0_READINESS_EDITOR_ENABLED !== 'true'
  );
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function boolish(value: string | undefined, fallback: boolean) {
  if (!value) return fallback ? 'true' : 'false';
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())
    ? 'true'
    : 'false';
}

async function readApiEnv() {
  try {
    const raw = await fs.readFile(API_ENV_PATH, 'utf8');
    return raw.split('\n').reduce<Record<string, string>>((acc, line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('='))
        return acc;
      const [key, ...rest] = trimmed.split('=');
      acc[key.trim()] = rest
        .join('=')
        .trim()
        .replace(/^["']|["']$/g, '');
      return acc;
    }, {});
  } catch {
    return {};
  }
}

function extractLine(markdown: string, label: string, fallback: string) {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = markdown.match(
    new RegExp(`^- ${escaped}:[^\\S\\r\\n]*([^\\r\\n]*)$`, 'm')
  );
  return match?.[1]?.trim() || fallback;
}

function extractKnownBlindSpots(markdown: string, fallback: string) {
  const section = markdown.match(
    /## Citation Gate State\n([\s\S]*?)(\n## |$)/m
  );
  if (!section) return fallback;

  const lines = section[1].split('\n');
  const start = lines.findIndex(
    (line) => line.trim() === '- Known blind spots:'
  );
  if (start === -1) return fallback;

  const blindSpots: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith('  - ')) {
      blindSpots.push(line.replace(/^  - /, '').trim());
      continue;
    }
    if (line.trim()) break;
  }

  return blindSpots.length ? blindSpots.join('\n') : fallback;
}

function normalizeCountryContext(value: string) {
  if (value.toLowerCase().includes('italy')) return 'Italy';
  return value;
}

function stripMarkdownCode(value: string) {
  return value.replace(/^`|`$/g, '');
}

function firstMarkdownCodeToken(value: string) {
  const match = value.match(/^`([^`]+)`/);
  return match?.[1] || stripMarkdownCode(value);
}

function isUnresolvedValue(value: string) {
  const normalized = value.trim().toLowerCase();
  const unresolvedPrefixes = ['to be ', 'needs ', 'pending '];
  return (
    normalized.length === 0 ||
    unresolvedPrefixes.some((prefix) => normalized.startsWith(prefix)) ||
    [
      'not confirmed',
      'not set',
      'not selected',
      'to be confirmed per order',
    ].includes(normalized)
  );
}

function fallbackIfUnresolved(value: string, fallback: string) {
  return isUnresolvedValue(value) ? fallback : value;
}

function normalizePayload(value: unknown, fallback: Phase0ReadinessPayload) {
  if (!value || typeof value !== 'object') return fallback;
  const payload = value as Partial<Phase0ReadinessPayload>;
  return {
    test_contour: { ...fallback.test_contour, ...payload.test_contour },
    detector_access: {
      ...fallback.detector_access,
      ...payload.detector_access,
    },
    human_minutes_budget: {
      ...fallback.human_minutes_budget,
      ...payload.human_minutes_budget,
    },
    citation_gate_state: {
      ...fallback.citation_gate_state,
      ...payload.citation_gate_state,
    },
    ownership: { ...fallback.ownership, ...payload.ownership },
    remediation_plan: {
      ...fallback.remediation_plan,
      ...payload.remediation_plan,
    },
  };
}

async function defaultPayload() {
  const [env, markdown] = await Promise.all([
    readApiEnv(),
    fs.readFile(READINESS_PATH, 'utf8').catch(() => ''),
  ]);

  const provenance = boolish(env.PROVENANCE_LEDGER_ENABLED, true);
  const citationEnabled = boolish(env.CITATION_VERIFICATION_ENABLED, false);
  const citationPolicy = env.CITATION_VERIFICATION_POLICY || 'mark_only';
  const semanticKeyPresent = Boolean(env.SEMANTIC_SCHOLAR_API_KEY);
  const countryContext = extractLine(
    markdown,
    'Country / university context',
    'Italy'
  );

  return {
    test_contour: {
      country: normalizeCountryContext(countryContext),
      university_context: extractLine(markdown, 'Exact university/context', ''),
      language: extractLine(markdown, 'Language', 'Italian'),
      work_type: extractLine(markdown, 'Work type', 'bachelor thesis'),
      sanity_run_size: extractLine(markdown, 'Sanity-run size', '20 pages'),
      target_full_run_size: extractLine(
        markdown,
        'Target full-run size',
        '60-70 pages after a 20-page sanity run'
      ),
      citation_style: extractLine(
        markdown,
        'Citation style',
        'to be confirmed per order'
      ),
    },
    detector_access: {
      plagiarism_checker: extractLine(
        markdown,
        'Plagiarism checker',
        'To be added after next edits and agreement'
      ),
      plagiarism_checker_kind: extractLine(
        markdown,
        'Plagiarism checker type',
        ''
      ),
      plagiarism_threshold: extractLine(
        markdown,
        'Plagiarism threshold',
        'To be set after next edits and agreement'
      ),
      ai_detector: fallbackIfUnresolved(
        extractLine(markdown, 'AI detector', ''),
        'GPTZero'
      ),
      ai_risk_threshold: extractLine(markdown, 'AI-risk threshold', ''),
      turnitin_ai_access: fallbackIfUnresolved(
        extractLine(markdown, 'Turnitin AI access', ''),
        'No direct access'
      ),
      proxy_detector: fallbackIfUnresolved(
        extractLine(markdown, 'Proxy detector, if Turnitin is unavailable', ''),
        'GPTZero'
      ),
      detector_limitations: fallbackIfUnresolved(
        extractLine(markdown, 'Detector limitations/proxy status', ''),
        'GPTZero is a proxy signal, not Turnitin AI or an exact university detector.'
      ),
      evidence_owner: extractLine(markdown, 'Evidence owner', ''),
      evidence_date: extractLine(markdown, 'Evidence date', todayIsoDate()),
    },
    human_minutes_budget: {
      price_band: extractLine(markdown, 'Price band', 'EUR 100-200'),
      estimated_ai_generation_cost: extractLine(
        markdown,
        'Estimated AI generation cost',
        ''
      ),
      estimated_detector_cost: extractLine(
        markdown,
        'Estimated detector/proxy cost',
        ''
      ),
      estimated_editor_cost: extractLine(markdown, 'Estimated editor cost', ''),
      estimated_total_cost: extractLine(markdown, 'Estimated total cost', ''),
      human_written_comparison_cost: extractLine(
        markdown,
        'Human-written comparison cost',
        ''
      ),
      manager_setup_budget: extractLine(markdown, 'Manager setup budget', ''),
      editor_review_budget: extractLine(markdown, 'Editor review budget', ''),
      editing_remediation_budget: extractLine(
        markdown,
        'Editing/remediation budget',
        ''
      ),
      detector_rerun_budget: extractLine(markdown, 'Detector/rerun budget', ''),
      delivery_prep_budget: extractLine(markdown, 'Delivery prep budget', ''),
      total_human_minutes_budget: extractLine(
        markdown,
        'Total human-minutes budget',
        ''
      ),
      cost_source: extractLine(markdown, 'Cost source', ''),
      budget_source: extractLine(markdown, 'Budget source', ''),
    },
    citation_gate_state: {
      provenance_ledger_enabled: extractLine(
        markdown,
        '`PROVENANCE_LEDGER_ENABLED`',
        provenance
      ),
      citation_verification_enabled: extractLine(
        markdown,
        '`CITATION_VERIFICATION_ENABLED`',
        citationEnabled
      ),
      citation_verification_policy: firstMarkdownCodeToken(
        extractLine(markdown, '`CITATION_VERIFICATION_POLICY`', citationPolicy)
      ),
      crossref_access: extractLine(
        markdown,
        'Crossref access',
        'not confirmed'
      ),
      openalex_access: extractLine(
        markdown,
        'OpenAlex access',
        'not confirmed'
      ),
      semantic_scholar_access: extractLine(
        markdown,
        'Semantic Scholar access/key',
        semanticKeyPresent
          ? 'key present locally, target access not confirmed'
          : 'not confirmed'
      ),
      arxiv_access: extractLine(markdown, 'arXiv access', 'not confirmed'),
      target_environment_evidence: extractLine(
        markdown,
        'Target environment evidence',
        ''
      ),
      known_blind_spots: extractKnownBlindSpots(markdown, ''),
    },
    ownership: {
      manager: extractLine(markdown, 'Manager for RUN-001', ''),
      editor: extractLine(markdown, 'Editor for RUN-001', ''),
      release_decision_owner: extractLine(
        markdown,
        'Release decision owner',
        ''
      ),
      detector_evidence_owner: extractLine(
        markdown,
        'Detector evidence owner',
        ''
      ),
    },
    remediation_plan: {
      pre_delivery_detector_fail: extractLine(
        markdown,
        'If detector fails before delivery',
        ''
      ),
      post_delivery_failure: extractLine(
        markdown,
        'If client/university rejects or returns work',
        ''
      ),
      max_extra_minutes: extractLine(
        markdown,
        'Maximum extra human minutes',
        ''
      ),
      client_delivery_policy: extractLine(
        markdown,
        'Client delivery/refund policy',
        ''
      ),
    },
  } satisfies Phase0ReadinessPayload;
}

function hasValue(value: string) {
  return !isUnresolvedValue(value);
}

function computeCriteria(payload: Phase0ReadinessPayload): Criterion[] {
  return [
    {
      key: 'context',
      label: 'Контур першого тесту',
      passed: hasValue(payload.test_contour.university_context),
    },
    {
      key: 'gptzero',
      label: 'GPTZero threshold',
      passed: hasValue(payload.detector_access.ai_risk_threshold),
    },
    {
      key: 'cost',
      label: 'Собівартість одного прогону',
      passed:
        hasValue(payload.human_minutes_budget.estimated_total_cost) &&
        hasValue(payload.human_minutes_budget.cost_source),
    },
    {
      key: 'owner',
      label: 'Відповідальний за RUN-001',
      passed: hasValue(payload.ownership.manager),
    },
    {
      key: 'remediation',
      label: 'Що робимо, якщо перевірка падає',
      passed:
        hasValue(payload.remediation_plan.pre_delivery_detector_fail) &&
        hasValue(payload.remediation_plan.client_delivery_policy),
    },
  ];
}

function renderList(value: string) {
  const lines = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) return '- Known blind spots:\n  - NOT SET';

  return [
    '- Known blind spots:',
    ...lines.map((line) => `  - ${line.replace(/^- /, '')}`),
  ].join('\n');
}

function markdownFromPayload(payload: Phase0ReadinessPayload) {
  const criteria = computeCriteria(payload);
  const isReady = criteria.every((criterion) => criterion.passed);
  const statusText = isReady ? 'READY FOR PHASE 1 SANITY RUN' : 'NOT READY';
  const checkbox = (criterion: Criterion) =>
    `- [${criterion.passed ? 'x' : ' '}] ${criterion.label}`;

  return `# Phase 0 Readiness Record

**Status:** ${statusText}
**Last updated:** ${todayIsoDate()}
**Purpose:** This is the canonical readiness artifact for starting Phase 1 proof runs. Do not mark Phase 0 complete until every required field below has a concrete value and evidence source.
**Implementation note:** The application supports structured manual detector
proxy evidence on production case release gates. Phase 0 remains operationally
not ready until detector access, thresholds, cost baseline, owners, and
remediation are filled from real operating decisions. Human minutes remain useful
for Phase 1 measurement, but the current operating priority is cost of production
versus a fully human-written workflow.

## Test Contour

- Country / university context: ${payload.test_contour.country}
- Exact university/context: ${payload.test_contour.university_context}
- Language: ${payload.test_contour.language}
- Work type: ${payload.test_contour.work_type}
- Sanity-run size: ${payload.test_contour.sanity_run_size}
- Target full-run size: ${payload.test_contour.target_full_run_size}
- Citation style: ${payload.test_contour.citation_style}

## Detector Access

- Plagiarism checker: ${payload.detector_access.plagiarism_checker || 'NOT CONFIRMED'}
- Plagiarism checker type: ${payload.detector_access.plagiarism_checker_kind || 'NOT SET'}
- Plagiarism threshold: ${payload.detector_access.plagiarism_threshold || 'NOT SET'}
- AI detector: ${payload.detector_access.ai_detector || 'NOT CONFIRMED'}
- AI-risk threshold: ${payload.detector_access.ai_risk_threshold || 'NOT SET'}
- Turnitin AI access: ${payload.detector_access.turnitin_ai_access || 'NOT CONFIRMED'}
- Proxy detector, if Turnitin is unavailable: ${payload.detector_access.proxy_detector || 'NOT SELECTED'}
- Detector limitations/proxy status: ${payload.detector_access.detector_limitations || 'NOT SET'}
- Planned proxy recording surface: production case detector-result release gate
  endpoint for \`plagiarism_proxy\` and \`ai_detection_proxy\`
- Evidence owner: ${payload.detector_access.evidence_owner || payload.ownership.detector_evidence_owner || 'NOT SET'}
- Evidence date: ${payload.detector_access.evidence_date || 'NOT SET'}

## Economics Baseline

- Price band: ${payload.human_minutes_budget.price_band}
- Estimated AI generation cost: ${payload.human_minutes_budget.estimated_ai_generation_cost || 'NOT SET'}
- Estimated detector/proxy cost: ${payload.human_minutes_budget.estimated_detector_cost || 'NOT SET'}
- Estimated editor cost: ${payload.human_minutes_budget.estimated_editor_cost || 'NOT SET'}
- Estimated total cost: ${payload.human_minutes_budget.estimated_total_cost || 'NOT SET'}
- Human-written comparison cost: ${payload.human_minutes_budget.human_written_comparison_cost || 'NOT SET'}
- Cost source: ${payload.human_minutes_budget.cost_source || 'NOT SET'}
- Human-minutes status: optional for current Phase 0; record during Phase 1 if available
- Manager setup budget: ${payload.human_minutes_budget.manager_setup_budget || 'NOT SET'}
- Editor review budget: ${payload.human_minutes_budget.editor_review_budget || 'NOT SET'}
- Editing/remediation budget: ${payload.human_minutes_budget.editing_remediation_budget || 'NOT SET'}
- Detector/rerun budget: ${payload.human_minutes_budget.detector_rerun_budget || 'NOT SET'}
- Delivery prep budget: ${payload.human_minutes_budget.delivery_prep_budget || 'NOT SET'}
- Total human-minutes budget: ${payload.human_minutes_budget.total_human_minutes_budget || 'NOT SET'}
- Budget source: ${payload.human_minutes_budget.budget_source || payload.human_minutes_budget.cost_source || 'NOT SET'}

## Citation Gate State

- \`PROVENANCE_LEDGER_ENABLED\`: ${payload.citation_gate_state.provenance_ledger_enabled}
- \`CITATION_VERIFICATION_ENABLED\`: ${payload.citation_gate_state.citation_verification_enabled}
- \`CITATION_VERIFICATION_POLICY\`: \`${payload.citation_gate_state.citation_verification_policy}\`
- Crossref access: ${payload.citation_gate_state.crossref_access || 'NOT CONFIRMED'}
- OpenAlex access: ${payload.citation_gate_state.openalex_access || 'NOT CONFIRMED'}
- Semantic Scholar access/key: ${payload.citation_gate_state.semantic_scholar_access || 'NOT CONFIRMED'}
- arXiv access: ${payload.citation_gate_state.arxiv_access || 'NOT CONFIRMED'}
- Target environment evidence: ${payload.citation_gate_state.target_environment_evidence || 'NOT SET'}
${renderList(payload.citation_gate_state.known_blind_spots)}

## People And Release Ownership

- Manager for RUN-001: ${payload.ownership.manager || 'NOT SET'}
- Editor for RUN-001: ${payload.ownership.editor || 'NOT SET'}
- Release decision owner: ${payload.ownership.release_decision_owner || 'NOT SET'}
- Detector evidence owner: ${payload.ownership.detector_evidence_owner || payload.detector_access.evidence_owner || 'NOT SET'}
- Ownership note: manager creates and tracks the case; editor edits the flagged content; release owner decides whether delivery is allowed; detector evidence owner runs GPTZero/plagiarism checks and records the numbers.

## Remediation Plan

- If detector fails before delivery: ${payload.remediation_plan.pre_delivery_detector_fail || 'NOT SET'}
- If client/university rejects or returns work: ${payload.remediation_plan.post_delivery_failure || 'NOT SET'}
- Maximum extra human minutes: ${payload.remediation_plan.max_extra_minutes || 'NOT SET'}
- Client delivery/refund policy: ${payload.remediation_plan.client_delivery_policy || 'NOT SET'}

## Phase 1 Start Criteria

Phase 1 may start only when all items are true:

${criteria.map(checkbox).join('\n')}

## Stop Condition

If any required detector or citation provider is unavailable, record the proxy and limitation here before running Phase 1. If no credible proxy exists, do not treat Phase 1 detector pass/fail as valid evidence.
`;
}

export async function GET() {
  if (forbiddenInProduction()) {
    return NextResponse.json(
      { error: 'Phase 0 readiness editor is disabled in production.' },
      { status: 403 }
    );
  }

  const payload = await defaultPayload();
  const markdown = await fs.readFile(READINESS_PATH, 'utf8').catch(() => '');
  return NextResponse.json({
    payload,
    criteria: computeCriteria(payload),
    markdown,
    path: READINESS_PATH,
  });
}

export async function PUT(request: NextRequest) {
  if (forbiddenInProduction()) {
    return NextResponse.json(
      { error: 'Phase 0 readiness editor is disabled in production.' },
      { status: 403 }
    );
  }

  const fallback = await defaultPayload();
  const payload = normalizePayload(await request.json(), fallback);
  const criteria = computeCriteria(payload);
  const markdown = markdownFromPayload(payload);
  await fs.writeFile(READINESS_PATH, markdown, 'utf8');

  return NextResponse.json({
    payload,
    criteria,
    markdown,
    path: READINESS_PATH,
    status: criteria.every((criterion) => criterion.passed)
      ? 'READY FOR PHASE 1 SANITY RUN'
      : 'NOT READY',
  });
}
