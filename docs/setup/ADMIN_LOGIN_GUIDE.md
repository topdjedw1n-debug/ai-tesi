# 🔑 Admin Login Guide - TesiGo

> Simple password-based admin authentication for testing

**Created:** 2025-11-27
**Status:** ✅ WORKING

---

## Quick Start

### 1. Prerequisites

```bash
# Start Docker infrastructure
cd /Users/maxmaxvel/AI\ TESI/infra/docker
docker-compose up -d

# Stop Docker API container (conflicts with local backend)
docker stop ai-thesis-api

# Start local backend
cd /Users/maxmaxvel/AI\ TESI/apps/api
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Login Credentials

```
Email:    admin@tesigo.com
Password: admin123
```

⚠️ **TESTING ONLY** - These credentials are hardcoded in `app.core.config.ADMIN_TEMP_PASSWORD`

---

## Authentication Flow

### Step 1: Login Request

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin-login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tesigo.com","password":"admin123"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 12,
    "email": "admin@tesigo.com",
    "full_name": "Admin User",
    "is_admin": true
  }
}
```

### Step 2: Use Access Token

```bash
TOKEN="<access_token_from_step_1>"

# Access protected endpoints
curl http://localhost:8000/api/v1/admin/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

---

## API Endpoint Details

### POST `/api/v1/auth/admin-login`

**Purpose:** Simple admin authentication without magic links

**Request Body:**
```json
{
  "email": "admin@tesigo.com",
  "password": "admin123"
}
```

**Validation:**
- User must exist in database
- User must have `is_admin = true`
- User must have `is_active = true`
- Password must match `settings.ADMIN_TEMP_PASSWORD`

**Success Response (200 OK):**
```json
{
  "access_token": "JWT_TOKEN_HERE",
  "token_type": "bearer",
  "user": {
    "id": 12,
    "email": "admin@tesigo.com",
    "full_name": "Admin User",
    "is_admin": true
  }
}
```

**Error Responses:**

**401 Unauthorized - Invalid Credentials:**
```json
{
  "error_code": "AUTHENTICATION_ERROR",
  "detail": "Invalid credentials or not an admin",
  "status_code": 401
}
```

**401 Unauthorized - Wrong Password:**
```json
{
  "error_code": "AUTHENTICATION_ERROR",
  "detail": "Invalid credentials",
  "status_code": 401
}
```

---

## Implementation Details

### Files Modified

1. **`/apps/api/app/api/v1/endpoints/auth.py`** (lines 395-451)
   - Added `AdminLoginRequest` Pydantic model
   - Added `admin_simple_login()` endpoint function

2. **`/apps/api/app/core/config.py`** (line 29)
   - Added `ADMIN_TEMP_PASSWORD = "admin123"`

3. **`/scripts/create-admin.sh`**
   - Script to create/update admin user in database
   - Sets `is_admin=true`, `is_super_admin=true`, `is_active=true`

### Database State

```sql
SELECT id, email, full_name, is_admin, is_super_admin, is_active
FROM users WHERE email='admin@tesigo.com';

-- Result:
-- id=12, email=admin@tesigo.com, full_name=Admin User
-- is_admin=true, is_super_admin=true, is_active=true
-- created_at=2025-11-27 16:12:10
```

---

## Testing Checklist

- ✅ Admin login endpoint responds (POST `/api/v1/auth/admin-login`)
- ✅ Returns valid JWT token
- ✅ Returns user data with `is_admin=true`
- ✅ Token format: `Bearer <JWT>`
- ⚠️ `/api/v1/auth/me` has schema validation issues (non-critical)

---

## Known Issues

### 1. UserResponse Schema Validation Error

**Symptom:** GET `/api/v1/auth/me` returns 500 error when using admin token

**Cause:** User schema requires `preferred_language`, `timezone`, `total_tokens_used` but admin user has NULL values

**Impact:** Non-critical for authentication testing

**Workaround:** Access admin panel directly without `/auth/me` validation

### 2. Logging Errors

**Symptom:** `KeyError: 'correlation_id'` in Loguru handler

**Cause:** Logging configuration expects correlation_id in context

**Impact:** Non-critical, doesn't affect functionality

---

## Security Notes

⚠️ **IMPORTANT: This is for TESTING ONLY**

**DO NOT use in production:**
- Hardcoded password (`admin123`)
- No password hashing
- No rate limiting
- No MFA/2FA
- No session management

**Production recommendations:**
1. Use existing magic link authentication (`/api/v1/admin/auth/login`)
2. Implement proper password hashing (bcrypt)
3. Add rate limiting (3 attempts per hour)
4. Enable MFA for admin accounts
5. Use session management with Redis

---

## Troubleshooting

### Backend returns 404 for admin-login

**Solution:**
```bash
# Check if endpoint is registered
curl -s http://localhost:8000/openapi.json | jq '.paths | keys | .[]' | grep admin-login

# Should return: "/api/v1/auth/admin-login"

# If not found:
1. Check auth.py has the endpoint (line 410)
2. Restart backend completely
3. Check for Python syntax errors
```

### Database connection refused

**Solution:**
```bash
# Start Docker infrastructure
cd infra/docker
docker-compose up -d

# Verify database is running
docker-compose ps | grep postgres
```

### Port 8000 already in use

**Solution:**
```bash
# Stop Docker API container
docker stop ai-thesis-api

# Or kill local process
lsof -ti :8000 | xargs kill -9
```

---

## Next Steps

Now that admin authentication works:

1. **Access Admin Panel**
   - Open http://localhost:3000/admin (if frontend is running)
   - Use token from login response

2. **Test Document Generation**
   - Create test document
   - Start generation
   - Monitor progress

3. **Test RAG APIs**
   - Configure Perplexity/Tavily/Serper API keys
   - Test search functionality
   - Verify citations

4. **Test Export**
   - Generate test document
   - Export to DOCX
   - Export to PDF
   - Verify formatting

---

## Future Improvements

**Planned for production:**
- [ ] Replace with magic link auth
- [ ] Add proper password hashing
- [ ] Implement rate limiting
- [ ] Add MFA/2FA
- [ ] Session management with Redis
- [ ] Audit logging for admin actions

**See:** `/docs/MVP_PLAN.md` for full roadmap

---

**Last Updated:** 2025-11-27
**Author:** AI Assistant
**Related Docs:**
- `/docs/MVP_PLAN.md` - MVP testing plan
- `/docs/COMPONENTS_CHECKLIST.md` - Component verification
- `/scripts/create-admin.sh` - Admin user setup
