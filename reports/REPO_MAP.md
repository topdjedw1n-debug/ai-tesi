# Repository Map

**Generated:** 2025-11-02  
**Project:** TesiGo v2.3 - AI Academic Paper Generator

---

## Directory Structure

```
AI TESI/
├── apps/
│   ├── api/                    # FastAPI Backend
│   │   ├── app/
│   │   │   ├── api/v1/endpoints/  # 4 endpoint modules
│   │   │   ├── core/              # 7 core modules
│   │   │   ├── models/            # 4 models
│   │   │   ├── schemas/           # 4 schemas
│   │   │   ├── services/          # 12 services
│   │   │   │   └── ai_pipeline/   # 5 pipeline modules
│   │   │   └── middleware/        # 2 middleware
│   │   ├── tests/                # 15 test files
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── mypy.ini
│   │
│   └── web/                    # Next.js Frontend
│       ├── app/                 # 3 pages
│       ├── components/          # 4 component groups
│       │   ├── dashboard/       # 4 components
│       │   ├── layout/          # 3 components
│       │   ├── sections/        # 4 components
│       │   └── ui/              # 4 components
│       ├── package.json
│       └── tsconfig.json
│
├── docs/                       # Documentation
│   ├── archive/               # Historical reports
│   ├── DEVELOPMENT_ROADMAP.md
│   └── PRODUCTION_DEPLOYMENT_PLAN.md
│
├── infra/docker/              # Infrastructure
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
│
├── scripts/                   # Utility scripts
├── tests/                     # Integration tests
└── reports/                   # Audit reports (this directory)
```

---

## File Counts

### Backend (apps/api)
- **Python files:** 48
- **Test files:** 15
- **Endpoint modules:** 4 (auth, documents, generate, admin)
- **Services:** 12
- **AI Pipeline modules:** 5
- **Models:** 4
- **Schemas:** 4

### Frontend (apps/web)
- **React components:** 15+
- **Pages:** 3
- **TypeScript files:** 20+

---

## Module Sizes

### Largest Modules (Backend)
1. `document_service.py` - 235 statements
2. `background_jobs.py` - 170 statements
3. `citation_formatter.py` - 166 statements
4. `rate_limit.py` - 164 statements
5. `config.py` - 185 statements

### Largest Modules (Frontend)
Based on component count and structure:
1. Dashboard components - 4 files
2. Section components - 4 files
3. Layout components - 3 files

---

## Test Coverage by Module

**Overall:** 49%

**Top 5 Covered:**
1. `exceptions.py` - 92%
2. `monitoring.py` - 92%
3. `logging.py` - 100%
4. `models` - 94-100%
5. `csrf.py` - 100%

**Bottom 5 Covered:**
1. `admin_service.py` - 14%
2. `humanizer.py` - 20%
3. `background_jobs.py` - 20%
4. `citation_formatter.py` - 24%
5. `endpoints/admin.py` - 25%

---

## Dependencies

### Backend (Python)
- **Total:** 56 packages
- **Key:** FastAPI, SQLAlchemy, Pydantic, OpenAI, Anthropic, MinIO, Redis

### Frontend (NPM)
- **Total:** ~40 packages
- **Key:** Next.js 14, React 18, TypeScript, Tailwind CSS

---

## Documentation Files

**Total:** 30+ markdown files

**Key Documents:**
- `P0_P1_COMPLETION_SUMMARY.md` - Claimed milestones
- `PROJECT_ROADMAP.md` - Development plan
- `AUDIT_SUMMARY_UK.md` - Previous audit
- `QUALITY_GATE.md` - Quality standards
- Various archived reports

---

## Configuration Files

### Backend
- `pyproject.toml` - Ruff, Black, isort config
- `mypy.ini` - Type checking config
- `pytest.ini` - Test configuration
- `requirements.txt` - Dependencies
- `.env` (not in repo) - Environment variables

### Frontend
- `package.json` - NPM dependencies
- `tsconfig.json` - TypeScript config
- `tailwind.config.js` - Styling config
- `next.config.js` - Next.js config

### Infrastructure
- `docker-compose.yml` - Development setup
- `docker-compose.prod.yml` - Production setup
- `Dockerfile` (x2) - Container definitions

---

## Dead Code / Unused Files

**Identified:**
- `apps/api/test.db` - Should be in .gitignore
- `apps/api/app/utils/` - Empty directory
- `apps/web/hooks/` - Empty directory
- `apps/web/types/` - Empty directory
- `apps/web/utils/` - Empty directory

---

## Duplicate Code

**Not Found:** No obvious code duplication detected in initial scan

---

## Architecture Notes

### Backend Architecture
- **Pattern:** Clean Architecture with services
- **Database:** SQLAlchemy async
- **Auth:** JWT with magic links
- **Storage:** MinIO for documents
- **Caching:** Redis

### Frontend Architecture
- **Framework:** Next.js 14 App Router
- **Styling:** Tailwind CSS
- **State:** Context API
- **Forms:** React Hook Form + Zod
- **API:** Axios

---

**End of Repository Map**
