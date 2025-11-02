#!/bin/bash
# Backup script for TesiGo application
# Creates backups of PostgreSQL database and MinIO storage
# Usage: ./scripts/backup.sh

set -e

# Configuration
BACKUP_BASE_DIR="${BACKUP_DIR:-./backups}"
BACKUP_DIR="${BACKUP_BASE_DIR}/$(date +%Y%m%d_%H%M%S)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    log_warn "Running as root - be careful with file permissions"
fi

log_info "Starting TesiGo backup process..."
log_info "Backup directory: ${BACKUP_DIR}"

# Create backup directories
mkdir -p "${BACKUP_DIR}/db"
mkdir -p "${BACKUP_DIR}/minio"

# PostgreSQL backup
if command -v pg_dump &> /dev/null; then
    log_info "Creating PostgreSQL backup..."
    
    # Get database connection details from environment or config
    DB_HOST="${POSTGRES_HOST:-localhost}"
    DB_PORT="${POSTGRES_PORT:-5432}"
    DB_NAME="${POSTGRES_DB:-ai_thesis_platform}"
    DB_USER="${POSTGRES_USER:-postgres}"
    
    # Build pg_dump command
    PGDMP_CMD="pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME}"
    
    # Try to run pg_dump
    if PGPASSWORD="${POSTGRES_PASSWORD}" ${PGDMP_CMD} \
        --format=custom \
        --compress=9 \
        --no-owner \
        --no-privileges \
        -f "${BACKUP_DIR}/db/postgres_${TIMESTAMP}.dump" 2>/dev/null; then
        log_info "PostgreSQL backup created successfully"
    else
        log_warn "PostgreSQL backup skipped - connection failed or database not accessible"
        log_warn "Run manually: ${PGDMP_CMD} --format=custom --compress=9 -f /path/to/backup.dump"
    fi
else
    log_warn "pg_dump not found - PostgreSQL backup skipped"
fi

# MinIO/S3 backup
if [ -d "/minio/data/documents" ]; then
    log_info "Creating MinIO backup..."
    
    if tar -czf "${BACKUP_DIR}/minio/documents_${TIMESTAMP}.tar.gz" \
        -C /minio/data documents 2>/dev/null; then
        log_info "MinIO backup created successfully"
    else
        log_warn "MinIO backup failed"
    fi
elif [ -d "infra/docker/uploads" ]; then
    log_info "Creating local MinIO backup from infra/docker/uploads..."
    
    if tar -czf "${BACKUP_DIR}/minio/documents_${TIMESTAMP}.tar.gz" \
        -C infra/docker uploads 2>/dev/null; then
        log_info "Local MinIO backup created successfully"
    else
        log_warn "Local MinIO backup failed"
    fi
else
    log_warn "MinIO data directory not found - skipping MinIO backup"
fi

# Calculate backup size
BACKUP_SIZE=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1 || echo "unknown")
log_info "Backup size: ${BACKUP_SIZE}"

# Old backup cleanup (keep backups older than 7 days)
log_info "Cleaning up old backups..."
if [ -d "${BACKUP_BASE_DIR}" ]; then
    OLD_BACKUPS=$(find "${BACKUP_BASE_DIR}" -type f -mtime +7 2>/dev/null | wc -l)
    
    if [ "${OLD_BACKUPS}" -gt 0 ]; then
        find "${BACKUP_BASE_DIR}" -type f -mtime +7 -delete 2>/dev/null || true
        log_info "Removed ${OLD_BACKUPS} old backup file(s)"
    else
        log_info "No old backups to remove"
    fi
fi

log_info "Backup process completed successfully!"
log_info "Backup location: ${BACKUP_DIR}"

# Display backup summary
echo ""
echo "=== Backup Summary ==="
echo "Backup directory: ${BACKUP_DIR}"
echo "Backup size: ${BACKUP_SIZE}"
echo "Timestamp: ${TIMESTAMP}"
echo ""
echo "To restore, run: ./scripts/restore.sh ${BACKUP_DIR}/db/postgres_${TIMESTAMP}.dump"
echo ""

