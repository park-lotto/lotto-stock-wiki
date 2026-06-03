from __future__ import annotations
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.channel_pipeline import agent_a, agent_b, agent_d
from scripts.channel_pipeline.manifest import get_manifest
from scripts.channel_pipeline.cost_guard import can_run, reduce_scope
from scripts.channel_pipeline.wiki_writer import apply_decisions
from scripts.channel_pipeline.models import PipelineState, Claim, WikiDecision


# ─────────────────────────────────────
# 상태 관리
# ─────────────────────────────────────

def _state_path(run_date: str, base_dir: Path) -> Path:
    return base_dir / "pipeline" / run_date.replace("-", "") / "state.json"


def load_state(run_date: str, base_dir: Path = ROOT) -> PipelineState:
    p = _state_path(run_date, base_dir)
    if p.exists():
        return PipelineState.model_validate_json(p.read_text(encoding="utf-8"))
    return PipelineState(run_date=run_date)


def save_state(state: PipelineState, base_dir: Path = ROOT) -> None:
    p = _state_path(state.run_date, base_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def _pipeline_dir(run_date: str, base_dir: Path) -> Path:
    d = base_dir / "pipeline" / run_date.replace("-", "")
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─────────────────────────────────────
# 메인
# ─────────────────────────────────────

async def run_pipeline(
    run_date: str,
    base_dir: Path = ROOT,
    wiki_root: Path = ROOT,
    dry_run: bool = False,
    resume: bool = False,
) -> PipelineState:
    state = load_state(run_date, base_dir) if resume else PipelineState(run_date=run_date)
    pd = _pipeline_dir(run_date, base_dir)

    # ── STEP 0: 파일 수집 + 비용 추정 ──
    manifest = get_manifest(run_date)
    ok, cost, reason = can_run(manifest)
    print(f"\n[STEP 0] 파일 수집 — {reason}")
    if not ok:
        manifest = reduce_scope(manifest)
        ok2, cost2, reason2 = can_run(manifest)
        print(f"  범위 축소 후: {reason2}")
        if not ok2:
            state.step = "failed"
            state.error = f"비용 초과: {reason2}"
            save_state(state, base_dir)
            return state

    # ── STEP 1: Agent A ──
    if state.step == "pending":
        print(f"\n[STEP 1] Agent A — Gemini Flash 분류")
        try:
            claims = await agent_a.run(manifest)
            claims_path = pd / "claims.json"
            agent_a.save(claims, claims_path)
            state.step = "A_done"
            state.claims_file = str(claims_path.relative_to(base_dir))
            save_state(state, base_dir)
            print(f"  → {len(claims)}개 클레임 추출")
        except Exception as e:
            state.step = "failed"
            state.error = f"Agent A: {e}"
            save_state(state, base_dir)
            return state

    # ── STEP 2: Agent B ──
    if state.step == "A_done":
        print(f"\n[STEP 2] Agent B — Sonnet 검증+결정")
        claims_path = base_dir / state.claims_file
        claims_raw = json.loads(claims_path.read_text(encoding="utf-8"))
        claims = [Claim.model_validate(c) for c in claims_raw]
        try:
            decisions = agent_b.run(claims, run_date)
            decisions_path = pd / "decisions.json"
            agent_b.save(decisions, decisions_path)
            state.step = "B_done"
            state.decisions_file = str(decisions_path.relative_to(base_dir))
            save_state(state, base_dir)
            append_count = sum(1 for d in decisions if d.action in ("append", "flag"))
            print(f"  → {len(decisions)}개 결정 (wiki반영: {append_count}개)")
        except Exception as e:
            state.step = "failed"
            state.error = f"Agent B: {e}"
            save_state(state, base_dir)
            return state

    # ── STEP 3: wiki 업데이트 + 브리핑 병렬 ──
    if state.step == "B_done":
        print(f"\n[STEP 3] wiki 업데이트 + 브리핑 병렬 실행")
        claims_raw = json.loads((base_dir / state.claims_file).read_text(encoding="utf-8"))
        decisions_raw = json.loads((base_dir / state.decisions_file).read_text(encoding="utf-8"))
        claims = [Claim.model_validate(c) for c in claims_raw]
        decisions = [WikiDecision.model_validate(d) for d in decisions_raw]

        wiki_task = asyncio.to_thread(apply_decisions, decisions, wiki_root, dry_run)
        briefing_task = asyncio.to_thread(
            agent_d.run, claims, decisions, run_date, base_dir / "out",
        )
        wiki_result, briefing_result = await asyncio.gather(
            wiki_task, briefing_task, return_exceptions=True,
        )

        if isinstance(wiki_result, Exception):
            print(f"  [wiki] 오류: {wiki_result}")
        else:
            print(f"  [wiki] {len(wiki_result)}개 파일 업데이트")

        if isinstance(briefing_result, Exception):
            print(f"  [브리핑] 오류: {briefing_result} — fallback 생성")
            agent_d.save_fallback(claims, run_date, base_dir / "out")
        else:
            print(f"  [브리핑] {briefing_result.name}")

        if not dry_run:
            _git_commit(run_date, base_dir)

        state.step = "done"
        save_state(state, base_dir)
        print(f"\n✅ 파이프라인 완료 — {run_date}")

    return state


def _git_commit(run_date: str, base_dir: Path) -> None:
    try:
        subprocess.run(
            ["git", "add", "wiki/", "out/", "pipeline/"],
            cwd=base_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"auto: channel-ingest {run_date}"],
            cwd=base_dir, check=True, capture_output=True,
        )
        print("  [git] 커밋 완료")
    except subprocess.CalledProcessError:
        print("  [git] 변경사항 없거나 오류")


def main() -> None:
    parser = argparse.ArgumentParser(description="채널 집계 파이프라인 v2")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume",  action="store_true")
    args = parser.parse_args()
    asyncio.run(run_pipeline(args.date, dry_run=args.dry_run, resume=args.resume))


if __name__ == "__main__":
    main()
