# Database Migrations

SQL migration scripts for the AI Thesis Platform database.

## Migration Files

1. **001_initial_schema.sql** - Initial database schema
2. **002_add_indexes.sql** - Performance indexes
3. **003_add_refunds.sql** - Refunds functionality
4. **004_add_settings.sql** - Platform settings
5. **005_add_missing_columns.sql** - Missing columns from models (2026-01-24)

## Running Migrations

### Local Development

```bash
# Run all migrations
psql -U postgres -d ai_thesis_platform -f migrations/001_initial_schema.sql
psql -U postgres -d ai_thesis_platform -f migrations/002_add_indexes.sql
# ... and so on
```

### Production (Docker)

```bash
# Run a specific migration
docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -f /path/to/migration.sql

# Or copy migration to container first
docker cp migrations/005_add_missing_columns.sql ai-thesis-postgres:/tmp/
docker exec ai-thesis-postgres psql -U postgres -d ai_thesis_platform -f /tmp/005_add_missing_columns.sql
```

### Using make (if available)

```bash
make migrate
```

## Migration Guidelines

1. **Always use `IF NOT EXISTS`** or `IF EXISTS` to make migrations idempotent
2. **Never modify existing migrations** - create new ones instead
3. **Test migrations locally** before running in production
4. **Include rollback instructions** in comments when possible
5. **Document breaking changes** in the migration file

## Schema Changes Log

### 2026-01-24 - Missing Columns Addition
- Added `user_sessions.is_active`, `last_activity`
- Added `ai_generation_jobs.total_tokens`, `cost_cents`, `success`, `ai_provider`, `ai_model`
- Added `documents.tokens_used`, `generation_time_seconds`, and other fields
- Added quality metrics to `document_sections`
