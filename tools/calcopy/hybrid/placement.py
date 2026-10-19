# -*- coding: utf-8 -*-
"""자막·효과 **배치 규칙** — 벤치 줄판독에서 세고(count), 편마다 계산한다(place). 관제 097, 2026-10-19.

사장님 10-19(강한 규칙): 자막팩을 모든 줄에 똑같이 바르지 않는다. 벤치는 영상마다·장면마다 다르게 들어간다
(어느 덩어리에 팝/타이핑/강조색/스티커/효과음이 붙나). 꾸밈이 없는 덩어리·구간은 꾸미지 않는다(없는 것도 스타일).

판단 주인:
  · 규칙 세기   = count(판 설정)  → 판 설정 placement.counted (벤치 8편 줄판독 + 효과음 신호 표 sfx_events_rules)
  · 편마다 배치 = place(rows, 판 설정, 씨앗) — **이 함수 하나**. 렌더러(render_bench)·자막표·검사(check_place)가 이걸 부른다.
자막팩(caption-motions.js)은 효과의 '모양'만, 어디에 붙나는 여기서만 정한다.

어떻게 편마다 다르게(10-19 줄판독 실측: 키치잇 Nv99 = 꾸밈 거의 없음·BRa = 타이핑 10·💎3, 편마다 결이 크게 다르다 →
벤치 8편을 한 평균으로 뭉개면 '어느 편도 아닌' 영상이 된다):
  ① 씨앗(편 slug)으로 **본보기 벤치 편 하나**를 고른다(8편 고르게) — 같은 편은 늘 같은 본보기, 편이 여럿이면 벤치 편들이 골고루.
  ② 칸(slot = 화자 narr/orig × 말 차례의 첫 덩어리 first/rest)마다 본보기 편의 등장 비율(팝·컷·반투명·타이핑…)을 우리 덩어리 수에 나눠 준다.
     본보기 편에 그 칸이 없으면 8편 합계 비율.
  ③ 강조 낱말 비율·스티커 종류와 개수·효과음 수도 본보기 편 그대로(우리 덩어리에 조건 맞는 자리가 있을 때만).
  ④ 어느 덩어리에 붙나 = 조건(lex: 감탄·고급·값·물음, 대본 key 낱말)이 맞는 덩어리 먼저, 나머지는 고르게 펼침.

    PYTHONUTF8=1 py tools/calcopy/hybrid/placement.py count <판>          # 벤치 줄판독 → 판 설정 placement.counted 갱신
    PYTHONUTF8=1 py tools/calcopy/hybrid/placement.py show <판>           # 센 규칙 표
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SLOTS = ("narr.first", "narr.rest", "orig.first", "orig.rest")
LEX = {
    "excl": r"!|대박|너무|진짜|완전|와우|와~|우와|헐|미쳤|최고|짱|맛있|예쁘|좋아|감동|난리",
    "lux": r"고급|명품|부내|부자|럭셔리|프리미엄|귀티|비싼|비싸|사악|억|백만|천만|수천",
    "price": r"\d+\s*(원|만|천)|가격|값|가성비|만원|원대|세일|할인",
    "ask": r"\?",
}


def lex_of(text: str) -> list[str]:
    return [k for k, p in LEX.items() if re.search(p, text or "")]


def norm_enter(s: str) -> str:
    """줄판독 enter 칸(자유 글) → pop|cut|fade|typing|append|other. '타이핑 아님'·'전체 한 번에' 같은 부정이 먼저."""
    s = (s or "").lower()
    if re.search(r"타이핑\s*아님|타이핑 없음|전체 한 번에|instant|^cut|컷인", s):
        return "pop" if re.search(r"작게 시작|튀|pop|확대", s) else "cut"
    if re.search(r"typing|타이핑|한 자씩|글자씩|1자씩", s):
        return "typing"
    if re.search(r"pop|작게 시작|튀어|확대|넘쳤", s):
        return "pop"
    if re.search(r"fade|반투명|서서히|flash", s):
        return "fade"
    if re.search(r"append|이어 붙", s):
        return "append"
    return "other"


def sticker_kind(what: str) -> str:
    w = what or ""
    for k, p in (("gem", r"💎|다이아"), ("heart", r"♥|하트"), ("spark_lines", r"강조선|\\\s*\||반짝|✦|별"), ("circle_arrow", r"빨간\s*원|화살표|동그라미"),
                 ("kk_doodle", r"ㅋㅋ"), ("comment_card", r"댓글"), ("object_pop", r"누끼|3D|입체|사진 스티커")):
        if re.search(p, w):
            return k
    return "other"


def slot_of(speaker: str, first: bool) -> str:
    return f"{speaker}.{'first' if first else 'rest'}"


# ── 세기 ──────────────────────────────────────────────────────────────
def _bench_rows(path: Path) -> tuple[list[dict], dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = [l for l in d.get("lines") or [] if not str(l.get("layer", "")).startswith("원본")]   # 원본에 박힌 층은 벤치 채널이 얹은 게 아니다
    prev = None
    for l in rows:
        sp = "narr" if str(l.get("speaker", "")).startswith("나레") else "orig"
        l["_sp"], l["_first"], prev = sp, sp != prev, sp
        l["_enter"] = norm_enter(str(l.get("enter", "")))
        l["_lex"] = lex_of(l.get("text", ""))
    return rows, d


def _sfx_table(style: dict) -> dict:
    B = style["bench"]
    if not B.get("sfx_events"):
        return {}
    d = json.loads((ROOT / B["sfx_events"]).read_text(encoding="utf-8"))
    out = {}
    for k, v in d.items():
        if k.startswith(B["sfx_key"] + "/"):
            where = []
            for e in v.get("cand") or []:
                near = e.get("near") or {}
                w = min(near, key=near.get) if near else "none"
                where.append(w if near.get(w, 9) <= 0.3 else "none")
            out[k.split("/", 1)[1]] = where
    return out


def count(style: dict) -> dict:
    """벤치 줄판독(덩어리) + 효과음 신호 표 → 편마다·칸마다 빈도. 반환 꼴 = 판 설정 placement.counted."""
    B = style["bench"]
    files = sorted((ROOT / B["line_reads"]).glob("*.json"))
    if not files:
        raise SystemExit(f"줄판독이 없다: {B['line_reads']}")
    sfx = _sfx_table(style)
    allslot = defaultdict(lambda: {"n": 0, "enter": Counter(), "emph": 0})
    videos = []
    for f in files:
        rows, d = _bench_rows(f)
        vid = d.get("id", f.stem)
        sl = defaultdict(lambda: {"n": 0, "enter": Counter(), "emph": 0})
        stick, variants = Counter(), Counter()
        stick_lex = defaultdict(Counter)
        for l in rows:
            key = slot_of(l["_sp"], l["_first"])
            for s in (sl[key], allslot[key]):
                s["n"] += 1; s["enter"][l["_enter"]] += 1; s["emph"] += bool(l.get("emph"))
            v = str(l.get("variant") or "")
            if v and v != "기본":
                variants[v] += 1
            for st in l.get("sticker") or []:
                k = sticker_kind(st.get("what", "") if isinstance(st, dict) else str(st))
                stick[k] += 1
                for x in l["_lex"] or ["none"]:
                    stick_lex[k][x] += 1
        videos.append({"id": vid, "n": len(rows),
                       "slots": {k: {"n": s["n"], "enter": dict(s["enter"].most_common()), "emph": s["emph"]} for k, s in sl.items()},
                       "stickers": dict(stick), "sticker_lex": {k: dict(c) for k, c in stick_lex.items()}, "variants": dict(variants),
                       "sfx": sfx.get(vid, []), "no_caption": len(d.get("no_caption") or [])})
    nv = len(videos)
    out = {"made_by": "tools/calcopy/hybrid/placement.py count", "source": B["line_reads"], "n_videos": nv,
           "slots": {k: {"n": s["n"], "enter": {e: round(c / s["n"], 3) for e, c in s["enter"].most_common()}, "emph": round(s["emph"] / s["n"], 3)}
                     for k, s in sorted(allslot.items())},
           "share": {"emph": round(sum(1 for v in videos if any(s["emph"] for s in v["slots"].values())) / nv, 3),
                     "typing": round(sum(1 for v in videos if any(s["enter"].get("typing") for s in v["slots"].values())) / nv, 3),
                     "sfx": round(sum(1 for v in videos if v["sfx"]) / nv, 3)},
           "stickers": {k: round(sum(1 for v in videos if v["stickers"].get(k)) / nv, 3) for k in sorted({k for v in videos for k in v["stickers"]})},
           "videos": videos}
    return out


# ── 편마다 배치(판단 주인) ──────────────────────────────────────────────
def _h(seed: str, what: str) -> int:
    return int(hashlib.md5(f"{seed}|{what}".encode()).hexdigest()[:8], 16)


def _chance(seed: str, what: str) -> float:
    return _h(seed, what) / 0xFFFFFFFF


def reference(style: dict, seed: str) -> dict | None:
    """씨앗 → 본보기 벤치 편(counted.videos 중 하나). 판 설정 placement.reference 로 고정할 수도 있다."""
    vs = (style["placement"].get("counted") or {}).get("videos") or []
    if not vs:
        return None
    fix = style["placement"].get("reference")
    if fix:
        return next((v for v in vs if v["id"] == fix), vs[0])
    return vs[_h(seed, "reference") % len(vs)]


def _alloc(n: int, dist: dict) -> list[str]:
    """비율 → n 개 이름(가장 큰 나머지) — 순서는 부드러운 가중 돌림(같은 것이 몰리지 않게)."""
    tot = sum(dist.values()) or 1
    want = {k: v / tot * n for k, v in dist.items()}
    cnt = {k: int(w) for k, w in want.items()}
    for k in sorted(want, key=lambda k: want[k] - cnt[k], reverse=True)[:n - sum(cnt.values())]:
        cnt[k] += 1
    cur = {k: 0.0 for k in cnt}
    seq = []
    for _ in range(n):
        for k in cur:
            cur[k] += cnt[k]
        k = max(cur, key=cur.get)
        seq.append(k); cur[k] -= n
    return seq


def _spread(idx: list[int], k: int) -> list[int]:
    if k <= 0 or not idx:
        return []
    if k >= len(idx):
        return list(idx)
    step = len(idx) / k
    return [idx[int(step * i + step / 2)] for i in range(k)]


def place(rows: list[dict], style: dict, seed: str) -> dict:
    """rows = 자막 덩어리 [{line, j, speaker:'narr'|'orig', text, key?, key_color?, object_src?, t0, t1}] (시간 순).
    반환 {reference, rows:[…+first, lex, enter, variant, emph, stickers], sfx:[{t, kind, why}], flashes:[t], log:[왜]}."""
    P = style["placement"]; R = P.get("rules") or {}; C = P.get("counted") or {}
    ref = reference(style, seed)
    out = [dict(r) for r in rows]
    log = [f"본보기 벤치 편 = {ref['id'] if ref else '없음(합계 비율)'}"]
    for k, r in enumerate(out):
        r["first"] = k == 0 or r["speaker"] != out[k - 1]["speaker"] or r["line"] != out[k - 1]["line"]
        r["lex"] = lex_of(r["text"])
        r["stickers"] = list(r.get("stickers") or [])
        r["slot"] = slot_of(r["speaker"], r["first"])
    fixed = R.get("enter") or {}
    # ① 등장: 칸마다 본보기 편 비율을 우리 덩어리에 나눠 준다(타이핑은 감탄 덩어리 먼저)
    for key in SLOTS:
        idx = [i for i, r in enumerate(out) if r["slot"] == key]
        if not idx:
            continue
        if key in fixed:
            for i in idx:
                out[i]["enter"] = fixed[key]
            continue
        src = ((ref or {}).get("slots", {}).get(key) or {}).get("enter") or (C.get("slots", {}).get(key) or {}).get("enter") or {"cut": 1}
        dist = {}
        for e, v in src.items():      # 이어 붙이기·기타는 우리 렌더에서 컷과 같다
            e = "cut" if e in ("other", "append") else e
            dist[e] = dist.get(e, 0) + v
        seq = _alloc(len(idx), dist)
        nty = seq.count("typing")
        rest = [e for e in seq if e != "typing"]
        ty_at = set(sorted(idx, key=lambda i: (0 if set(out[i]["lex"]) & {"excl"} else 1, i))[:nty]) if nty else set()
        it = iter(rest)
        for i in idx:
            out[i]["enter"] = "typing" if i in ty_at else next(it)
    # ② 강조 낱말: 칸마다 본보기 편 강조 비율 × 우리 덩어리 수 (대본 key 가 있는 덩어리 중 고르게) — 0 이면 칠하지 않는다
    for key in SLOTS:
        rs = ((ref or {}).get("slots", {}).get(key) or (C.get("slots", {}).get(key)) or {})
        rate = rs.get("emph", 0) / max(1, rs.get("n", 1)) if ref and key in ref.get("slots", {}) else (C.get("slots", {}).get(key) or {}).get("emph", 0.0)
        idx_all = [i for i, r in enumerate(out) if r["slot"] == key]
        idx = [i for i in idx_all if out[i].get("key")]
        for i in _spread(idx, round(rate * len(idx_all))):
            out[i]["emph"] = [{"word": out[i]["key"], **({"color": out[i]["key_color"]} if out[i].get("key_color") else {})}]
    # ③ 줄 변형(꿀템노트 빨강 펀치 등): 본보기 편에 그 변형이 있으면 조건 맞는 덩어리 하나
    for name, rule in (R.get("variants") or {}).items():
        have = sum(c for v, c in ((ref or {}).get("variants") or {}).items() if rule.get("match", name) in v)
        cand = [i for i, r in enumerate(out) if r["speaker"] == rule.get("speaker", r["speaker"]) and (not rule.get("lex") or set(rule["lex"]) & set(r["lex"]))]
        for i in _spread(cand, have):
            out[i]["variant_force"] = name
            log.append(f"변형 {name} → {out[i]['line']}「{out[i]['text']}」")
    # ④ 스티커: 본보기 편의 종류·개수(규칙에 있는 종류만 — 그릴 수 있는 것), 조건 맞는 덩어리
    for kind, rule in (R.get("stickers") or {}).items():
        if kind == "comment_card":
            continue        # 댓글 카드는 렌더러 틀 층(대본 comment 가 있을 때) — plan_rows 가 본보기 편 수로 정한다
        need = int(((ref or {}).get("stickers") or {}).get(kind, 0)) if ref else 0
        if not need:
            continue
        cand = [i for i, r in enumerate(out) if (not rule.get("lex") or set(rule["lex"]) & set(r["lex"])) and (not rule.get("speaker") or r["speaker"] == rule["speaker"])
                and (not rule.get("needs_key") or r.get("key")) and (kind != "object_pop" or r.get("object_src"))]
        for i in _spread(cand, need):
            st = {"kind": kind, "word": out[i].get("key") or ""}
            if kind == "object_pop":
                st.update({"src": out[i]["object_src"], "hold": "beat"})
            out[i]["stickers"].append(st)
            log.append(f"스티커 {kind} → {out[i]['line']}「{out[i]['text']}」")
        if len(cand) < need:
            log.append(f"스티커 {kind} 본보기 {need}개 중 {len(cand)}개만(조건 맞는 덩어리 모자람)")
    # 타이핑 덩어리에 따라붙는 스티커(키치잇 원음 타이핑 + ♥): 본보기 편에 그 스티커가 있을 때만
    ty = R.get("typing_sticker")
    if ty and ((ref or {}).get("stickers") or {}).get(ty["kind"]):
        for r in out:
            if r["enter"] == "typing" and r["speaker"] == ty.get("speaker", r["speaker"]):
                r["stickers"].append({"kind": ty["kind"], "follow": True})
    # ⑤ 효과음: 본보기 편의 고립 후보 수(판 규칙 max 까지)·자리
    S = R.get("sfx") or {}
    sfx = []
    want = (ref or {}).get("sfx") or []
    n = min(len(want), int(S.get("max", 3)))
    if S and n:
        spots = []
        for w in [w for w, _ in Counter(want).most_common() if w != "none"] + ["cap"]:
            if w == "switch":
                spots += [(r["t0"], "switch") for k, r in enumerate(out) if k and r["speaker"] != out[k - 1]["speaker"]]
            elif w == "sticker":
                spots += [(r["t0"], "sticker") for r in out if r["stickers"]]
            else:
                spots += [(r["t0"], "cap") for r in out[1:]]
        seen = set()
        for t, why in spots:      # 벤치 고립 후보는 앞쪽(첫 원음 훅·첫 전환)에 몰린다 → 앞에서부터
            if len(sfx) >= n:
                break
            if all(abs(t - s) > 0.4 for s in seen):
                sfx.append({"t": round(t, 3), "kind": S.get("kind", "ding"), "why": why}); seen.add(t)
        sfx.sort(key=lambda e: e["t"])
    log.append(f"효과음 {len(sfx)}발(본보기 {len(want)}) {[(s['t'], s['why']) for s in sfx]}")
    # ⑥ 전환 흰 번쩍임(키치잇 BRa·_Wa): 판 규칙 편 비율로 있나 → 있으면 마지막 화자 바뀜
    F = R.get("flash")
    flashes = []
    if F and _chance(seed, "flash") < float(F.get("share", 0)):
        cand = [r["t0"] for k, r in enumerate(out) if k and r["speaker"] != out[k - 1]["speaker"]]
        if cand:
            flashes = [cand[-1]]
        log.append(f"번쩍 {flashes}")
    effects_step(out, style, seed, log)
    for r in out:
        r["variant"] = r.pop("variant_force", None) or variant_of(r, style)
    tally = Counter(r["enter"] for r in out)
    log.append(f"등장 {dict(tally)} · 강조 {sum(1 for r in out if r.get('emph'))}/{len(out)}")
    return {"reference": ref["id"] if ref else None, "rows": out, "sfx": sfx, "flashes": flashes, "log": log}


# ── 효과별 붙는 조건(주인 = 자막팩 계약 caption-motions.js CAPTION_EFFECT_RULES, 관제 235) ─────────────
# 조건 글(채널·편당 횟수·글자 수)은 계약 파일 한 곳에서 읽는다 — 여기는 '그 조건이 우리 덩어리 중 어디냐'를 고르는 법(박자 자리)만.
# 효과 이름 → (자막팩에서 어떻게 거나: 줄 변형 이름 | 스티커 kind, 박자 자리 고르기)
EFFECT_HOW = {
    "rgbGlitch": ("variant", "glitch"), "wipeRTL": ("variant", "wipe"), "rainbowCycle": ("variant", "rainbow"),
    "hearts": ("sticker", "hearts"), "comic_burst": ("sticker", "comic_burst"), "aside_line": ("sticker", "aside_line"),
    "append_text": ("sticker", "append_text"), "sound_word": ("sticker", "sound_word"), "small_text": ("sticker", "small_text"),
}
TEXT_NEEDS = {"aside_line": "aside", "append_text": "append", "sound_word": "sound", "small_text": "small"}   # 대본 caps 에 그 글이 있을 때만


def effect_rules() -> dict:
    s = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
    return json.loads(s.split("/*RULES*/")[1]) if "/*RULES*/" in s else {}


def _per_video(cond: str) -> tuple[int, int]:
    m = re.search(r"편당\s*(\d+)\s*(?:~\s*(\d+))?\s*회", cond or "")
    return (int(m.group(1)), int(m.group(2) or m.group(1))) if m else (0, 1)


def _effect_where(name: str, out: list[dict], cond: str) -> list[int]:
    nc = lambda r: len(re.sub(r"\s", "", r["text"]))
    m = re.search(r"(\d+)\s*~\s*(\d+)\s*자", cond or ""); lo, hi = (int(m.group(1)), int(m.group(2))) if m else (0, 99)
    m = re.search(r"(\d+)\s*자 이상", cond or ""); lo = int(m.group(1)) if m else lo
    hook_end = next((r["t0"] for k, r in enumerate(out) if k and r["speaker"] != out[0]["speaker"]), 8.0)
    if name == "rgbGlitch":       # 훅(앞 원음 구간) 원음 줄, 제품 이름(key)이 처음 나오는 줄
        return [i for i, r in enumerate(out) if r["speaker"] == "orig" and r["t0"] < max(hook_end, 3.5) and r.get("key")][:1]
    if name == "wipeRTL":         # 화면 바뀐 직후 첫 줄, 8자 이상 원음, 둘로 나눈 둘째 조각 제외
        return [i for i, r in enumerate(out) if r["speaker"] == "orig" and r["first"] and nc(r) >= lo]
    if name == "rainbowCycle":    # 편 첫 나레 줄, 8~10자
        i = next((i for i, r in enumerate(out) if r["speaker"] == "narr"), None)
        return [i] if i is not None and lo <= nc(out[i]) <= hi + 2 else []
    if name == "hearts":          # 편 첫 장면 감탄 한마디
        return [0] if out and set(out[0]["lex"]) & {"excl"} else []
    if name == "comic_burst":     # 2초 넘게 머무는 나레 줄
        return [i for i, r in enumerate(out) if r["speaker"] == "narr" and r["t1"] - r["t0"] > 2.0]
    if name == "aside_line":      # 1.5초+ 머무는 원음 줄
        return [i for i, r in enumerate(out) if r["speaker"] == "orig" and r["t1"] - r["t0"] >= 1.5]
    return [i for i, r in enumerate(out)]


def effects_step(out: list[dict], style: dict, seed: str, log: list):
    """CAPTION_EFFECT_RULES 중 이 판 벤치 채널 효과만: 편당 횟수(씨앗으로 범위 안에서 고름) → 박자 자리 → 줄 변형·스티커."""
    ko = style["bench"].get("ko")
    ref = reference(style, seed)
    for name, R in effect_rules().items():
        if name.startswith("_") or name not in EFFECT_HOW or not ko or ko not in R.get("채널", ""):
            continue
        # 영상마다 다르게: 그 효과가 '본 곳'(벤치 편 id 앞부분)에 본보기 편이 있을 때만 — 없는 편을 본보기로 삼았으면 안 붙인다
        seen_ids = re.findall(r"[A-Za-z0-9_-]{3,}", R.get("본 곳", ""))
        if not ref or not any(ref["id"].startswith(x) for x in seen_ids):
            continue
        lo, hi = _per_video(R.get("조건", ""))
        n = lo + _h(seed, f"effect:{name}") % (hi - lo + 1)
        if not n:
            log.append(f"효과 {name} 0회(편당 {lo}~{hi})"); continue
        need = TEXT_NEEDS.get(name)
        cand = [i for i in _effect_where(name, out, R.get("조건", "")) if not need or out[i].get(need)]
        how, key = EFFECT_HOW[name]
        for i in _spread(cand, n):
            if how == "variant":
                if not out[i].get("variant_force"):
                    out[i]["variant_force"] = key
            else:
                st = {"kind": key}
                if need:
                    st["text"] = out[i][need]
                if name == "comic_burst":
                    st["variant"] = "a"
                if name == "hearts":
                    st.update({"x": 50, "y": 41, "hold": 1.0})
                out[i]["stickers"].append(st)
            log.append(f"효과 {name} → {out[i]['line']}「{out[i]['text']}」(계약 조건: {R.get('조건', '')[:40]})")


def variant_of(r: dict, style: dict) -> str:
    """정한 등장 → 자막팩 줄 변형 이름. 팩 기본(caption.pack_default: 칸마다 팩이 원래 내는 등장)과 같으면 변형 없음(''),
    다르면 caption.variant_for[등장] — 팩에 그 변형이 있어야 한다(caption-motions.js PACKS)."""
    cap = style["caption"]
    if r["enter"] == "typing" and cap.get("typing_variant") and r["speaker"] == "orig":
        return cap["typing_variant"]
    if r["enter"] == (cap.get("pack_default") or {}).get(r["slot"], r["enter"]):
        return ""
    return (cap.get("variant_for") or {}).get(r["enter"], "")


def check_place(placed: dict, style: dict) -> dict:
    """배치 결과 ↔ 본보기 벤치 편 대조(검사): 칸마다 등장 비율 차이(최대 절댓값)·강조 비율·스티커·효과음 수."""
    ref = next((v for v in (style["placement"].get("counted") or {}).get("videos") or [] if v["id"] == placed.get("reference")), None)
    rows = placed["rows"]
    rep, worst = {}, 0.0
    for key in SLOTS:
        mine = [r for r in rows if r["slot"] == key]
        rs = (ref or {}).get("slots", {}).get(key)
        if not mine or not rs:
            continue
        ours = Counter(r["enter"] for r in mine)
        bd = {("cut" if e in ("other", "append") else e): 0.0 for e in rs["enter"]}
        for e, c in rs["enter"].items():
            bd["cut" if e in ("other", "append") else e] += c / rs["n"]
        diff = max(abs(ours.get(e, 0) / len(mine) - bd.get(e, 0)) for e in set(bd) | set(ours))
        worst = max(worst, diff)
        rep[key] = {"bench": {e: round(v, 2) for e, v in bd.items()}, "ours": {e: round(c / len(mine), 2) for e, c in ours.items()},
                    "bench_emph": round(rs["emph"] / rs["n"], 2), "ours_emph": round(sum(1 for r in mine if r.get("emph")) / len(mine), 2), "n": len(mine)}
    rep["stickers"] = {"bench": (ref or {}).get("stickers"), "ours": dict(Counter(s["kind"] for r in rows for s in r["stickers"]))}
    rep["sfx"] = {"bench": len((ref or {}).get("sfx") or []), "ours": len(placed["sfx"])}
    # 덩어리 수가 적으면 비율이 굵게 갈린다(우리 3덩어리 칸에서 1개 = 33%) → 칸 크기에 맞춘 허용 오차
    tol = {k: 0.5 / max(1, v["n"]) + 0.15 for k, v in rep.items() if isinstance(v, dict) and "n" in v}
    ok = all(max(abs(v["ours"].get(e, 0) - v["bench"].get(e, 0)) for e in set(v["bench"]) | set(v["ours"])) <= tol[k]
             for k, v in rep.items() if k in tol)
    return {"ok": ok, "reference": placed.get("reference"), "worst_slot_diff": round(worst, 3), "slots": rep}


def main():
    from tools.calcopy.hybrid import styles as ST
    if len(sys.argv) < 3:
        print(__doc__); return 2
    cmd, name = sys.argv[1], sys.argv[2]
    st = ST.load(name)
    if cmd == "count":
        c = count(st)
        ST.save_counted(name, c)
        print(json.dumps({k: v for k, v in c.items() if k != "videos"}, ensure_ascii=False, indent=1))
        for v in c["videos"]:
            print(v["id"], v["n"], {k: s["enter"] for k, s in v["slots"].items()}, "stk", v["stickers"], "var", v["variants"], "sfx", len(v["sfx"]))
    elif cmd == "show":
        print(json.dumps({k: v for k, v in st["placement"].items() if k != "counted"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
