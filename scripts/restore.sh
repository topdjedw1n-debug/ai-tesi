#!/bin/bash
# Restore script for TesiGo application
# Restores PostgreSQL database from backup
# Usage: ./scripts/restore.sh <backup_file>

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if backup file is provided
if [ -z "$1" ]; then
    log_error "Usage: $0 <backup_file>"
    echo ""
    echo "Example: $0 ./backups/20231102_143022/db/postgres_20231102_143022.dump"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    log_error "Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

log_info "Preparing to restore from: ${BACKUP_FILE}"

# Check if pg_restore is available
if ! command -v pg_restore &> /dev/null; then
    log_error "pg_restore not found. Please install PostgreSQL client tools."
    exit 1
fi

# Get database connection details from environment or config
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-ai_thesis_platform}"
DB_USER="${POSTGRES_USER:-postgres}"

log_info "Database: ${DB_HOST}:${DB_PORT}/${DB_NAME} (User: ${DB_USER})"

# Warning and confirmation
echo ""
log_warn "⚠️  WARNING: This will OVERWRITE the current database!"
log_warn "All current data will be lost and replaced with backup data."
echo ""
read -p "Are you sure you want to continue? Type 'yes' to confirm: " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
    log_info "Restore cancelled by user"
    exit 0
fi

# Check backup file format
BACKUP_FORMAT=$(file "${BACKUP_FILE}")
log_info "Backup file format: ${BACKUP_FORMAT}"

# Try to restore
log_info "Starting database restore..."

if PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    "${BACKUP_FILE}" 2>&1; then
    log_info "Database restore completed successfully!"
else
    log_error "Database restore failed!"
    echo ""
    log_warn "If you see errors related to 'does not exist', try restoring without --clean flag:"
    log_warn "pg_restore -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} ${BACKUP_FILE}"
    exit 1
fi

log_info "Restore process completed!"
echo ""
echo "To verify the restore, check your database:"
echo "  psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -c 'SELECT COUNT(*) FROM users;'"
echo ""

