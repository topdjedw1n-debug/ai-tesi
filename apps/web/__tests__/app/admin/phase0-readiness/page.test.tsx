import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Phase0ReadinessPage from '@/app/admin/phase0-readiness/page';

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}));

const payload = {
  test_contour: {
    country: 'Italy',
    university_context: '',
    language: 'Italian',
    work_type: 'bachelor thesis',
    sanity_run_size: '20 pages',
    target_full_run_size: '60-70 pages after a 20-page sanity run',
    citation_style: 'to be confirmed per order',
  },
  detector_access: {
    plagiarism_checker: '',
    plagiarism_checker_kind: '',
    plagiarism_threshold: '',
    ai_detector: '',
    ai_risk_threshold: '',
    turnitin_ai_access: 'not confirmed',
    proxy_detector: '',
    detector_limitations: '',
    evidence_owner: '',
    evidence_date: '2026-06-30',
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
    crossref_access: 'CONFIRMED from local machine',
    openalex_access: 'CONFIRMED from local machine',
    semantic_scholar_access: 'key present locally, HTTP 403',
    arxiv_access: 'CONFIRMED from local machine',
    target_environment_evidence: '',
    known_blind_spots: 'Semantic Scholar key/access needs correction.',
  },
  ownership: {
    manager: '',
    editor: '',
    release_decision_owner: '',
    detector_evidence_owner: '',
  },
  remediation_plan: {
    pre_delivery_detector_fail: 'Do not deliver. Run remediation.',
    post_delivery_failure: 'Open an editor escalation.',
    max_extra_minutes: 'Track during RUN-001.',
    client_delivery_policy: 'Client receives only manager-approved delivery.',
  },
};

describe('Phase0ReadinessPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          payload,
          criteria: [],
          markdown: '# Phase 0 Readiness Record',
          path: '/repo/docs/PHASE0_READINESS_RECORD.md',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          payload: {
            ...payload,
            test_contour: {
              ...payload.test_contour,
              university_context: 'University of Bologna',
            },
            detector_access: {
              ...payload.detector_access,
              plagiarism_checker: 'To be added after next edits and agreement',
              ai_detector: 'GPTZero',
              ai_risk_threshold: '< 20%',
              turnitin_ai_access: 'No direct access',
              proxy_detector: 'GPTZero',
            },
            human_minutes_budget: {
              ...payload.human_minutes_budget,
              estimated_total_cost: 'EUR 25-40',
              cost_source: 'Token estimate plus GPTZero and editor spot-check.',
            },
            ownership: {
              ...payload.ownership,
              manager: 'Max',
              release_decision_owner: 'Max',
              detector_evidence_owner: 'Max',
            },
          },
          criteria: [
            {
              key: 'context',
              label: 'Контур першого тесту',
              passed: true,
            },
          ],
          markdown: '# Phase 0 Readiness Record\n\n**Status:** NOT READY',
          path: '/repo/docs/PHASE0_READINESS_RECORD.md',
          status: 'NOT READY',
        }),
      });
  });

  it('lets a manager save quick Phase 0 setup without filling the full record', async () => {
    render(<Phase0ReadinessPage />);

    expect(await screen.findByText('Phase 0 Quick Setup')).toBeInTheDocument();

    fireEvent.change(
      screen.getByLabelText(/Університет або реальний контекст замовлення/),
      { target: { value: 'University of Bologna' } }
    );
    fireEvent.change(screen.getByLabelText(/GPTZero pass threshold/), {
      target: { value: '< 20%' },
    });
    fireEvent.change(screen.getByLabelText(/Estimated total cost/), {
      target: { value: 'EUR 25-40' },
    });
    fireEvent.change(screen.getByLabelText(/Cost source/), {
      target: { value: 'Token estimate plus GPTZero and editor spot-check.' },
    });
    fireEvent.change(screen.getByLabelText(/Owner RUN-001/), {
      target: { value: 'Max' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save setup' }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenLastCalledWith(
        '/api/admin/phase0-readiness',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const body = JSON.parse((global.fetch as jest.Mock).mock.calls[1][1].body);
    expect(body.test_contour.university_context).toBe('University of Bologna');
    expect(body.detector_access.ai_detector).toBe('GPTZero');
    expect(body.detector_access.turnitin_ai_access).toBe('No direct access');
    expect(body.detector_access.proxy_detector).toBe('GPTZero');
    expect(body.detector_access.plagiarism_checker).toBe(
      'To be added after next edits and agreement'
    );
    expect(body.human_minutes_budget.estimated_total_cost).toBe('EUR 25-40');
    expect(body.ownership.manager).toBe('Max');
  });
});
