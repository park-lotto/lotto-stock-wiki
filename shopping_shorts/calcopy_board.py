"""칼카피 진행판 — 채널마다 칼카피 표준 7단계가 어디까지 왔나 (관제 097, 2026-10-15).

판단 주인: collect() 하나. 원장은 채널 폴더마다 `channel/<채널>/calcopy.json` 한 장이다.
화면(/admin/calcopy)·자동 돌림·보고는 전부 이 함수를 부른다 — 각자 폴더를 훑지 않는다.

원장 형식:
{
  "name": "뜨거운사람들", "url": "https://www.youtube.com/@...", "concept": "인물 썰",
  "stats": {"subs": 21000, "median_views": 138658, "per_day": 1.0},
  "steps": {"1": {"state": "done|doing|blocked|todo", "date": "2026-09-27",
                  "note": "한 줄", "files": ["channel/hotpeople/..."]}, ...},
  "next": "다음 할 일 한 줄"
}
"""
from __future__ import annotations

import json
from pathlib import Path

STEPS = [
    ("1", "채널 선정"),
    ("2", "실측(10층)"),
    ("3", "대본 구조"),
    ("4", "소재 확보"),
    ("5", "컨셉 프리셋"),
    ("6", "시험 3편"),
    ("7", "시청 판정·등록"),
]
STATES = ("done", "doing", "blocked", "todo")

ROOT = Path(__file__).resolve().parent.parent  # repo 루트 (channel/ 이 여기 있다)


def _step(raw) -> dict:
    s = raw if isinstance(raw, dict) else {}
    state = s.get("state") if s.get("state") in STATES else "todo"
    files = [f for f in (s.get("files") or []) if isinstance(f, str)]
    return {"state": state, "date": str(s.get("date") or ""),
            "note": str(s.get("note") or ""), "files": files}


def collect(root: Path | None = None) -> dict:
    """channel/*/calcopy.json 을 모아 채널별 단계 상태를 돌려준다. 깨진 원장은 errors 로 드러낸다."""
    base = Path(root) if root else ROOT
    channels, errors = [], []
    for path in sorted((base / "channel").glob("*/calcopy.json")):
        slug = path.parent.name
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            errors.append({"slug": slug, "error": f"{type(e).__name__}: {e}"})
            continue
        steps = {k: _step((raw.get("steps") or {}).get(k)) for k, _ in STEPS}
        done = sum(1 for v in steps.values() if v["state"] == "done")
        current = next((k for k, _ in STEPS if steps[k]["state"] != "done"), None)
        channels.append({
            "slug": slug,
            "name": str(raw.get("name") or slug),
            "url": str(raw.get("url") or ""),
            "concept": str(raw.get("concept") or ""),
            "stats": raw.get("stats") if isinstance(raw.get("stats"), dict) else {},
            "steps": steps,
            "done": done,
            "current": current,
            "blocked": any(v["state"] == "blocked" for v in steps.values()),
            "next": str(raw.get("next") or ""),
            "updated": max((v["date"] for v in steps.values()), default=""),
        })
    channels.sort(key=lambda c: c["updated"], reverse=True)
    return {"steps": [{"key": k, "label": l} for k, l in STEPS],
            "channels": channels, "errors": errors}


def ledger_path(slug: str, root: Path | None = None) -> Path:
    return (Path(root) if root else ROOT) / "channel" / slug / "calcopy.json"


def load(slug: str, root: Path | None = None) -> dict:
    p = ledger_path(slug, root)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"steps": {}}


def set_step(slug: str, key: str, state: str, note: str = "", files: list[str] | None = None,
             date: str = "", root: Path | None = None, **top) -> dict:
    """원장 쓰기의 주인 — 자동 실행기·손 기록 모두 이 함수로만 쓴다. top 은 name·url·concept·stats·next."""
    import datetime as _dt
    if key not in dict(STEPS) or state not in STATES:
        raise ValueError(f"단계/상태가 틀림: {key} {state}")
    d = load(slug, root)
    for k, v in top.items():
        if v is not None:
            d[k] = v
    d.setdefault("steps", {})[key] = {"state": state, "date": date or _dt.date.today().isoformat(),
                                     "note": note, "files": list(files or [])}
    p = ledger_path(slug, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d
