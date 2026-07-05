# 인사이트 페이지 Phase 1-b-2 (촉매 요약 섹션 + 라이트 테마 이식) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This file has NO python test suite — "run test" steps mean rendering `dashboard/insights.html` in a real browser (`GET /` on the running dashboard server) and reading the DOM, per this repo's verification-grounding-pack convention. Never mark a step done from source-reading alone.

**Goal:** Finish Phase 1-b-2 of the 인사이트 리디자인 (spec: `docs/specs/2026-07-04-인사이트-이벤트캘린더-설계.md`) — graft a "📅 다가오는 촉매" summary section into the live `dashboard/insights.html` L0 view bound to the already-shipped `/api/catalysts` endpoint, then re-skin the page's design tokens from the current dark/gold theme to the Apple-light system validated in `docs/mockups/insights-apple-light-v5.html`.

**Architecture:** `dashboard/insights.html` is a single large (2564-line) client-rendered SPA (`#app` → `render()` swaps `#view` innerHTML per route: L0 library home, L1/L2/L3 drill-down, stock autocomplete, studio presets). It does NOT share markup with the static mockup — the mockup is a design-token/component reference only, not a template to paste in. Task 1 adds one new sidebar block to the existing L0 `main-right` column, following the exact fetch/render pattern already used by `loadRecentReports()` (same file, `dashboard/catalysts.html` has the working reference markup+JS to port). Task 2 is a design-token pass: swap the `:root` CSS variables and the small set of component rules that hard-code dark-specific colors (not `var(--x)`), leaving all JS/data logic untouched.

**Tech Stack:** FastAPI backend (`dashboard/server.py`, unchanged), vanilla JS SPA frontend, Pretendard font (already CDN-loaded in the mockups, not yet in insights.html).

## Global Constraints

- Shared branch `feat/briefing-engine` — run `git branch --show-current` immediately before every commit (feedback: [[feedback_shared_worktree_branch_check]]).
- Render output — no automated test proves visual correctness. Every task ends with a real browser check via `mcp__claude-in-chrome__*` against the locally running dashboard server (default `http://localhost:8090/`), not just "the code looks right."
- Do not touch `dashboard/server.py` — `/api/catalysts` and `/api/watchlist` already exist and are verified (Phase 1-a/1-b-1). No backend changes in this plan.
- Do not touch any L1/L2/L3/stock-autocomplete/studio-preset rendering logic — those routes are out of scope; only the L0 view (`showL0()`, line ~941) and shared CSS/helpers change.
- Reuse existing helpers verbatim: `qs()`, `apiFetch()`, `escHtml()`, `escAttr()`, `fmtDate()` (all defined in `dashboard/insights.html`, ~line 890-2545). Do not redefine them.
- Korean UI copy stays Korean, matching existing tone in the file (e.g. "불러오는 중…", "불러오기 실패").
- No `Math.random()`/`Date.now()`-based non-determinism introduced (irrelevant here — no such calls needed).

---

### Task 1: 촉매 요약 섹션 (다크/골드 테마 유지, /api/catalysts 바인딩)

**Files:**
- Modify: `dashboard/insights.html`
  - CSS: insert new rules near the existing `.brief-hist`/`.bh-empty` block (~line 188-193)
  - HTML: insert new `side-title` + container block inside `main-right`, between the "📚 소스 라이브러리" block and the "📰 최근 리포트" block (~line 1046-1050)
  - JS: add `loadCatalystSummary()` function near `loadRecentReports()` (~line 1065-1088), and call it from `showL0()` alongside the existing `loadSignals(); loadBriefHistory(); loadRecentReports();` (line 1061-1063)

**Interfaces:**
- Consumes: `GET /api/catalysts?mine=1&days=14` → `{today, count, events: [{event_date, dday, asset, sector, content, event_kind, entity_scope, confidence, confirmed, affected_stocks}]}` (shape defined by `pipeline/atoms/calendar_build.to_api_dict`, already live per `dashboard/server.py:2518`). `entity_scope` ∈ `domestic|foreign|policy`. `confidence` ∈ `1..4` (1=확정…4=추정). Reference implementation already rendering this exact shape: `dashboard/catalysts.html` lines 137-166 (`loadCatalysts()`).
- Produces: `#catalyst-summary` DOM container that Task 2 will re-skin (CSS class names must stay stable across Task 1→2: `.cat-sum-item`, `.cat-sum-dday`, `.cat-sum-conf`).

- [ ] **Step 1: Add CSS for the summary rows**

Insert after line 193 (`.bh-empty { ... }`) in `dashboard/insights.html`:

```css
.cat-sum-item { display: flex; align-items: center; gap: 9px; padding: 8px 2px; border-top: 1px solid var(--line); }
.cat-sum-item:first-child { border-top: none; }
.cat-sum-dday { flex: 0 0 auto; font-size: .68rem; font-weight: 800; padding: 3px 7px; border-radius: 6px; background: #1c1c22; color: var(--muted); white-space: nowrap; }
.cat-sum-dday.soon { background: #2a1210; color: #ff6b60; }
.cat-sum-dday.near { background: #2a1f0a; color: var(--gold); }
.cat-sum-body { flex: 1; min-width: 0; }
.cat-sum-nm { font-size: .82rem; font-weight: 700; color: var(--txt); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-sum-meta { font-size: .68rem; color: var(--muted); margin-top: 1px; display: flex; gap: 6px; flex-wrap: wrap; }
.cat-sum-conf { font-weight: 700; }
.cat-sum-conf.c1, .cat-sum-conf.c2 { color: var(--gold); }
.cat-sum-flag { color: #7dd3fc; }
```

- [ ] **Step 2: Insert the sidebar block markup**

In `showL0()`'s template literal, right after this existing line (~1046-1047):
```
        <div class="side-title">📚 소스 라이브러리 <button class="lib-toggle" onclick="toggleLib(this)">펼치기 ▾</button></div>
        <div id="lib-chips" class="lib-chips">${libChips || '<div style="color:var(--muted)">카테고리 없음</div>'}</div>
        <div id="lib-detail" class="lib-detail" style="display:none"></div>
        <div id="lib-cards" class="cat-grid-side" style="display:none">${catCards}</div>
```
insert (before the `📰 최근 리포트` side-title):
```
        <div class="side-title" style="margin-top:18px">📅 다가오는 촉매 <small style="color:var(--gold-dim);font-weight:400">클릭하면 그 종목/섹터 브리핑</small></div>
        <div id="catalyst-summary" class="brief-hist">불러오는 중…</div>
```

- [ ] **Step 3: Add the loader function**

Add right before `function toggleLib(btn) {` (~line 1089):

```javascript
async function loadCatalystSummary() {
  const box = qs('#catalyst-summary'); if (!box) return;
  const FLAG = { foreign: '🌏 해외', policy: '🏛 정책', domestic: '' };
  try {
    const res = await apiFetch('/api/catalysts?mine=1&days=14');
    const events = res.events || [];
    if (!events.length) { box.innerHTML = '<div class="bh-empty">예정된 촉매가 없어요 (오늘 캘린더 수집분 대기)</div>'; return; }
    box.innerHTML = events.slice(0, 6).map(e => {
      const dday = e.dday ?? 0;
      const ddCls = dday <= 3 ? 'soon' : dday <= 7 ? 'near' : '';
      const confCls = 'c' + (e.confidence || 4);
      const confLbl = { 1: '확정', 2: '높음', 3: '관측', 4: '추정' }[e.confidence || 4];
      const flag = FLAG[e.entity_scope] || '';
      return `<div class="cat-sum-item" onclick="sigBrief('${escAttr(e.asset || '')}')">
        <span class="cat-sum-dday ${ddCls}">D-${dday}</span>
        <div class="cat-sum-body">
          <div class="cat-sum-nm">${escHtml(e.asset)}</div>
          <div class="cat-sum-meta">
            <span>${escHtml(e.event_kind || '')}</span>
            <span class="cat-sum-conf ${confCls}">${confLbl}</span>
            ${flag ? `<span class="cat-sum-flag">${flag}</span>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
  } catch (e) { box.innerHTML = '<div class="bh-empty">촉매를 불러오지 못했습니다.</div>'; }
}
```

`sigBrief(asset)` already exists in this file (used by `loadRecentReports()`, ~line 1083) — reused here unchanged, no new function needed for the click-to-brief behavior.

- [ ] **Step 4: Wire the loader into `showL0()`**

Change (~line 1061-1063):
```javascript
  loadSignals();
  loadBriefHistory();
  loadRecentReports();
```
to:
```javascript
  loadSignals();
  loadBriefHistory();
  loadRecentReports();
  loadCatalystSummary();
```

- [ ] **Step 5: Start the dashboard server locally (if not already running)**

Check first whether a server is already up (avoid double-binding the port):
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/
```
If not `200`, start it per this repo's existing run pattern (check `dashboard/server.py` bottom / existing `run` skill for the exact launch command) — do not guess a command; if unsure, ask the user how the dev server is normally started here (a prior session used `localhost:8090`, PID-tracked, per `NEXT_SESSION.md`).

- [ ] **Step 6: Browser-verify the new section renders real data**

Use `mcp__claude-in-chrome__*` (load tools first via `ToolSearch query:"select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp"`):
1. Navigate to `http://localhost:8090/` (or wherever insights.html is served — check `server.py` route, likely `GET /` or `GET /insights`).
2. `read_page` or `get_page_text` to confirm `#catalyst-summary` exists in `main-right` and shows either real D-N rows or the "예정된 촉매가 없어요" empty state (both are valid PASS — do NOT require non-empty data, since `NEXT_SESSION.md` already documented the calendar collector may be quota-empty).
3. Confirm no JS console errors via `read_console_messages` (pattern: `error`).
Report honestly which state was observed (empty vs populated) — do not claim populated data was seen if it wasn't.

- [ ] **Step 7: Commit**

```bash
git branch --show-current
git add dashboard/insights.html
git commit -m "feat(insights): add 다가오는 촉매 summary section bound to /api/catalysts"
```

---

### Task 2: 라이트 테마 디자인 토큰 이식 (Apple-light, v5 시안 기준)

**Files:**
- Modify: `dashboard/insights.html`
  - `:root` CSS variables (line 9-19)
  - Any component rule using a **literal hex/rgba color** instead of `var(--x)` (must be grepped and fixed one by one — do not assume the initial scan below is exhaustive; re-grep after Step 1)
  - `<head>`: add Pretendard font `<link>` (mirroring `docs/mockups/insights-apple-light-v5.html` line 7)

**Interfaces:**
- Consumes: Task 1's `.cat-sum-*` class names (must still look correct under light tokens — verify in Step 4).
- Produces: nothing consumed by later tasks — this is the terminal task of this plan.

- [ ] **Step 1: Add Pretendard font link**

In `<head>`, after the existing `<script src=".../marked.min.js">` line (line 7), add:
```html
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
```

- [ ] **Step 2: Replace the `:root` token block**

Replace lines 9-19:
```css
:root {
  --gold: #d4af37; --gold-dim: #9a7d28; --bg: #0a0a0a;
  --card: #16161a; --line: #2a2a30; --txt: #e8e6e0; --muted: #8a8a92;
  --yt: #7c3aed; --yt-bg: #1a0e2e; --yt-line: #3d1f6b;
  --tg: #0891b2; --tg-bg: #0c1f25; --tg-line: #1a4a55;
  --rp: #d4af37; --rp-bg: #1a1608; --rp-line: #4a3d10;
  --bl: #22c55e; --bl-bg: #0c1f12; --bl-line: #1a4a2a;
  --nw: #f97316; --nw-bg: #1f1308; --nw-line: #4a2f10;
  --buy: #16a34a; --sell: #dc2626; --neutral: #6b7280;
  --bull: #16a34a; --bear: #dc2626;
}
```
with (keeping every variable NAME identical so no downstream rule needs renaming — only values change, plus category accent vars gain light-appropriate tints per source-type, following the mockup's per-category SVG-icon color choices at `docs/mockups/insights-apple-light-v5.html` lines 235-241):
```css
:root {
  --gold: #0066cc; --gold-dim: #0055aa; --bg: #ffffff;
  --card: #ffffff; --line: #e5e5e7; --txt: #1d1d1f; --muted: #86868b;
  --yt: #af52de; --yt-bg: #f5eefc; --yt-line: #e3cef7;
  --tg: #2AABEE; --tg-bg: #eaf6fd; --tg-line: #cdeaf9;
  --rp: #b25e00; --rp-bg: #fdf3e7; --rp-line: #f2ddb8;
  --bl: #03C75A; --bl-bg: #e8fbf0; --bl-line: #c7f3d9;
  --nw: #5E6AD2; --nw-bg: #eef0fb; --nw-line: #d6dafa;
  --buy: #1d8a3f; --sell: #d70015; --neutral: #86868b;
  --bull: #1d8a3f; --bear: #d70015;
}
body { background: #f5f5f7; }
```
(second-layer canvas `#f5f5f7` vs card `#ffffff` mirrors the mockup's `--bg`/`--bg-2` split — `body` background becomes the page canvas, `.topbar`/cards stay pure white via `--card`.)

- [ ] **Step 3: Grep for hardcoded dark-specific literals and fix each**

```bash
grep -n "#1c1c22\|#0a0a0a\|#221c0a\|#14320f\|#2a5a1e\|#7dd957\|rgba(0,0,0,0\." dashboard/insights.html
```
For each hit found, replace with a light-appropriate equivalent using existing `var(--x)` tokens where the surrounding rule's intent is "hover surface" (→ `var(--bg)`, i.e. `#f5f5f7`) or "success accent bg/fg" (→ `var(--bl-bg)`/`var(--bl)`). Do this inline, rule by rule — there is no bulk find/replace that's safe here since the intent differs per rule (do not blind-substitute; read each rule's selector to infer purpose before changing).

- [ ] **Step 4: Browser-verify full page + drill-down still renders correctly under light tokens**

Reuse the same `mcp__claude-in-chrome__*` tools from Task 1:
1. Navigate to the insights page (same URL as Task 1 Step 6).
2. Screenshot the L0 view — confirm: white/`#f5f5f7` canvas, no leftover near-black backgrounds, gold/blue accent readable, `.cat-sum-*` rows from Task 1 still legible (their literal hex fallbacks like `#1c1c22`/`#2a1210`/`#2a1f0a` in `.cat-sum-dday` etc. were added in Task 1 for the DARK theme — these must also be fixed in this step; re-grep `dashboard/insights.html` for `.cat-sum-` and update those 3 hardcoded backgrounds to light equivalents, e.g. `#f5f5f7`/`#fdeceb`/`#fdf3e0`).
3. Click into one L1 (sector) drill-down and one L2/L3 doc view — confirm text remains readable (no white-on-white or dark-card-on-white leftover blocks) since those views share the same `var(--card)`/`var(--txt)` tokens and should inherit correctly, but must be eyeballed since they weren't touched directly.
4. Check console for errors.
Report exactly what was visually confirmed vs not (e.g., if L2/L3 weren't reachable due to empty data, say so — don't claim verification that didn't happen).

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add dashboard/insights.html
git commit -m "style(insights): port Apple-light design tokens from v5 mockup"
```

---

## Post-plan (not in scope here, for NEXT_SESSION.md)

- Full component-level redesign (searchbar pill shape, source-library accordion visual rework, signal-card spark-line visual from v6) — only the *token layer* ships in this plan; component-shape changes are a separate follow-up if the user wants pixel-parity with the mockup rather than just a re-tinted existing layout.
- Server deployment / Lightsail push — per this repo's established pattern, do only after explicit user confirmation (`feedback_server_dashboard_only`, `project_hosting`).
