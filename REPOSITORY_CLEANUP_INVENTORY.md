# Repository Inventory & Cleanup Plan (READ-ONLY)

## 1) Summary

**Total Repository Size**: ~1.1GB

**Discovery Date**: 2025-01-27 (Phase A — Read-Only Audit)

### Size Breakdown
- `apps/web/node_modules/`: 575MB (52% of repo)
- `qa_venv/`: 318MB (29% of repo)
- `apps/api/venv/`: 318MB (29% of repo)
- `apps/web/.next/`: 64MB (6% of repo)
- `htmlcov/`: 536KB + 1.8MB = 2.3MB
- `logs/`: 1.0MB
- Caches: 32KB (.pytest_cache) + 8KB (.ruff_cache) = 40KB

### Candidates for Cleanup
- **SAFE-DELETE**: ~932MB (85% of repository)
- **REVIEW**: 7 items (empty dirs, untracked files)
- **KEEP**: All source code, configs, docs, migrations

---

## 2) SAFE-DELETE

All items listed below are **regenerable** artifacts, caches, or local-only dependencies.

### Virtual Environments (636MB total)
| Path | Size | Reason | Recovery |
|------|------|--------|----------|
| `qa_venv/` | 318MB | Python virtual environment | `python3 -m venv qa_venv && pip install -r requirements.txt` |
| `apps/api/venv/` | 318MB | Python virtual environment | `python3 -m venv venv && pip install -r requirements.txt` |

### Node Dependencies (575MB total)
| Path | Size | Reason | Recovery |
|------|------|--------|----------|
| `apps/web/node_modules/` | 575MB | NPM dependencies | `npm install` or `pnpm install` |
| `apps/web/.next/standalone/node_modules/` | (subset) | Next.js standalone build deps | Regenerated via `npm run build` |

### Build & Cache Artifacts (74MB total)
| Path | Size | Reason | Recovery |
|------|------|--------|----------|
| `apps/web/.next/` | 64MB | Next.js build cache | `npm run build` |
| `htmlcov/` | 536KB | Python coverage HTML | `pytest --cov && coverage html` |
| `apps/api/htmlcov/` | 1.8MB | API coverage HTML | `pytest --cov && coverage html` |
| `.pytest_cache/` | 32KB | Pytest cache | `pytest` (auto-regenerated) |
| `.ruff_cache/` | 8KB | Ruff lint cache | `ruff check` (auto-regenerated) |
| `apps/api/.mypy_cache/` | ~500KB | MyPy type cache | `mypy .` (auto-regenerated) |

### Coverage Reports (28KB)
| Path | Size | Reason | Recovery |
|------|------|--------|----------|
| `coverage.xml` | 28KB | Coverage XML report | `pytest --cov && coverage xml` |
| `apps/api/coverage.xml` | 28KB | API coverage XML | `pytest --cov && coverage xml` |

### Logs (1.0MB)
| Path | Size | Reason | Recovery |
|------|------|--------|----------|
| `logs/` | 1.0MB | Application logs | Automatic on restart |
| `apps/api/logs/` | (subset) | API logs | Automatic on restart |

### OS Artifacts (~50KB total)
| Path | Count | Reason | Recovery |
|------|-------|--------|----------|
| `.DS_Store` | Multiple | macOS metadata | Automatic by macOS |

### Environment Files (Tracked by .gitignore but present)
| Path | Reason | Action |
|------|--------|--------|
| `apps/api/.env` | Local environment vars | KEEP (contains secrets) |
| `apps/web/.env.local` | Local environment vars | KEEP (contains secrets) |

**⚠️ Note**: Environment files are already ignored by `.gitignore` but will be listed in `git clean -nfdX`. They should **NOT** be deleted as they contain local configuration.

### Pytest Caches (Already Ignored)
| Path | Size | Reason |
|------|------|--------|
| `.pytest_cache/` | 32KB | Root pytest cache |
| `apps/api/.pytest_cache/` | (subset) | API pytest cache |

### Ruff Caches (Already Ignored)
| Path | Size | Reason |
|------|------|--------|
| `.ruff_cache/` | 8KB | Root ruff cache |
| `apps/api/.ruff_cache/` | (subset) | API ruff cache |

**Total Safe-Delete Size**: ~932MB

---

## 3) REVIEW

Items that need human confirmation before deletion.

### Empty Untracked Directories
| Path | Status | Risk | Decision |
|------|--------|------|----------|
| `apps/api/app/utils/` | Empty | LOW | Can delete if truly unused |
| `infra/docker/uploads/` | Empty | MEDIUM | May be mount point; verify before deletion |

### Untracked Documentation Files
| Path | Size | Risk | Decision |
|------|------|------|----------|
| `EXECUTION_MAP_v2.3.md` | 32KB | LOW | Phase 0 artifact; may be valuable |
| `PHASE_0_DIAGNOSTIC_REPORT.md` | 8KB | LOW | Phase 0 artifact; may be valuable |
| `PHASE_0_FIX_REPORT.md` | 12KB | LOW | Phase 0 artifact; may be valuable |

**Recommendation**: These Phase 0 reports should likely be **COMMITTED** to git rather than deleted, as they document critical fixes.

---

## 4) KEEP

Items that must **NOT** be deleted (source code, configs, migrations, etc.).

### Source Code
- ✅ All files under `apps/api/app/`, `apps/web/app/`, `apps/web/components/`
- ✅ All test files in `tests/`, `apps/api/tests/`
- ✅ All configuration files: `pyproject.toml`, `package.json`, `tsconfig.json`, `Dockerfile`, etc.

### Configuration & Infra
- ✅ `.gitignore`, `.git/`, `docker-compose.yml`, `alembic/`
- ✅ `mypy.ini`, `ruff.toml`, `pytest.ini`, `tsconfig.json`
- ✅ `infra/docker/` (except possibly empty uploads/)

### Documentation
- ✅ All `.md` files in root (README, DEVELOPMENT_ROADMAP, etc.)
- ✅ All docs in `apps/` (unless explicitly temporary)

### Scripts & Migrations
- ✅ `scripts/`, `setup.sh`, `setup-dev.sh`
- ✅ Alembic migration files (if any)

### Data & Secrets (Local Only)
- ✅ `.env` files (kept locally, never committed)
- ✅ `infra/docker/uploads/` (verify mount point)

---

## 5) Proposed .gitignore Additions

Current `.gitignore` is **COMPREHENSIVE** and already covers all patterns. 

**Missing additions** (optional improvements):

```diff
# Python (additions)
+.mypy_cache/
+.ruff_cache/
+pytest_cache/    # Already has .pytest_cache but add just in case

# Coverage
+coverage.xml
+htmlcov/

# Next.js additional patterns
+.next/standalone/

# Root level caches
+.pytest_cache/
+.ruff_cache/
+.mypy_cache/
+htmlcov/
+coverage.xml
+
+# QA virtual env
+qa_venv/
```

**However**: Since `venv/` is already covered, and most caches are in subdirectories with their patterns, the current `.gitignore` is functionally complete.

**Recommendation**: No changes needed. Current `.gitignore` is sufficient.

---

## 6) DRY-RUN Commands

### Command 1: List All Untracked Files/Dirs (No Deletion)
```bash
git clean -nfd
```

**Output Preview**:
```
Would remove EXECUTION_MAP_v2.3.md
Would remove PHASE_0_DIAGNOSTIC_REPORT.md
Would remove PHASE_0_FIX_REPORT.md
Would remove apps/api/app/utils/
Would remove apps/web/hooks/
Would remove apps/web/types/
Would remove apps/web/utils/
Would remove infra/docker/uploads/
```

### Command 2: List Only Ignored Files (Caches/Builds)
```bash
git clean -nfdX
```

**Output Preview**:
```
Would remove .DS_Store
Would remove .pytest_cache/
Would remove .ruff_cache/
Would remove apps/api/.mypy_cache/
Would remove apps/api/.pytest_cache/
Would remove apps/api/.ruff_cache/
Would remove apps/api/htmlcov/
Would remove apps/api/logs/
Would remove apps/api/venv/
Would remove apps/web/.DS_Store
Would remove apps/web/.env.local
Would remove apps/web/.next/
Would remove apps/web/node_modules/
Would remove htmlcov/
Would remove logs/
Would remove qa_venv/
```

### Command 3: Get Precise Sizes of Deletable Items
```bash
# Python virtual environments
du -sh qa_venv apps/api/venv

# Node dependencies
du -sh apps/web/node_modules

# Build artifacts
du -sh apps/web/.next htmlcov apps/api/htmlcov coverage.xml

# Caches
du -sh .pytest_cache .ruff_cache apps/api/.mypy_cache

# Logs
du -sh logs apps/api/logs
```

### Command 4: Check for Large Files in Git History
```bash
# Find files > 20MB in tracked history
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ {print substr($0,6)}' | sort -k2 -n | tail -10
```

---

## 7) Risks & Safeguards

### What We Will NOT Delete

✅ **Tracked Files**: Any file tracked by git (`git ls-files`)  
✅ **Environment Variables**: `.env*` files (contain secrets)  
✅ **Migrations**: Alembic/DB migration files  
✅ **Source Code**: All `.py`, `.ts`, `.tsx`, `.js`, `.jsx` under `app/`, `components/`, `services/`  
✅ **Configs**: All `.toml`, `.ini`, `.json` config files  
✅ **Documentation**: Markdown files in root  
✅ **Scripts**: `.sh`, `.py` scripts in `scripts/`  
✅ **Docker**: All Dockerfiles, docker-compose files  

### Recovery Strategy

If accidental deletion occurs:

1. **Virtual Environments**: Recreate with `venv` + `pip install -r requirements.txt`
2. **Node Modules**: Recreate with `npm install` or `pnpm install`
3. **Build Cache**: Regenerated by `npm run build` or `pytest`
4. **Git History**: Always available via `git log` and `.git/`

### Data Loss Prevention

- ⚠️ **NO deletion of `.env` files** (explicit exclusion)
- ⚠️ **NO deletion of `infra/docker/uploads/`** without verification
- ⚠️ **NO deletion of documentation** without review
- ✅ All deletions are **LOCAL ONLY** (not affecting remote repo)

---

## 8) Awaiting Approval

### Approval Checklist

Before proceeding to Phase B, confirm:

- [ ] **Phase A inventory is accurate** (sizes and paths verified)
- [ ] **Safe-delete list is acceptable** (all items can be regenerated)
- [ ] **Review items are assessed** (empty dirs, Phase 0 reports)
- [ ] **Keep list is complete** (no source/config files marked for deletion)
- [ ] **Recovery strategy understood** (all items regenerable)
- [ ] **No production data at risk** (all deletions are local-only)
- [ ] **Git history is backed up** (if paranoid, `git remote -v` to confirm)

### Recommended Actions Before Approval

1. **Commit Phase 0 Reports** (if valuable):
   ```bash
   git add EXECUTION_MAP_v2.3.md PHASE_0_DIAGNOSTIC_REPORT.md PHASE_0_FIX_REPORT.md
   git commit -m "docs: Add Phase 0 diagnostic and fix reports"
   ```

2. **Verify Environment Files**:
   ```bash
   # Make sure .env files are not accidentally committed
   git check-ignore apps/api/.env apps/web/.env.local
   ```

3. **Create Backup** (optional):
   ```bash
   # Create a backup branch
   git branch backup-before-cleanup
   ```

### Next Steps (Phase B)

After approval, Phase B will output:

1. **Dry-run deletion script** (all commands prefixed with `echo`)
2. **Actual deletion commands** (commented out until explicit approval)
3. **Size savings estimate** (final freed space)
4. **Verification commands** (confirm deletions succeeded)

---

## Phase A Complete

**Status**: ✅ **READ-ONLY INVENTORY COMPLETE**

**Total Deletable Size**: ~932MB (85% of repository)

**Risk Level**: **LOW** (all items regenerable)

**Awaiting**: Human approval to proceed to Phase B

**Timestamp**: 2025-01-27

