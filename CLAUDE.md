# CLAUDE.md - AI Agent Instructions for TesiGo

## Project Overview

**TesiGo** - AI-powered academic paper generation platform (theses, dissertations, coursework).

**Stack:** FastAPI (Python 3.11) + Next.js 14 (App Router) + PostgreSQL + Redis + MinIO

**Business Model:** Pay-per-page (EUR only), magic link auth, Stripe payments

## Quality Rules (MANDATORY)

**Before EVERY task:**
1. Read and follow `/.github/AGENT_QUALITY_RULES.md`
2. Verify REAL code (read_file/grep_search) - never assume
3. Show proof (grep output, curl results) before confirming "done"
4. If doubts - STOP and ASK, don't guess

**Forbidden:**
- Confirm without code verification
- Trust documentation without checking actual code
- Give uncertain answers ("probably", "seems like", "maybe")
- Skip context docs (MASTER_DOCUMENT, DECISIONS_LOG)

**Self-check before confirming:**
- [ ] Verified REAL code?
- [ ] Matches documentation?
- [ ] Can prove correctness?
- [ ] Updated docs if needed?

## Critical Documentation

| Priority | File | Purpose |
|----------|------|---------|
| 0 | `/.github/AGENT_QUALITY_RULES.md` | HOW to work (mandatory) |
| 1 | `/docs/MASTER_DOCUMENT.md` | Technical reference |
| 2 | `/docs/sec/DECISIONS_LOG.md` | Architecture decisions |
| 3 | `/docs/MVP_PLAN.md` | Current status, TODOs |
| 4 | `/.github/copilot-instructions.md` | Full AI instructions |

**Ignore:** `/docs/archive/`, `/reports/` (outdated)

## Temporary Solutions Protocol

Every temporary solution MUST be documented in `/docs/MVP_PLAN.md`:

```python
# TEMPORARY: Mock data - See /docs/MVP_PLAN.md -> "TEMPORARY SOLUTIONS" -> #1
# TODO: Replace with real DB query (Priority: MEDIUM, Time: 1-2h)
return {"total_users": 0}
```

## Tech Stack Versions (CRITICAL)

- **Python:** 3.11+ (NOT 3.12+ - breaks dependencies)
- **Node.js:** 18+
- **FastAPI:** 0.104.1
- **Next.js:** 14.0.3
- **PostgreSQL:** 15-alpine
- **Redis:** 7-alpine

## Key Commands

```bash
# Backend
cd apps/api && uvicorn main:app --reload --port 8000

# Frontend
cd apps/web && npm run dev

# Tests
cd apps/api && pytest tests/ -v

# Health check
curl http://localhost:8000/health
```

## Code Patterns

### Database (ALWAYS use dependency injection)
```python
async def my_endpoint(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
```

### IDOR Protection (MANDATORY)
```python
if doc.user_id != current_user.id:
    raise HTTPException(403, "Not authorized")
```

### Type Hints (enforced by mypy)
```python
async def process(user_id: int, amount: Decimal) -> Payment:
    pass
```

## Anti-Patterns (DO NOT)

- Create sessions manually (`db = Session()`)
- Use float for currency (use `Decimal`)
- SQL injection via f-strings
- Sync code in async context
- Hardcode secrets

## CI Quality Gates

On every PR:
1. Python 3.11 version check
2. Ruff linting (must pass)
3. MyPy type checking (baseline: 151 errors)
4. Pytest tests (must pass)
5. Coverage >= 70%

## Commit Format for Temporary Solutions

```
feat: <feature> (temp solution docs added)

Temporary solution documented in MVP_PLAN.md #<number>
TODO: <action> (<time estimate>)
```

## When Stuck

1. Check `MASTER_DOCUMENT.md`
2. Search existing patterns in codebase
3. Read `DECISIONS_LOG.md` for context
4. ASK rather than assume

**Philosophy:** Quality > Speed. Better ask than do wrong.
