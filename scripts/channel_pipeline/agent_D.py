"""
channel_pipeline/agent_D.py — Haiku: wiki 파일 실제 수정 + 신뢰도 갱신

판단 없이 기계적으로:
  - C1 결정대로 마크다운 파일에 행 삽입/플래그 추가
  - 증권사 컨센서스 1행 덮어쓰기
  - 7일 롤링 만료 행 처리
  - channel_trust.json 갱신
"""

from __future__ import annotations
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from channel_pipeline import trust_tracker

FAILED_LOG = ROOT / "pipeline" / "D_failed_updates.txt"


def _log_fail(decision_id: str, error: str) -> None:
    FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FAILED_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} | {decision_id} | {error}\n")


def _ensure_section(text: str, section: str) -> str:
    """섹션이 없으면 파일 끝에 추가"""
    if section not in text:
        text = text.rstrip() + f"\n\n{section}\n\n"
    return text


def _insert_after_section(text: str, section: str, new_row: str) -> str:
    """섹션 헤더 바로 다음 줄에 새 행 삽입"""
    lines = text.split("\n")
    result = []
    inserted = False
    for i, line in enumerate(lines):
        result.append(line)
        if not inserted and section in line:
            # 다음 빈줄 또는 표 헤더 다음에 삽입
            result.append(new_row)
            inserted = True
    if not inserted:
        result.append(f"\n{section}\n{new_row}")
    return "\n".join(result)


def _overwrite_broker_row(text: str, broker: str, new_row: str) -> str:
    """증권사 컨센서스 — 동일 증권사 행 교체"""
    lines = text.split("\n")
    replaced = False
    result = []
    for line in lines:
        if f"| {broker} " in line or f"|{broker}|" in line:
            if not replaced:
                result.append(new_row)
                replaced = True
            # 기존 행 삭제 (추가 안 함)
        else:
            result.append(line)
    if not replaced:
        # 컨센서스 섹션 끝에 추가
        text2 = "\n".join(result)
        text2 = _insert_after_section(text2, "## 증권사 컨센서스", new_row)
        return text2
    return "\n".join(result)


def _add_conflict_flag(text: str, note: str, section: str) -> str:
    """⚠️ 충돌 플래그 추가"""
    flag_line = f"\n> ⚠️ CONFLICT: {note}\n"
    lines = text.split("\n")
    result = []
    for line in lines:
        result.append(line)
        if section in line:
            result.append(flag_line)
    return "\n".join(result)


def _apply_rolling(text: str, section: str, days: int = 7) -> str:
    """7일 롤링 — 8일 이상 경과 행 제거"""
    cutoff = datetime.now() - timedelta(days=days)
    lines = text.split("\n")
    in_section = False
    result = []

    for line in lines:
        if line.startswith("## ") and section in line:
            in_section = True
            result.append(line)
            continue
        elif line.startswith("## ") and in_section:
            in_section = False

        if in_section and re.match(r'^\| 20\d{2}-\d{2}-\d{2}', line):
            date_match = re.match(r'^\| (\d{4}-\d{2}-\d{2})', line)
            if date_match:
                try:
                    row_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    if row_date < cutoff:
                        continue  # 8일 이상 경과 → 삭제
                except ValueError:
                    pass

        result.append(line)

    return "\n".join(result)


def apply_single(decision: dict, dry_run: bool = False) -> bool:
    """단일 결정 적용"""
    action = decision.get("action", "skip")
    target = decision.get("target_file", "")
    section = decision.get("target_section", "## 최신 이벤트")
    content = decision.get("content_to_append", "")
    conflict_note = decision.get("conflict_note", "")
    decision_id = decision.get("decision_id", "?")

    if action == "skip":
        return True

    path = ROOT / target
    if not path.exists():
        if action == "create":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"# {path.stem.replace('stock_', '')}\n\n{section}\n\n",
                encoding="utf-8"
            )
        else:
            _log_fail(decision_id, f"파일 없음: {target}")
            return False

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")

        if action == "flag":
            text = _add_conflict_flag(text, conflict_note or "충돌 감지", section)

        elif action in ("update", "create") and content:
            # 증권사 컨센서스는 덮어쓰기
            if "증권사" in section:
                broker = content.split("|")[1].strip() if "|" in content else ""
                if broker:
                    text = _overwrite_broker_row(text, broker, content)
                else:
                    text = _ensure_section(text, section)
                    text = _insert_after_section(text, section, content)
            else:
                text = _ensure_section(text, section)
                text = _apply_rolling(text, section)
                text = _insert_after_section(text, section, content)

        if not dry_run:
            path.write_text(text, encoding="utf-8")
            print(f"  [{action}] {target} → {section}")

        return True

    except Exception as e:
        _log_fail(decision_id, str(e))
        print(f"  [Agent D] 오류 ({decision_id}): {e}")
        return False


def run(decisions_data: dict, dry_run: bool = False) -> dict:
    """Agent D 메인 실행"""
    print(f"[Agent D] Haiku wiki 업데이트 시작 (dry_run={dry_run})")

    decisions = decisions_data.get("wiki_updates", [])
    success, fail = 0, 0

    for decision in decisions:
        ok = apply_single(decision, dry_run)
        if ok:
            success += 1
        else:
            fail += 1

    # 신뢰도 갱신
    trust_updates = decisions_data.get("trust_updates", [])
    if trust_updates and not dry_run:
        trust = trust_tracker.load()
        trust_tracker.apply_deltas(trust, trust_updates)

    print(f"[Agent D] 완료 — 성공: {success}, 실패: {fail}")
    return {"success": success, "fail": fail, "dry_run": dry_run}
