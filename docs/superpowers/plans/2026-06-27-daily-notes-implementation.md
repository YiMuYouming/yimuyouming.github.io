# Daily Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collaborative Daily Notes publishing layer that turns a reviewed Vault note plus user trading feeling into a public, designed HTML market-handbook page.

**Architecture:** Keep Daily Notes independent from `review-notes` so the new media layer cannot pollute review statistics. Add a focused generator script that reuses safe parsing helpers from `tools/convert_review.py`, writes `daily-notes/YYYY-MM-DD.html`, rebuilds `daily-notes/index.html`, and refreshes one homepage module.

**Tech Stack:** Python standard library, existing static HTML/CSS, existing Portal verification scripts.

---

### Task 1: Generator Behavior Tests

**Files:**
- Create: `tools/test_convert_daily_note.py`
- Create: `tools/convert_daily_note.py`

- [ ] **Step 1: Write failing tests**

Create tests that build a temporary Portal tree, feed a sample Vault review note, and assert:
- `daily-notes/YYYY-MM-DD.html` is generated.
- The page has six public sections.
- Sensitive ticket, share count, cost price, and exact trade plan language is not present.
- `daily-notes/index.html` is rebuilt with one archive card.
- `index.html` gets a Daily Notes module without changing existing review counts.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python3 tools/test_convert_daily_note.py
```

Expected: fails because `tools/convert_daily_note.py` does not exist yet.

- [ ] **Step 3: Implement minimal generator**

Create `tools/convert_daily_note.py` with:
- `build_daily_note(md_path, user_feeling="")`
- `render_daily_note_page(note)`
- `update_daily_notes_index(note)`
- `update_home_daily_notes(note)`
- `sanitize_public_text(text)`

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python3 tools/test_convert_daily_note.py
```

Expected: all Daily Notes tests pass.

### Task 2: Reading-Card Visual Template

**Files:**
- Modify: `tools/convert_daily_note.py`
- Create: `daily-notes/index.html`
- Create: `daily-notes/YYYY-MM-DD.html` during generation

- [ ] **Step 1: Add assertions for reading-card structure**

Extend tests to assert the generated HTML contains:
- `.daily-note-shell`
- `.note-hero`
- `.note-thesis`
- `.note-market-aside`
- `.note-cognition-card`
- `.note-system-voice`
- `.note-watch-list`

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python3 tools/test_convert_daily_note.py
```

Expected: fails until template classes exist.

- [ ] **Step 3: Implement warm-ink editorial CSS**

Use Portal colors: `#F7F5F3`, `#FFFFFF`, `#E5E2DE`, `#D97706`, `#2D2926`, limited red/green market accents. Keep mobile layout single-column at 720px and below.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python3 tools/test_convert_daily_note.py
```

Expected: all Daily Notes tests pass.

### Task 3: Homepage Entry

**Files:**
- Modify: `index.html`
- Modify: `tools/convert_daily_note.py`

- [ ] **Step 1: Add homepage behavior tests**

Tests should verify:
- Homepage module is inserted after `</section>` for `#reviews`.
- It links to `daily-notes/index.html`.
- Latest card links to `daily-notes/YYYY-MM-DD.html?from=daily-notes`.
- Existing `日报归档` count remains unchanged.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python3 tools/test_convert_daily_note.py
```

Expected: fails until homepage insertion exists.

- [ ] **Step 3: Implement homepage updater**

Add markers:

```html
<!-- DAILY_NOTES_SECTION_START -->
...
<!-- DAILY_NOTES_SECTION_END -->
```

The updater replaces marker content if present, otherwise inserts after the reviews section.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python3 tools/test_convert_daily_note.py
```

Expected: all tests pass.

### Task 4: Portal Verification Integration

**Files:**
- Modify: `tools/portal_check.py`
- Modify: `tools/test_convert_daily_note.py`

- [ ] **Step 1: Add a check expectation**

Daily Note pages should count as child pages that need a back-home link, and homepage links to `daily-notes/` should be checked like existing HTML links.

- [ ] **Step 2: Run self-test**

Run:

```bash
python3 tools/portal_check.py --self-test
```

Expected: pass after integration.

### Task 5: Full Verification

**Files:**
- No new files beyond implementation outputs.

- [ ] **Step 1: Run focused tests**

```bash
python3 tools/test_convert_daily_note.py
python3 tools/test_convert_review.py
```

- [ ] **Step 2: Run existing Portal gate**

```bash
python3 tools/test_sync_pnl_data.py
python3 tools/test_portal_pnl_kpi.py
python3 tools/portal_check.py --self-test
python3 tools/portal_check.py
git diff --check
```

- [ ] **Step 3: Browser QA**

Serve locally:

```bash
python3 -m http.server 8765
```

Check desktop and 390px mobile for:
- `index.html#daily-notes`
- `daily-notes/index.html`
- latest `daily-notes/YYYY-MM-DD.html`

Verify no horizontal overflow, no text overlap, no empty cards, and back links work.
