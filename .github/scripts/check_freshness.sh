#!/usr/bin/env bash
set -euo pipefail

# Doc Freshness SLA (MVP)
# - Opens doc-review issues when docs/usecases exceed thresholds.
# - ALSO opens issues for missing last_validated (unreviewed) so docs don't slip through forever.
# - Does NOT mutate repo files (no auto-stale frontmatter writes).
#
# Controls:
# - MAX_ISSUES: cap number of issues created per run (0 = unlimited). Default: 20.

REPO="${GITHUB_REPOSITORY:-thepagent/claw-info}"
LABEL="doc-review"
GRACE_DAYS="${GRACE_DAYS:-7}"
MAX_ISSUES="${MAX_ISSUES:-20}"

threshold_for() {
  case "$1" in
    usecases/*) echo 14 ;;
    docs/*) echo 28 ;;
    *) echo 56 ;;
  esac
}

# Returns 0 if label exists or was created; 1 if unavailable.
ensure_label() {
  if gh label list -R "$REPO" --search "$LABEL" --limit 100 >/dev/null 2>&1; then
    # gh label list doesn't fail if label missing, so check output
    if gh label list -R "$REPO" --search "$LABEL" --limit 100 | awk '{print $1}' | grep -Fxq "$LABEL"; then
      return 0
    fi
  fi

  # Try to create it; if not permitted, continue without label.
  gh label create "$LABEL" -R "$REPO" -c "#C2E0C6" -d "Doc freshness review" >/dev/null 2>&1 || return 1
  return 0
}

label_ok=0
if ensure_label; then label_ok=1; fi

TODAY_EPOCH="$(date +%s)"
CREATED_ISSUES=0

reached_cap() {
  # MAX_ISSUES=0 means unlimited
  [[ "$MAX_ISSUES" == "0" ]] && return 1
  (( CREATED_ISSUES >= MAX_ISSUES ))
}

create_issue() {
  local title="$1"
  local body="$2"
  local assignee="${3:-}"

  # De-duplication: search by machine tag (exact, stable)
  local tag
  tag="$(printf "%s" "$body" | sed -n 's/^DocFreshnessPath: //p' | head -n1)"
  if [[ -n "$tag" ]]; then
    existing_count=$(gh issue list -R "$REPO" --state open --search "\"DocFreshnessPath: $tag\"" --json number --jq 'length' 2>/dev/null || echo 0)
    if [[ "$existing_count" != "0" ]]; then
      return 0
    fi
  fi

  # Compose args safely
  args=("gh" "issue" "create" "-R" "$REPO" "--title" "$title" "--body" "$body")
  if [[ "$label_ok" == "1" ]]; then
    args+=("--label" "$LABEL")
  fi

  local out=""

  if [[ -n "$assignee" ]]; then
    # Assignee can fail if user is not assignable; fall back gracefully.
    if out=$("${args[@]}" --assignee "$assignee" 2>/dev/null); then
      CREATED_ISSUES=$((CREATED_ISSUES + 1))
      return 0
    fi
  fi

  if out=$("${args[@]}" 2>/dev/null); then
    CREATED_ISSUES=$((CREATED_ISSUES + 1))
  fi
}

scan_file() {
  local f="$1"
  local last owner age threshold

  last=$(awk -F': ' '/^last_validated:/{print $2; exit}' "$f" | tr -d '\r')
  owner=$(awk -F': ' '/^validated_by:/{print $2; exit}' "$f" | tr -d '\r')
  threshold=$(threshold_for "$f")

  if [[ -z "$last" ]]; then
    title="[Doc Review] $f missing last_validated"
    body=$(cat <<EOF
DocFreshnessPath: $f

This document is missing required frontmatter field: \`last_validated\`.

- Path: \`$f\`
- Required: add frontmatter like:
  - \`last_validated: YYYY-MM-DD\`
  - \`validated_by: <github-username>\`

Please update within ${GRACE_DAYS} days.
EOF
)
    create_issue "$title" "$body" "${owner:-}"
    return 0
  fi

  # Validate date parse
  if ! last_epoch=$(date -d "$last" +%s 2>/dev/null); then
    title="[Doc Review] $f invalid last_validated"
    body=$(cat <<EOF
DocFreshnessPath: $f

The \`last_validated\` value could not be parsed as a date.

- Path: \`$f\`
- last_validated: \`$last\`

Expected format: YYYY-MM-DD
EOF
)
    create_issue "$title" "$body" "${owner:-}"
    return 0
  fi

  age=$(( (TODAY_EPOCH - last_epoch) / 86400 ))

  if (( age > threshold )); then
    title="[Doc Review] $f needs validation"
    body=$(cat <<EOF
DocFreshnessPath: $f

This document exceeded its review window.

- Path: \`$f\`
- Last validated: \`$last\` (${age} days ago)
- Threshold: ${threshold} days

Please verify against current source code and update \`last_validated\` (and \`validated_by\` if ownership changed) within ${GRACE_DAYS} days.
EOF
)
    create_issue "$title" "$body" "${owner:-}"
  fi
}

# Scan docs + usecases markdown (skip missing dirs)
DIRS=()
[[ -d docs ]] && DIRS+=(docs)
[[ -d usecases ]] && DIRS+=(usecases)

if (( ${#DIRS[@]} == 0 )); then
  echo "No docs/ or usecases/ directories found; skipping."
  exit 0
fi

while IFS= read -r -d '' f; do
  if reached_cap; then
    echo "Reached MAX_ISSUES=${MAX_ISSUES}; stopping early."
    break
  fi

  scan_file "$f"

  if reached_cap; then
    echo "Reached MAX_ISSUES=${MAX_ISSUES}; stopping early."
    break
  fi
done < <(find "${DIRS[@]}" -type f -name "*.md" -print0)

echo "Created issues this run: ${CREATED_ISSUES} (MAX_ISSUES=${MAX_ISSUES})"