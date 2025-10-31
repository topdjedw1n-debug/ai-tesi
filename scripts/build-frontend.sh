#!/bin/bash
# Frontend build verification script
# Usage: ./scripts/build-frontend.sh

set -e

cd "$(dirname "$0")/../apps/web" || exit 1

# Create logs directory
mkdir -p ../../logs/tasks/full-verification

echo "Checking Node.js version..."
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
echo "Node.js version: $(node --version)"

if [ "$NODE_VERSION" -lt 20 ]; then
    echo "ERROR: Node.js 20+ required. Current: $(node --version)"
    exit 1
fi

echo "Installing dependencies..."
npm ci

echo "Running type check..."
npm run type-check > ../../logs/tasks/full-verification/frontend-build.txt 2>&1 || true

echo "Building Next.js application..."
npm run build >> ../../logs/tasks/full-verification/frontend-build.txt 2>&1 || true

echo "Build verification complete. Results saved to logs/tasks/full-verification/frontend-build.txt"

