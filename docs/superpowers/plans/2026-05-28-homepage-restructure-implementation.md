# Homepage Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the portal homepage as an external trust-building homepage while preserving all existing internal links, PnL interactions, review-note access, reports, insights, and market snapshot functionality.

**Architecture:** Keep the project as a static HTML portal. Preserve the existing embedded `PNL_DATA` block and canvas-based PnL renderer, but redesign the surrounding homepage information architecture and visual hierarchy. Update sync scripts only where marker stability is needed so future PnL and market data refreshes do not break the new layout.

**Tech Stack:** Static HTML, inline CSS, vanilla JavaScript, Python sync scripts, GitHub Pages-compatible assets.

---

## Files

- Modify: `/Users/yimu/Documents/YM_Capital/portal/index.html`
  - Replace current “工作平台 / Daily Desk” layout with external portal structure.
  - Preserve `<!-- PNL_DATA_START -->` / `<!-- PNL_DATA_END -->`.
  - Preserve PnL chart controls: day/week/month/quarter/year/all and sh/sz/cy.
  - Preserve links to latest reviews, review index, tools, insights, reports.
  - Add stable homepage markers for dynamic blocks.

- Modify: `/Users/yimu/Documents/YM_Capital/portal/tools/sync_pnl_data.py`
  - Replace PnL data as before.
  - Replace market snapshot via new `MARKET_SNAPSHOT_START/END` marker instead of brittle DOM string slicing.
  - Replace performance summary or sync timestamp if needed.

- Modify if needed: `/Users/yimu/Documents/YM_Capital/portal/tools/convert_review.py`
  - Keep latest review update compatible with redesigned review card/list.
  - Avoid changing generated review pages.

- Keep: `/Users/yimu/Documents/YM_Capital/portal/review-notes/index.html`
  - No redesign in this phase.

## Task 1: Prepare homepage shell

- [ ] Preserve the embedded `PNL_DATA` script block.
- [ ] Replace title from “工作平台” to a public-facing title.
- [ ] Add sections in this order: hero, methodology, performance, review system, research library, workspace entry, footer.
- [ ] Keep all existing destinations reachable.

Verification:

```bash
rg -n "PNL_DATA_START|PNL_DATA_END|收益记录|复盘系统|研究沉淀|工作台入口" index.html
```

Expected: all markers and new sections are present.

## Task 2: Redesign PnL section without removing controls

- [ ] Keep index controls: 上证、深证、创业板.
- [ ] Keep period controls: 日、周、月、近三月、近一年、全部.
- [ ] Add `全部` period control if current UI does not expose it.
- [ ] Default JavaScript state should prefer `all` if `PNL_DATA.all_sh` exists, otherwise fall back to `quarter`.
- [ ] Move today-specific metrics into a lower-trust-detail row or fold them below the main four indicators.
- [ ] Add data source and TWR explanation.

Verification:

```bash
rg -n "data-p=\"all\"|data-idx=\"sh\"|data-idx=\"sz\"|data-idx=\"cy\"|Hermes|TWR" index.html
```

Expected: all controls and trust copy are present.

## Task 3: Stabilize sync markers

- [ ] Add `<!-- MARKET_SNAPSHOT_START -->` and `<!-- MARKET_SNAPSHOT_END -->` around market snapshot content.
- [ ] Update `sync_pnl_data.py` to replace the market block by marker.
- [ ] Preserve existing `PNL_DATA` replacement behavior.
- [ ] If a marker is missing, the script should fail explicitly with a clear message.

Verification:

```bash
python3 tools/sync_pnl_data.py --source local
```

Expected in a local environment with bridge running: sync succeeds. If bridge is not running, failure is acceptable and should be explicit.

Cloud verification command:

```bash
python3 tools/sync_pnl_data.py
```

Expected: `synced N PnL days + market snapshot from cloud:agentuser@43.132.146.234 → index.html`.

## Task 4: Preserve review conversion compatibility

- [ ] Inspect `convert_review.py` latest-homepage update logic.
- [ ] If it depends on old `.day-row` structure, either preserve `.day-row` in latest review list or update the replacement block to the new structure.
- [ ] Do not change review page generation unless required.

Verification:

```bash
python3 -m py_compile tools/convert_review.py tools/sync_pnl_data.py
```

Expected: no syntax errors.

## Task 5: Browser and static validation

- [ ] Start local static server.
- [ ] Open homepage in browser.
- [ ] Verify desktop: hero, methodology, performance, reviews, research, workspace are readable.
- [ ] Verify mobile width: no horizontal overflow, controls wrap cleanly.
- [ ] Verify PnL canvas renders and controls switch periods/indexes.

Verification:

```bash
python3 -m http.server 8765
```

Open: `http://127.0.0.1:8765/`

## Completion Criteria

- Existing content and destinations are still available.
- PnL interactions are still available.
- Homepage reads as an external trust-building portal.
- Sync script can still update PnL and market data.
- No commit or push is performed without user confirmation.

