"""기획 단계만 실행하는 얇은 러너 — SSE 이벤트 yield.
pipeline.py의 STEP1 로직을 그대로 따르되(같은 state.json 스키마), 웹에서 실시간
진행상황을 보여줄 수 있게 print 대신 이벤트를 yield한다. pipeline.py는 안 건드림(최소침습).
주의: pipeline.py처럼 `from . import agent_plan`(상대import, 패키지경로로만 로드 가능)를
쓰지 않는다 — dashboard/server.py가 sys.path에 scripts/yt_agents 디렉터리를 직접 추가해
flat하게 import하므로(Task 4), 여기서도 sys.path 기반 절대import로 통일한다."""
import json
import sys
from datetime import datetime
from pathlib import Path

# Task 4(dashboard/server.py)에서 flat import를 지원하기 위해 sys.path 기반 절대import를 사용한다.
# agent_plan.py의 상대import가 작동하도록 먼저 scripts/ 디렉터리를 sys.path에 추가해
# scripts.yt_agents를 정상적인 패키지로 인식되게 한다.
_root_scripts = str(Path(__file__).parent.parent)
if _root_scripts not in sys.path:
    sys.path.insert(0, _root_scripts)

# sys.path 기반 절대import (pipeline.py의 상대import와 다르게)
from scripts.yt_agents import agent_plan

ROOT = Path(__file__).parent.parent.parent
OUT = ROOT / "out"
THRESHOLD = 7
MAX_RETRY = 3


def _state_path(pid):
    return OUT / f"yt_pipeline_{pid}" / "state.json"


def _load_state(pid, idea):
    p = _state_path(pid)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"id": pid, "idea": idea, "created": datetime.now().isoformat(), "steps": {}, "files": {}}


def _save_state(pid, state):
    p = _state_path(pid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_references(references: list[dict]) -> str:
    if not references:
        return ""
    lines = ["\n\n=== 사용자가 담은 터진 영상 레퍼런스 (참고할 것) ==="]
    for r in references:
        lines.append(f"- \"{r.get('title','')}\" ({r.get('channel_title','')}) "
                      f"— 채널 평균 대비 {r.get('view_pct_above_avg', 0):+.0f}%")
    return "\n".join(lines)


def run_plan_stage(idea: str, references: list[dict] = None, pipeline_id: str = None):
    pid = pipeline_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    idea_with_refs = idea + _format_references(references or [])
    state = _load_state(pid, idea)

    yield {"type": "step", "id": "plan", "status": "running", "attempt": 1, "max_attempt": MAX_RETRY}

    plan_dir = OUT / f"yt_pipeline_{pid}"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.md"

    qc_feedback, total_score, attempt = "", 0, 0
    for attempt in range(MAX_RETRY):
        plan_text = agent_plan.run(idea_with_refs, feedback=qc_feedback)
        plan_file.write_text(plan_text, encoding="utf-8")

        qc = agent_plan.qc(plan_text)
        total_score = qc.get("total", 0)
        passed = total_score >= THRESHOLD

        yield {
            "type": "step", "id": "plan", "status": "running",
            "attempt": attempt + 1, "max_attempt": MAX_RETRY,
            "qc_score": total_score, "feedback": qc.get("feedback", ""),
        }
        if passed:
            break
        qc_feedback = qc.get("feedback", "")

    state["steps"]["plan"] = {"status": "done", "qc_score": total_score, "attempts": attempt + 1}
    state["files"]["plan"] = str(plan_file)
    _save_state(pid, state)

    yield {"type": "done", "pid": pid, "plan_text": plan_text, "qc_score": total_score}
