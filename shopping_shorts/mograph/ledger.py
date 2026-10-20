# -*- coding: utf-8 -*-
"""부품·레퍼런스·프리셋 장부 — 판단 주인 load_parts / save_verdict / upsert_part (관제 244).

파일(저장소 추적, 한 줄 = 레코드 하나):
  data/parts.jsonl    부품(overlay·scene·transition·caption·preset)
  data/refs.jsonl     레퍼런스(url·구간·실측)
  data/presets.jsonl  모션 프리셋
★overlay 의 모양·시간표 주인은 여전히 static/motion-graphics-pack.js(ITEMS, 관제 222)다 — 장부는 impl 로 가리키고
  출처·라이선스·분류·판정·실적만 더한다. 같은 값을 두 곳에 적지 않는다(label·duration 은 화면이 팩 JS 에서 읽는다).
★판정(verdicts[])은 검사 결과와 같은 레코드에 쌓인다 — "검사 통과인데 사장님은 별로" 건수가 기준을 고칠 신호."""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PARTS = DATA_DIR / "parts.jsonl"
REFS = DATA_DIR / "refs.jsonl"
PRESETS = DATA_DIR / "presets.jsonl"

KINDS = ("overlay", "scene", "transition", "caption", "preset")
VERDICTS = ("good", "bad")
VERDICT_TAGS = ("세로안됨", "너무빠름", "너무느림", "가독성", "촌스러움", "우리톤아님", "가로판OK", "세로로다시", "바로쓰자")

_LOCK = threading.Lock()

# 팩 ITEMS(overlay)·기존 도형(graphic) 씨앗 — impl 키만 적는다. 모양·시간표는 팩 JS 가 주인.
_OVERLAY_SEED = [
    {"slug": "countdown321", "kind": "overlay", "group": "카운트다운·숫자",
     "src": {"url": "https://youtube.com/shorts/xbyBPW8jIKw", "span": "1.20~3.35초"},
     "license": {"origin": "레퍼런스 실측(프레임 수치)", "status": "ours"},
     "impl": {"runtime": "canvas", "file": "shopping_shorts/static/motion-graphics-pack.js", "key": "countdown321"},
     "ratio": "9:16", "check": {"tool": "tools/mograph/check_countdown.py"}},
] + [
    {"slug": "graphic_" + g, "kind": "overlay", "group": grp, "legacy": True,
     "src": {"url": "", "span": ""}, "license": {"origin": "지어낸 모양(옛 도형)", "status": "ours"},
     "impl": {"runtime": "canvas", "file": "shopping_shorts/static/scene-decoration-catalog.js", "key": g},
     "ratio": "9:16"}
    for g, grp in (("arrow_bold", "가리키기"), ("arrow_curve", "가리키기"), ("burst", "강조"), ("circle_ring", "강조"))
]


def _read(path):
    if not path.exists():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            rows.append(json.loads(ln))
    return rows


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _norm(rec):
    rec.setdefault("verdicts", [])
    rec.setdefault("usage", {"jobs_60d": 0, "members_60d": 0})
    rec.setdefault("version", 1)
    rec.setdefault("ratio_variants", [])
    rec.setdefault("check", {})
    rec.setdefault("legacy", False)
    return rec


def load_parts(kind=None, status=None):
    """장부를 읽는다(주인). kind·라이선스 상태로 거를 수 있다."""
    rows = [_norm(r) for r in _read(PARTS)]
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    if status:
        rows = [r for r in rows if (r.get("license") or {}).get("status") == status]
    return rows


def find_part(slug):
    for r in load_parts():
        if r.get("slug") == slug:
            return r
    return None


def upsert_part(rec, overwrite=False):
    """레코드 추가(같은 slug 가 있으면 overwrite 가 아닌 한 verdicts·usage 를 지키고 메타만 갱신)."""
    if not rec.get("slug") or rec.get("kind") not in KINDS:
        raise ValueError("slug·kind 필수 (kind: %s)" % ", ".join(KINDS))
    with _LOCK:
        rows = load_parts()
        for i, r in enumerate(rows):
            if r["slug"] == rec["slug"]:
                keep = {} if overwrite else {k: r[k] for k in ("verdicts", "usage", "check", "version") if k in r}
                rows[i] = _norm({**r, **rec, **keep})
                _write(PARTS, rows)
                return rows[i]
        rows.append(_norm(dict(rec)))
        _write(PARTS, rows)
        return rows[-1]


def save_verdict(slug, verdict, tags=None, note="", by="사장님"):
    """판정 1건을 그 부품 레코드의 verdicts[] 에 쌓는다. 되돌려 주는 값 = 갱신된 레코드."""
    if verdict not in VERDICTS:
        raise ValueError("verdict 는 good|bad")
    tags = [t for t in (tags or []) if t in VERDICT_TAGS]
    with _LOCK:
        rows = load_parts()
        for r in rows:
            if r["slug"] == slug:
                r["verdicts"].append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "by": by, "verdict": verdict,
                                      "tags": tags, "note": (note or "")[:500]})
                _write(PARTS, rows)
                return r
    raise KeyError("없는 부품: %s" % slug)


def last_verdict(rec):
    v = rec.get("verdicts") or []
    return v[-1] if v else None


def sync_from_sources(sources):
    """원본 폴더에서 뽑은 레코드(sources.scan_sources)와 overlay 씨앗을 장부에 넣는다. 있는 것은 메타만 갱신·판정 보존."""
    n = 0
    for rec in _OVERLAY_SEED + list(sources):
        upsert_part(rec)
        n += 1
    return n


def load_refs():
    return _read(REFS)


def load_presets():
    return _read(PRESETS)


if __name__ == "__main__":      # py -m shopping_shorts.mograph.ledger  → 원본 폴더 스캔해 장부 채우기
    from shopping_shorts.mograph import sources
    n = sync_from_sources(sources.scan_sources())
    rows = load_parts()
    print("장부 %s: %d건 동기화 · 총 %d건 (scene %d · overlay %d)" % (
        PARTS, n, len(rows), sum(r["kind"] == "scene" for r in rows), sum(r["kind"] == "overlay" for r in rows)))
