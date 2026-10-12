# Script Style Copy Families Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Instagram story and direct-demo title families, preserve the confirmed script style, and use it in scene decoration unless the user explicitly picks a visual template.

**Architecture:** `headcopy_gen.py` remains the single generator and validates all paired title fields. `produce.html` maps a confirmed script draft to one copy family, persists that family in the existing work state, and resolves it against an explicit frame-template override in one function. The existing API continues receiving only `script` and normalized `copy_family`.

**Tech Stack:** Python, FastAPI, vanilla JavaScript, pytest, Puppeteer.

---

### Task 1: Add the two generator families

**Files:**
- Modify: `shopping_shorts/headcopy_gen.py`
- Modify: `shopping_shorts/tests/test_headcopy_gen.py`

- [x] **Step 1: Write failing family tests**

Add tests that call `suggest(..., family="instagram_story")` and `suggest(..., family="demo_direct")`, capture the prompt, and assert that `text`, `subline`, and `upload_title` survive as one candidate. Assert the Instagram prompt contains relationship-story instructions and the direct-demo prompt contains product/use instructions.

- [x] **Step 2: Verify RED**

Run: `py -m pytest shopping_shorts/tests/test_headcopy_gen.py -q`

Expected: both new-family tests fail because `normalize_family()` currently collapses them to `youtube_reveal`.

- [x] **Step 3: Implement minimal generator support**

Extend the allowed family set:

```python
_FAMILIES = {"generic", "youtube_reveal", "instagram_story", "demo_direct"}
```

Add a prompt per new family and a shared paired-family set:

```python
_PAIRED_FAMILIES = {"youtube_reveal", "instagram_story", "demo_direct"}
prompt = _FAMILY_PROMPTS.get(family, _PROMPT)
```

For all paired families, preserve `subline` and `upload_title`; keep the existing maximum lengths and reject any rendered line wider than 11 characters.

- [x] **Step 4: Verify GREEN**

Run: `py -m pytest shopping_shorts/tests/test_headcopy_gen.py -q`

Expected: all generator tests pass.

### Task 2: Preserve and resolve the confirmed script family

**Files:**
- Modify: `shopping_shorts/static/produce.html`
- Modify: `shopping_shorts/tests/test_headcopy_ui.py`
- Create: `shopping_shorts/tests/test_script_copy_family_ui.py`

- [x] **Step 1: Write failing UI wiring tests**

Add static regression tests asserting:

```javascript
function s2CopyFamilyForDraft(dr) { ... }
STATE.script_style_id = dr.style_id || null;
STATE.script_copy_family = s2CopyFamilyForDraft(dr);
```

Also assert `_workState`, `_restoreWork`, `revertWork`, and `_consumeProduceHandoff` save/restore both fields. Assert `currentCopyFamily()` reads `STATE.script_copy_family` unless `frame.copy_family_override` is true.

- [x] **Step 2: Verify RED**

Run: `py -m pytest shopping_shorts/tests/test_headcopy_ui.py shopping_shorts/tests/test_script_copy_family_ui.py -q`

Expected: failures for missing style mapping, persistence, and override markers.

- [x] **Step 3: Implement one mapping function**

Add:

```javascript
function s2CopyFamilyForDraft(dr){
  if(!(dr&&dr.style_id)) return 'demo_direct';
  const st=(S2.styles||[]).find(x=>String(x.id)===String(dr.style_id));
  const plat=s2Platform(st||{});
  return plat==='ig' ? 'instagram_story' : (plat==='yt' ? 'youtube_reveal' : 'demo_direct');
}
```

In `s2Confirm()` and `s2ConfirmToNewWork()`, store `script_style_id` and `script_copy_family`. Add them to `_workState()` and all three work restoration paths with old-data-safe defaults.

- [x] **Step 4: Implement explicit template precedence**

Make `currentCopyFamily()` return the template family only when `frame.copy_family_override` is true; otherwise return `STATE.script_copy_family`, then template/default. When `frPick(preset)` is called with a preset, store `copy_family_override:true` in the frame state.

- [x] **Step 5: Verify GREEN**

Run: `py -m pytest shopping_shorts/tests/test_headcopy_ui.py shopping_shorts/tests/test_script_copy_family_ui.py shopping_shorts/tests/test_produce_work_save.py shopping_shorts/tests/test_produce_work_restore.py -q`

Expected: all tests pass.

### Task 3: Verify API separation and browser behavior

**Files:**
- Modify: `shopping_shorts/tests/test_headcopy_api.py`
- Modify: `out/qa_headcopy_family.cjs`
- Modify: `handoff/장면꾸미기재편.md`
- Modify: `wiki/log.d/장면꾸미기재편.md`

- [x] **Step 1: Add cache-separation coverage**

Parameterize the API cache test over `youtube_reveal`, `instagram_story`, and `demo_direct`, asserting the same script calls the generator once per family.

- [x] **Step 2: Verify the API distinguishes all values**

Run: `py -m pytest shopping_shorts/tests/test_headcopy_api.py -q`

Expected before normalization support: the two new values collapse to one cache key and the test fails.

- [x] **Step 3: Expand browser QA**

For each family, inject a paired candidate, set `STATE.script_copy_family`, call `useHeadcopy(0)`, and assert the large title and subline both reach the preview. Then call `frPick('sul_even')` and assert explicit template selection resolves to `youtube_reveal`.

- [x] **Step 4: Run full relevant verification**

Run all headcopy, frame-decoration, work-save, and work-restore tests, then run the Puppeteer QA against the local `/produce` server.

Expected: zero pytest failures, browser `errors: []`, and no clipped two-line headline in the saved screenshots.

- [x] **Step 5: Record and commit**

Append the three-family behavior and verification evidence to the handoff and log, inspect `git diff --check`, and commit only the intended files. Do not merge to `main` or deploy.
