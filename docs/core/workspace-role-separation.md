# Workspace role separation: AGENTS.md, SOUL.md, IDENTITY.md, USER.md (and memory)

This document explains the intended responsibilities of the common workspace files so new users don’t mix concerns.

> TL;DR: **Rules go in `AGENTS.md`**, **persona goes in `SOUL.md`**, **identity card goes in `IDENTITY.md`**, **user preferences go in `USER.md`**.

## The core idea

Separate **operational policy** (what the agent may do) from **style/persona** (how it speaks) and from **user-specific preferences** (what this particular user wants).

This keeps:
- policy reviewable and auditable
- persona consistent
- user preferences safe and easy to update

## File responsibilities

### `AGENTS.md` — Workspace rules & operational policy (what is allowed)

Use for:
- approval gates (e.g., “ask first before edits/commands/external messages”)
- safety constraints and red lines
- tool usage conventions
- repo-specific workflows

Avoid:
- user private details
- long persona / tone definitions

### `SOUL.md` — Persona & voice (how the agent behaves and speaks)

Use for:
- tone, mannerisms, cultural sensibility
- teaching style and interaction patterns
- boundaries as *behavioral* guidance (not operational permissions)

Avoid:
- instructions that require frequent per-user updates
- secrets / tokens / personal data

### `IDENTITY.md` — Short identity card (quick “who am I”)

Use for:
- name
- short description (“what kind of creature/assistant”)
- vibe keywords
- signature emoji

Keep it short: it’s a “business card”, not a policy document.

### `USER.md` — User preferences & boundaries (what this user wants)

Use for:
- how to address the user
- language preferences
- autonomy tolerance (how often to ask)
- recurring context (timezone, formatting preferences)

This is where you should put “defaults the user wants”, without changing global safety posture.

## Memory: `MEMORY.md` vs `memory/`

Many setups use a two-layer memory structure:

- `memory/YYYY-MM-DD.md` (or similar): **daily, raw notes** (highly personal)
- `MEMORY.md`: **curated long-term memory** (still personal)

**Security note:** both are typically sensitive. Treat them as private by default.

## Common pitfalls (and how to avoid them)

- Putting user private details into `AGENTS.md` → leaks if the repo is shared.
- Mixing persona (`SOUL.md`) with permissions (`AGENTS.md`) → unclear boundaries.
- Treating `USER.md` as “policy” → different users need different autonomy; policy should be stable.

## Related docs

- Approval-first workflow: see #297.
- Agent-owned GitHub repo / backups: see #298.
