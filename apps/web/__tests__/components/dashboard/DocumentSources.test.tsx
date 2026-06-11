/**
 * Tests for DocumentSources component (sources certificate)
 * Covers the three verification statuses, summary banner, DOI links,
 * empty/error states. API is mocked.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { DocumentSources } from '@/components/dashboard/DocumentSources';
import { apiClient } from '@/lib/api';

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
  },
  API_ENDPOINTS: {
    DOCUMENTS: {
      PROVENANCE: (id: number) => `/api/v1/documents/${id}/provenance`,
    },
  },
}));

const verificationSummaryEvent = (sources: any[], overrides: any = {}) => ({
  id: 2,
  stage: 'verification',
  event_type: 'verification_summary',
  payload: {
    total: sources.length,
    counts: {},
    policy: 'mark_only',
    not_found_titles: [],
    providers: ['crossref', 'openalex'],
    sources,
    ...overrides,
  },
  created_at: '2026-06-11T10:00:00Z',
});

const THREE_STATUS_SOURCES = [
  {
    title: 'Attention Is All You Need',
    authors: ['Ashish Vaswani', 'Noam Shazeer'],
    year: 2017,
    doi: '10.5555/attention',
    status: 'verified',
  },
  {
    title: 'Phantom Paper',
    authors: ['John Doe'],
    year: 2020,
    doi: null,
    status: 'not_found',
  },
  {
    title: 'Flaky Provider Paper',
    authors: [],
    year: 2021,
    doi: '10.1234/flaky',
    status: 'failed', // unresolvable
  },
];

const provenanceResponse = (events: any[]) => ({
  document_id: 42,
  total: events.length,
  events,
});

describe('DocumentSources Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows skeleton with Sources header while loading', () => {
      (apiClient.get as jest.Mock).mockImplementation(
        () => new Promise(() => {})
      );

      render(<DocumentSources documentId={42} />);

      expect(screen.getByText('Sources')).toBeInTheDocument();
      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Verification Statuses', () => {
    it('renders verified, not_found and unresolvable sources with their badges', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(
        provenanceResponse([verificationSummaryEvent(THREE_STATUS_SOURCES)])
      );

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
      });

      // Titles
      expect(screen.getByText('Phantom Paper')).toBeInTheDocument();
      expect(screen.getByText('Flaky Provider Paper')).toBeInTheDocument();

      // Status badges: verified ✓ / not_found ✗ / unresolvable ?
      expect(screen.getByText('Verified')).toBeInTheDocument();
      expect(screen.getByText('Not found')).toBeInTheDocument();
      expect(screen.getByText('Unverifiable')).toBeInTheDocument();
    });

    it('renders authors and year for a source', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(
        provenanceResponse([verificationSummaryEvent(THREE_STATUS_SOURCES)])
      );

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(
          screen.getByText('Ashish Vaswani, Noam Shazeer · 2017')
        ).toBeInTheDocument();
      });

      // Source without authors still shows the year
      expect(screen.getByText('2021')).toBeInTheDocument();
    });

    it('renders clickable DOI links', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(
        provenanceResponse([verificationSummaryEvent(THREE_STATUS_SOURCES)])
      );

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(
          screen.getByRole('link', { name: '10.5555/attention' })
        ).toBeInTheDocument();
      });

      const link = screen.getByRole('link', { name: '10.5555/attention' });
      expect(link).toHaveAttribute('href', 'https://doi.org/10.5555/attention');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');

      // DOI-less source has no link
      expect(
        screen.queryByRole('link', { name: 'Phantom Paper' })
      ).not.toBeInTheDocument();
    });
  });

  describe('Summary Banner', () => {
    it('shows verified count and providers', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(
        provenanceResponse([verificationSummaryEvent(THREE_STATUS_SOURCES)])
      );

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(screen.getByTestId('sources-banner')).toHaveTextContent(
          '1/3 sources verified via Crossref, OpenAlex'
        );
      });

      // Partially verified -> warning styling
      expect(screen.getByTestId('sources-banner')).toHaveClass('bg-amber-50');
    });

    it('uses success styling when all sources are verified', async () => {
      const allVerified = THREE_STATUS_SOURCES.map((s) => ({
        ...s,
        status: 'verified',
      }));
      (apiClient.get as jest.Mock).mockResolvedValue(
        provenanceResponse([verificationSummaryEvent(allVerified)])
      );

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(screen.getByTestId('sources-banner')).toHaveTextContent(
          '3/3 sources verified via Crossref, OpenAlex'
        );
      });

      expect(screen.getByTestId('sources-banner')).toHaveClass('bg-green-50');
    });
  });

  describe('Fallback Without Verification', () => {
    it('falls back to rag_retrieved sources with Pending status', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(
        provenanceResponse([
          {
            id: 1,
            stage: 'retrieval',
            event_type: 'rag_retrieved',
            payload: {
              section_index: 1,
              section_title: 'Introduction',
              sources_used: 1,
              sources: [
                {
                  title: 'Unchecked Paper',
                  doi: '10.9/unchecked',
                  year: 2022,
                  verification_status: 'unverified',
                },
              ],
            },
            created_at: '2026-06-11T10:00:00Z',
          },
        ])
      );

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(screen.getByText('Unchecked Paper')).toBeInTheDocument();
      });

      expect(screen.getByText('Pending')).toBeInTheDocument();
    });
  });

  describe('Empty and Error States', () => {
    it('renders nothing when there are no provenance events', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(provenanceResponse([]));

      const { container } = render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });
    });

    it('renders nothing on API error', async () => {
      const consoleSpy = jest
        .spyOn(console, 'error')
        .mockImplementation(() => {});
      (apiClient.get as jest.Mock).mockRejectedValue(new Error('403'));

      const { container } = render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });

      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('API Integration', () => {
    it('calls the provenance endpoint for the document', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(provenanceResponse([]));

      render(<DocumentSources documentId={42} />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith(
          '/api/v1/documents/42/provenance'
        );
      });
    });
  });
});
