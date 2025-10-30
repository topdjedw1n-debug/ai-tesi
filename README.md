# AI Thesis Platform

A production-grade MVP for generating academic papers (thesis sections) using AI with a modern web stack.

## 🏗️ Architecture

This is a monorepo containing:

- **Frontend**: Next.js 14 with App Router, TypeScript, and Tailwind CSS
- **Backend**: FastAPI with Pydantic, SQLAlchemy, and async support
- **Database**: PostgreSQL with async support
- **Storage**: MinIO for document storage
- **Caching**: Redis for session management and caching
- **Containerization**: Docker and Docker Compose

## 📁 Project Structure

```
AI TESI/
├── apps/
│   ├── web/                 # Next.js frontend
│   │   ├── app/            # App Router pages
│   │   ├── components/     # React components
│   │   ├── lib/           # Utilities and API client
│   │   └── hooks/         # Custom React hooks
│   └── api/                # FastAPI backend
│       ├── app/
│       │   ├── api/       # API endpoints
│       │   ├── core/      # Core configuration
│       │   ├── models/    # Database models
│       │   ├── schemas/   # Pydantic schemas
│       │   └── services/  # Business logic
│       └── requirements.txt
├── infra/
│   └── docker/            # Docker configuration
│       ├── docker-compose.yml
│       └── init.sql
└── .cursor/
    └── config.json        # Cursor IDE configuration
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

### Using Docker (Recommended)

1. **Clone and navigate to the project:**
   ```bash
   cd "AI TESI"
   ```

2. **Start all services:**
   ```bash
   cd infra/docker
   docker-compose up -d
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - MinIO Console: http://localhost:9001

### Local Development

1. **Backend Setup:**
   ```bash
   cd apps/api
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

2. **Frontend Setup:**
   ```bash
   cd apps/web
   npm install
   npm run dev
   ```

3. **Database Setup:**
   ```bash
   # Start PostgreSQL, Redis, and MinIO
   cd infra/docker
   docker-compose up postgres redis minio -d
   ```

## 🔧 Configuration

### Environment Variables

Create `.env` files in the respective app directories:

**Backend (`apps/api/.env`):**
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_thesis_platform
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
SECRET_KEY=your-secret-key
```

**Frontend (`apps/web/.env.local`):**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📚 API Endpoints

### Authentication
- `POST /api/v1/auth/magic-link` - Request magic link
- `POST /api/v1/auth/verify-magic-link` - Verify magic link
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/logout` - Logout

### Generation
- `POST /api/v1/generate/outline` - Generate document outline
- `POST /api/v1/generate/section` - Generate specific section
- `GET /api/v1/generate/models` - List available AI models

### Documents
- `GET /api/v1/documents` - List user documents
- `POST /api/v1/documents` - Create new document
- `GET /api/v1/documents/{id}` - Get document details
- `DELETE /api/v1/documents/{id}` - Delete document
- `GET /api/v1/documents/{id}/export/{format}` - Export document

### Health
- `GET /health` - Health check

## 🎯 Features

### Current MVP Features
- ✅ User authentication with magic links
- ✅ Document outline generation
- ✅ Section-by-section generation
- ✅ Multiple AI providers (OpenAI, Anthropic)
- ✅ Document export (DOCX, PDF)
- ✅ Responsive dashboard
- ✅ Real-time generation status
- ✅ Usage tracking and analytics

### Planned Features
- 🔄 Document collaboration
- 🔄 Advanced AI model selection
- 🔄 Citation management
- 🔄 Template system
- 🔄 Admin panel
- 🔄 API rate limiting
- 🔄 Email notifications

## 🛠️ Development

### Code Quality
- **Frontend**: ESLint, Prettier, TypeScript strict mode
- **Backend**: Black, isort, mypy, pytest
- **Database**: SQLAlchemy with async support

### Testing
```bash
# Backend tests
cd apps/api
pytest

# Frontend tests
cd apps/web
npm test
```

### Database Migrations
```bash
cd apps/api
alembic upgrade head
```

## 🐳 Docker Services

- **postgres**: PostgreSQL 15 database
- **redis**: Redis 7 for caching
- **minio**: MinIO for object storage
- **api**: FastAPI backend service
- **web**: Next.js frontend service

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For support and questions, please open an issue in the repository.
