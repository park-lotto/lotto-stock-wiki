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

---

### Task 3: L0 레이아웃 실제 v5 이식 (히어로·검색바·소스라이브러리·시그널레일)

**배경 — 왜 이 태스크가 필요한가:** 사용자가 Task 2 색상 전용 패스만으로는 부족하고 **v5 목업의 실제 레이아웃(비율·모양·배치)까지** 원한다고 명확히 확인함 (2026-07-05). Task 2(색상 토큰)는 계속 유효하고 먼저 진행 — 이 Task 3가 그 위에서 L0 뷰의 시각 구조를 v5에 맞게 재작업한다.

**범위 원칙(위험 최소화):** JS가 참조하는 기존 `id`/클래스명(`#signals-box`, `#lib-chips`, `#lib-cards`, `#lib-detail`, `.bchip`, `.sig-block`, `.sig-head`, `.sig-asset`, `.sig-caret`, `#catalyst-summary` 등)은 **그대로 유지** — CSS 값과 마크업의 시각적 배치만 바꾼다. 함수 재바인딩(`onclick` 대상 변경) 없이 순수 CSS 재작성 + 최소 마크업 조정으로 v5의 "느낌"을 재현한다. L1~L6 드릴다운, 브리핑 워크스페이스(`#nbws`) 모달, 종목 자동완성, 스튜디오 프리셋은 이 태스크의 범위 밖(구조 변경 없음, Task 2의 토큰만 적용된 상태 유지).

**정직성 제약 — 스파크라인:** v5 목업의 시그널 카드는 장식용 스파크라인(가짜 시계열)을 쓴다. 실제 `/api/insights/signals` 응답(`stocks`/`macro` 배열, 필드: `asset`,`today`,`spike`,`is_new`)에는 시계열 값이 없다 — **지어낸 스파크라인을 그리지 말 것**. 대신 기존 `sigRow()`가 이미 만드는 실데이터 배지(🆕/▲spike/▼spike/=)를 카드 안에 그대로 유지해 v5의 "카드 하단 시각 요소" 자리를 대신한다.

**Files:**
- Modify: `dashboard/insights.html`
  - CSS: `.hero`(63-66), `.brief-bar`/`.brief-row`/`.bchip`/`.brief-input`/`.brief-go`(83-96), `.main-2col`/`.side-title`(99-101), `.lib-chips`/`.lib-chip`(107-114), `.cat-grid-side`(146-150), `.sig-title`/`.sig-grp`/`.sig-grid`/`.sig-block`(155-161) — restyle values/layout, do not rename selectors
  - HTML: `showL0()` template (~line 1004 이후) — minor structural wrapper adjustments only (e.g. wrapping the existing `<h1>`/`<p class="sub">` in a flex row for the tagline, matching v5's `.hero` layout) — **do not change any `id=` or `onclick=` attribute value**

**Interfaces:**
- Consumes: Task 2's re-tinted `:root` tokens (`--gold`→light blue, `--bg`→white, `--card`→white, `--line`→light hairline, `--txt`/`--muted` light-ink values) and Task 1's `.cat-sum-*` classes (already re-tinted by Task 2 Step 3).
- Produces: nothing consumed later — this is the plan's terminal task.

- [ ] **Step 1: Hero + 브리핑바(ask bar) — v5 비율로 재작성**

Replace CSS lines 63-66:
```css
.hero { padding: 36px 0 28px; }
.hero h1 { font-size: 1.7rem; font-weight: 800; letter-spacing: -.5px; margin-bottom: 5px; }
.hero h1 .gold { color: var(--gold); }
.hero .sub { color: var(--muted); font-size: .85rem; margin-bottom: 24px; }
```
with:
```css
.hero { padding: 56px 0 28px; }
.hero h1 { font-size: clamp(34px, 5vw, 52px); font-weight: 800; letter-spacing: -.03em; line-height: 1.05; margin-bottom: 8px; }
.hero h1 .gold { color: var(--gold); }
.hero .sub { color: var(--muted); font-size: .92rem; margin-bottom: 28px; }
```
(v5 자체는 clamp(44px,7vw,76px)까지 가지만, 이 페이지 `<h1>`엔 이모지+긴 한글 타이틀이 들어가 있어 그대로 쓰면 줄바꿈이 깨짐 — 실측 후 필요하면 낮춘 값으로 조정해도 됨, 다만 최소 30px 이상으로 기존 1.7rem(27px)보다는 뚜렷하게 커야 함.)

Replace CSS lines 83-96 (`.brief-bar` through `.brief-go:hover`):
```css
.brief-bar { width: 100%; background: var(--bg-2, #f5f5f7); border-radius: 28px; padding: 30px 30px 24px; }
.brief-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.brief-row:last-of-type { margin-bottom: 0; }
.bchip { padding: 7px 14px; border-radius: 980px; border: 1px solid var(--line); background: #fff; color: var(--muted); font-family: inherit; font-size: .82rem; cursor: pointer; transition: all .15s; }
.bchip.on { background: var(--txt); border-color: var(--txt); color: #fff; }
.brief-input { flex: 1; min-width: 200px; padding: 15px 18px; border-radius: 16px; border: 1px solid var(--line); background: #fff; color: var(--txt); font-family: inherit; font-size: .95rem; outline: none; transition: border-color .15s; }
.brief-input:focus { border-color: var(--muted); }
.brief-go { padding: 15px 26px; border-radius: 16px; border: none; background: var(--txt); color: #fff; font-family: inherit; font-size: .9rem; font-weight: 700; cursor: pointer; white-space: nowrap; transition: transform .15s, filter .15s; }
.brief-go:hover { filter: brightness(1.3); transform: translateY(-1px); }
```
(`var(--bg-2, #f5f5f7)` — insights.html has no `--bg-2` variable; the fallback value covers it without requiring you to also edit Task 2's `:root` block. If Task 2 already added `--bg-2`, the fallback is simply unused — either is fine, do not treat this as a conflict.)

Note: `.brief-research.on` (line 84 of the original file) already exists as a separate rule for the 🔎리서치 toggle — leave it untouched, it inherits fine from the new `.bchip` base.

- [ ] **Step 2: 소스 라이브러리 — 아이콘 타일 행으로 재작성**

Replace CSS lines 99-101 (`.main-2col` through `.side-title`):
```css
.main-2col { display: grid; grid-template-columns: 1.7fr 1fr; gap: 26px; align-items: start; margin: 34px 0 8px; }
.main-left, .main-right { min-width: 0; }
.side-title { font-size: .78rem; font-weight: 700; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: .04em; display: flex; align-items: center; }
```

Replace CSS lines 107-114 (`.lib-chips` through `.lib-chip.report{...}` line, i.e. the `.lib-chip` block and its category color-accent siblings) — find the full `.lib-chip` rule set (starts `.lib-chips { display: flex...`, ends at the `.lib-new` rule before `.lib-detail`) and replace with:
```css
.lib-chips { display: flex; flex-wrap: wrap; gap: 14px; justify-content: flex-start; }
.lib-chip { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 14px 10px 10px; background: #fff; border: 1px solid var(--line); border-left: 1px solid var(--line); border-radius: 16px; cursor: pointer; transition: transform .15s, box-shadow .15s; min-width: 76px; text-align: center; }
.lib-chip:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,.06); }
.lib-ico { font-size: 1.4rem; }
.lib-name { font-size: .74rem; font-weight: 600; color: var(--txt); }
.lib-cnt { font-size: .7rem; font-weight: 700; color: var(--gold); }
.lib-new { font-size: .6rem; font-weight: 700; background: var(--bl-bg); color: var(--bl); border: 1px solid var(--bl-line); border-radius: 5px; padding: 1px 5px; }
```
(원래 `.lib-chip.youtube{border-left-color:...}` 같은 카테고리별 accent-color 규칙들은 `border-left`가 이제 `1px solid var(--line)`로 통일되므로 **삭제**해도 되고, 남겨둬도 무해함(덮어써짐) — 삭제가 더 깔끔하지만 필수는 아님, 실측 후 판단.)

Replace CSS lines 146-150 (`.cat-grid-side` block):
```css
.cat-grid-side { display: grid; grid-template-columns: 1fr; gap: 12px; }
.cat-grid-side .cat-card { border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,.05); }
.cat-grid-side .cat-card .body { padding: 14px 18px; }
.cat-grid-side .cat-card .divider, .cat-grid-side .cat-card .hot-label, .cat-grid-side .cat-card .hot-item, .cat-grid-side .cat-card .go-btn { display: none; }
.cat-grid-side .cat-card .meta { margin-bottom: 0; }
```

- [ ] **Step 3: 시그널 — 세로 그리드 → 가로 스크롤 레일(카드)로 재작성**

Replace CSS lines 155-161 (`.sig-title` through `.sig-block:hover`):
```css
.sig-title { font-size: .95rem; font-weight: 700; color: var(--txt); margin-bottom: 14px; }
.sig-title small { color: var(--muted); font-weight: 400; font-size: .74rem; margin-left: 6px; }
.sig-grp { font-size: .76rem; font-weight: 700; color: var(--muted); margin: 16px 0 8px; }
.sig-grp small { color: var(--gold); }
.sig-grid { display: flex; gap: 14px; overflow-x: auto; padding: 4px 2px 14px; scroll-snap-type: x mandatory; scrollbar-width: thin; }
.sig-block { flex: 0 0 220px; scroll-snap-align: start; background: #fff; border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 4px 20px rgba(0,0,0,.05); overflow: hidden; transition: transform .15s, box-shadow .15s; }
.sig-block:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,.09); border-color: var(--line); }
```
(`sig-detail`/`sig-asset`/`sig-cnt`/`sig-caret`/`sig-sample`/`sig-brief-btn` 등 나머지 `.sig-*` 규칙은 카드 내부 컨텐츠라 그대로 두어도 새 카드 쉐잎 안에서 자연스럽게 맞음 — 실측에서 padding이 어색하면 `.sig-head`/`.sig-detail`의 `padding`만 소폭 조정, 구조는 변경하지 말 것.)

- [ ] **Step 4: 브라우저로 L0 전체 레이아웃 실측**

`mcp__claude-in-chrome__*` 사용 (미로드시 `ToolSearch query:"select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp"`):
1. `http://localhost:8090/insights` 로드 (서버 미기동시 `"C:\Users\TheRose\AppData\Local\Python\bin\python.exe" dashboard/server.py`).
2. 스크린샷으로 확인: 히어로가 뚜렷하게 커짐, 브리핑바가 라운드 카드+필형 인풋, 소스 라이브러리가 아이콘 타일 행, 시그널이 가로 스크롤 레일. v5와 "동일한 구조 언어"인지 — 픽셀 완전 동일까지는 아니어도 됨, 비율·모양·배치가 명확히 v5 계열인지가 기준.
3. 소스 라이브러리 아이콘 하나 클릭 → 기존 `libShow`/`toggleLib` 동작(펼침/접힘) 여전히 작동하는지 확인.
4. 시그널 카드(있으면) 클릭 → `sigExpand` 아코디언 여전히 작동하는지 확인. 데이터 없으면(크롤 대기) 빈 상태 문구가 새 레일 안에서도 깨지지 않고 보이는지 확인.
5. 콘솔 에러 없는지 확인.
정직하게 보고: 실측 못한 부분(예: 시그널 데이터 없어 카드 클릭 미확인)은 그렇게 명시.

- [ ] **Step 5: Commit**

```bash
git branch --show-current
git add dashboard/insights.html
git commit -m "style(insights): rebuild L0 layout to match v5 mockup structure (hero/ask-bar/library/signal-rail)"
```

---

## Post-plan (not in scope here, for NEXT_SESSION.md)

- L1~L6 드릴다운·브리핑 워크스페이스(`#nbws`) 모달의 구조적 재설계(현재는 Task 2 토큰만 적용, 레이아웃은 기존 유지) — 원하면 별도 후속 작업.
- 서버 배포 / Lightsail push — 이 저장소의 확립된 패턴에 따라, 명시적인 사용자 확인 후에만 진행(`feedback_server_dashboard_only`, `project_hosting`).
