# ✅ CHECKLIST: Before Creating Temporary Solution

> **Quick reference before writing ANY temporary code**

---

## 🚨 STOP! Before you write temporary code, answer:

### ❓ Is this temporary?

- [ ] Mock data / hardcoded values
- [ ] Skipped validation / security check
- [ ] Simplified logic (missing edge cases)
- [ ] Missing error handling
- [ ] Performance shortcut
- [ ] "TODO: Fix this later" comment

**If ANY checkbox is checked → FOLLOW THIS PROTOCOL!**

---

## 📝 3-STEP PROTOCOL

### Step 1: Add TODO in Code
```python
# ⚠️ TEMPORARY: [Brief description]
# See /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #[number]
# TODO: [What needs to be done]
#   [Specific code example]
```

### Step 2: Add Entry to MVP_PLAN.md

**File:** `/docs/MVP_PLAN.md`  
**Section:** "⚠️ КРИТИЧНО: ТИМЧАСОВІ РІШЕННЯ"

**Template:**
```markdown
#### [N]. **[Title]**
**Дата:** YYYY-MM-DD
**Файл:** `/path/to/file.py`
**Проблема:** [Why temporary]
**Тимчасове рішення:**
```code
[Show the temporary code]
```
**Що ПОТРІБНО зробити:**
- [ ] Task 1
- [ ] Task 2
**Пріоритет:** 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW
**Оцінка часу:** X hours
```

### Step 3: Commit Both Together
```bash
git add [your-file.py] docs/MVP_PLAN.md
git commit -m "feat: [feature] (with temporary solution documented)"
```

---

## 🎯 PRIORITY GUIDE

**🔴 HIGH (Fix before production):**
- Security bypasses
- Data validation skips
- Payment logic shortcuts
- Authentication workarounds

**🟡 MEDIUM (Fix soon):**
- Mock data for user-facing features
- Missing error handling
- Performance issues
- Incomplete business logic

**🟢 LOW (Nice to have):**
- Internal tools
- Development helpers
- Non-critical optimizations

---

## ✅ CHECKLIST BEFORE COMMIT

- [ ] TODO comment added to code
- [ ] Entry added to `/docs/MVP_PLAN.md`
- [ ] Date specified
- [ ] File path specified
- [ ] Action plan specified
- [ ] Priority assigned
- [ ] Time estimated

---

## 🚫 NEVER DO THIS

```python
# ❌ NO DOCUMENTATION
return {"count": 0}  # temporary

# ❌ VAGUE TODO
# TODO: fix this later

# ❌ NO REFERENCE
# This is temporary, need to replace
```

---

## ✅ ALWAYS DO THIS

```python
# ✅ FULL DOCUMENTATION
# ⚠️ TEMPORARY: Mock data - See /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #1
# TODO: Replace with real DB query:
#   count = await db.execute(select(func.count(User.id)))
#   return {"count": count.scalar()}
return {"count": 0}
```

---

## 📚 REFERENCES

- **Full Protocol:** [`/docs/TEMPORARY_SOLUTIONS_PROTOCOL.md`](./TEMPORARY_SOLUTIONS_PROTOCOL.md)
- **Tracking File:** [`/docs/MVP_PLAN.md`](./MVP_PLAN.md) → "ТИМЧАСОВІ РІШЕННЯ"
- **AI Instructions:** [`/.github/copilot-instructions.md`](../.github/copilot-instructions.md)

---

## 💡 WHY THIS MATTERS

**Without documentation:**
- 🔴 Temporary becomes permanent
- 🔴 Technical debt explodes
- 🔴 Bugs hide in "temporary" code
- 🔴 Production surprises

**With documentation:**
- ✅ Clear technical debt tracking
- ✅ Controlled refactoring priorities
- ✅ Safe production deployment
- ✅ Team knowledge sharing

---

**Print this. Pin this. Live this.**

**No temporary solution without documentation. Ever.**
