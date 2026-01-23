# TesiGo AI Agent Instructions

> **Single source of truth for AI agent behavior in this project.**

**Version:** 3.0 | **Updated:** 2026-01-22 | **Status:** ACTIVE

---

## 🚨 START PROTOCOL (EVERY TASK - NO EXCEPTIONS)

**Before doing ANY work, complete these 5 steps:**

```
1. RESTATE:    What am I doing? (1-2 sentences)
2. ASSUMPTIONS: What I assume to be true (1-3 items, or "none")
3. PLAN:       Steps to complete (3-7 max)
4. RISKS:      Edge cases, potential issues (1-3)
5. OUTPUT:     What artifact will be delivered (diff/file/test)
```

**Show this to user. Wait for "Так, починай" before executing.**

**Why?** Prevents wasted work, catches misunderstandings early, forces thinking before coding.

---

## 🔴 P0: NON-NEGOTIABLE RULES

### Never Do (Instant Fail)
- ❌ Execute without showing plan first
- ❌ Say "Done" without showing proof (grep/read_file output)
- ❌ Assume code behavior - read the actual file
- ❌ Use uncertain words: "мабуть", "здається", "можливо", "probably"
- ❌ Trust documentation blindly - verify against real code
- ❌ Skip ownership checks (IDOR vulnerability)
- ❌ Use f-strings in SQL queries (SQL injection)
- ❌ Hardcode secrets in code
- ❌ Create sync I/O in async functions
- ❌ Ignore type hints (mypy must pass)

### Always Do (Required)
- ✅ Read real code with `read_file` before changing it
- ✅ Show proof for every claim (grep output, line numbers)
- ✅ Check IDOR: `if doc.user_id != current_user.id: raise 403`
- ✅ Use `Decimal` for money, never `float`
- ✅ Update `/docs/MVP_PLAN.md` when adding TODOs
- ✅ Follow existing patterns in codebase

### 3+ Fixes Rule
If you've tried 3+ fixes and issue persists → **STOP**.
Say: "This may be an architectural issue, not a bug. Let's discuss approach."

### Debugging Iron Law
**❌ NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST**

Before proposing ANY fix:
1. Complete root cause investigation (Phase 1)
2. Understand the pattern (Phase 2)
3. Form and test hypothesis (Phase 3)
4. Only then implement fix (Phase 4)

**See:** `.github/DEBUG_PROTOCOL.md` for full systematic debugging process.

**Red flags that you're violating this:**
- "Quick fix for now"
- "Just try changing X"
- "I think the problem is..." (without evidence)
- Proposing solutions before tracing data flow
- Each fix reveals new problem elsewhere

---

## 🟠 P1: ARCHITECTURE CONSTRAINTS

### Tech Stack (Strict Versions)
```
Backend:  Python 3.11+ (NOT 3.12), FastAPI 0.104.1, SQLAlchemy 2.0.23 (async)
Frontend: Next.js 14.0.3, TypeScript, React 18
Database: PostgreSQL 15, Redis 7, MinIO
AI:       OpenAI 1.3.5, Anthropic 0.7.0
```

### Module Boundaries
```
apps/api/app/
├── api/v1/endpoints/  → HTTP handlers only, thin layer
├── services/          → Business logic (async required)
├── models/            → SQLAlchemy ORM (async)
├── schemas/           → Pydantic validation
├── core/              → Config, DB, security, exceptions
└── middleware/        → Rate limiting, CORS, auth

apps/web/
├── app/               → Next.js App Router pages
├── components/        → React components
└── lib/api.ts         → Single API client (auto-refresh tokens)
```

### Database Patterns
```python
# ✅ Endpoints: Use dependency injection
async def endpoint(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))

# ✅ Background jobs: Use context manager
async def background_task():
    async with AsyncSessionLocal() as db:
        await db.execute(...)
        await db.commit()  # Explicit commit required
```

### Authentication
```python
# Users: Magic link → JWT (30 min access, 7 days refresh)
@router.get("/user-endpoint")
async def endpoint(user: User = Depends(get_current_user)): ...

# Admins: Password → Session
@router.get("/admin-endpoint")
async def endpoint(admin: User = Depends(get_admin_user)): ...
```

---

## 🟡 P2: QUALITY GATES

### Before Completing Any Task
- [ ] Code works (tested manually or with pytest)
- [ ] Types valid (`mypy` passes or explicitly handled)
- [ ] Linter clean (`ruff` passes)
- [ ] No security issues (IDOR checked, no SQL injection)
- [ ] Docs updated if behavior changed

### Temporary Solutions Protocol
Every hack/mock/TODO MUST be documented:
```python
# ⚠️ TEMPORARY: [description]
# See: /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #[N]
# TODO: [what to fix] | Priority: 🔴/🟡/🟢 | Time: Xh
```

### Error Handling
```python
# Use custom exceptions, not HTTPException
from app.core.exceptions import ValidationError, NotFoundError

raise ValidationError("Page count must be 3-200")  # 400
raise NotFoundError("Document not found")           # 404
```

---

## 🟢 P3: WORKFLOW

### Before Task
1. Read relevant docs (MASTER_DOCUMENT if architecture, DECISIONS_LOG if design choice)
2. Find existing patterns with `grep_search`
3. Understand current code with `read_file`

### During Task
1. Make minimal changes (smallest diff that works)
2. Follow existing code style
3. Add type hints to new code
4. Test as you go

### After Task
1. Verify with `read_file` - did changes apply correctly?
2. Run `grep_search` to confirm no duplicates/issues
3. Update docs if needed
4. Show proof of completion

### Definition of Done
```
✅ Code works
✅ Types valid
✅ Linter passes
✅ Security checked
✅ Proof shown
✅ Docs updated (if applicable)
```

---

## 📖 SSOT (Source of Truth Hierarchy)

| Priority | Document | Use For |
|----------|----------|---------|
| 1 | **This file** (`copilot-instructions.md`) | How to work, rules, constraints |
| 2 | **`DEBUG_PROTOCOL.md`** | Systematic debugging (4 phases, root cause) |
| 3 | **`AI_PLAYBOOK.md`** | Code patterns, examples, "how we do X" |
| 4 | **`docs/MASTER_DOCUMENT.md`** | Full technical reference |
| 5 | **`docs/sec/DECISIONS_LOG.md`** | Why we chose X over Y |
| 6 | **`docs/MVP_PLAN.md`** | Current status, TODOs, temporary solutions |

**Ignore:** `/docs/archive/`, `/reports/` (outdated)

---

## ❓ UNCERTAINTY PROTOCOL

### When Unsure
1. State what you're unsure about
2. List 2-3 options you're considering
3. Ask: "Which approach should I take?"
4. **Do not guess. Do not proceed without answer.**

### Red Flags (Stop & Ask)
- Code contradicts documentation
- Multiple valid approaches exist
- Change might break other parts
- Security implications unclear
- Business rule ambiguous

---

## 🎯 PROJECT CONTEXT (Quick Reference)

### Business Model
- Pay-per-page: €0.50/page (dynamic via admin)
- Currency: EUR only
- Pages: 3 min, 200 max
- Refunds: Auto on system error, manual approval for user requests

### Key Flows
1. **Auth:** Email → Magic link → JWT → Auto-refresh
2. **Payment:** Create intent → Stripe checkout → Webhook → Start generation
3. **Generation:** Outline → Sections (with RAG) → Quality check → Export DOCX/PDF

### Languages
- Content: EN, DE, FR, ES, IT, CS, UK
- UI: English (future: multi-language)

---

## 📊 OUTPUT FORMAT

### For Code Changes
```
## Changes Made
- File: `path/to/file.py`
  - Line X: [what changed]
  - Reason: [why]

## Proof
[grep/read_file output showing change]

## Testing
[How to verify it works]
```

### For Analysis/Review
```
## Summary
[1-2 sentences]

## Findings
1. [Finding with proof]
2. [Finding with proof]

## Recommendations
- [Action item]
```

---

## 🔧 QUICK COMMANDS

```bash
# Backend
cd apps/api && pytest tests/ -v                    # Run tests
cd apps/api && uvicorn main:app --reload           # Start dev server

# Frontend
cd apps/web && npm run dev                         # Start dev server
cd apps/web && npm test                            # Run tests

# Database
cd apps/api && alembic upgrade head                # Apply migrations
cd apps/api && alembic revision --autogenerate -m "desc"  # Create migration

# Infrastructure
cd infra/docker && docker-compose up -d            # Start DB/Redis/MinIO
```

---

**Remember: Quality > Speed. Proof > Assumptions. Ask > Guess.**

**For debugging, see: `.github/DEBUG_PROTOCOL.md`**
**For patterns and examples, see: `.github/AI_PLAYBOOK.md`**
