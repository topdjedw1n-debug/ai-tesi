import { redirect } from 'next/navigation'
import { isUserPaymentFlowEnabled } from '@/lib/feature-flags'

export default function DashboardPaymentsRedirect() {
  if (!isUserPaymentFlowEnabled) {
    redirect('/dashboard')
  }

  redirect('/payment/history')
}
