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
| [DECISIONS_LOG.md](./docs/DECISIONS_LOG.md) | All architectural decisions | To understand "why" |
| [.ai-instructions](./.ai-instructions) | Instructions for AI assistants | If you're an AI |

---

## 🏗️ Architecture

```
Next.js Frontend ──► FastAPI Backend ──► PostgreSQL
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                  Redis         MinIO
                    │             │
                    └──────┬──────┘
                           ▼
                    OpenAI / Anthropic
```

**Tech Stack:**
- **Backend:** FastAPI + SQLAlchemy + Pydantic
- **Frontend:** Next.js 14 + TypeScript + Tailwind
- **Database:** PostgreSQL 15 + Redis 7
- **AI:** OpenAI GPT-4 + Anthropic Claude
- **Storage:** MinIO (S3-compatible)
- **Payments:** Stripe

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

### Critical Fixes Needed (1 day work)
1. **IDOR Protection** - Add ownership checks
2. **JWT Hardening** - Strong keys required
3. **File Validation** - Magic bytes checking
4. **Backup Strategy** - Implement 3-2-1 rule

**Details:** MASTER_DOCUMENT.md Section 6.2

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