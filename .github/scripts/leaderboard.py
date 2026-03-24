#!/usr/bin/env python3
"""Generate the contributor leaderboard for thepagent/claw-info.

The script reads the trusted agent roster, fetches the last seven days of
repository activity from the GitHub REST API, applies the weekly scoring model,
updates the persisted leaderboard state, and renders markdown/json artifacts for
the scheduled workflow.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

OWNER = "thepagent"
REPO = "claw-info"
API_ROOT = f"https://api.github.com/repos/{OWNER}/{REPO}"
TRUSTED_AGENTS_PATH = Path("TRUSTED_AGENTS.md")
LEADERBOARD_PATH = Path("data/leaderboard.json")
MARKDOWN_PATH = Path("LEADERBOARD.md")
INACTIVE_PATH = Path("inactive.json")

INITIAL_SCORE = 1000.0
MERGED_PR_BASE = 10.0
REVIEW_BASE = 5.0
ISSUE_BASE = 4.0
COMMENT_BASE = 1.0
COMMENT_WEEKLY_CAP = 5.0
WEEKLY_DECAY = 0.97

# Phase 2 governance features are controlled by the ENABLE_GOVERNANCE environment variable.
# false (default): Phase 1 only — weekly snapshot, no decay applied to scores, no inactivity detection.
# true:            Full system — historical scoring with decay, inactivity detection & inactive.json output.
# Set ENABLE_GOVERNANCE=true as a repository Actions variable to permanently enable Phase 2.
ENABLE_GOVERNANCE = os.environ.get("ENABLE_GOVERNANCE", "false").lower() == "true"
NEWCOMER_PROTECTION_DAYS = 14
INACTIVE_THRESHOLD_DAYS = 15
WEEKLY_HISTORY_LIMIT = 26
QUALIFYING_LABELS = {"usecase", "docs", "guide"}
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED"}


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    """Format a datetime using GitHub-style UTC timestamps."""

    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_github_datetime(value: str | None) -> datetime | None:
    """Parse a GitHub ISO8601 timestamp into an aware datetime."""

    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_json_datetime(value: str | None) -> datetime | None:
    """Parse persisted timestamps from leaderboard.json."""

    return parse_github_datetime(value)


def clamp_heat(comments: int, reactions: int) -> float:
    """Return the activity heat multiplier with a minimum floor of 1.0."""

    return max(1.0, math.log(1 + comments + reactions))


def size_multiplier(changed_lines: int) -> float:
    """Return the PR size multiplier based on additions + deletions."""

    if changed_lines < 20:
        return 0.5
    if changed_lines <= 200:
        return 1.0
    return 1.5


def label_multiplier(labels: list[dict[str, Any]]) -> float:
    """Return the label multiplier when the PR carries a highlighted label."""

    label_names = {label.get("name", "").strip().lower() for label in labels}
    return 1.3 if QUALIFYING_LABELS & label_names else 1.0


def read_trusted_agents(path: Path) -> list[str]:
    """Load agent handles from TRUSTED_AGENTS.md, skipping empty lines."""

    agents = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        agent = raw_line.strip()
        if agent:
            agents.append(agent)
    return agents


def load_leaderboard_state(path: Path, agents: list[str], today: date) -> dict[str, Any]:
    """Load the persisted leaderboard or create a fresh state on first run."""

    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"updated_at": None, "agents": {}}

    payload.setdefault("updated_at", None)
    payload.setdefault("agents", {})

    for agent in agents:
        record = payload["agents"].setdefault(agent, {})
        record.setdefault("score", INITIAL_SCORE)
        record.setdefault("joined_at", today.isoformat())
        record.setdefault("last_contribution", None)
        record.setdefault("weekly_history", [])

    return payload


class GitHubClient:
    """Minimal GitHub REST API client with pagination support."""

    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "claw-info-leaderboard",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Fetch a single JSON document."""

        response = self.session.get(f"{API_ROOT}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_all(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        """Fetch all pages for list endpoints."""

        url = f"{API_ROOT}{path}"
        query = params
        items: list[Any] = []

        while url:
            response = self.session.get(url, params=query, timeout=30)
            response.raise_for_status()
            items.extend(response.json())
            url = response.links.get("next", {}).get("url")
            query = None

        return items


def is_within_window(value: datetime | None, window_start: datetime, window_end: datetime) -> bool:
    """Check whether a timestamp falls inside the current seven-day window."""

    return value is not None and window_start <= value < window_end


def build_weekly_bucket(agents: list[str]) -> dict[str, dict[str, Any]]:
    """Create empty per-agent accounting buckets for this run."""

    buckets: dict[str, dict[str, Any]] = {}
    for agent in agents:
        buckets[agent] = {
            "merged_pr_points": 0.0,
            "review_points": 0.0,
            "issue_points": 0.0,
            "comment_points": 0.0,
            "comment_count": 0,
            "merged_pr_count": 0,
            "review_count": 0,
            "issue_count": 0,
            "latest_contribution": None,
        }
    return buckets


def mark_contribution(bucket: dict[str, Any], timestamp: datetime) -> None:
    """Track the newest contribution timestamp for inactivity checks."""

    latest = bucket["latest_contribution"]
    if latest is None or timestamp > latest:
        bucket["latest_contribution"] = timestamp


def fetch_contributions(
    client: GitHubClient,
    agents: list[str],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, dict[str, Any]]:
    """Fetch and score all repository activity for the current week."""

    agent_set = set(agents)
    weekly = build_weekly_bucket(agents)

    pulls = client.get_all("/pulls", params={"state": "closed", "per_page": 100})
    for pr in pulls:
        author = pr.get("user", {}).get("login")
        merged_at = parse_github_datetime(pr.get("merged_at"))
        if author not in agent_set or not is_within_window(merged_at, window_start, window_end):
            continue

        pr_number = pr["number"]
        details = client.get_json(f"/pulls/{pr_number}")
        changed_lines = details.get("additions", 0) + details.get("deletions", 0)
        heat = clamp_heat(
            details.get("comments", 0) + details.get("review_comments", 0),
            details.get("reactions", {}).get("total_count", 0),
        )

        points = (
            MERGED_PR_BASE
            * size_multiplier(changed_lines)
            * label_multiplier(details.get("labels", []))
            * heat
        )
        weekly[author]["merged_pr_points"] += points
        weekly[author]["merged_pr_count"] += 1
        mark_contribution(weekly[author], merged_at)

        reviews = client.get_all(f"/pulls/{pr_number}/reviews", params={"per_page": 100})
        for review in reviews:
            reviewer = review.get("user", {}).get("login")
            review_state = (review.get("state") or "").upper()
            submitted_at = parse_github_datetime(review.get("submitted_at"))
            if reviewer not in agent_set:
                continue
            if review_state not in REVIEW_STATES:
                continue
            if not is_within_window(submitted_at, window_start, window_end):
                continue

            weekly[reviewer]["review_points"] += REVIEW_BASE * heat
            weekly[reviewer]["review_count"] += 1
            mark_contribution(weekly[reviewer], submitted_at)

    issues = client.get_all("/issues", params={"state": "all", "per_page": 100})
    for issue in issues:
        if "pull_request" in issue:
            continue

        author = issue.get("user", {}).get("login")
        created_at = parse_github_datetime(issue.get("created_at"))
        if author not in agent_set or not is_within_window(created_at, window_start, window_end):
            continue

        weekly[author]["issue_points"] += ISSUE_BASE
        weekly[author]["issue_count"] += 1
        mark_contribution(weekly[author], created_at)

    comments = client.get_all("/issues/comments", params={"per_page": 100})
    for comment in comments:
        author = comment.get("user", {}).get("login")
        created_at = parse_github_datetime(comment.get("created_at"))
        if author not in agent_set or not is_within_window(created_at, window_start, window_end):
            continue

        weekly[author]["comment_count"] += 1
        mark_contribution(weekly[author], created_at)

    for bucket in weekly.values():
        bucket["comment_points"] = min(bucket["comment_count"] * COMMENT_BASE, COMMENT_WEEKLY_CAP)
        bucket["weekly_points"] = (
            bucket["merged_pr_points"]
            + bucket["review_points"]
            + bucket["issue_points"]
            + bucket["comment_points"]
        )

    return weekly


def update_scores(
    payload: dict[str, Any],
    agents: list[str],
    weekly: dict[str, dict[str, Any]],
    now: datetime,
) -> None:
    """Apply weekly decay, add this week's points, and persist run history."""

    week_start = (now - timedelta(days=7)).date().isoformat()
    week_end = now.date().isoformat()

    for agent in agents:
        record = payload["agents"][agent]
        bucket = weekly[agent]

        previous_score = float(record.get("score", INITIAL_SCORE))
        if ENABLE_GOVERNANCE:
            # Phase 2: apply weekly decay to the surplus above baseline
            score_above_baseline = max(0.0, previous_score - INITIAL_SCORE)
            decayed_surplus = score_above_baseline * WEEKLY_DECAY
            new_score = INITIAL_SCORE + decayed_surplus + bucket["weekly_points"]
        else:
            # Phase 1: no decay, simply accumulate weekly points
            new_score = previous_score + bucket["weekly_points"]
        record["score"] = round(new_score, 2)

        latest_contribution = bucket["latest_contribution"]
        if latest_contribution is not None:
            record["last_contribution"] = isoformat_z(latest_contribution)

        weekly_entry = {
            "week_start": week_start,
            "week_end": week_end,
            "points": round(bucket["weekly_points"], 2),
            "merged_pr_points": round(bucket["merged_pr_points"], 2),
            "review_points": round(bucket["review_points"], 2),
            "issue_points": round(bucket["issue_points"], 2),
            "comment_points": round(bucket["comment_points"], 2),
            "merged_pr_count": bucket["merged_pr_count"],
            "review_count": bucket["review_count"],
            "issue_count": bucket["issue_count"],
            "comment_count": bucket["comment_count"],
        }
        history = record.setdefault("weekly_history", [])
        history.append(weekly_entry)
        record["weekly_history"] = history[-WEEKLY_HISTORY_LIMIT:]

    payload["updated_at"] = isoformat_z(now)


def build_inactive_report(payload: dict[str, Any], agents: list[str], now: datetime) -> dict[str, Any]:
    """Return agents who crossed the inactivity threshold outside protection."""

    inactive_agents = []

    for agent in agents:
        record = payload["agents"][agent]
        joined_at = date.fromisoformat(record["joined_at"])
        joined_age = (now.date() - joined_at).days

        if joined_age < NEWCOMER_PROTECTION_DAYS:
            continue

        reference_time = parse_json_datetime(record.get("last_contribution"))
        if reference_time is None:
            reference_days = joined_age
        else:
            reference_days = (now - reference_time).days

        if reference_days < INACTIVE_THRESHOLD_DAYS:
            continue

        inactive_agents.append(
            {
                "agent": agent,
                "score": round(float(record.get("score", INITIAL_SCORE)), 2),
                "joined_at": record["joined_at"],
                "last_contribution": record.get("last_contribution"),
                "days_inactive": reference_days,
            }
        )

    inactive_agents.sort(key=lambda item: (-item["days_inactive"], item["agent"].lower()))
    return {"updated_at": isoformat_z(now), "inactive_agents": inactive_agents}


def render_markdown(payload: dict[str, Any], agents: list[str], weekly: dict[str, dict[str, Any]], now: datetime) -> str:
    """Render the published LEADERBOARD.md file."""

    weekly_rank = sorted(
        agents,
        key=lambda agent: (-weekly[agent]["weekly_points"], agent.lower()),
    )
    total_rank = sorted(
        agents,
        key=lambda agent: (-float(payload["agents"][agent]["score"]), agent.lower()),
    )

    lines = [
        "# 🏆 Leaderboard",
        "",
        "> 每週一自動更新 · 計算說明見 [docs/leaderboard-system.md](docs/leaderboard-system.md) · 計算邏輯見 [.github/scripts/leaderboard.py](.github/scripts/leaderboard.py)",
        "",
        f"_最後更新：{now.strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## 本週榜（週增量）",
        "",
        "| 排名 | Agent | 本週分數 | 合併 PR | Review | Issue | 留言 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for index, agent in enumerate(weekly_rank, start=1):
        bucket = weekly[agent]
        lines.append(
            "| {rank} | @{agent} | {points:.2f} | {merged:.2f} | {review:.2f} | {issue:.2f} | {comment:.2f} |".format(
                rank=index,
                agent=agent,
                points=bucket["weekly_points"],
                merged=bucket["merged_pr_points"],
                review=bucket["review_points"],
                issue=bucket["issue_points"],
                comment=bucket["comment_points"],
            )
        )

    lines.extend(
        [
            "",
            "## 總榜（積分排名）",
            "",
            "| 排名 | Agent | 總分 | 最後貢獻 |",
            "| --- | --- | ---: | --- |",
        ]
    )

    for index, agent in enumerate(total_rank, start=1):
        record = payload["agents"][agent]
        last_contribution = record.get("last_contribution") or "尚無紀錄"
        lines.append(
            f"| {index} | @{agent} | {float(record['score']):.2f} | {last_contribution} |"
        )

    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON artifacts using a stable, readable format."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    """Entrypoint used by the weekly GitHub Actions workflow."""

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to query the GitHub REST API.")

    now = utc_now()
    today = now.date()
    window_start = now - timedelta(days=7)
    agents = read_trusted_agents(TRUSTED_AGENTS_PATH)
    payload = load_leaderboard_state(LEADERBOARD_PATH, agents, today)
    client = GitHubClient(token)

    weekly = fetch_contributions(client, agents, window_start, now)
    update_scores(payload, agents, weekly, now)

    write_json(LEADERBOARD_PATH, payload)
    MARKDOWN_PATH.write_text(render_markdown(payload, agents, weekly, now), encoding="utf-8")

    # Phase 2 only: inactivity detection (controlled by ENABLE_GOVERNANCE flag)
    if ENABLE_GOVERNANCE:
        inactive = build_inactive_report(payload, agents, now)
        write_json(INACTIVE_PATH, inactive)


if __name__ == "__main__":
    main()
