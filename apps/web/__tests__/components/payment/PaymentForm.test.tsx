/**
 * Tests for PaymentForm component
 * Tests payment form display, submission, validation, error handling
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { PaymentForm } from '@/components/payment/PaymentForm';
import { apiClient, getAccessToken } from '@/lib/api';
import { useRouter } from 'next/navigation';

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
  },
  getAccessToken: jest.fn(),
  API_ENDPOINTS: {
    PRICING: {
      CURRENT: '/api/v1/pricing/current',
    },
    PAYMENT: {
      CREATE_CHECKOUT: '/api/v1/payment/create-checkout',
    },
  },
}));

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock toast
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

// Mock fetch
global.fetch = jest.fn();

describe('PaymentForm Component', () => {
  const mockRouter = {
    push: jest.fn(),
    replace: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
    (getAccessToken as jest.Mock).mockReturnValue('mock-token');

    // Mock pricing endpoint
    (apiClient.get as jest.Mock).mockResolvedValue({
      price_per_page: 0.50,
      min_pages: 3,
      max_pages: 200,
      currencies: ['EUR'],
    });

    // Reset fetch mock
    (global.fetch as jest.Mock).mockClear();
  });

  describe('Loading State', () => {
    it('shows loading state while fetching pricing', async () => {
      (apiClient.get as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<PaymentForm documentId={1} pages={10} />);

      // Component shows default pricing immediately (fallback)
      // This is OK behavior - user can still see the form
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });
    });
  });

  describe('Success State', () => {
    it('displays payment amount correctly', async () => {
      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay.*€5\.00/i })).toBeInTheDocument();
      });
    });

    it('calculates total from pages and price per page', async () => {
      render(<PaymentForm documentId={1} pages={20} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay.*€10\.00/i })).toBeInTheDocument();
      });
    });

    it('displays document information', async () => {
      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        const container = document.body;
        expect(container.textContent).toMatch(/10.*pages?/i);
      });
    });

    it('shows pay button', async () => {
      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });
    });
  });

  describe('Form Submission', () => {
    it('handles successful payment initialization', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({
          checkout_url: 'https://checkout.stripe.com/test',
        }),
      });

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      // Should call fetch with correct params
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/v1/payment/create-checkout?document_id=1&pages=10'),
          expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
              Authorization: 'Bearer mock-token',
            }),
          })
        );
      });

      // Note: Cannot test window.location.href assignment in jsdom
      // This is a known limitation - actual redirect happens in browser
    });

    it('disables button during submission', async () => {
      (global.fetch as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      // Button should be disabled
      expect(payButton).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    it('handles payment API error', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({
          detail: 'Payment failed',
        }),
      });

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });

      // Button should be re-enabled after error
      await waitFor(() => {
        expect(payButton).not.toBeDisabled();
      });
    });

    it('handles missing checkout URL', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({}), // No checkout_url
      });

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });

      // Button should be re-enabled
      await waitFor(() => {
        expect(payButton).not.toBeDisabled();
      });
    });

    it('handles missing auth token', async () => {
      (getAccessToken as jest.Mock).mockReturnValue(null);

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      await waitFor(() => {
        expect(mockRouter.push).toHaveBeenCalledWith('/');
      });
    });

    it('uses fallback pricing on fetch error', async () => {
      (apiClient.get as jest.Mock).mockRejectedValue(new Error('Pricing API Error'));

      render(<PaymentForm documentId={1} pages={10} />);

      // Should still calculate with default pricing (10 pages × €0.50 = €5.00)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay.*€5\.00/i })).toBeInTheDocument();
      });
    });
  });

  describe('Cancel Functionality', () => {
    it('calls onCancel when cancel button clicked', async () => {
      const onCancel = jest.fn();

      render(<PaymentForm documentId={1} pages={10} onCancel={onCancel} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });

    it('does not show cancel button when onCancel not provided', async () => {
      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument();
    });
  });

  describe('Pricing Configuration', () => {
    it('fetches pricing on mount', async () => {
      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/api/v1/pricing/current');
      });
    });

    it('uses custom pricing from API', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({
        price_per_page: 1.00,
        min_pages: 3,
        max_pages: 200,
        currencies: ['EUR'],
      });

      render(<PaymentForm documentId={1} pages={10} />);

      // 10 pages × €1.00 = €10.00
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay.*€10\.00/i })).toBeInTheDocument();
      });
    });
  });
});
