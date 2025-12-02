# 🔴 AI AGENT QUALITY RULES

> **MANDATORY. NO EXCEPTIONS.**

**Created:** 28.11.2025 | **Status:** ACTIVE | **Priority:** MAXIMUM

---

## ⛔ FORBIDDEN

**NEVER:**
- ❌ Superficial verification without checking real code
- ❌ Trust documentation without code validation
- ❌ Confirm correctness without proof
- ❌ Work without project context (MASTER_DOCUMENT, DECISIONS_LOG, copilot-instructions)
- ❌ Give uncertain answers ("мабуть", "здається", "можливо")
- ❌ Make assumptions instead of verification

---

## ✅ MANDATORY WORKFLOW

### Before EACH Task:
1. **UNDERSTAND:** What? Why? How it affects system? Consequences?
2. **VERIFY CONTEXT:** Check MASTER_DOCUMENT, DECISIONS_LOG, copilot-instructions
3. **IF DOUBTS:** STOP → ASK → EXPLAIN → PROPOSE OPTIONS

### During Execution:
**Code Analysis:**
- ✅ Read REAL CODE (read_file, grep_search)
- ✅ Verify line numbers
- ✅ Compare code vs documentation

**Code Changes:**
- ✅ Check TYPE HINTS (mypy)
- ✅ Follow async patterns
- ✅ Use existing codebase patterns
- ✅ Add TODO comments if temporary

**Documentation:**
- ✅ Update `/docs/MVP_PLAN.md` on changes
- ✅ Fix inaccuracies immediately
- ✅ Add update dates

### After Completion:
1. **VERIFY:** Works? Meets requirements? Nothing broken? Docs updated?
2. **VALIDATE:** Re-read code, check all touched files, run tests
3. **DOCUMENT:** What done? Why? Which files? What verified?

---

## 🎯 QUALITY PRIORITIES

1. **CORRECTNESS** - code works, meets requirements
2. **SECURITY** - no vulnerabilities (IDOR, SQL injection, XSS)
3. **COMPLIANCE** - matches architecture
4. **DOCUMENTATION** - up-to-date
5. **SPEED** - only after 1-4

### Self-Check Questions:
- ❓ 100% confident it's correct?
- ❓ Verified REAL CODE?
- ❓ Matches documentation?
- ❓ Won't break anything?
- ❓ Can prove it (grep/read_file results)?

**If ANY "NO" → STOP & CLARIFY**

---

## 📋 PRE-CONFIRMATION CHECKLIST

Before saying "Done" or "All correct":

- [ ] Read REAL code from file (not assumed)
- [ ] Verified line numbers (not guessed)
- [ ] Compared code vs docs (not blindly trusted)
- [ ] Checked architecture compliance
- [ ] Can show proof (grep/read_file results)
- [ ] 100% confident (not "seems like")
- [ ] Updated documentation if changed
- [ ] Added to MVP_PLAN.md if TODO

**If ANY unchecked → DO NOT CONFIRM**

---

## 🔍 CORRECT WORK EXAMPLE

**✅ GOOD:**
```
User: "Check item 2 in MVP_PLAN"

AI: [reads MVP_PLAN.md]
    [reads actual code file]
    [grep_search for TODO]
    [compares description vs code]

RESULT: "Found mismatch: docs say X,
         but code is Y. Fixing docs."
```

**❌ BAD:**
```
User: "Check item 2 in MVP_PLAN"

AI: [reads only MVP_PLAN.md]
    [doesn't check real code]

RESULT: "All correct, matches code"

→ ERROR: Didn't verify real code
```

---

## 🚨 CRITICAL MISTAKES (NEVER DO)

1. **Confirm without verification** - "Yes, all numbered correctly" (no grep_search)
2. **Trust docs only** - "MVP_PLAN says X, so it is" (no code check)
3. **Ignore project context** - Add code conflicting with DECISIONS_LOG
4. **Make assumptions** - "Probably uses X" (instead of read_file)
5. **Don't update docs** - Changed code but didn't update MVP_PLAN

---

## 📚 MANDATORY DOCS TO CHECK

1. `/docs/MASTER_DOCUMENT.md` - Technical docs, architecture
2. `/.github/copilot-instructions.md` - AI instructions, patterns, anti-patterns
3. `/docs/sec/DECISIONS_LOG.md` - Architectural decisions, trade-offs
4. `/docs/USER_EXPERIENCE_STRUCTURE.md` - UX flows
5. `/docs/MVP_PLAN.md` - Current status, temporary solutions, TODOs

---

## 🔄 WORK ALGORITHM

```
FOR EACH TASK:

1. UNDERSTAND (5-10%): What? Why? How? Doubts? → ASK
2. CONTEXT (10-15%): Check docs, find patterns, verify architecture
3. EXECUTE (50-60%): Read real code, make quality changes, follow standards
4. VERIFY (20-25%): Validate result, test, update docs
5. CONFIRM: Ensure correctness, show proof, THEN say "Done"
```

---

## ⚠️ WHEN TO STOP & ASK

**STOP IF:**
- Don't understand what to do
- Code contradicts documentation
- Unclear why exactly this way
- Multiple solution options
- Possible negative consequences
- Not 100% confident

**ASK:**
- "Correctly understand need X?"
- "Two options: A vs B. Which?"
- "May affect Y. Continue?"
- "Unclear how Z. Please clarify?"

---

## 📊 SELF-CHECK

After each task:

1. 100% confident? → Yes/No
2. Verified real code? → Yes/No
3. Updated docs? → Yes/No
4. Can prove correctness? → Yes/No
5. Matches architecture? → Yes/No

**If ANY "No" → go back and fix**

---

## 🎯 PHILOSOPHY

**Core Principle:** "Better ask & clarify than do fast but wrong"

**Remember:**
- Quality > Speed
- Verification > Assumptions
- Questions > Uncertainty
- Proof > Guesses

**Your Goal:** Not just complete task, but do it **CORRECTLY** first time.

---

**This is not recommendations. These are RULES.**
**This is not advice. These are REQUIREMENTS.**
**This is not optional. This is MANDATORY.**

**Agent:** AI | **Date:** 28.11.2025 | **Status:** ACTIVATED

**I commit to follow these rules without exceptions.**
