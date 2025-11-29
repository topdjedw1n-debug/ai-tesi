# 🚀 QUICK START - TesiGo

> Запустити проект за 5 хвилин

---

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- 8GB RAM minimum
- 10GB free disk space

---

## 🎯 5-Minute Setup

### Step 1: Clone & Navigate
```bash
git clone https://github.com/tesigo/tesigo-app.git
cd tesigo-app
```

### Step 2: Start Infrastructure (2 min)
```bash
cd infra/docker
docker-compose up -d

# Wait for healthy status
docker-compose ps
```

### Step 3: Configure Environment (1 min)
```bash
# Backend
cd ../../apps/api
cp .env.example .env
# Edit .env - add your OpenAI/Anthropic keys

# Frontend
cd ../web
cp .env.local.example .env.local
```

### Step 4: Start Backend (1 min)
```bash
cd ../api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Step 5: Start Frontend (1 min)
```bash
# New terminal
cd apps/web
npm install
npm run dev
```

### ✅ Done!
Open http://localhost:3000

---

## 🔑 Default Credentials

### MinIO (File Storage)
- URL: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

### PostgreSQL
- Host: `localhost:5432`
- Database: `tesigo_db`
- Username: `tesigo_user`
- Password: `tesigo_password`

### Redis
- URL: `redis://localhost:6379`
- No auth required (local)

---

## 🧪 Test the Setup

### 1. Check Health
```bash
# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:3000/api/health
```

### 2. Create Test User
```bash
# Request magic link
curl -X POST http://localhost:8000/api/v1/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### 3. Check Logs
```bash
# Backend logs
tail -f apps/api/logs/app.log

# Docker logs
docker-compose logs -f
```

---

## 🛠️ Common Issues

### Port Already in Use
```bash
# Find process
lsof -i :8000
# Kill it
kill -9 <PID>
```

### Docker Permission Denied
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Database Connection Error
```bash
docker-compose restart postgres
docker-compose logs postgres
```

### Module Not Found
```bash
# Recreate virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

---

## 📝 Environment Variables

### Minimal .env for Backend
```env
# Required
DATABASE_URL=postgresql://tesigo_user:tesigo_password@localhost/tesigo_db
SECRET_KEY=your-secret-key-min-32-chars-long-change-this
JWT_SECRET=another-secret-key-min-32-chars-change-this

# AI (at least one required)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Optional for local
ENVIRONMENT=development
DEBUG=true
```

### Minimal .env.local for Frontend
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## 🚦 Next Steps

1. **Read full documentation:** [MASTER_DOCUMENT.md](./MASTER_DOCUMENT.md)
2. **Understand decisions:** [sec/DECISIONS_LOG.md](./sec/DECISIONS_LOG.md)
3. **Setup production:** [setup/PRODUCTION_DEPLOYMENT_PLAN.md](./setup/PRODUCTION_DEPLOYMENT_PLAN.md)
4. **Run tests:** `pytest tests/`
5. **Check security:** Fix critical issues from Section 6.2 in MASTER_DOCUMENT

---

## 💡 Quick Commands

```bash
# Start everything
./scripts/start-local.sh

# Stop everything
docker-compose down

# Reset database
docker-compose down -v
docker-compose up -d

# View all logs
docker-compose logs -f

# Run tests
pytest tests/ -v

# Format code
ruff format .

# Type check
mypy app/
```

---

## 🆘 Getting Help

1. Check [MASTER_DOCUMENT.md](./MASTER_DOCUMENT.md) - Section 9: Known Issues
2. Search in [sec/DECISIONS_LOG.md](./sec/DECISIONS_LOG.md) for reasoning
3. Check Docker logs: `docker-compose logs <service>`
4. Check app logs: `tail -f apps/api/logs/app.log`

---

**Time to first request: ~5 minutes**
**Time to production-ready: See MASTER_DOCUMENT.md Section 7.3**
