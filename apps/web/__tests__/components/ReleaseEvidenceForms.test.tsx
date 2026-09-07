import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReleaseEvidenceForms } from '@/components/production/ReleaseEvidenceForms';
import { adminApiClient, ReleaseGate } from '@/lib/api/admin';

jest.mock('@/lib/api/admin', () => ({
  adminApiClient: {
    listDetectorReports: jest.fn(),
    uploadDetectorReport: jest.fn(),
    recordDetectorResult: jest.fn(),
    recordContentReview: jest.fn(),
    downloadDetectorReport: jest.fn(),
  },
}));
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}));

const fingerprint = 'a'.repeat(64);
const report = {
  id: 8,
  filename: 'Compilatio.pdf',
  artifact_fingerprint_sha256: fingerprint,
};
const saved = jest.fn().mockResolvedValue(undefined);

function renderForms(gates: ReleaseGate[] = []) {
  return render(
    <ReleaseEvidenceForms
      caseId={4}
      fingerprint={fingerprint}
      gates={gates}
      onSaved={saved}
    />
  );
}

describe('Exact DOCX evidence forms', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (adminApiClient.listDetectorReports as jest.Mock).mockResolvedValue([
      report,
    ]);
    (adminApiClient.recordDetectorResult as jest.Mock).mockResolvedValue({
      status: 'passed',
    });
    (adminApiClient.recordContentReview as jest.Mock).mockResolvedValue({
      status: 'passed',
    });
  });

  it('requires report selection and an explicit exact-file acknowledgement', async () => {
    renderForms();
    const form = screen.getByRole('form', { name: 'Показник AI' });
    await within(form).findByRole('option', { name: report.filename });
    fireEvent.change(within(form).getByLabelText('Результат, %'), {
      target: { value: '10' },
    });
    fireEvent.change(
      within(form).getByLabelText('Збережений звіт Compilatio'),
      { target: { value: '8' } }
    );
    expect(
      within(form).getByRole('button', { name: 'Зберегти результат' })
    ).toBeDisabled();
    fireEvent.click(within(form).getByLabelText(/Звіт і відсоток стосуються/));
    fireEvent.click(
      within(form).getByRole('button', { name: 'Зберегти результат' })
    );
    await waitFor(() =>
      expect(adminApiClient.recordDetectorResult).toHaveBeenCalledWith(
        4,
        'ai_detection_proxy',
        expect.objectContaining({
          result_percent: 10,
          artifact_format: 'docx',
          artifact_fingerprint_sha256: fingerprint,
          report_id: 8,
          report_matches_artifact: true,
        })
      )
    );
    expect(saved).toHaveBeenCalledTimes(1);
  });

  it('explains over-threshold results and records the actual value without manual acceptance', async () => {
    (adminApiClient.recordDetectorResult as jest.Mock).mockResolvedValue({
      status: 'failed',
    });
    renderForms();
    const form = screen.getByRole('form', {
      name: 'Збіги тексту (similarity)',
    });
    await within(form).findByRole('option', { name: report.filename });
    fireEvent.change(within(form).getByLabelText('Результат, %'), {
      target: { value: '22' },
    });
    expect(within(form).getByText(/Понад 10%/)).toBeInTheDocument();
    expect(
      within(form).queryByRole('option', { name: /passed|прийняти/i })
    ).not.toBeInTheDocument();
    fireEvent.change(
      within(form).getByLabelText('Збережений звіт Compilatio'),
      { target: { value: '8' } }
    );
    fireEvent.click(within(form).getByLabelText(/Звіт і відсоток стосуються/));
    fireEvent.click(
      within(form).getByRole('button', { name: 'Зберегти результат' })
    );
    await waitFor(() =>
      expect(adminApiClient.recordDetectorResult).toHaveBeenCalledWith(
        4,
        'plagiarism_proxy',
        expect.objectContaining({ result_percent: 22 })
      )
    );
  });

  it('keeps a stale form bound to its original DOCX and displays the server conflict', async () => {
    (adminApiClient.recordDetectorResult as jest.Mock).mockRejectedValue(
      new Error('DOCX змінився. Перевірте новий файл.')
    );
    renderForms();
    const form = screen.getByRole('form', { name: 'Показник AI' });
    await within(form).findByRole('option', { name: report.filename });
    fireEvent.change(within(form).getByLabelText('Результат, %'), {
      target: { value: '5' },
    });
    fireEvent.change(
      within(form).getByLabelText('Збережений звіт Compilatio'),
      { target: { value: '8' } }
    );
    fireEvent.click(within(form).getByLabelText(/Звіт і відсоток стосуються/));
    fireEvent.submit(form);
    expect(await within(form).findByRole('alert')).toHaveTextContent(
      'DOCX змінився'
    );
    expect(adminApiClient.recordDetectorResult).toHaveBeenCalledWith(
      4,
      'ai_detection_proxy',
      expect.objectContaining({ artifact_fingerprint_sha256: fingerprint })
    );
    expect(saved).not.toHaveBeenCalled();
  });

  it('uploads the selected file with its DOCX version and offers the saved report', async () => {
    (adminApiClient.listDetectorReports as jest.Mock).mockResolvedValue([]);
    (adminApiClient.uploadDetectorReport as jest.Mock).mockResolvedValue(
      report
    );
    renderForms();
    const file = new File(['%PDF-report'], 'Compilatio.pdf', {
      type: 'application/pdf',
    });
    const user = userEvent.setup();
    await user.upload(screen.getByLabelText(/Файл звіту/), file);
    const submit = screen.getByRole('button', { name: 'Прикріпити звіт' });
    expect(submit).toBeEnabled();
    // jsdom does not update native required-file validity for user-event's FileList.
    // The real browser check covers native submission; this checks the upload payload.
    fireEvent.submit(submit.closest('form')!);
    await waitFor(() =>
      expect(adminApiClient.uploadDetectorReport).toHaveBeenCalledWith(
        4,
        fingerprint,
        file
      )
    );
    expect(
      await screen.findAllByRole('option', { name: report.filename })
    ).toHaveLength(2);
  });

  it('does not pre-accept content and records an explicit no-rewrite review', async () => {
    renderForms();
    const form = screen.getByRole('form', { name: 'Огляд змісту' });
    expect(
      within(form).getByRole('button', { name: 'Зберегти огляд' })
    ).toBeDisabled();
    fireEvent.change(within(form).getByLabelText('Рішення щодо змісту'), {
      target: { value: 'accepted' },
    });
    expect(within(form).getByRole('button', { name: 'Зберегти огляд' })).toBeDisabled();
    fireEvent.change(within(form).getByLabelText('Фактична кількість сторінок у DOCX'), { target: { value: '18' } });
    fireEvent.click(
      within(form).getByRole('button', { name: 'Зберегти огляд' })
    );
    await waitFor(() =>
      expect(adminApiClient.recordContentReview).toHaveBeenCalledWith(4, {
        artifact_fingerprint_sha256: fingerprint,
        decision: 'accepted',
        reviewed_page_count: 18,
        reason: '',
      })
    );
  });

  it('keeps confirmed rewriting visibly failed without another acceptance control', async () => {
    renderForms([
      {
        gate_key: 'editorial_review',
        status: 'failed',
        summary: 'Потрібне переписування.',
        evidence: { decision: 'rewritten' },
      } as ReleaseGate,
    ]);
    const form = screen.getByRole('form', { name: 'Огляд змісту' });
    expect(within(form).getByRole('alert')).toHaveTextContent(
      'не можна прийняти'
    );
    expect(within(form).queryByRole('combobox')).not.toBeInTheDocument();
    expect(
      within(form).queryByRole('button', { name: 'Зберегти огляд' })
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(adminApiClient.listDetectorReports).toHaveBeenCalled()
    );
  });
});
