const truthyValues = new Set(['1', 'true', 'yes', 'on'])

const isEnabled = (value: string | undefined, defaultValue = false): boolean => {
  if (!value) {
    return defaultValue
  }
  return truthyValues.has(value.trim().toLowerCase())
}

/**
 * Feature flags for controlled runtime rollouts.
 * Defaults are enabled after Wave 1 stabilization; can be disabled as kill-switches.
 */
export const FEATURE_FLAGS = {
  userPaymentFlow: isEnabled(process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW, true),
  userRefundFlow: isEnabled(process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW, true),
}

export const isUserPaymentFlowEnabled = FEATURE_FLAGS.userPaymentFlow
export const isUserRefundFlowEnabled =
  FEATURE_FLAGS.userPaymentFlow && FEATURE_FLAGS.userRefundFlow
