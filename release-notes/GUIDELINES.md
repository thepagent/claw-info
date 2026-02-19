# Release Notes Guidelines

This document defines the guidelines for generating release notes for each OpenClaw release.

## File Naming Convention

- **Filename**: `release-notes/YYYY-MM-DD.md`
- **Date**: Use the release date (e.g., `2026-02-15.md`)
- **Header**: Include the release date in the title (e.g., `# OpenClaw v2026.02.15 Release Notes (2026-02-15)`)

## Document Structure

### 1. Header

Include:
- Release title with version and date
- GitHub Release link (e.g., `[GitHub Release](https://github.com/openclaw/openclaw/releases/tag/v2026.2.15)`)

### 2. Overview

Provide a high-level summary using bullet points, grouped by category:

- **功能更新 (Features)** - New capabilities added
- **安全性提升 (Security)** - Security-related improvements
- **錯誤修復 (Bug Fixes)** - Bug fixes and stabilizations

Each item should start with the star rating followed by a short description.

### 3. Detailed Sections

After the overview, provide detailed sections for each category:

- **功能更新 (Features) - by Star Rating**
- **安全性提升 (Security) - by Star Rating**
- **錯誤修復 (Bug Fixes) - by Star Rating**

Within each section, list items in descending order of star rating (⭐⭐⭐ first, then ⭐⭐, then ⭐).

### 4. Item Format

Each item should follow this format:

```markdown
### ⭐⭐⭐ Item Title ([#PR_NUMBER](https://github.com/openclaw/openclaw/pull/PR_NUMBER))
- **用途**: What this feature/fix does
- **解決問題**: Problem it solves
- **影響**: Impact and benefits
```

Always include the PR/Issue number at the end.

#### 引用格式（Link rule, recommended）

- 在 release notes 內出現的 `#PR_NUMBER` / `#ISSUE_NUMBER` **一律要可點**（統一用 Markdown link）。
  - Upstream OpenClaw PR：`[#12345](https://github.com/openclaw/openclaw/pull/12345)`
  - `claw-info` 自己的 issue：`[#54](https://github.com/thepagent/claw-info/issues/54)`
- GitHub 雖然常會自動把 `#54` 變成連結，但**建議仍用明確的 Markdown link** 以保持一致、避免漏連。

此規則可讓讀者快速驗證來源、降低歧義。

### 5. Summary Table

Include a summary table showing:

| 類別 | 3 顆星 | 2 顆星 | 1 顆星 | 摘要 |
|------|--------|--------|--------|------|
| 功能更新 | X | X | X | X |
| 安全性 | X | X | X | X |
| 錯誤修復 | X | X | X | X |
| **總計** | X | X | X | X |

### 6. Footer

Include:
- **發佈日期**: Release date (YYYY-MM-DD)
- **版本**: Release version (e.g., 2026.02.15)
- **狀態**: Production Ready
- **GitHub Release**: Link to the release

## Star Rating Guidelines

Use star ratings to indicate importance:

| Stars | Criteria |
|-------|----------|
| ⭐⭐⭐ | Critical - Security fixes, major features, breaking changes, critical bug fixes |
| ⭐⭐ | Important - Significant improvements, important bug fixes, important features |
| ⭐ | Minor - Small improvements, optimizations, minor bug fixes, documentation updates |
| (none) | Routine -日常 maintenance, minor tweaks |

### Star Rating Examples

**⭐⭐⭐ (Critical)**
- Security vulnerabilities (SHA-1 → SHA-256, container escape prevention)
- Major new features (Discord Components v2, nested subagents)
- Critical bug fixes (DM messaging failures, media loss)

**⭐⭐ (Important)**
- Important security improvements (token redaction, sandbox hardening)
- Significant functionality (streaming fixes, session continuity)
- Important quality improvements (XSS prevention, input validation)

**⭐ (Minor)**
- Usability improvements (emoji support, UX refinements)
- Minor bug fixes (command deduplication, state restoration)
- Documentation and tooling improvements

## Language and Style

- **Primary Language**: Traditional Chinese (zh-TW)
- **Tone**: Professional and neutral
- **No Personality**: Avoid any persona or character-specific language
- **Concise**: Be brief but informative
- **Action-oriented**: Focus on what changed and why it matters

## Content Requirements

### For Each Release

- **At least 10 items per category** (Features, Security, Bug Fixes)
- **Complete details**: Ensure every item has用途, 解決問題, 影響
- **PR/Issue references**: Always include PR/Issue numbers

### Categories

1. **功能更新 (Features)** - New capabilities
2. **安全性提升 (Security)** - Security-related improvements
3. **錯誤修復 (Bug Fixes)** - Bug fixes and stabilizations

## Best Practices

1. **Review GitHub releases first** - Always check the official GitHub releases for the target version
2. **Sort by importance** - Order items by star rating (most important first)
3. **Include GitHub link** - Add direct link to the release in the header
4. **Use markdown tables** - For summary and complex information
5. **Proofread** - Ensure all PR links are correct and descriptions are accurate

## Checklist Before Commit

- [ ] GitHub release page reviewed for accuracy
- [ ] All items include star ratings
- [ ] Items sorted by star rating (descending)
- [ ] All items include PR/Issue numbers
- [ ] All items have用途, 解決問題, 影響
- [ ] Summary table completed
- [ ] GitHub release link included
- [ ] No persona/language (professional only)

## Example File Structure

```markdown
# OpenClaw v2026.02.15 版本發佈說明

[GitHub Release](https://github.com/openclaw/openclaw/releases/tag/v2026.2.15)

## 概述

...

## 功能更新 (Features) - by Star Rating

### ⭐⭐⭐ Item 1
...

### ⭐⭐ Item 2
...

## 安全性提升 (Security) - by Star Rating

...

## 錯誤修復 (Bug Fixes) - by Star Rating

...

## 總結

| 類別 | 3 顆星 | 2 顆星 | 1 顆星 | 摘要 |
|------|--------|--------|--------|------|
| ... | ... | ... | ... | ... |

**發佈日期**: 2026-02-15  
**版本**: 2026.02.15  
**狀態**: Production Ready  
**GitHub Release**: [link](https://...)
```

---

*Last Updated: 2026-02-15*
