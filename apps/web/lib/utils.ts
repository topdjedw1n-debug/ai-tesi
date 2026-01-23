/**
 * Utility functions for TesiGo Frontend
 * @module utils
 */

/**
 * Merge class names (similar to clsx/classnames)
 * Used by UI components for conditional styling with Tailwind CSS
 *
 * @param {...(string | undefined | null | false)[]} classes - Class names to merge
 * @returns {string} Merged class string with falsy values filtered out
 * @example
 * ```tsx
 * <div className={cn('base-class', isActive && 'active', 'another-class')} />
 * // Output: "base-class active another-class" (if isActive is true)
 * ```
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}

/**
 * Format date to readable localized string
 * @param {string | Date} date - Date to format (ISO string or Date object)
 * @returns {string} Formatted date string (e.g., "Nov 28, 2025")
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format date and time to readable localized string with time
 * @param {string | Date | null} date - Date to format (ISO string or Date object)
 * @param {string} fallback - Fallback string if date is null/undefined
 * @returns {string} Formatted date-time string (e.g., "Nov 28, 2025, 10:30 AM")
 * @example
 * ```tsx
 * formatDateTime('2025-11-28T10:30:00Z') // "Nov 28, 2025, 10:30 AM"
 * formatDateTime(null, 'N/A') // "N/A"
 * ```
 */
export function formatDateTime(date: string | Date | null, fallback = '—'): string {
  if (!date) return fallback;
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format date only (no time) to readable string
 * Used by admin components
 */
export function formatDateOnly(date: string | Date | null, fallback = '—'): string {
  if (!date) return fallback;
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Sanitize text to prevent XSS attacks
 * Escapes HTML special characters by using browser's textContent API
 *
 * @param {string} text - Raw text that may contain unsafe HTML
 * @returns {string} Sanitized text safe for innerHTML
 * @security Prevents XSS by escaping <, >, &, ", ' characters
 * @example
 * ```tsx
 * sanitizeText('<script>alert("xss")</script>')
 * // Returns: "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
 * ```
 */
export function sanitizeText(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Truncate text to specified length with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} length - Maximum length (including ellipsis)
 * @returns {string} Truncated text with "..." if needed
 * @example
 * ```tsx
 * truncate('This is a long text', 10) // "This is a ..."
 * ```
 */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return text.slice(0, length) + '...';
}

/**
 * Format number as currency with locale-specific formatting
 * @param {number} amount - Amount to format (in base currency unit, not cents)
 * @param {string} [currency='EUR'] - ISO 4217 currency code (default: EUR)
 * @returns {string} Formatted currency string (e.g., "€10.50")
 * @example
 * ```tsx
 * formatCurrency(10.5) // "€10.50"
 * formatCurrency(1500.99, 'USD') // "$1,500.99"
 * ```
 */
export function formatCurrency(amount: number, currency = 'EUR'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount);
}

/**
 * Sleep for specified milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
