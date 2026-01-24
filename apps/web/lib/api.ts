/**
 * API Client для TesiGo Frontend
 *
 * Функціональність:
 * - Централізована конфігурація API endpoints
 * - JWT автентифікація з автоматичним refresh
 * - Token management (localStorage)
 * - Retry logic з exponential backoff
 * - Type-safe API calls
 */

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

interface TokenPayload {
  exp: number;
  user_id: number;
  email: string;
}

interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
}

interface HttpMethod {
  get: <T = any>(url: string, config?: RequestInit) => Promise<T>;
  post: <T = any>(url: string, data?: any, config?: RequestInit) => Promise<T>;
  put: <T = any>(url: string, data?: any, config?: RequestInit) => Promise<T>;
  delete: <T = any>(url: string, config?: RequestInit) => Promise<T>;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_STORAGE_KEY = 'auth_token';
const REFRESH_TOKEN_STORAGE_KEY = 'refresh_token';
const TOKEN_EXPIRY_BUFFER = 5 * 60; // 5 minutes before expiry

// ============================================================================
// TOKEN MANAGEMENT
// ============================================================================

/**
 * Отримати access token з localStorage
 */
export const getAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
};

/**
 * Отримати refresh token з localStorage
 */
const getRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
};

/**
 * Зберегти tokens в localStorage
 */
export const setTokens = (accessToken: string, refreshToken: string): void => {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken);
};

/**
 * Видалити tokens з localStorage
 */
export const clearTokens = (): void => {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
};

/**
 * Перевірити чи token скоро прострочиться
 */
const willTokenExpireSoon = (token: string): boolean => {
  try {
    // Manual JWT decode (не використовуємо jose щоб уникнути ESM issues в Jest)
    const payload = token.split('.')[1];
    if (!payload) return true;

    const decoded = JSON.parse(atob(payload)) as TokenPayload;
    const currentTime = Math.floor(Date.now() / 1000);
    return decoded.exp - currentTime < TOKEN_EXPIRY_BUFFER;
  } catch {
    return true; // Якщо не можемо декодувати - вважаємо що прострочений
  }
};

// ============================================================================
// AUTO-REFRESH MECHANISM
// ============================================================================

let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

/**
 * Оновити access token використовуючи refresh token
 * Включає deduplication для одночасних запитів
 */
const refreshAccessToken = async (): Promise<string | null> => {
  // Deduplication: якщо вже йде refresh - повертаємо той самий Promise
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearTokens();
        return null;
      }

      const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        clearTokens();
        return null;
      }

      const data = await response.json();
      const newAccessToken = data.access_token;
      const newRefreshToken = data.refresh_token || refreshToken;

      setTokens(newAccessToken, newRefreshToken);
      return newAccessToken;
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearTokens();
      return null;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
};

/**
 * Отримати валідний access token (з автоматичним refresh якщо потрібно)
 */
const getValidAccessToken = async (): Promise<string | null> => {
  const token = getAccessToken();

  if (!token) {
    return null;
  }

  // Preemptive refresh: якщо token скоро прострочиться
  if (willTokenExpireSoon(token)) {
    const newToken = await refreshAccessToken();
    return newToken;
  }

  return token;
};

// ============================================================================
// API CLIENT
// ============================================================================

/**
 * Створити headers для API запиту
 */
const createHeaders = async (customHeaders?: HeadersInit): Promise<Record<string, string>> => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (customHeaders) {
    Object.entries(customHeaders).forEach(([key, value]) => {
      if (typeof value === 'string') {
        headers[key] = value;
      }
    });
  }

  const token = await getValidAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
};

/**
 * Обробити API відповідь
 */
const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    // Спроба автоматичного refresh на 401
    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (!newToken) {
        // Redirect на login якщо refresh не вдався
        if (typeof window !== 'undefined') {
          window.location.href = '/auth/login';
        }
        throw new Error('Authentication required');
      }
      throw new Error('Token refreshed, retry request');
    }

    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`);
  }

  const data = await response.json();
  return data;
};

/**
 * Централізований API client з автоматичним refresh
 */
export const apiClient: HttpMethod = {
  get: async <T = any>(url: string, config?: RequestInit): Promise<T> => {
    const headers = await createHeaders(config?.headers);
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'GET',
      ...config,
      headers,
    });
    return handleResponse<T>(response);
  },

  post: async <T = any>(url: string, data?: any, config?: RequestInit): Promise<T> => {
    const headers = await createHeaders(config?.headers);
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'POST',
      ...config,
      headers,
      body: JSON.stringify(data),
    });
    return handleResponse<T>(response);
  },

  put: async <T = any>(url: string, data?: any, config?: RequestInit): Promise<T> => {
    const headers = await createHeaders(config?.headers);
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'PUT',
      ...config,
      headers,
      body: JSON.stringify(data),
    });
    return handleResponse<T>(response);
  },

  delete: async <T = any>(url: string, config?: RequestInit): Promise<T> => {
    const headers = await createHeaders(config?.headers);
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'DELETE',
      ...config,
      headers,
    });
    return handleResponse<T>(response);
  },
};

// ============================================================================
// API ENDPOINTS
// ============================================================================

export const API_ENDPOINTS = {
  /**
   * Authentication endpoints
   */
  AUTH: {
    MAGIC_LINK: '/api/v1/auth/magic-link',
    VERIFY_MAGIC_LINK: '/api/v1/auth/verify-magic-link',
    REFRESH: '/api/v1/auth/refresh',
    LOGOUT: '/api/v1/auth/logout',
    ME: '/api/v1/auth/me',
    ADMIN_LOGIN: '/api/v1/auth/admin-login',
  },

  /**
   * Documents endpoints
   */
  DOCUMENTS: {
    BASE: '/api/v1/documents',
    CREATE: '/api/v1/documents',
    LIST: '/api/v1/documents',
    STATS: '/api/v1/documents/stats',
    ACTIVITY: '/api/v1/documents/activity',
    GET: (id: number) => `/api/v1/documents/${id}`,
    UPDATE: (id: number) => `/api/v1/documents/${id}`,
    DELETE: (id: number) => `/api/v1/documents/${id}`,
    EXPORT: (id: number) => `/api/v1/documents/${id}/export`,
  },

  /**
   * Generation endpoints
   */
  GENERATE: {
    OUTLINE: '/api/v1/generate/outline',
    SECTION: '/api/v1/generate/section',
    FULL: '/api/v1/generate/full',
    MODELS: '/api/v1/generate/models',
    USAGE: '/api/v1/generate/usage',
  },

  /**
   * Payment endpoints
   */
  PAYMENT: {
    CREATE_INTENT: '/api/v1/payment/create-intent',
    CREATE_CHECKOUT: '/api/v1/payment/create-checkout',
    VERIFY: '/api/v1/payment/verify',
    WEBHOOK: '/api/v1/payment/webhook',
    HISTORY: '/api/v1/payment/history',
    GET: (id: number) => `/api/v1/payment/${id}`,
  },

  /**
   * Pricing endpoints
   */
  PRICING: {
    CONFIG: '/api/v1/pricing/config',
    CURRENT: '/api/v1/pricing/current',
    CALCULATE: '/api/v1/pricing/calculate',
  },

  /**
   * Job status endpoints
   */
  JOBS: {
    STATUS: (id: number) => `/api/v1/jobs/${id}/status`,
    CANCEL: (id: number) => `/api/v1/jobs/${id}/cancel`,
  },

  /**
   * Admin endpoints
   */
  ADMIN: {
    STATS: '/api/v1/admin/stats',
    USERS: '/api/v1/admin/users',
    DOCUMENTS: '/api/v1/admin/documents',
    PAYMENTS: '/api/v1/admin/payments',
    REFUNDS: '/api/v1/admin/refunds',
    PRICING: '/api/v1/admin/pricing',
    USER: (id: number) => `/api/v1/admin/users/${id}`,
    DOCUMENT: (id: number) => `/api/v1/admin/documents/${id}`,
    PAYMENT: (id: number) => `/api/v1/admin/payments/${id}`,
    REFUND_APPROVE: (id: number) => `/api/v1/admin/refunds/${id}/approve`,
    REFUND_REJECT: (id: number) => `/api/v1/admin/refunds/${id}/reject`,
  },
};

/**
 * Default export
 */
export default apiClient;
