const truthyValues = new Set(['1', 'true', 'yes', 'on'])

const isEnabled = (value: string | undefined, defaultValue = false): boolean => {
  if (!value) {
    return defaultValue
  }
  return truthyValues.has(value.trim().toLowerCase())
}

/**
 * Feature flags for controlled runtime rollouts.
 * Stage 0 defaults keep sales disabled; payment/refund flows are opt-in.
 */
export const FEATURE_FLAGS = {
  userPaymentFlow: isEnabled(process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW, false),
  userRefundFlow: isEnabled(process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW, false),
}

export const isUserPaymentFlowEnabled = FEATURE_FLAGS.userPaymentFlow
export const isUserRefundFlowEnabled =
  FEATURE_FLAGS.userPaymentFlow && FEATURE_FLAGS.userRefundFlow
