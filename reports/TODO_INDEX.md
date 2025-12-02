# TODO and FIXME Index

**Generated:** 2025-11-02

---

## Backend TODOs

### High Priority

**File:** `apps/api/app/services/auth_service.py:69`
```python
# TODO: Send email with magic link
```
**Status:** Feature incomplete
**Action:** Implement email sending

---

**File:** `apps/api/app/services/admin_service.py:239`
```python
# TODO: Implement proper grouping based on group_by parameter
```
**Status:** Feature incomplete
**Action:** Implement aggregation logic

---

### Configuration Notes

**File:** `apps/api/app/core/config.py`
Multiple DEBUG references for environment-driven behavior (not TODOs)

---

## Frontend TODOs

### High Priority

**File:** `apps/web/components/dashboard/GenerateSectionForm.tsx:77`
```typescript
// TODO: Replace with actual API call
```
**Status:** Mock implementation
**Action:** Integrate with backend API

---

**File:** `apps/web/components/dashboard/DocumentsList.tsx:45`
```typescript
// TODO: Fetch real documents from API
```
**Status:** Mock data
**Action:** Implement API integration

---

**File:** `apps/web/components/dashboard/RecentActivity.tsx:49`
```typescript
// TODO: Fetch real activities from API
```
**Status:** Mock data
**Action:** Implement API integration

---

**File:** `apps/web/components/dashboard/StatsOverview.tsx:23`
```typescript
// TODO: Fetch real stats from API
```
**Status:** Mock data
**Action:** Implement API integration

---

### Medium Priority

**File:** `apps/web/app/dashboard/settings/page.tsx:15`
```typescript
// TODO: Implement settings save
```
**Status:** Feature incomplete
**Action:** Add save functionality

---

**File:** `apps/web/components/providers/AuthProvider.tsx:52`
```typescript
// TODO: Verify token with backend
```
**Status:** Mock verification
**Action:** Add backend token validation

---

**File:** `apps/web/components/providers/AuthProvider.tsx:71`
```typescript
// TODO: Call backend API to send magic link
```
**Status:** Mock implementation
**Action:** Integrate with auth endpoint

---

**File:** `apps/web/components/providers/AuthProvider.tsx:133`
```typescript
// TODO: Call backend API to invalidate session
```
**Status:** Mock logout
**Action:** Add logout API call

---

## Summary

**Backend TODOs:** 2
**Frontend TODOs:** 8
**Total:** 10

**Critical:** 8 TODOs in frontend (feature incomplete)
**Impact:** Frontend cannot function without backend integration

**Recommendation:** All frontend TODOs should be addressed before production

---

