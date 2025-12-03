/**
 * Tests for StatsOverview component
 * Tests stats display, loading states, error handling
 */

import { render, screen, waitFor } from '@testing-library/react';
import { StatsOverview } from '@/components/dashboard/StatsOverview';
import { apiClient } from '@/lib/api';

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
  },
  API_ENDPOINTS: {
    DOCUMENTS: {
      STATS: '/api/v1/documents/stats',
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

describe('StatsOverview Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading skeleton while fetching stats', () => {
      // Mock slow API response
      (apiClient.get as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<StatsOverview />);

      // Should show loading skeletons (4 stat cards)
      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Success State', () => {
    it('displays stats correctly', async () => {
      const mockStats = {
        totalDocuments: 5,
        totalWords: 12500,
        totalCost: 25.50,
        totalTokens: 50000,
      };

      (apiClient.get as jest.Mock).mockResolvedValue(mockStats);

      render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('Total Documents')).toBeInTheDocument();
      });

      // Check all stat values are displayed
      expect(screen.getByText('5')).toBeInTheDocument(); // totalDocuments
      expect(screen.getByText('12,500')).toBeInTheDocument(); // totalWords formatted
      expect(screen.getByText('€25.50')).toBeInTheDocument(); // totalCost formatted
      expect(screen.getByText('50,000')).toBeInTheDocument(); // totalTokens formatted
    });

    it('displays stat labels', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 0,
        totalWords: 0,
        totalCost: 0,
        totalTokens: 0,
      });

      render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('Total Documents')).toBeInTheDocument();
      });

      expect(screen.getByText('Words Generated')).toBeInTheDocument();
      expect(screen.getByText('Total Cost')).toBeInTheDocument();
      expect(screen.getByText('AI Tokens Used')).toBeInTheDocument();
    });

    it('handles zero stats gracefully', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 0,
        totalWords: 0,
        totalCost: 0,
        totalTokens: 0,
      });

      render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('Total Documents')).toBeInTheDocument();
      });

      expect(screen.getByText('€0.00')).toBeInTheDocument();
    });

    it('formats large numbers correctly', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 1000,
        totalWords: 1234567,
        totalCost: 9999.99,
        totalTokens: 9876543,
      });

      render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('Total Documents')).toBeInTheDocument();
      });

      expect(screen.getByText('1,234,567')).toBeInTheDocument();
      expect(screen.getByText('€9999.99')).toBeInTheDocument();
      expect(screen.getByText('9,876,543')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('handles API errors gracefully', async () => {
      (apiClient.get as jest.Mock).mockRejectedValue(new Error('API Error'));

      render(<StatsOverview />);

      // Should show zero stats after error (check for cost which is unique)
      await waitFor(() => {
        expect(screen.getByText('€0.00')).toBeInTheDocument();
      });

      expect(screen.getByText('Total Documents')).toBeInTheDocument();
    });

    it('handles partial data from API', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 5,
        // Missing other fields
      });

      render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument();
      });

      // Should default missing values to 0
      expect(screen.getByText('€0.00')).toBeInTheDocument();
    });
  });

  describe('API Integration', () => {
    it('calls correct API endpoint', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 0,
        totalWords: 0,
        totalCost: 0,
        totalTokens: 0,
      });

      render(<StatsOverview />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/api/v1/documents/stats');
      });

      expect(apiClient.get).toHaveBeenCalledTimes(1);
    });

    it('fetches stats on mount', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 3,
        totalWords: 5000,
        totalCost: 10.0,
        totalTokens: 20000,
      });

      render(<StatsOverview />);

      // API should be called immediately
      expect(apiClient.get).toHaveBeenCalled();

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });
  });

  describe('UI Elements', () => {
    it('renders 4 stat cards', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 1,
        totalWords: 1000,
        totalCost: 5.0,
        totalTokens: 10000,
      });

      render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('Total Documents')).toBeInTheDocument();
      });

      // Should have 4 distinct stat labels
      expect(screen.getByText('Total Documents')).toBeInTheDocument();
      expect(screen.getByText('Words Generated')).toBeInTheDocument();
      expect(screen.getByText('Total Cost')).toBeInTheDocument();
      expect(screen.getByText('AI Tokens Used')).toBeInTheDocument();
    });

    it('displays icons for each stat', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        totalDocuments: 1,
        totalWords: 1000,
        totalCost: 5.0,
        totalTokens: 10000,
      });

      const { container } = render(<StatsOverview />);

      await waitFor(() => {
        expect(screen.getByText('Total Documents')).toBeInTheDocument();
      });

      // Should have SVG icons (Heroicons)
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThanOrEqual(4);
    });
  });
});
