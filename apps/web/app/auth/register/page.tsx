import { redirect } from 'next/navigation'

/**
 * Self-signup is closed (founder decision 2026-08-21, docs/AGENT_SYNC.md §13).
 * The internal pilot is manager-only, so this route sends visitors to the
 * sign-in page instead of creating accounts for unknown emails.
 */
export default function RegisterPage() {
  redirect('/auth/login')
}
