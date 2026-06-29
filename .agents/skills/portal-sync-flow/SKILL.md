---
name: portal-sync-flow
description: Use the YiMu Capital Portal sync checklist and publish gates without freezing implementation choices. Use when the user says "同步门户", "同步今天门户", "根据流程同步门户", "更新每日市场手记", "Daily Note", "发布 Portal", or asks to sync Vault ReviewNotes, Daily Notes, insights, validation, browser QA, commit, or push for /Users/yimu/Documents/YM_Capital/portal.
---

# Portal Sync Flow

Use this skill as a fast publish checklist for `/Users/yimu/Documents/YM_Capital/portal`, not as a rigid script. Treat `AGENTS.md`, `docs/PORTAL_2.0.md`, and the scripts in `tools/` as the detailed source of truth.

## Operating Stance

- Use this skill to avoid missed gates, not to block better judgment.
- Optimize scripts, page structure, copy, QA coverage, and sequencing when the task calls for it.
- Keep the few hard gates fixed: source of truth, public-safety redaction, cloud sync truth, validation, browser QA, and commit/push confirmation.
- If the requested task is narrower than a full publish, run only the relevant checklist items and clearly state what was intentionally skipped.
- If repeated work reveals a better recurring step, update this skill or `AGENTS.md` after the improved pattern is proven.

## Start Here

1. Read `AGENTS.md` first, then check `docs/PORTAL_2.0.md` when architecture or acceptance criteria are unclear.
2. Run `git status --short` before changes and preserve unrelated work.
3. Identify the target Vault ReviewNote under `/Users/yimu/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/` by comparing it with `review-notes/*.html`.

## Fast Checklist

Use these as checklist items, adapting the order when there is a concrete reason:

- Refresh the cloud data module with `python3 tools/sync_pnl_data.py`. Default to cloud Hermes; use `--source local` only for explicit local debugging.
- Verify the sync did not hide failure with old data: inspect command output and `index.html` for `FAIL`, `cloud bridge fetch failed`, or visible `云端 bridge 不可用` placeholders before proceeding.
- Convert the Vault ReviewNote with `python3 tools/convert_review.py <vault_md_path>`. This updates `review-notes/YYYY-MM-DD.html`, `review-notes/index.html`, and homepage review surfaces.
- Generate or refresh the Daily Note with `python3 tools/convert_daily_note.py <vault_md_path> [optional user feeling]`. Daily Note content must come from the Vault ReviewNote, not from Market Watch watch notes or existing Portal HTML.
- Extract §二 / 今日认知 into `insights/index.html`, assign each item to the existing insights themes, and keep homepage insight counts aligned with detail-card counts. Ask before creating a new theme.
- Run validation and browser QA at the level of risk introduced by the changes. Full publishes need the full release gate.
- Show `git diff --stat` and a concise diff summary. Commit and push only after user confirmation; if the user already said "推送吧", validate first, then commit and push directly.

Do not use `python3 tools/convert_review.py <vault_md_path> --commit` in the normal publish flow. Commit only after validation, browser QA, and the diff summary gate.

## Public-Layer Red Lines

- Portal is a public reading layer, not the content SSOT.
- Vault ReviewNote is the source for review HTML and Daily Note publication.
- Do not expose ticket IDs, exact execution details, 成本, 股数, precise buy/sell instructions, or sensitive position detail.
- Do not use stale local data to mask cloud bridge or sync failures.
- Keep generated content in the Portal reading style and preserve existing design conventions.

## Validation

For a full Portal publish, run these commands before reporting completion:

```bash
python3 tools/test_convert_review.py
python3 tools/test_convert_daily_note.py
python3 tools/test_sync_pnl_data.py
python3 tools/test_portal_pnl_kpi.py
python3 tools/portal_check.py --self-test
python3 tools/portal_check.py
git diff --check
```

For browser QA, serve through a local HTTP server if file URLs are blocked. For full publishes, check at least:

- `index.html#research`
- `index.html#daily-notes`
- latest `review-notes/YYYY-MM-DD.html`
- latest `daily-notes/YYYY-MM-DD.html`
- `insights/index.html`

Desktop and 390px mobile checks must look for horizontal overflow, text overlap, empty cards, broken navigation, missing latest-card links, and count drift between homepage, archive, and insights pages.
