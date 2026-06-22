describe('feature flags', () => {
  const originalPayment = process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW
  const originalRefund = process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW

  afterEach(() => {
    jest.resetModules()
    if (originalPayment === undefined) {
      delete process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW
    } else {
      process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW = originalPayment
    }
    if (originalRefund === undefined) {
      delete process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW
    } else {
      process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW = originalRefund
    }
  })

  it('defaults payment and refund flows off for Stage 0', () => {
    delete process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW
    delete process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW
    jest.resetModules()

    const flags = require('../feature-flags')

    expect(flags.isUserPaymentFlowEnabled).toBe(false)
    expect(flags.isUserRefundFlowEnabled).toBe(false)
  })

  it('keeps refund disabled unless payment is also enabled', () => {
    delete process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW
    process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW = 'true'
    jest.resetModules()

    const flags = require('../feature-flags')

    expect(flags.isUserPaymentFlowEnabled).toBe(false)
    expect(flags.isUserRefundFlowEnabled).toBe(false)
  })

  it('allows explicit sales opt-in', () => {
    process.env.NEXT_PUBLIC_ENABLE_USER_PAYMENT_FLOW = 'true'
    process.env.NEXT_PUBLIC_ENABLE_USER_REFUND_FLOW = 'true'
    jest.resetModules()

    const flags = require('../feature-flags')

    expect(flags.isUserPaymentFlowEnabled).toBe(true)
    expect(flags.isUserRefundFlowEnabled).toBe(true)
  })
})
