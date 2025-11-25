# 🎓 TesiGo - AI-Powered Academic Paper Generation

> Generate high-quality academic papers with AI, guaranteed plagiarism-free

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.0+-black.svg)](https://nextjs.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## 🚀 Quick Start

```bash
# Clone and setup in 5 minutes
git clone https://github.com/tesigo/tesigo-app.git
cd tesigo-app

# Start everything
cd infra/docker && docker-compose up -d
cd ../../apps/api && uvicorn main:app --reload
# New terminal
cd apps/web && npm run dev

# Open browser
open http://localhost:3000
```

**Full setup guide:** [docs/QUICK_START.md](./docs/QUICK_START.md)

---

## 📚 Documentation

| Document | Description | When to Read |
|----------|-------------|--------------|
| [MASTER_DOCUMENT.md](./docs/MASTER_DOCUMENT.md) | Complete technical documentation | Always first |
| [QUICK_START.md](./docs/QUICK_START.md) | 5-minute setup guide | To run locally |
| [ДОСТУП_ДО_СТОРІНОК.md](./docs/ДОСТУП_ДО_СТОРІНОК.md) | **NEW:** All pages, admin panel & API endpoints | To access interfaces |
| [STEP_BY_STEP_PRODUCTION_GUIDE.md](./docs/STEP_BY_STEP_PRODUCTION_GUIDE.md) | **NEW:** Detailed production setup (8 steps) | Before deployment |
| [QUICK_FIX_GUIDE.md](./docs/QUICK_FIX_GUIDE.md) | **NEW:** Fast P0 bug fixes (2 hours) | For critical bugs |
| [DECISIONS_LOG.md](./docs/DECISIONS_LOG.md) | All architectural decisions | To understand "why" |
| [.ai-instructions](./.ai-instructions) | Instructions for AI assistants | If you're an AI |

---

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Next.js 14    │─────▶│   FastAPI 0.104  │─────▶│ PostgreSQL 15│
│   Frontend      │      │   Backend        │      │   Database   │
└─────────────────┘      └──────────────────┘      └──────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            ┌─────────────┐         ┌─────────────┐
            │  Redis 7    │         │   MinIO     │
            │  Cache      │         │  Storage    │
            └─────────────┘         └─────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │  OpenAI / Anthropic   │
                    │      AI APIs          │
                    └───────────────────────┘
```

**Tech Stack:**
- **Backend:** FastAPI 0.104 + SQLAlchemy 2.0 + Pydantic 2.5
- **Frontend:** Next.js 14 + TypeScript + Tailwind CSS
- **Database:** PostgreSQL 15 + Redis 7
- **AI:** OpenAI GPT-4/3.5 + Anthropic Claude 3.5
- **Storage:** MinIO (S3-compatible)
- **Payments:** Stripe
- **Monitoring:** Prometheus + Sentry

---

## 📁 Project Structure

```
AI TESI/
├── apps/
│   ├── web/                    # Next.js 14 Frontend
│   │   ├── app/               # App Router (7 pages)
│   │   ├── components/        # React components (16 files)
│   │   ├── hooks/            # Custom React hooks
│   │   └── utils/            # Utilities
│   └── api/                   # FastAPI Backend
│       ├── app/
│       │   ├── api/v1/endpoints/  # 7 API routers
│       │   ├── services/          # 18 services
│       │   ├── models/            # 5 database models
│       │   ├── schemas/           # Pydantic schemas
│       │   ├── core/              # Config, deps, monitoring
│       │   └── middleware/        # Rate limit, CSRF
│       ├── tests/            # 115+ tests (48% coverage)
│       └── requirements.txt
├── infra/
│   └── docker/
│       ├── docker-compose.yml        # Development
│       └── docker-compose.prod.yml   # Production
├── docs/                      # 15+ documentation files
├── reports/                   # Audit & QA reports
└── scripts/                   # Deployment scripts
```

**Key Stats:**
- **7 API Routers:** auth, documents, generate, jobs, admin, payment, user
- **18 Services:** AI pipeline, auth, payments, background jobs, etc.
- **115+ Tests:** 48% coverage (target: 80%)
- **Production Ready:** 80% (after P0 fixes)

---

## ✨ Features

### For Users
- 🤖 AI-powered paper generation
- ✅ Plagiarism-free guarantee
- 📄 Export to DOCX/PDF
- 💾 Auto-save & versioning
- 📊 Real-time progress tracking
- 💳 Pay-per-page model (€0.50/page)

### For Developers
- 🔥 100% async Python
- 📝 Full type hints
- 🔒 Security-first design
- 📊 Prometheus metrics
- 🪵 Structured logging
- 🧪 Comprehensive tests

---

## 🛠️ Development

### Prerequisites
- Python 3.11+ (not 3.12!)
- Node.js 18+
- Docker & Docker Compose
- 8GB RAM minimum

### Environment Setup
```bash
# Backend
cp apps/api/.env.example apps/api/.env
# Add your OpenAI/Anthropic API keys

# Frontend
cp apps/web/.env.local.example apps/web/.env.local
```

### Running Tests
```bash
# Backend tests
cd apps/api
pytest tests/ -v

# Type checking
mypy app/

# Linting
ruff check .
```

---

## 🚢 Deployment

### Production Checklist
- [ ] Fix critical security issues (see MASTER_DOCUMENT.md Section 6.2)
- [ ] Set strong SECRET_KEY and JWT_SECRET (32+ chars)
- [ ] Configure Stripe webhooks
- [ ] Setup SSL certificates
- [ ] Configure backups
- [ ] Setup monitoring

### Deploy Command
```bash
cd infra/docker
docker-compose -f docker-compose.prod.yml up -d
```

**Full deployment guide:** See MASTER_DOCUMENT.md Section 7

---

## 🔒 Security

### Critical Fixes Needed (1 day work) - **GUIDES AVAILABLE**
1. ✅ **IDOR Protection** - Add ownership checks
2. ✅ **JWT Hardening** - Strong keys required
3. ✅ **File Validation** - Magic bytes checking
4. ⚠️ **Email Integration** - Add SMTP service

**Quick Fix:** See [QUICK_FIX_GUIDE.md](./docs/QUICK_FIX_GUIDE.md)
**Full Setup:** See [STEP_BY_STEP_PRODUCTION_GUIDE.md](./docs/STEP_BY_STEP_PRODUCTION_GUIDE.md)

---

## 📊 Project Status

### ✅ Completed
- Core functionality
- AI integration
- Payment system
- User authentication
- Document generation

### 🚧 TODO Before Launch
- Security fixes (1 day)
- BackgroundJob integration
- Webhook verification
- Basic monitoring

### 📅 Roadmap
See MASTER_DOCUMENT.md Section 10

---

## 🤝 Contributing

1. Read [DECISIONS_LOG.md](./docs/DECISIONS_LOG.md) to understand our choices
2. Follow code style in [.ai-instructions](./.ai-instructions)
3. Update MASTER_DOCUMENT.md for API changes
4. Add tests for new features
5. Keep it simple

---

## 📝 License

Proprietary - All rights reserved

---

## 🆘 Support

- **Documentation:** [docs/MASTER_DOCUMENT.md](./docs/MASTER_DOCUMENT.md)
- **Known Issues:** MASTER_DOCUMENT.md Section 9
- **Quick Start:** [docs/QUICK_START.md](./docs/QUICK_START.md)

---

**Built with ❤️ using FastAPI and Next.js**
