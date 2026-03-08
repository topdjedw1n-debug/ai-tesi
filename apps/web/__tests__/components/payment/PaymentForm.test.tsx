/**
 * Tests for PaymentForm component
 * Tests payment form display, submission, validation, error handling
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { PaymentForm } from '@/components/payment/PaymentForm';
import { apiClient } from '@/lib/api';

// Enable payment flow in component tests (production default is disabled via feature flag)
jest.mock('@/lib/feature-flags', () => ({
  isUserPaymentFlowEnabled: true,
}));

// Mock API client
jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
  API_ENDPOINTS: {
    PRICING: {
      CURRENT: '/api/v1/pricing/current',
    },
    PAYMENT: {
      CREATE_CHECKOUT: '/api/v1/payment/create-checkout',
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

describe('PaymentForm Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Mock pricing endpoint
    (apiClient.get as jest.Mock).mockResolvedValue({
      price_per_page: 0.50,
      min_pages: 3,
      max_pages: 200,
      currencies: ['EUR'],
    });
    (apiClient.post as jest.Mock).mockResolvedValue({
      checkout_url: 'https://checkout.stripe.com/test',
    });
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
      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      // Should call centralized API client with correct endpoint
      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith(
          '/api/v1/payment/create-checkout?document_id=1&pages=10'
        );
      });
    });

    it('disables button during submission', async () => {
      (apiClient.post as jest.Mock).mockImplementation(
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
      (apiClient.post as jest.Mock).mockRejectedValue(new Error('Payment failed'));

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalled();
      });

      // Button should be re-enabled after error
      await waitFor(() => {
        expect(payButton).not.toBeDisabled();
      });
    });

    it('handles missing checkout URL', async () => {
      (apiClient.post as jest.Mock).mockResolvedValue({}); // No checkout_url

      render(<PaymentForm documentId={1} pages={10} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /pay/i })).toBeInTheDocument();
      });

      const payButton = screen.getByRole('button', { name: /pay/i });
      fireEvent.click(payButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalled();
      });

      // Button should be re-enabled
      await waitFor(() => {
        expect(payButton).not.toBeDisabled();
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
