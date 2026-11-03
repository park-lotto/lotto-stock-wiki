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


# ── 채널 보관함(서버 데이터) — 사장님이 페이지에서 바꾸는 것만 여기 산다 (2026-10-15) ──
#   분석 결과(갈래.json·1차분석_편별.json·calcopy.json)는 저장소 channel/<slug>/ 에서 읽기만 한다.
#   보관함은 shopping_shorts/data/calcopy/channels.json(git 밖) — 서버가 git 파일을 쓰면 자동배포가 멈춘다.
import re as _re
import threading as _th
import urllib.parse as _up

STATUSES = ("후보", "진행", "완료", "보류", "삭제")
TAGS = ("정치", "연예", "뷰티", "썰", "홈템")
_LOCK = _th.Lock()


def store_path(data_dir: Path | None = None) -> Path:
    return (Path(data_dir) if data_dir else Path(__file__).resolve().parent / "data") / "calcopy" / "channels.json"


def _store_load(data_dir=None) -> dict:
    p = store_path(data_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _store_save(d: dict, data_dir=None):
    p = store_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _now():
    import datetime as _dt
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def slug_of(url: str) -> str:
    """채널 주소 → 보관함 열쇠. @핸들은 핸들 그대로(한글 허용), /channel/UC… 는 id."""
    u = _up.unquote((url or "").strip())
    m = _re.search(r"/channel/(UC[\w-]{20,})", u)
    if m:
        return m.group(1)
    m = _re.search(r"@([^/?#\s]+)", u)
    if m:
        return m.group(1)
    raise ValueError("채널 주소가 아닙니다 (예: https://www.youtube.com/@채널이름)")


def add_channel(url: str, tags=None, memo: str = "", priority: int = 3, resolver=None, data_dir=None) -> dict:
    """채널 저장. resolver(url)->{name,channel_id,subs} 는 실패해도 저장은 한다(실패 사유를 남긴다)."""
    slug = slug_of(url)
    info, err = {}, ""
    if resolver:
        try:
            info = resolver(url) or {}
        except Exception as e:  # noqa: BLE001 — 수치 실패는 저장을 막지 않되 화면에 드러낸다
            err = f"{type(e).__name__}: {str(e)[:160]}"
    with _LOCK:
        d = _store_load(data_dir)
        if slug in d and d[slug].get("status") != "삭제":
            raise ValueError(f"이미 저장된 채널입니다: {slug}")
        d[slug] = {"url": _up.unquote(url.strip()), "name": info.get("name") or slug,
                   "channel_id": info.get("channel_id"), "subs": info.get("subs"), "resolve_error": err,
                   "tags": [t for t in (tags or []) if t], "memo": memo, "priority": int(priority),
                   "status": "후보", "created": _now(), "updated": _now(), "styles": {}}
        _store_save(d, data_dir)
    return d[slug]


def update_channel(slug: str, fields: dict, data_dir=None) -> dict:
    allowed = {"name", "tags", "memo", "priority", "status"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"바꿀 수 없는 칸: {sorted(bad)}")
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"상태는 {STATUSES} 중 하나")
    with _LOCK:
        d = _store_load(data_dir)
        c = d.setdefault(slug, {"status": "진행", "created": _now(), "styles": {}})
        c.update(fields)
        c["updated"] = _now()
        _store_save(d, data_dir)
    return c


def set_style(slug: str, name: str, rename: str | None = None, confirmed: bool | None = None,
              memo: str | None = None, data_dir=None) -> dict:
    """갈래 확정·이름 바꾸기 — 사람 판정은 여기에만 쌓인다(분석 파일은 안 건드림)."""
    with _LOCK:
        d = _store_load(data_dir)
        c = d.setdefault(slug, {"status": "진행", "created": _now(), "styles": {}})
        s = c.setdefault("styles", {}).setdefault(name, {})
        if rename is not None:
            s["rename"] = rename.strip()
        if confirmed is not None:
            s["confirmed"] = bool(confirmed)
            s["confirmed_at"] = _now()
        if memo is not None:
            s["memo"] = memo
        c["updated"] = _now()
        _store_save(d, data_dir)
    return s


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def board(root: Path | None = None, data_dir=None) -> dict:
    """보관함 목록 — 저장소 원장(collect)과 서버 보관함을 채널 열쇠로 합친다."""
    base = collect(root)
    store = _store_load(data_dir)
    by = {c["slug"]: c for c in base["channels"]}
    # 같은 채널이 두 이름으로 갈리지 않게: 보관함에 저장한 주소가 분석 원장(channel/<slug>)의 주소와 같으면 원장 이름으로 합친다
    def _norm(u):
        u = _up.unquote(str(u or "")).strip().rstrip("/")
        return u[:-7] if u.endswith("/shorts") else u
    by_url = {_norm(c.get("url")): k for k, c in by.items() if c.get("url")}
    for k in list(store):
        tgt = by_url.get(_norm(store[k].get("url")))
        if tgt and tgt != k:
            store[tgt] = {**store.pop(k), **{x: v for x, v in (store.get(tgt) or {}).items() if v}}
    out = []
    for slug in sorted(set(by) | set(store)):
        c = dict(by.get(slug) or {"slug": slug, "name": slug, "url": "", "concept": "", "stats": {},
                                  "steps": {k: _step(None) for k, _ in STEPS}, "done": 0, "current": "1",
                                  "blocked": False, "next": "", "updated": ""})
        s = store.get(slug, {})
        if s.get("status") == "삭제":
            continue
        for k in ("name", "url"):
            if s.get(k):
                c[k] = s[k]
        stats = dict(c.get("stats") or {})
        if s.get("subs") is not None:
            stats["subs"] = s["subs"]
        c["stats"] = stats
        c.update({"status": s.get("status") or ("진행" if slug in by else "후보"), "tags": s.get("tags") or [],
                  "memo": s.get("memo") or "", "priority": s.get("priority", 3),
                  "resolve_error": s.get("resolve_error") or "", "saved": s.get("created") or ""})
        g = _read_json((Path(root) if root else ROOT) / "channel" / slug / "갈래.json")
        c["n_styles"] = len((g or {}).get("styles") or [])
        out.append(c)
    out.sort(key=lambda c: (STATUSES.index(c["status"]) if c["status"] in STATUSES else 9, c["priority"], c["name"]))
    return {"steps": base["steps"], "channels": out, "errors": base["errors"], "statuses": STATUSES, "tags": TAGS}


def detail(slug: str, root: Path | None = None, data_dir=None) -> dict:
    """채널 하나 — 단계·갈래(사람 판정 덮어씀)·편 목록."""
    b = next((c for c in board(root, data_dir)["channels"] if c["slug"] == slug), None)
    if b is None:
        raise KeyError(slug)
    folder = (Path(root) if root else ROOT) / "channel" / slug
    g = _read_json(folder / "갈래.json") or {}
    rows = {r["id"]: r for r in (_read_json(folder / "1차분석_편별.json") or [])}
    human = (_store_load(data_dir).get(slug) or {}).get("styles") or {}
    styles = []
    for s in g.get("styles") or []:
        h = human.get(s["name"], {})
        vids = [rows[i] for i in s["ids"] if i in rows]
        styles.append({**s, "label": h.get("rename") or s["name"], "confirmed": bool(h.get("confirmed")),
                       "human_memo": h.get("memo", ""),
                       "voice": _top([v.get("voice") for v in vids]), "honorific": _top([v.get("honorific") for v in vids]),
                       "duration_median": _median([v.get("duration") for v in vids]),
                       "cps_median": _median([v.get("cps") for v in vids]),
                       "effects_per_video": _median([v.get("n_effects") for v in vids]),
                       "videos": [{k: v.get(k) for k in ("id", "views", "title", "hook", "voice", "honorific",
                                                         "duration", "frame_variant", "beats", "n_effects", "n_sfx")}
                                  for v in vids]})
    return {**b, "styles": styles, "group_rule": g.get("rule", ""), "n_videos": len(rows)}


def _top(xs):
    import collections as _c
    xs = [x for x in xs if x]
    return _c.Counter(xs).most_common(3)


def _median(xs):
    import statistics as _s
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(_s.median(xs), 1) if xs else None


# ── 숏템프리셋 홈(관제 224, 2026-10-17 사장님 "칼카피라고 하지 말고 숏템프리셋") ──
#    판단 주인: preset_home() 하나. 주인 데이터는 장부 3장(channel/브랜드.json·스타일.json·결과물.json) —
#    칼카피숏템엔진 트랙이 쓰고, 이 함수는 읽어서 브랜드·스타일·결과물을 서로 엮기만 한다.
#    결과물 판정 상태(result_state)도 여기 한 곳 — 화면은 이 값을 그대로 띄운다.
PRESET_LEDGERS = ("channel/브랜드.json", "channel/스타일.json", "channel/결과물.json")   # 페이지가 읽는 장부 = 엔진에서 옮길 장부(tools/calcopy/sync_preset_ledgers.py)
PRESET_DOCS = (
    ("channel/sseolpulda/스타일_전수분류.md", "썰풀다 스타일 전수분류"),
    ("channel/sseolpulda/스타일_역할극/설명서.md", "대사썰(역할극) 설명서"),
    ("channel/sseolpulda/동종채널_2026-10-17.md", "동종 채널 조사 10-17"),
    ("channel/homedesignnote/대본설명서/설명서.md", "잇썸홈(두유노홈디노) 대본 설명서"),
)
RESULT_STATES = ("통과", "사장님 확인 대기", "자동 검사만", "검수 중")


def result_state(judge: str, fine: bool = False) -> str:
    """결과물 장부의 판정 글(judge) → 상태 4칸 중 하나. 사람 판정 전·확인 대기를 '통과'로 세지 않는다.

    판정 글 읽기의 주인은 이 함수 하나다(표준 tools/calcopy/칼카피_공통규칙표준.md §11 ⑧ — preset_card 도 이걸 부른다).
    ① judge 앞머리 토큰이 있으면 그것만 본다: [사장님승인]·[페이블통과] → 통과 · [자동검사만] → 자동 검사만 · [확인대기] → 사장님 확인 대기.
    ② 토큰이 없으면 옛 글 규칙 — 단 '사장님 승인'·'컨펌' 은 통과(10-25 잇템로그 승인 8편이 '확인 대기'로 뜬 사고).
    fine=True 면 통과를 '사장님 승인'·'페이블 통과'로 갈라 돌려준다(L3 사장님 판정 = preset_card.facts owner_pass).
    """
    j = str(judge or "").lstrip()
    tokens = {"[사장님승인]": "사장님 승인", "[페이블통과]": "페이블 통과", "[자동검사만]": "자동 검사만", "[확인대기]": "사장님 확인 대기"}
    st = next((v for t, v in tokens.items() if j.startswith(t)), None)
    if st is None:
        if "자동 검사" in j:
            st = "자동 검사만"
        elif "사장님 승인" in j or "컨펌" in j:
            st = "사장님 승인"
        elif "후보" in j or "사장님" in j or "확인 전" in j or "재확인" in j:
            st = "사장님 확인 대기"
        elif "통과" in j:
            st = "페이블 통과" if "페이블" in j else "통과"
        else:
            st = "검수 중"
    if fine:
        return st
    return "통과" if st in ("사장님 승인", "페이블 통과") else st


def preset_home(root: Path | None = None) -> dict:
    """숏템프리셋 홈 — 브랜드(벤치 채널↔우리 이름)·스타일(채널 가로지름)·결과물을 한 번에. 깨진 장부는 errors 로 드러낸다."""
    base = Path(root) if root else ROOT
    errors = []

    def _book(name, key):
        p = base / "channel" / f"{name}.json"
        d = _read_json(p)
        if d is None or not isinstance(d.get(key), (dict, list)):
            errors.append(f"channel/{name}.json 을 읽지 못했다" + ("" if p.exists() else "(파일 없음)"))
            return {}
        return d

    bb, sb, rb = _book("브랜드", "brands"), _book("스타일", "styles"), _book("결과물", "items")
    brand_of = {slug: (b or {}).get("brand") or slug for slug, b in (bb.get("brands") or {}).items()}
    results = []
    for it in rb.get("items") or []:
        results.append({**it, "brand": brand_of.get(it.get("channel")) or it.get("channel_name") or it.get("channel"),
                        "in_ledger": it.get("channel") in brand_of, "state": result_state(it.get("judge"))})
    results.sort(key=lambda r: -(r.get("n") or 0))

    def _bench(raw):
        rows = [{"slug": slug, "brand": brand_of.get(slug, slug), **{k: v for k, v in (b or {}).items()}}
                for slug, b in (raw or {}).items()]
        return sorted(rows, key=lambda b: -(b.get("n") or 0))

    def _strengths(raw):    # 장부 꼴은 dict(what·evidence·strength·channel·source·date) — 옛 글 한 줄도 what 으로 받는다
        return [x if isinstance(x, dict) else {"what": str(x)} for x in (raw or [])]

    styles = []
    for name, st in sorted((sb.get("styles") or {}).items(), key=lambda kv: kv[1].get("priority", 99)):
        bench = _bench(st.get("bench"))
        mine = [r for r in results if r.get("style") == name]
        styles.append({"name": name, "old_name": st.get("old_name", ""), "priority": st.get("priority"),
                       "desc": st.get("desc", ""), "why": st.get("why", ""), "audio_kinds": st.get("audio_kinds") or [],
                       "must": st.get("must") or [], "exclude": st.get("exclude", ""), "how": st.get("how", ""),
                       "example": st.get("example", ""), "flow": st.get("flow") or None,
                       "strengths": _strengths(st.get("strengths")), "strengths_keys": st.get("strengths_keys", ""),
                       "bench": bench, "bench_videos": sum(b.get("n") or 0 for b in bench),
                       "results": [r["n"] for r in mine]})
    options = [{"name": name, **{k: v for k, v in (o or {}).items() if k not in ("bench", "strengths")},
                "strengths": _strengths((o or {}).get("strengths")), "bench": _bench((o or {}).get("bench"))}
               for name, o in (sb.get("options") or {}).items()]

    def _brand_row(slug, b, in_ledger):
        mine = [r for r in results if r.get("channel") == slug]
        cnt = {s: sum(1 for r in mine if r["state"] == s) for s in RESULT_STATES}
        return {"slug": slug, "brand": b.get("brand") or slug, "bench": b.get("bench", ""),
                "old_names": b.get("old_names") or [], "in_ledger": in_ledger,
                "styles": [s["name"] for s in styles if any(x["slug"] == slug for x in s["bench"])],
                "results": len(mine), "states": cnt, "latest": mine[0] if mine else None}

    brands = [_brand_row(slug, b or {}, True) for slug, b in (bb.get("brands") or {}).items()]
    for slug in sorted({r.get("channel") for r in results if not r["in_ledger"]} - {None}):
        nm = next((r.get("channel_name") for r in results if r.get("channel") == slug), slug)
        brands.append(_brand_row(slug, {"brand": nm}, False))

    docs = [{"path": p, "title": t, "exists": (base / p).exists()} for p, t in PRESET_DOCS]
    return {"brands": brands, "styles": styles, "results": results, "states": list(RESULT_STATES),
            "docs": docs, "style_judge": sb.get("judge", ""), "not_measured": sb.get("not_measured", ""),
            "root": sb.get("root") or None, "options": options, "doc_paths": sorted(doc_paths(base)),
            "summary": {"brands": len(bb.get("brands") or {}), "styles": len(styles), "results": len(results),
                        "passed": sum(1 for r in results if r["state"] == "통과")},
            "errors": errors}


def referenced_docs(style_book: dict) -> set[str]:
    """스타일 장부가 근거로 가리키는 분석 문서(channel/…md) — flow·strengths·bench·options 의 source 어디에 적혀 있든."""
    found = set()

    def _walk(v):
        if isinstance(v, dict):
            for x in v.values():
                _walk(x)
        elif isinstance(v, list):
            for x in v:
                _walk(x)
        elif isinstance(v, str):
            found.update(m for m in _re.findall(r"channel/[^\s()'\",·]+?\.md", v) if ".." not in m)
    _walk(style_book)
    return found


def doc_paths(root: Path | None = None) -> set[str]:
    """화면에서 열 수 있는 문서 = PRESET_DOCS + 스타일 장부가 가리키는 문서. 이 밖은 안 열린다."""
    base = Path(root) if root else ROOT
    return {p for p, _ in PRESET_DOCS} | referenced_docs(_read_json(base / "channel" / "스타일.json") or {})


def preset_doc(path: str, root: Path | None = None) -> str:
    """분석 문서 원문 — doc_paths 에 든 것만(아무 파일이나 읽히지 않게)."""
    if path not in doc_paths(root):
        raise KeyError(path)
    return ((Path(root) if root else ROOT) / path).read_text(encoding="utf-8")
