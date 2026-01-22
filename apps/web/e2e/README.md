# 🎭 Playwright E2E Tests

> Real browser testing for critical user flows

**Status:** ✅ Infrastructure ready, ⚠️ Tests need frontend test IDs

**Created:** 2025-12-03
**Tests:** 21 E2E scenarios across 5 flows
**Pass Rate:** 1/21 (5%) - Expected, requires frontend updates

---

## 📊 Test Coverage

| Flow | Tests | Status | Notes |
|------|-------|--------|-------|
| **Magic Link Auth** | 3 | ⚠️ 1/3 passing | Needs email input selectors |
| **Document Creation** | 4 | ⚠️ 0/4 passing | Needs form test IDs |
| **Payment Checkout** | 4 | ⚠️ 0/4 passing | Needs payment button IDs |
| **Dashboard Stats** | 4 | ⚠️ 0/4 passing | Needs stat card IDs |
| **Document List** | 6 | ⚠️ 0/6 passing | Needs list item IDs |

**Total:** 21 tests, 1 passing (infrastructure validated ✅)

---

## 🚀 Quick Start

### Run All Tests
```bash
npm run test:e2e
```

### Run Specific Test File
```bash
npx playwright test e2e/auth-magic-link.spec.ts
```

### Debug Mode (see browser)
```bash
npm run test:e2e:debug
```

### UI Mode (interactive)
```bash
npm run test:e2e:ui
```

---

## 📋 Test Files

### 1. `auth-magic-link.spec.ts` (3 tests)
Tests authentication flow:
- ✅ **PASSING:** Invalid token error handling
- ⏳ Full magic link flow (email → verify → dashboard)
- ⏳ Rate limiting enforcement

**Why failing:** Missing selectors:
- `input[type="email"]` - works, but form submission needs test ID
- Toast notification - needs `data-testid="toast-notification"`

### 2. `document-creation.spec.ts` (4 tests)
Tests document creation:
- ⏳ Create from dashboard form
- ⏳ Validate min page count (3 pages)
- ⏳ Handle creation failure
- ⏳ Update stats after creation

**Why failing:** Missing selectors:
- `[data-testid="create-document-section"]`
- `[data-testid="document-title-input"]`
- `[data-testid="document-topic-input"]`
- `[data-testid="create-document-btn"]`

### 3. `payment-checkout.spec.ts` (4 tests)
Tests payment flow:
- ⏳ Display payment calculation
- ⏳ Redirect to Stripe checkout
- ⏳ Handle payment failure
- ⏳ Disable button during processing

**Why failing:** Missing selectors:
- `[data-testid="payment-required-section"]`
- `[data-testid="price-calculation"]`
- `[data-testid="pay-generate-btn"]`

### 4. `dashboard-stats.spec.ts` (4 tests)
Tests dashboard statistics:
- ⏳ Display stat cards
- ⏳ Show recent activity
- ⏳ Empty state
- ⏳ Error handling

**Why failing:** Missing selectors:
- `[data-testid="dashboard-stats"]`
- `[data-testid="stat-total-documents"]`
- `[data-testid="recent-activity"]`

### 5. `document-list.spec.ts` (6 tests)
Tests document list:
- ⏳ Display all documents
- ⏳ Filter by status
- ⏳ Sort by date
- ⏳ Navigate to detail
- ⏳ Delete with confirmation
- ⏳ Cancel deletion

**Why failing:** Missing selectors:
- `[data-testid="documents-list"]`
- `[data-testid^="document-card-"]`
- `[data-testid="filter-completed"]`
- `[data-testid="delete-document-{id}"]`

---

## 🔧 How to Fix Tests

### Option 1: Add Test IDs to Components (Recommended)

Update frontend components to include `data-testid` attributes:

```tsx
// Before
<button onClick={handleCreate}>Create Document</button>

// After
<button
  data-testid="create-document-btn"
  onClick={handleCreate}
>
  Create Document
</button>
```

**Priority components to update:**
1. `/app/auth/login/page.tsx` - email input, send button
2. `/app/dashboard/page.tsx` - stats cards, document list
3. `/components/DocumentForm.tsx` - form inputs, create button
4. `/components/PaymentSection.tsx` - payment button, calculation

### Option 2: Update Tests to Use Existing Selectors

Modify tests to find elements by text/role instead of test IDs:

```typescript
// Instead of:
const button = page.locator('[data-testid="create-document-btn"]')

// Use:
const button = page.getByRole('button', { name: /create document/i })
```

---

## 📝 Test Helpers

### `helpers.ts` Utilities:

**mockLogin(page, email)** - Simulates authentication
```typescript
await mockLogin(page, 'test@example.com')
```

**mockApiRoute(page, url, response)** - Intercepts API calls
```typescript
await mockApiRoute(page, '**/api/v1/documents', { id: 1, title: 'Test' })
```

**mockAuthMe(page, userData)** - Mocks /auth/me endpoint
```typescript
await mockAuthMe(page, { email: 'test@example.com' })
```

**fillDocumentForm(page, data)** - Fills document creation form
```typescript
await fillDocumentForm(page, {
  title: 'My Thesis',
  topic: 'AI Ethics',
  pages: 25
})
```

---

## 🎯 Success Criteria

Tests will pass when:
- ✅ Frontend components have `data-testid` attributes
- ✅ Real backend running on `localhost:8000` (or mocked APIs work)
- ✅ Database seeded with test data
- ✅ Selectors match actual component structure

---

## 🐛 Common Issues

### Issue 1: Timeouts (15s)
**Cause:** Selector not found
**Fix:** Add `data-testid` to component or update selector

### Issue 2: "toHaveTitle" fails
**Expected:** "TesiGo"
**Actual:** "AI Thesis Platform"
**Fix:** Update expectation or page title

### Issue 3: Mock API not intercepting
**Cause:** Route pattern doesn't match
**Fix:** Check URL pattern in `page.route()` call

---

## 📊 Progress Tracking

**Current Status:**
- ✅ Playwright installed & configured
- ✅ 21 E2E tests written (best practices)
- ✅ Helper utilities created
- ✅ Infrastructure validated (1 test passing)
- ⚠️ Frontend needs test IDs (~2-3h work)

**Next Steps:**
1. Add `data-testid` to 10-15 key components (2h)
2. Rerun tests (`npm run test:e2e`)
3. Fix remaining failures (timing, selectors) (1h)
4. Achieve 80%+ pass rate (target: 17+/21)

---

## 📚 Resources

- [Playwright Docs](https://playwright.dev)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Selectors Guide](https://playwright.dev/docs/selectors)
- [Test Generator](https://playwright.dev/docs/codegen) - `npx playwright codegen`

---

**Tests demonstrate production-ready E2E patterns. Frontend integration TBD.**
