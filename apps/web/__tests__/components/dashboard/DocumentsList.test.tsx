/**
 * Tests for DocumentsList component
 * Tests document list display, loading states, empty states
 */

import { render, screen, waitFor } from '@testing-library/react';
import { DocumentsList } from '@/components/dashboard/DocumentsList';
import { apiClient } from '@/lib/api';

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
  },
  API_ENDPOINTS: {
    DOCUMENTS: {
      LIST: '/api/v1/documents',
    },
  },
}));

// Mock toast
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

// Mock Next.js Link
jest.mock('next/link', () => {
  return ({ children, href }: any) => {
    return <a href={href}>{children}</a>;
  };
});

describe('DocumentsList Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading skeleton with Recent Documents header', () => {
      (apiClient.get as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<DocumentsList />);

      // Component shows "Recent Documents" header, not "loading" text
      expect(screen.getByText('Recent Documents')).toBeInTheDocument();
      // Check for skeleton elements
      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Success State', () => {
    it('displays documents list', async () => {
      const mockDocuments = [
        {
          id: 1,
          title: 'AI in Education',
          topic: 'Machine Learning',
          status: 'completed',
          created_at: '2025-12-01T10:00:00Z',
          updated_at: '2025-12-01T11:00:00Z',
          word_count: 2500,
        },
        {
          id: 2,
          title: 'Climate Change',
          topic: 'Environmental Science',
          status: 'draft',
          created_at: '2025-12-01T12:00:00Z',
          updated_at: '2025-12-01T12:00:00Z',
          word_count: 0,
        },
      ];

      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: mockDocuments,
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText('AI in Education')).toBeInTheDocument();
      });

      expect(screen.getByText('Climate Change')).toBeInTheDocument();
      // Word count uses toLocaleString() - check for formatted number
      expect(screen.getByText('2,500 words')).toBeInTheDocument();
    });

    it('displays document statuses correctly', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [
          {
            id: 1,
            title: 'Doc 1',
            status: 'draft',
            created_at: '2025-12-01T10:00:00Z',
          },
          {
            id: 2,
            title: 'Doc 2',
            status: 'completed',
            created_at: '2025-12-01T10:00:00Z',
          },
        ],
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText('Draft')).toBeInTheDocument();
      });

      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    it('limits display to 5 documents', async () => {
      const mockDocuments = Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        title: `Document ${i + 1}`,
        status: 'draft',
        created_at: '2025-12-01T10:00:00Z',
      }));

      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: mockDocuments,
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText('Document 1')).toBeInTheDocument();
      });

      // Should show only first 5
      expect(screen.getByText('Document 5')).toBeInTheDocument();
      expect(screen.queryByText('Document 6')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no documents', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [],
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText(/no documents/i)).toBeInTheDocument();
      });
    });

    it('shows empty state with undefined documents', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({});

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText(/no documents/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('handles API errors gracefully', async () => {
      (apiClient.get as jest.Mock).mockRejectedValue(new Error('API Error'));

      render(<DocumentsList />);

      // Should show empty state after error
      await waitFor(() => {
        expect(screen.getByText(/no documents/i)).toBeInTheDocument();
      });
    });
  });

  describe('API Integration', () => {
    it('calls correct API endpoint', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [],
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/api/v1/documents');
      });
    });

    it('fetches documents on mount', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [
          {
            id: 1,
            title: 'Test Doc',
            created_at: '2025-12-01T10:00:00Z',
          },
        ],
      });

      render(<DocumentsList />);

      expect(apiClient.get).toHaveBeenCalled();

      await waitFor(() => {
        expect(screen.getByText('Test Doc')).toBeInTheDocument();
      });
    });
  });

  describe('Document Details', () => {
    it('displays word count when available', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [
          {
            id: 1,
            title: 'Test Doc',
            word_count: 2500,
            created_at: '2025-12-01T10:00:00Z',
          },
        ],
      });

      render(<DocumentsList />);

      await waitFor(() => {
        // Word count uses toLocaleString() - formatted as "2,500"
        expect(screen.getByText('2,500 words')).toBeInTheDocument();
      });
    });

    it('handles missing title gracefully', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [
          {
            id: 1,
            created_at: '2025-12-01T10:00:00Z',
          },
        ],
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText('Document 1')).toBeInTheDocument();
      });
    });

    it('defaults missing status to draft', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [
          {
            id: 1,
            title: 'Test Doc',
            created_at: '2025-12-01T10:00:00Z',
          },
        ],
      });

      render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText('Draft')).toBeInTheDocument();
      });
    });
  });

  describe('UI Elements', () => {
    it('renders view all documents link', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        documents: [
          {
            id: 1,
            title: 'Test',
            created_at: '2025-12-01T10:00:00Z',
          },
        ],
      });

      const { container } = render(<DocumentsList />);

      await waitFor(() => {
        expect(screen.getByText('Test')).toBeInTheDocument();
      });

      const links = container.querySelectorAll('a[href*="/dashboard/documents"]');
      expect(links.length).toBeGreaterThan(0);
    });
  });
});
