# Git Commit Message Template for Temporary Solutions

## Format:

```
<type>: <subject> (with temporary solution documented)

- Implemented: <what was implemented>
- Temporary: <what is temporary>
- Documented: /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #<number>
- TODO: <when will be fixed>

Refs: #<issue-number>
```

## Example:

```
feat: Add admin dashboard endpoints (with temporary solution documented)

- Implemented: 4 admin dashboard API endpoints (stats, charts, activity, metrics)
- Temporary: All endpoints return mock data (zeros/empty arrays)
- Documented: /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #1
- TODO: Replace with real DB queries after generation pipeline is tested (1-2 hours)

Files:
- Created: apps/api/app/api/v1/endpoints/admin_dashboard.py
- Updated: apps/api/main.py (router registration)
- Updated: docs/MVP_PLAN.md (temporary solution entry)

Refs: MVP testing phase
```

## Short Format:

```
feat: <feature> (temp solution docs added)

Temporary solution documented in MVP_PLAN.md #<number>
TODO: <action> (<time estimate>)
```

## Example Short:

```
feat: admin dashboard endpoints (temp solution docs added)

Temporary solution documented in MVP_PLAN.md #1
TODO: Replace mock data with real DB queries (1-2h)
```

---

**Always mention that temporary solution is documented!**
