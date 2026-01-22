# ⚠️ DEPRECATED - AGENT_QUALITY_RULES.md

> **This file is deprecated. All rules have been consolidated.**

**Deprecated:** 2026-01-22 | **Reason:** Consolidation into layered documentation

---

## 📚 New Structure (Source of Truth)

| Layer | File | Purpose |
|-------|------|---------|
| **A** | `.github/copilot-instructions.md` | Policy, rules, constraints, workflow |
| **B** | `.github/AI_PLAYBOOK.md` | Patterns, examples, "how we do X" |
| **C** | `.github/HOW_TO_WORK_WITH_AI_AGENT.md` | Human guide for prompts |

---

## 🎯 Quick Reference (P0 Rules Only)

For full details, see `copilot-instructions.md`. Here's the essential:

### START PROTOCOL (Every Task)
```
1. RESTATE:     What am I doing?
2. ASSUMPTIONS: What I assume
3. PLAN:        Steps (3-7)
4. RISKS:       Edge cases
5. OUTPUT:      What I'll deliver
```

### Non-Negotiable Rules
1. ✅ Show plan before executing
2. ✅ Read real code, don't assume
3. ✅ Show proof for every claim
4. ✅ If 3+ fixes fail → stop, discuss architecture
5. ✅ Update docs when changing code

### Forbidden Actions
- ❌ Execute without showing plan
- ❌ Say "Done" without proof
- ❌ Use "мабуть", "здається", "probably"
- ❌ Trust docs without code verification

---

## 🔗 Migration

If you were using rules from this file:

| Old Rule | New Location |
|----------|--------------|
| FORBIDDEN actions | `copilot-instructions.md` → P0: NON-NEGOTIABLE |
| MANDATORY WORKFLOW | `copilot-instructions.md` → P3: WORKFLOW |
| PRE-CONFIRMATION CHECKLIST | `copilot-instructions.md` → P2: QUALITY GATES |
| Code examples | `AI_PLAYBOOK.md` |
| Human prompts | `HOW_TO_WORK_WITH_AI_AGENT.md` |

---

**Do not update this file. Use the new structure.**
