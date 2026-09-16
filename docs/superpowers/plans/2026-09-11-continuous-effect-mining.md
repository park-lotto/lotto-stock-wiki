# Continuous Effect Mining Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a restart-safe, continuously scheduled Shorts collection and deterministic effect-signal analysis worker foundation.

**Architecture:** A focused `shopping_shorts.effect_mining` package owns its SQLite schema, durable queue, source connectors, handlers, scheduler, and CLI. Platform and media I/O are injected behind protocols so the core pipeline is testable without the network; production adapters reuse the repository's YouTube search, media download, and scene-motion analysis functions.

**Tech Stack:** Python 3, SQLite, argparse, existing yt-dlp/FFmpeg helpers, pytest

---

## File map

- Create `shopping_shorts/effect_mining/__init__.py`: package marker and analyzer version.
- Create `shopping_shorts/effect_mining/db.py`: schema, item/source persistence, leased queue, retry and status queries.
- Create `shopping_shorts/effect_mining/connectors.py`: connector protocol, registry, YouTube keyword adapter.
- Create `shopping_shorts/effect_mining/analyzers.py`: deterministic cut/motion adapter and candidate derivation.
- Create `shopping_shorts/effect_mining/pipeline.py`: discover/acquire/measure/promote handlers and task routing.
- Create `shopping_shorts/effect_mining/runner.py`: scheduler tick, worker tick, heartbeat and continuous loops.
- Create `shopping_shorts/effect_mining/cli.py`: init/add-source/schedule/work/status commands.
- Create `shopping_shorts/tests/test_effect_mining_db.py`: queue, dedupe, lease and retry behavior.
- Create `shopping_shorts/tests/test_effect_mining_pipeline.py`: end-to-end injected pipeline.
- Create `shopping_shorts/tests/test_effect_mining_cli.py`: operator-facing CLI smoke tests.
- Create `deploy/effect-mining-worker.service.example`: separate worker service template.
- Create `deploy/effect-mining-scheduler.service.example`: scheduler service template.
- Modify `shopping_shorts/requirements.txt`: no new runtime dependency; document existing basis only if needed.

### Task 1: Durable database and leased queue

**Files:**
- Create: `shopping_shorts/effect_mining/__init__.py`
- Create: `shopping_shorts/effect_mining/db.py`
- Test: `shopping_shorts/tests/test_effect_mining_db.py`

- [x] **Step 1: Write failing tests** for source scheduling dedupe, item identity upsert, atomic claim, expired lease recovery, exponential retry, dead-letter transition, and queue counts.
- [x] **Step 2: Run** `pytest -q shopping_shorts/tests/test_effect_mining_db.py` and confirm import/behavior failures are caused by the missing package.
- [x] **Step 3: Implement** schema creation and the minimal `MiningDB` API used by those tests. Use UTC epoch seconds and `BEGIN IMMEDIATE` for claims.
- [x] **Step 4: Run** `pytest -q shopping_shorts/tests/test_effect_mining_db.py` and confirm all tests pass.
- [ ] **Step 5: Commit** with `feat: add durable effect mining queue`. (Git index permission blocked; final commit pending.)

### Task 2: Injected continuous pipeline

**Files:**
- Create: `shopping_shorts/effect_mining/connectors.py`
- Create: `shopping_shorts/effect_mining/analyzers.py`
- Create: `shopping_shorts/effect_mining/pipeline.py`
- Test: `shopping_shorts/tests/test_effect_mining_pipeline.py`

- [x] **Step 1: Write failing tests** using fake connector/downloader/analyzer implementations. Verify `discover → acquire → measure → promote`, repeated discovery dedupe, analyzer-version dedupe, and failure retry.
- [x] **Step 2: Run** `pytest -q shopping_shorts/tests/test_effect_mining_pipeline.py` and observe the expected missing-module failures.
- [x] **Step 3: Implement** protocols, registry, handlers, and deterministic candidate derivation. Production adapters call `youtube_search.search`, `media_download.download_any`, and `scene_cut` functions only inside handler execution.
- [x] **Step 4: Run** both effect-mining test files and confirm they pass.
- [ ] **Step 5: Commit** with `feat: connect mining collection and analysis stages`. (Git index permission blocked; final commit pending.)

### Task 3: Scheduler, worker loop, and CLI

**Files:**
- Create: `shopping_shorts/effect_mining/runner.py`
- Create: `shopping_shorts/effect_mining/cli.py`
- Test: `shopping_shorts/tests/test_effect_mining_cli.py`

- [x] **Step 1: Write failing tests** for one scheduler tick, one worker tick, JSON status output, and source registration validation.
- [x] **Step 2: Run** `pytest -q shopping_shorts/tests/test_effect_mining_cli.py` and confirm expected failures.
- [x] **Step 3: Implement** one-shot functions first, then continuous loops with configurable poll seconds and graceful keyboard interrupt.
- [x] **Step 4: Run** all three effect-mining test files and confirm they pass.
- [ ] **Step 5: Commit** with `feat: add continuous mining scheduler and worker cli`. (Git index permission blocked; final commit pending.)

### Task 4: Deployment templates and operator proof

**Files:**
- Create: `deploy/effect-mining-worker.service.example`
- Create: `deploy/effect-mining-scheduler.service.example`
- Create: `handoff/effect-mining-workers.md`

- [x] **Step 1: Add service templates** that run scheduler and worker as separate processes, read environment from `/etc/shopping-shorts.env`, restart on failure, and write data under a configurable worker data root.
- [x] **Step 2: Exercise locally** with a temporary DB: initialize, add a no-network source, schedule, print status, stop and resume.
- [x] **Step 3: Run regression tests**: `pytest -q shopping_shorts/tests/test_effect_mining_db.py shopping_shorts/tests/test_effect_mining_pipeline.py shopping_shorts/tests/test_effect_mining_cli.py`.
- [x] **Step 4: Inspect** `git status --porcelain` and verify only this track's files changed.
- [x] **Step 5: Record** deployment variables, verified commands, limitations, and next tracks in the handoff; commit pending Git index permission.

## Self-review

- Spec coverage: queue durability, dedupe, retry, lease recovery, pipeline stages, real adapters, CLI and separate deployment processes all have tasks.
- Deferred work is explicitly outside this phase rather than an implementation placeholder: OCR/audio/LLM/review UI/recipe generation each consumes the stable signal and candidate contracts created here.
- Type consistency: every stage exchanges JSON-compatible dictionaries keyed by persisted integer IDs; analyzer version belongs in measure dedupe and signal uniqueness.
