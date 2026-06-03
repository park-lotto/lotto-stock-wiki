"""
channel_pipeline/pipeline.py — 채널 집계 멀티에이전트 파이프라인 오케스트레이터

실행:
    python -m scripts.channel_pipeline.pipeline
    python -m scripts.channel_pipeline.pipeline --date 2026-06-04
    python -m scripts.channel_pipeline.pipeline --dry-run
    python -m scripts.channel_pipeline.pipeline --step A          # A 단계만
    python -m scripts.channel_pipeline.pipeline --resume          # 실패 단계부터

흐름:
    STEP 0: 파일 목록 확정 + 비용 추정
    STEP 1: Agent A (Gemini Flash) — 분류
    STEP 2: Agent B (Sonnet) — 토론
    STEP 3a: Agent C1 (Sonnet) — wiki 승격 결정  ┐ 병렬
    STEP 3b: Agent E (Haiku) — 브리핑 초안        ┘
    STEP 4: Agent D (Haiku) — wiki 업데이트
    STEP 5: 브리핑 최종화 + git commit
"""

from __future__ import annotations
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from channel_pipeline import agent_A, agent_B, agent_C1, agent_D, agent_E
from channel_pipeline.file_manifest import get_manifest, summarize
from channel_pipeline.cost_estimator import can_run, reduce_scope

PIPELINE_DIR_BASE = ROOT / "pipeline"


# ──────────────────────────────────────────────
# 상태 관리
# ──────────────────────────────────────────────

def _state_path(run_date: str) -> Path:
    d = run_date.replace("-", "")
    return PIPELINE_DIR_BASE / d / "state.json"


def load_state(run_date: str) -> dict:
    p = _state_path(run_date)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "run_date": run_date,
        "pipeline_id": f"{run_date.replace('-','')}_{datetime.now():%H%M%S}",
        "steps": {k: {"status": "pending"} for k in ["A_claims","B_debate","C1_wiki","D_update","E_html"]},
        "file_manifest": {},
        "cost_estimate_usd": {},
    }


def save_state(run_date: str, state: dict) -> None:
    p = _state_path(run_date)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _step_done(state: dict, step: str) -> bool:
    return state["steps"].get(step, {}).get("status") == "done"


def _mark_step(state: dict, step: str, status: str, error: str | None = None) -> None:
    state["steps"][step] = {
        "status": status,
        "completed_at": datetime.now().isoformat() if status in ("done","failed") else None,
        "error": error,
    }


def _pipeline_dir(run_date: str) -> Path:
    d = run_date.replace("-", "")
    p = PIPELINE_DIR_BASE / d
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ──────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────

async def run_pipeline(run_date: str, state: dict, dry_run: bool,
                        step_only: str | None = None) -> dict:
    pd = _pipeline_dir(run_date)

    # ── STEP 0: 파일 목록 + 비용 추정 ──
    if not state["file_manifest"]:
        manifest = get_manifest(run_date)
        ok, cost, reason = can_run(manifest)
        print(f"\n[STEP 0] 파일 목록")
        print(summarize(manifest))
        print(f"예상 비용: {reason}")

        if not ok:
            manifest = reduce_scope(manifest)
            ok2, cost2, reason2 = can_run(manifest)
            print(f"범위 축소 후: {reason2}")
            if not ok2:
                print("[중단] 비용 초과 — 파이프라인 종료")
                return state

        state["file_manifest"] = manifest
        state["cost_estimate_usd"]["total"] = cost
        save_state(run_date, state)

    manifest = state["file_manifest"]

    # ── STEP 1: Agent A ──
    if (not step_only or step_only == "A") and not _step_done(state, "A_claims"):
        print(f"\n[STEP 1] Agent A — Gemini Flash 분류")
        _mark_step(state, "A_claims", "running")
        save_state(run_date, state)
        try:
            result_A = await agent_A.run(manifest, run_date)
            agent_A.save(result_A, pd)
            _mark_step(state, "A_claims", "done")
            print(f"  → {result_A.processing_stats.get('total_claims', 0)}개 클레임")
        except Exception as e:
            _mark_step(state, "A_claims", "failed", str(e))
            print(f"[STEP 1 실패] {e}")
        save_state(run_date, state)

    if step_only == "A":
        return state

    # ── STEP 2: Agent B ──
    if not _step_done(state, "A_claims"):
        print("[STEP 2 스킵] A 단계 미완료")
        return state

    if (not step_only or step_only == "B") and not _step_done(state, "B_debate"):
        print(f"\n[STEP 2] Agent B — Sonnet 교차검증·토론")
        claims_data = _load_json(pd / "A_claims.json")
        channels_data = claims_data.get("channels", {})
        _mark_step(state, "B_debate", "running")
        save_state(run_date, state)
        try:
            result_B = await agent_B.run(channels_data, run_date)
            agent_B.save(result_B, pd)
            _mark_step(state, "B_debate", "done")
            print(f"  → {result_B.summary.get('total_debates', 0)}개 토론")
        except Exception as e:
            _mark_step(state, "B_debate", "failed", str(e))
            print(f"[STEP 2 실패] {e}")
        save_state(run_date, state)

    if step_only == "B":
        return state

    if not _step_done(state, "B_debate"):
        print("[STEP 3 스킵] B 단계 미완료")
        return state

    debate_data = _load_json(pd / "B_debate.json")

    # ── STEP 3: C1 + E 병렬 ──
    print(f"\n[STEP 3] Agent C1 + E 병렬 실행")

    c1_task = asyncio.create_task(_run_C1(debate_data, run_date, pd, state))
    e_task  = asyncio.create_task(_run_E_draft(debate_data, run_date, pd))

    c1_result, e_result = await asyncio.gather(c1_task, e_task, return_exceptions=True)
    save_state(run_date, state)

    # ── STEP 4: Agent D ──
    if not _step_done(state, "C1_wiki"):
        print("[STEP 4 스킵] C1 단계 미완료")
        return state

    print(f"\n[STEP 4] Agent D — wiki 파일 업데이트")
    decisions_data = _load_json(pd / "C1_wiki_decisions.json")
    _mark_step(state, "D_update", "running")
    save_state(run_date, state)
    try:
        d_result = agent_D.run(decisions_data, dry_run=dry_run)
        _mark_step(state, "D_update", "done")
    except Exception as e:
        _mark_step(state, "D_update", "failed", str(e))
        print(f"[STEP 4 실패] {e}")
    save_state(run_date, state)

    # ── STEP 5: 브리핑 최종화 ──
    if not dry_run and not isinstance(e_result, Exception):
        print(f"\n[STEP 5] 브리핑 + git commit")
        _mark_step(state, "E_html", "done")

        if not dry_run:
            _git_commit(run_date)

    save_state(run_date, state)
    print(f"\n✅ 파이프라인 완료 — {run_date}")
    return state


async def _run_C1(debate_data, run_date, pd, state):
    _mark_step(state, "C1_wiki", "running")
    try:
        result_C1 = await agent_C1.run(debate_data, run_date)
        agent_C1.save(result_C1, pd)
        _mark_step(state, "C1_wiki", "done")
        print(f"  [C1] → {len(result_C1.wiki_updates)}개 결정")
        return result_C1
    except Exception as e:
        _mark_step(state, "C1_wiki", "failed", str(e))
        print(f"  [C1 실패] {e}")
        return None


async def _run_E_draft(debate_data, run_date, pd):
    decisions_path = pd / "C1_wiki_decisions.json"
    decisions_data = _load_json(decisions_path) if decisions_path.exists() else {}
    try:
        out_path = agent_E.run(debate_data, decisions_data, run_date)
        print(f"  [E] → {out_path.name}")
        return out_path
    except Exception as e:
        print(f"  [E 실패] {e}")
        return None


def _git_commit(run_date: str) -> None:
    try:
        subprocess.run(
            ["git", "add", "wiki/", "out/", "pipeline/"],
            cwd=ROOT, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"auto: channel-ingest {run_date}"],
            cwd=ROOT, check=True, capture_output=True
        )
        print("  [git] 커밋 완료")
    except subprocess.CalledProcessError:
        print("  [git] 변경사항 없거나 오류")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="채널 집계 파이프라인")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume",  action="store_true")
    parser.add_argument("--step",    choices=["A","B","C1","D","E"], default=None)
    args = parser.parse_args()

    state = load_state(args.date)
    if not args.resume:
        # 새 실행이면 완료된 단계 초기화
        for k in state["steps"]:
            if state["steps"][k]["status"] == "failed":
                state["steps"][k]["status"] = "pending"

    asyncio.run(run_pipeline(args.date, state, args.dry_run, args.step))


if __name__ == "__main__":
    main()
