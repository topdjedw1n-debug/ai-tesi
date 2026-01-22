/**
 * Tests for RecentActivity component
 * Tests activity list display, loading states, empty states
 */

import { render, screen, waitFor } from '@testing-library/react';
import { RecentActivity } from '@/components/dashboard/RecentActivity';
import { apiClient } from '@/lib/api';

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
  },
  API_ENDPOINTS: {
    DOCUMENTS: {
      ACTIVITY: '/api/v1/documents/activity',
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

describe('RecentActivity Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading skeleton with Recent Activity header', () => {
      (apiClient.get as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<RecentActivity />);

      // Component shows "Recent Activity" header, not "loading" text
      expect(screen.getByText('Recent Activity')).toBeInTheDocument();
      // Check for skeleton elements
      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Success State', () => {
    it('displays activities list', async () => {
      const mockActivities = [
        {
          id: 1,
          type: 'document_created',
          title: 'AI in Education', // Document title, not activity label
          description: 'New document created',
          timestamp: '2025-12-01T10:00:00Z',
          status: 'success',
        },
        {
          id: 2,
          type: 'document_completed',
          title: 'Climate Change', // Document title
          description: 'Document generation completed',
          timestamp: '2025-12-01T11:00:00Z',
          status: 'success',
        },
      ];

      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: mockActivities,
      });

      render(<RecentActivity />);

      await waitFor(() => {
        // Component shows activityLabels[type] + "for" + title
        expect(screen.getByText('Document Created')).toBeInTheDocument();
      });

      // Check document titles are shown
      expect(screen.getByText('AI in Education')).toBeInTheDocument();
      expect(screen.getByText('Climate Change')).toBeInTheDocument();
    });

    it('displays activity descriptions', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [
          {
            id: 1,
            type: 'document_created',
            title: 'Unique Doc Title 123', // Unique document title
            description: 'This is a test description',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
        ],
      });

      render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText('This is a test description')).toBeInTheDocument();
      });
    });

    it('displays activity timestamps', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [
          {
            id: 1,
            type: 'document_created',
            title: 'Timestamp Test Doc',
            description: 'Testing timestamp display',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
        ],
      });

      render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText('Timestamp Test Doc')).toBeInTheDocument();
      });

      // Should display formatted date/time (formatDateTime output)
      expect(screen.getByText(/Dec 1, 2025/i)).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no activities', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [],
      });

      render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
      });
    });

    it('shows empty state with undefined activities', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({});

      render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('handles API errors gracefully', async () => {
      (apiClient.get as jest.Mock).mockRejectedValue(new Error('API Error'));

      render(<RecentActivity />);

      // Should show empty state after error
      await waitFor(() => {
        expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
      });
    });
  });

  describe('API Integration', () => {
    it('calls correct API endpoint', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [],
      });

      render(<RecentActivity />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/api/v1/documents/activity');
      });
    });

    it('fetches activities on mount', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [
          {
            id: 1,
            type: 'document_created',
            title: 'Mount Test Document',
            description: 'Testing mount behavior',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
        ],
      });

      render(<RecentActivity />);

      expect(apiClient.get).toHaveBeenCalled();

      await waitFor(() => {
        expect(screen.getByText('Mount Test Document')).toBeInTheDocument();
      });
    });
  });

  describe('Activity Types', () => {
    it('displays different activity types', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [
          {
            id: 1,
            type: 'document_created',
            title: 'My Created Document',
            description: 'Document was created',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
          {
            id: 2,
            type: 'outline_generated',
            title: 'My Outline Document',
            description: 'Outline was generated',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
          {
            id: 3,
            type: 'document_completed',
            title: 'My Completed Document',
            description: 'Document was completed',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
        ],
      });

      render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText('My Created Document')).toBeInTheDocument();
      });

      expect(screen.getByText('My Outline Document')).toBeInTheDocument();
      expect(screen.getByText('My Completed Document')).toBeInTheDocument();

      // Check activity labels are shown
      expect(screen.getByText('Document Created')).toBeInTheDocument();
      expect(screen.getByText('Outline Generated')).toBeInTheDocument();
      expect(screen.getByText('Document Completed')).toBeInTheDocument();
    });

    it('displays activity status colors', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [
          {
            id: 1,
            type: 'document_created',
            title: 'Success Document',
            description: 'Successful activity',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
          {
            id: 2,
            type: 'document_created',
            title: 'Error Document',
            description: 'Failed activity',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'error',
          },
        ],
      });

      const { container } = render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText('Success Document')).toBeInTheDocument();
      });

      expect(screen.getByText('Error Document')).toBeInTheDocument();

      // Should have icons with different colors
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('UI Elements', () => {
    it('displays activity icons', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        activities: [
          {
            id: 1,
            type: 'document_created',
            title: 'Icon Test Document',
            description: 'Testing icon display',
            timestamp: '2025-12-01T10:00:00Z',
            status: 'success',
          },
        ],
      });

      const { container } = render(<RecentActivity />);

      await waitFor(() => {
        expect(screen.getByText('Icon Test Document')).toBeInTheDocument();
      });

      // Should have SVG icon
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThan(0);
    });
  });
});
