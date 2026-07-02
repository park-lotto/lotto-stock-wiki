"""track.py — 퍼널 정확도 이력 누적 (자동 수렴의 토대).

매일 '퍼널이 뽑은 종목' vs '그가 실제 산 종목' 적중률을 스냅샷으로 쌓는다.
이력이 쌓이면 (1) 정교해지고 있나 추세로 확인 (2) 계속 놓치는 패턴 발견
(3) 임계값을 과거 이력에 백테스트해 자동 튜닝 — 점근적 수렴.

CLI:
    python -m pipeline.people.track 태린이아빠          # 오늘 스냅샷 저장
    python -m pipeline.people.track 태린이아빠 --history  # 적중률 추세
"""
import sys
import io
import json
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_ROOT = Path(__file__).parent.parent.parent
_BASE = _ROOT / "pipeline" / "people" / "validation"


def _record_from_selection(sel: dict) -> dict:
    """today_selection 결과 → 이력 레코드 (순수 함수)."""
    v = sel.get("validation") or {}
    cands = [c["name"] for c in sel.get("candidates", [])]
    return {
        "date": sel.get("date"),
        "hit_rate": v.get("hit_rate"),
        "mentioned_count": v.get("mentioned_count"),
        "matched": v.get("matched", []),
        "missed": v.get("missed", []),
        "candidates": cands,
        "thresholds": (sel.get("thresholds") or {}),
    }


def save_record(person: str, record: dict, base_dir=None) -> Path:
    base = Path(base_dir) if base_dir else _BASE
    d = base / person
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{record.get('date') or 'unknown'}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def history(person: str, base_dir=None) -> list:
    """날짜순 이력 레코드 리스트."""
    base = Path(base_dir) if base_dir else _BASE
    d = base / person
    if not d.exists():
        return []
    recs = []
    for f in d.glob("*.json"):
        try:
            recs.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    recs.sort(key=lambda r: r.get("date") or "")
    return recs


def snapshot(person: str, base_dir=None) -> dict:
    """오늘 종목선정 재현 → 검증 → 이력 저장. 저장된 레코드 반환."""
    from pipeline.people.brain_view import today_selection
    sel = today_selection(person)
    if not sel.get("available"):
        return {"available": False, "note": sel.get("note")}
    rec = _record_from_selection(sel)
    save_record(person, rec, base_dir=base_dir)
    return rec


def trend(person: str, base_dir=None) -> dict:
    """적중률 추세 요약."""
    recs = history(person, base_dir=base_dir)
    rates = [(r["date"], r["hit_rate"]) for r in recs if r.get("hit_rate") is not None]
    return {
        "days": len(recs),
        "series": rates,
        "latest": rates[-1][1] if rates else None,
        "avg": (round(sum(x for _, x in rates) / len(rates), 3) if rates else None),
    }


if __name__ == "__main__":
    person = sys.argv[1] if len(sys.argv) > 1 else "태린이아빠"
    if "--history" in sys.argv:
        t = trend(person)
        print(f"[{person}] 적중률 이력 {t['days']}일 · 평균 {t['avg']} · 최근 {t['latest']}")
        for date, rate in t["series"]:
            bar = "█" * int((rate or 0) * 40)
            print(f"  {date}  {rate:.2f}  {bar}")
    else:
        rec = snapshot(person)
        if rec.get("available") is False:
            print(rec.get("note"))
        else:
            print(f"[{person}] {rec['date']} 스냅샷 저장 — 적중률 {rec['hit_rate']} "
                  f"(일치 {len(rec['matched'])}, 놓침 {len(rec['missed'])})")
