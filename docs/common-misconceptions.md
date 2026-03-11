# Common Misconceptions and Pitfalls

> A practical guide to avoid common mistakes when working with OpenClaw agent workflows.

## Concept Confusions

### 1. Cron vs Heartbeat

**Why it's confusing:**
- Both relate to "scheduled execution"
- Often appear together in workflow configurations

**Correct understanding:**
- **Cron** = Trigger (WHEN to run)
- **Heartbeat** = Task content (WHAT to run)
- Relationship: Cron triggers → reads HEARTBEAT.md → executes task

**Analogy:**
- Cron = Alarm clock (rings at set time)
- Heartbeat = Todo list (what needs to be done)

---

### 2. sessionTarget vs payload.kind

**Why it's confusing:**
- Both affect execution behavior
- Documentation doesn't clearly state they "must match"

**Correct combinations:**
- ✅ `main + systemEvent` = Lightweight tasks (<1 minute)
- ✅ `isolated + agentTurn` = Independent tasks (long-running, needs isolation)
- ❌ Mixed combinations may cause cron to trigger but not execute

**Decision tree:**
```
Need scheduled automatic execution?
├─ Task < 1 minute and needs main session context?
│   └─ Yes → main + systemEvent
└─ No
    └─ isolated + agentTurn
```

---

### 3. Payload Independence

**Why it's confusing:**
- Assumption that isolated sessions automatically inherit AGENTS.md/SOUL.md
- Assumption that they can "rely on main session rules"

**Fact:**
- Payload is an **independent instruction source**
- Does **NOT** automatically read AGENTS.md, SOUL.md
- Must explicitly include all required instructions

**Correct approach:**
```
# ❌ Bad (assumes automatic AGENTS.md reading)
Check system status for me

# ✅ Correct (explicitly states all instructions)
Read HEARTBEAT.md if it exists (workspace context).
Follow it strictly.
Do not infer or repeat old tasks from prior chats.
If nothing needs attention, reply HEARTBEAT_OK.
```

---

## Practical Traps

### 4. One-time Cron Forgetting autoDelete

**Problem:**
- `schedule.kind: "at"` (one-time)
- Forgot to add `autoDelete: true`
- Expired cron jobs remain in the list indefinitely

**Solution:**
```yaml
schedule:
  kind: "at"
  at: "2026-03-07T09:00:00+08:00"
autoDelete: true  # ← Must add this
```

---

### 5. Forgetting to Sync Cron Payload After Rule Changes

**Problem:**
- Changed rules in AGENTS.md
- Assumed isolated sessions would automatically know
- But payload is independent and doesn't auto-inherit

**Solution:**
Every time you change AGENTS.md rules, check if related cron payloads need同步 updates.

---

### 6. Timeout Too Short

**Problem:**
- Isolated sessions have default timeout
- External APIs may be slow (seconds to tens of seconds)
- Script execution may take several minutes

**Solution:**
```yaml
session:
  timeoutSeconds: 300  # 5 minutes
```

---

## Best Practices

### Before Creating a Cron Job

1. **Determine the execution pattern:**
   - One-time or recurring?
   - Lightweight or long-running?
   - Needs main session context or isolated?

2. **Choose the right combination:**
   - Quick check: `main + systemEvent`
   - Background task: `isolated + agentTurn`

3. **Write explicit payloads:**
   - Include all necessary instructions
   - Don't rely on implicit context
   - Test the payload manually first

### Maintenance Checklist

- [ ] Review cron jobs monthly for expired one-time jobs
- [ ] Sync payload instructions when AGENTS.md changes
- [ ] Monitor timeout settings for slow operations
- [ ] Check session target matches task requirements

## Related Documentation

- [`cron.md`](./cron.md) — Complete cron system documentation
- [`nodes.md`](./nodes.md) — Node configuration and management
- [`ios_arch.md`](./ios_arch.md) — iOS architecture specifics