/**
 * Test utilities for component testing
 * Provides common mocks and helper functions
 */

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';

// Mock router for Next.js navigation tests
export const mockRouter = {
  push: jest.fn(),
  replace: jest.fn(),
  prefetch: jest.fn(),
  back: jest.fn(),
  pathname: '/dashboard',
  query: {},
  asPath: '/dashboard',
  route: '/dashboard',
  events: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
  },
};

// Mock toast notifications
export const mockToast = {
  success: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
  warning: jest.fn(),
};

// Mock API responses - common document data
export const mockDocument = {
  id: 1,
  title: 'Test Document',
  topic: 'AI in Education',
  language: 'en',
  target_pages: 10,
  status: 'draft',
  created_at: '2025-12-01T10:00:00Z',
  updated_at: '2025-12-01T10:00:00Z',
};

// Mock user data
export const mockUser = {
  id: 1,
  email: 'test@example.com',
  full_name: 'Test User',
  is_active: true,
  is_admin: false,
  created_at: '2025-11-01T10:00:00Z',
};

// Mock admin user
export const mockAdminUser = {
  ...mockUser,
  id: 2,
  email: 'admin@tesigo.com',
  full_name: 'Admin User',
  is_admin: true,
};

// Mock payment data
export const mockPayment = {
  id: 1,
  document_id: 1,
  user_id: 1,
  amount: 5.0,
  currency: 'EUR',
  status: 'completed',
  stripe_intent_id: 'pi_test123',
  created_at: '2025-12-01T10:00:00Z',
};

// Mock stats data
export const mockStats = {
  total_users: 100,
  active_users: 75,
  total_documents: 250,
  completed_documents: 200,
  total_revenue: 1250.0,
  documents_this_month: 45,
};

// Mock activity data
export const mockActivity = [
  {
    id: 1,
    action: 'document.created',
    document_id: 1,
    document_title: 'Test Document',
    created_at: '2025-12-01T10:00:00Z',
  },
  {
    id: 2,
    action: 'document.completed',
    document_id: 1,
    document_title: 'Test Document',
    created_at: '2025-12-01T11:00:00Z',
  },
];

// Mock refund data
export const mockRefund = {
  id: 1,
  payment_id: 1,
  user_id: 1,
  amount: 5.0,
  reason: 'Quality issues',
  status: 'pending',
  created_at: '2025-12-01T10:00:00Z',
};

/**
 * Custom render function that wraps component with common providers
 * Can be extended later with AuthProvider, QueryClientProvider, etc.
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  // For now, just use standard render
  // Can add providers here as needed: <AuthProvider><QueryClient>{ui}</QueryClient></AuthProvider>
  return render(ui, options);
}

/**
 * Wait for async operations to complete
 */
export const waitForAsync = () => new Promise(resolve => setTimeout(resolve, 0));

/**
 * Create mock fetch response
 */
export function createMockResponse<T>(data: T, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as Response;
}

/**
 * Mock window.matchMedia for responsive tests
 */
export function mockMatchMedia(matches: boolean = false) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
}

/**
 * Reset all mocks between tests
 */
export function resetAllMocks() {
  mockRouter.push.mockClear();
  mockRouter.replace.mockClear();
  mockRouter.prefetch.mockClear();
  mockRouter.back.mockClear();
  mockToast.success.mockClear();
  mockToast.error.mockClear();
  mockToast.info.mockClear();
  mockToast.warning.mockClear();
}
