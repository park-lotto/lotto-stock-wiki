# -*- coding: utf-8 -*-
"""숏템프리셋 카드 생성기·합격선 판정기 (관제 263, 표준 tools/calcopy/칼카피_공통규칙표준.md §2·§6, 지시서 표준작업지시/01).

카드는 **읽어 모은 뷰**다(표준 §2-1) — 주인 장부들을 읽어 `channel/<slug>/_kal/카드.json` 을 생성한다. 손으로 고치면 다음 build 가 덮는다.
  주인: channel/프리셋.json(형식·엔진·회원) · channel/브랜드.json · channel/스타일.json · channel/<slug>/_kal/규칙빈도.json(측정)
        · channel/<slug>/줄판독/*.json · channel/<slug>/뜯기/*/뜯기.json · tools/calcopy/hybrid/styles/<판>.json(styles.load)
        · shopping_shorts/static/caption-motions.js(자막팩 키 = PACKS 표식 사이 JSON) · channel/결과물.json
        · 관문 산출물(지시서 04·05·09): <slug 폴더 안> 품질관문.json·재현일치도.json·눈검수.json·업그레이드_측정.json · _kal/회원실측.json

판단 주인(0순위-C): 요소 레코드 = rules_of · 단계 판정 = level · 미측정 거절 = validate. 화면(HTML)·check 출력은 이 셋을 부른다.

    PYTHONUTF8=1 py tools/calcopy/preset_card.py build <slug>|--all
    PYTHONUTF8=1 py tools/calcopy/preset_card.py check <slug>|--all        # L 판정표 + 미측정 수, exit 0 = 고른 프리셋 전부 L4
    PYTHONUTF8=1 py tools/calcopy/preset_card.py audit-diff [감사.json]     # 표준감사 L0/L1 사실 칸과 대조
    (공통 옵션 --root <폴더> : 저장소 대신 그 폴더를 주인 장부 뿌리로 — 사보타주·시험용 복사본)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.calcopy.engine import kal_analyze  # noqa: E402  (줄판독 칸 검사 check_doc · MIN_N — 주인 그대로 부른다)
from tools.calcopy.hybrid import styles as styles_mod  # noqa: E402  (판 설정 읽기 주인)
from shopping_shorts.calcopy_board import result_state  # noqa: E402  (결과물 판정 글 읽기 주인 — 표준 §11 ⑧)

MADE_BY = "tools/calcopy/preset_card.py build"
ROOT = REPO
LINE_READS_MIN = 6              # 표준 §6 L0
COUNTED_MIN = 6                 # 표준 §6 L1 placement.counted.n_videos
ELEMENTS = ("cap_look", "cap_enter", "cap_emph", "cap_exit", "transition", "cut_rhythm", "scene_fit", "bgm", "sfx",
            "meme", "sticker", "pointer", "thumb", "speech", "script")       # 표준 §2-3 15종(이 표기 고정)
CONF_OK = ("픽셀", "눈", "신호")
AXES = {"1자막": ("cap_look", "cap_enter", "cap_emph", "cap_exit"), "3전환": ("transition", "cut_rhythm"),
        "4장면대사": ("scene_fit",), "6대본언어": ("script", "speech"), "7소리": ("bgm", "sfx"),
        "8스티커짤": ("sticker", "meme", "pointer"), "9썸네일": ("thumb",)}
# 판 칸 후보(경로, 지원) — 앞에서부터 처음 있는 칸. 없으면 × + 표준 §3-3 결손 번호.
ENGINE_CELLS = {
    "cap_look": ([("caption.pack", "○")], "-"),
    "cap_enter": ([("placement.rules.enter", "○"), ("caption.pack_default", "○")], "-"),
    "cap_emph": ([("placement.rules.emph", "○"), ("placement.rules.variants", "△"), ("placement.rules.hook", "△"),
                  ("placement.rules.line_color", "△"), ("caption.variant_for", "△")], "-"),
    "cap_exit": ([("caption.exit", "○")], "-"),
    "transition": ([("cuts.transition", "○"), ("placement.rules.transition", "○"), ("frame.flash_sec", "△")], "A1"),
    "cut_rhythm": ([("cuts.shot_median", "○"), ("cuts", "△")], "-"),
    "scene_fit": ([("scene_fit", "○")], "A5"),
    "bgm": ([("bgm.duck_narr_db", "○"), ("bgm.db_below_voice", "△"), ("bgm.id", "△")], "A4"),
    "sfx": ([("placement.rules.sfx", "○"), ("sfx_files", "△")], "A2"),
    "meme": ([("placement.rules.meme", "○")], "A3"),
    "sticker": ([("placement.rules.stickers", "△")], "A3"),
    "pointer": ([("placement.rules.stickers.circle_arrow", "△"), ("placement.rules.pointer", "○")], "A3"),
    "thumb": ([("thumb", "○")], "A6"),
    "speech": ([("speech", "○"), ("cps_target", "○")], "A7"),
    "script": ([("script.audit", "○"), ("script", "△")], "-"),
}
POINTER_RE = re.compile(r"원|화살표|circle|arrow", re.I)
MEME_RE = re.compile(r"짤|meme|밈", re.I)
# 프리셋.json hand_scripts 중 '(옛 …)'·_deprecated 표식 = 공용 렌더러로 대체된 읽기 전용 참고물(표준 §3-1) — 덧대기 수에 안 센다(카드엔 reference 로 남김)
DEPRECATED_RE = re.compile(r"\(옛|_deprecated")


def set_root(root: Path | str | None):
    """주인 장부 뿌리를 바꾼다(시험·사보타주 복사본). 판 설정 읽기 주인(styles)의 폴더도 같이 옮긴다."""
    global ROOT
    ROOT = Path(root).resolve() if root else REPO
    styles_mod.DIR = ROOT / "tools/calcopy/hybrid/styles"


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _json(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _sha(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:12]


def _get(d, dotted: str):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def presets() -> dict:
    d = _json(ROOT / "channel/프리셋.json")
    if not d:
        raise SystemExit("channel/프리셋.json 이 없다 — 형식 장부 없이 카드를 만들 수 없다")
    return d["presets"]


def pack_keys() -> tuple:
    """자막팩 키 = caption-motions.js PACKS 표식 사이 JSON 의 최상위 키(scene_style.caption_pack_keys 와 같은 읽기)."""
    p = ROOT / "shopping_shorts/static/caption-motions.js"
    if not p.exists():
        return ()
    return tuple(json.loads(p.read_text(encoding="utf-8").split("/*PACKS*/")[1]))


# ---------------------------------------------------------------- 주인 장부 읽기
def load_owners(slug: str) -> dict:
    """주인 장부들을 읽는다. 없는 장부는 None(조용히 기본값 금지 — 카드에 없음이 그대로 보인다)."""
    P = presets()
    if slug not in P:
        raise SystemExit(f"프리셋 '{slug}' 이 channel/프리셋.json 에 없다 — 있는 것: {', '.join(P)}")
    pre = P[slug]
    ch = ROOT / "channel" / slug
    inputs = [ROOT / "channel/프리셋.json"]
    brands = _json(ROOT / "channel/브랜드.json") or {}
    if brands:
        inputs.append(ROOT / "channel/브랜드.json")
    brand_ref = pre.get("brand_ref") or slug
    brand = (brands.get("brands") or {}).get(brand_ref)
    st_led = _json(ROOT / "channel/스타일.json")
    sound = []
    if st_led:
        inputs.append(ROOT / "channel/스타일.json")
        for name, s in sorted((st_led.get("styles") or {}).items()):
            b = (s.get("bench") or {}).get(slug)
            if b:
                sound.append({"style": name, "n": b.get("n")})
    lr_files = sorted((ch / "줄판독").glob("*.json")) if (ch / "줄판독").is_dir() else []
    line_reads = [_json(f) for f in lr_files]
    inputs += lr_files
    tt_files = sorted((ch / "뜯기").glob("*/뜯기.json")) if (ch / "뜯기").is_dir() else []
    tteutgi = [_json(f) for f in tt_files]
    inputs += tt_files
    kal = ch / "_kal"
    opt = {}
    for key, p in (("rules_freq", kal / "규칙빈도.json"), ("script_lang", kal / "대본언어.json"), ("palette", ch / "팔레트.json"),
                   ("sfx_events", kal / "sfx_events.json"), ("member_live", kal / "회원실측.json")):
        opt[key] = _json(p)
        if p.exists():
            inputs.append(p)
    gate = {}
    for name in ("품질관문.json", "재현일치도.json", "눈검수.json", "업그레이드_측정.json"):
        hits = sorted(ch.rglob(name)) if ch.is_dir() else []
        gate[name] = _json(hits[-1]) if hits else None
        gate[name + ".path"] = _rel(hits[-1]) if hits else None
        inputs += hits[-1:]
    style, style_name, style_err = None, None, None
    sf = (pre.get("engine") or {}).get("style_file")
    if sf:
        sp = ROOT / sf
        if sp.exists() and sp.parent.resolve() == styles_mod.DIR.resolve():
            style_name = sp.stem
            style = styles_mod.load(style_name)
            raw = _json(sp)
            inputs.append(sp)
            if raw.get("base"):
                inputs.append(styles_mod.DIR / f"{raw['base']}.json")
            if (styles_mod.DIR / "_common.json").exists():
                inputs.append(styles_mod.DIR / "_common.json")
        else:
            style_err = f"판 파일 없음(또는 hybrid/styles 밖): {sf}"
    cm = ROOT / "shopping_shorts/static/caption-motions.js"
    if cm.exists():
        inputs.append(cm)
    res_led = _json(ROOT / "channel/결과물.json")
    results = []
    if res_led:
        inputs.append(ROOT / "channel/결과물.json")
        results = [it for it in res_led.get("items") or [] if it.get("channel") in (slug, pre.get("brand_ref"))]
    return {"slug": slug, "preset": pre, "brand": brand, "sound": sound, "line_reads": line_reads, "line_read_files": lr_files,
            "tteutgi": tteutgi, **opt, "gate": gate, "style": style, "style_name": style_name, "style_raw": _json(ROOT / sf) if style_name else None,
            "style_err": style_err, "style_analysis": (ch / "스타일분석.md").exists(), "results": results,
            "inputs": {_rel(p): _sha(p) for p in sorted(set(inputs), key=lambda x: _rel(x))}}


# ---------------------------------------------------------------- 요소 레코드
def _engine(O: dict, element: str) -> dict:
    st = O["style"]
    cands, gap = ENGINE_CELLS[element]
    if st is None:
        return {"engine_cell": None, "engine_support": "×", "engine_gap": "판 파일 없음(B1·지시서 07)"}
    for path, sup in cands:
        v = _get(st, path)
        if v not in (None, {}, [], ""):
            if element == "cap_look" and v not in pack_keys():
                return {"engine_cell": f"{O['style_name']}.json {path}={v}", "engine_support": "×", "engine_gap": "자막팩 키 없음(caption-motions.js)"}
            if st.get("renderer") != "bench":
                sup = "△"
            return {"engine_cell": f"{O['style_name']}.json {path}", "engine_support": sup, "engine_gap": None if sup == "○" else gap}
    if element == "thumb" and st.get("renderer") == "bench":
        return {"engine_cell": "render_bench thumb.stamp_video(판 칸 없음)", "engine_support": "○", "engine_gap": None}
    return {"engine_cell": None, "engine_support": "×", "engine_gap": gap}


def _rec(element, cond, action, k=None, n=None, rate=None, base=None, grade=None, evidence=None, confidence="미측정", measure_task=None):
    return {"element": element, "cond": cond, "action": action, "k": k, "n": n, "rate": rate, "base": base, "grade": grade,
            "evidence": evidence or [], "confidence": confidence, "measure_task": measure_task}


def _grade(k, n):
    if not n:
        return None
    if n < kal_analyze.MIN_N:
        return "표본부족"
    return "강" if k / n >= 0.6 else "중" if k / n >= 0.3 else "약"


def _kinds(lines, key):
    c = Counter()
    for l in lines:
        v = l.get(key)
        if v is None:
            continue
        c[re.split(r"[\s(（:]", str(v).strip(), maxsplit=1)[0] or "기타"] += 1
    return c


def rules_of(slug: str, O: dict | None = None) -> list[dict]:
    """(판단 주인) 프리셋 하나 → 표준 §2-3 요소 레코드 목록. 규칙빈도 rules[] 매핑 + 줄판독·뜯기·대본언어에서 센 것.
    못 센 요소는 confidence '미측정' + measure_task '06-<slug>'."""
    O = O or load_owners(slug)
    task = f"06-{slug}"
    out: list[dict] = []
    R = O["rules_freq"]
    src = f"channel/{slug}/_kal/규칙빈도.json"
    if R:
        for r in R.get("rules") or []:
            eff = r.get("effect") or ""
            if eff.startswith("enter="):
                el, act = "cap_enter", eff
            elif eff == "enter_fx":
                el, act = "cap_enter", "효과 붙은 등장"
            elif eff in ("emph", "sticker", "sfx"):
                el, act = {"emph": "cap_emph", "sticker": "sticker", "sfx": "sfx"}[eff], eff
            else:
                continue
            k, n = r.get("k"), r.get("n")
            ok = isinstance(k, (int, float)) and isinstance(n, (int, float)) and n > 0
            # rate·등급은 k/n 에서 다시 낸다(장부의 rate 칸을 베끼지 않는다 — k 만 바뀌어도 카드가 따라간다)
            out.append(_rec(el, r.get("cond"), act, k, n, round(k / n, 2) if ok else None, r.get("base"), _grade(k, n) if ok else None, [src], "눈"))
        pl = R.get("plain") or {}
        if pl.get("denom"):
            out.append(_rec("cap_enter", "없음", "꾸밈 없는 줄(plain)", pl.get("n"), pl.get("denom"), round(pl["n"] / pl["denom"], 2),
                            None, _grade(pl["n"], pl["denom"]), [src], "눈"))
        nar = (R.get("by_speaker") or {}).get("나레") or {}
        if nar.get("cps"):
            out.append(_rec("speech", "화자=나레", f"말속도 {nar['cps']} 자/초 · 덩어리 {nar.get('sec_med')}초", None, nar.get("n"), None,
                            None, _grade(nar.get("n") or 0, nar.get("n") or 0), [src], "눈"))
    docs = [d for d in O["line_reads"] if isinstance(d, dict)]
    lines = [l for d in docs for l in d.get("lines") or [] if isinstance(l, dict)]
    lsrc = [f"channel/{slug}/줄판독 {len(docs)}편"]
    if lines:
        nst = [l for l in lines if "sticker" in l]
        if nst:
            whats = [str(s.get("what") if isinstance(s, dict) else s) for l in nst for s in (l.get("sticker") or [])]
            kp = sum(1 for l in nst if any(POINTER_RE.search(str(s.get("what") if isinstance(s, dict) else s)) for s in l.get("sticker") or []))
            km = sum(1 for l in nst if any(MEME_RE.search(str(s.get("what") if isinstance(s, dict) else s)) for s in l.get("sticker") or []))
            n = len(nst)
            out.append(_rec("pointer", "전체 줄", f"원·화살표 스티커 ({', '.join(w[:12] for w in whats if POINTER_RE.search(w))[:60] or '없음'})",
                            kp, n, round(kp / n, 2), None, _grade(kp, n), lsrc, "눈"))
            out.append(_rec("meme", "전체 줄", "짤 스티커", km, n, round(km / n, 2), None, _grade(km, n), lsrc, "눈"))
        for el, key in (("transition", "transition"), ("cap_exit", "exit")):
            c = _kinds(lines, key)
            n = sum(c.values())
            for kind, k in sorted(c.items(), key=lambda x: (-x[1], x[0])):
                out.append(_rec(el, "전체 줄", f"{key}={kind}", k, n, round(k / n, 2), None, _grade(k, n), lsrc, "눈"))
        fits = [float(l["fit"]) for l in lines if isinstance(l.get("fit"), (int, float)) and not isinstance(l.get("fit"), bool)]
        if fits:
            k = sum(1 for f in fits if f >= 7)
            out.append(_rec("scene_fit", "전체 줄", f"대사↔장면 평균 {round(statistics.mean(fits), 2)} · 7 미만 {round(1 - k / len(fits), 2)}",
                            k, len(fits), round(k / len(fits), 2), None, _grade(k, len(fits)), lsrc, "눈"))
        looks = [l for l in lines if l.get("font") or l.get("size_px")]
        if looks and not O["palette"]:
            out.append(_rec("cap_look", "전체 줄", "글꼴·px 칸 기입", len(looks), len(lines), round(len(looks) / len(lines), 2), None,
                            _grade(len(looks), len(lines)), lsrc, "눈"))
    if docs:
        f0 = [d for d in docs if d.get("frame0")]
        if f0:
            out.append(_rec("thumb", "0초 프레임", "frame0 기입", len(f0), len(docs), round(len(f0) / len(docs), 2), None, _grade(len(f0), len(docs)), lsrc, "눈"))
    if O["palette"]:
        P = O["palette"]
        roles = P.get("roles") if isinstance(P.get("roles"), dict) else {k: v for k, v in P.items() if isinstance(v, list)}
        out.append(_rec("cap_look", "역할별", f"팔레트 역할 {len(roles)}종", None, None, None, None, None, [f"channel/{slug}/팔레트.json"], "픽셀"))
    TT = [t for t in O["tteutgi"] if isinstance(t, dict)]
    tsrc = [f"channel/{slug}/뜯기 {len(TT)}편"]
    meds = [((t.get("cuts") or {}).get("shot_len") or {}).get("median") for t in TT]
    p90s = [((t.get("cuts") or {}).get("shot_len") or {}).get("p90") for t in TT]
    meds = [x for x in meds if isinstance(x, (int, float))]
    p90s = [x for x in p90s if isinstance(x, (int, float))]
    if meds:
        out.append(_rec("cut_rhythm", "편 단위", f"컷 중앙 {round(statistics.median(meds), 2)}초 · p90 {round(statistics.median(p90s), 2) if p90s else '-'}초",
                        len(meds), len(TT), None, None, _grade(len(meds), len(TT)), tsrc, "신호"))
    bg = [t.get("bgm_rules") for t in TT if isinstance(t.get("bgm_rules"), dict) and t["bgm_rules"].get("ok")]
    if bg:
        k = sum(1 for b in bg if b.get("present"))
        out.append(_rec("bgm", "편 단위", "배경음 있음", k, len(bg), round(k / len(bg), 2), None, _grade(k, len(bg)), tsrc, "신호"))
    sx = [t.get("sfx_rules") for t in TT if isinstance(t.get("sfx_rules"), dict) and t["sfx_rules"].get("ok")]
    if sx:
        ps = [s.get("per_sec") for s in sx if isinstance(s.get("per_sec"), (int, float))]
        out.append(_rec("sfx", "편 단위", f"효과음 후보 중앙 {round(statistics.median(ps), 3) if ps else '-'} 발/초", len(sx), len(TT), None, None,
                        _grade(len(sx), len(TT)), tsrc, "신호"))
    S = O["script_lang"]
    if S and isinstance(S.get("나레"), dict):
        nar = S["나레"]
        n = nar.get("n_sentence_end") or 0
        for e in nar.get("endings") or []:
            out.append(_rec("script", "나레 문장 끝", f"어미 ~{e.get('ending')}", e.get("k"), n, e.get("rate"), None, _grade(e.get("k") or 0, n),
                            [f"channel/{slug}/_kal/대본언어.json"], "눈"))
    have = {r["element"] for r in out}
    for el in ELEMENTS:
        if el not in have:
            out.append(_rec(el, None, None, confidence="미측정", measure_task=task))
    for r in out:
        r.update(_engine(O, r["element"]))
    out.sort(key=lambda r: (ELEMENTS.index(r["element"]),))
    return out


def element_status(recs: list[dict]) -> str:
    """요소 하나의 측정 상태 — × 전부 미측정 · ○ 픽셀이거나 k/n 분모 ≥MIN_N(표본부족 아님) · △ 그 밖(표본부족·분모 없는 신호)."""
    if all(r["confidence"] == "미측정" for r in recs):
        return "×"
    for r in recs:
        if r["confidence"] == "픽셀" or (r.get("n") and r["n"] >= kal_analyze.MIN_N and r.get("grade") not in (None, "표본부족")):
            return "○"
    return "△"


def validate(card: dict) -> list[str]:
    """(판단 주인) build 거절 사유 — 미측정 레코드에 measure_task 가 없으면 거절(표준 §2-3 빈 칸 규칙)."""
    errs = []
    for r in card.get("rules") or []:
        if r.get("element") not in ELEMENTS:
            errs.append(f"요소 이름 밖: {r.get('element')}")
        if r.get("confidence") == "미측정" and not r.get("measure_task"):
            errs.append(f"{r.get('element')}: 미측정인데 measure_task 없음")
    return errs


# ---------------------------------------------------------------- 단계 판정
HAND_CONST = "손 상수"      # why 에 이 말이 있으면 근거가 아니라 '측정 전 손 값' 자백 → 근거로 치지 않는다(지어낸 근거 방지, 페이블 10-25)


def _is_why(w) -> bool:
    return w is not None and HAND_CONST not in str(w)


def _pack_paths(style_name: str | None) -> set[str]:
    """styles.load 가 packs 에서 채우는 옛 칸 경로 — 판 원본(_skip_packs)에 packs 변환만 얹어 생긴 칸을 diff 로 찾는다(이름 하드코딩 금지).
    이 칸들은 packs 가 정본이라 판 옛 칸에 why 를 달 수 없다(두 벌 금지) → 숫자 칸 why 셈에서 뺀다."""
    if not style_name:
        return set()
    import copy
    from tools.calcopy.hybrid import pack_map
    s0 = styles_mod.load(style_name, _skip_packs=True)
    probe = {"packs": copy.deepcopy(s0.get("packs") or {}), "caption": {}}
    if isinstance(_get(s0, "placement.rules.meme"), dict):
        probe["placement"] = {"rules": {"meme": {}}}
    before = json.loads(json.dumps(probe))
    pack_map.apply_to_style(probe, None, style_name)
    out = set()

    def leaves(v, path):
        if isinstance(v, dict) and v:
            for k, x in v.items():
                leaves(x, path + [str(k)])
        else:
            out.add(".".join(path))
    for k, v in probe.items():
        if k != "packs":
            leaves(v, [k])
    return {p for p in out if _get(before, p) != _get(probe, p)}


def _no_why(raw: dict, from_packs: set[str] | frozenset = frozenset(), hand: list | None = None) -> list[str]:
    """판 파일 숫자 칸 중 근거(why/_from)가 없는 칸 경로. 근거는 그 칸을 품은 사전(뿌리 제외) 어디에든 있으면 된다. counted(made_by)는 기계 산출.
    뿌리 숫자 칸(cps_target 등)은 판 머리 why 사전(why:{칸: …}) 또는 옛 꼴 _why_<칸> 이 근거. packs 에서 채운 칸(from_packs)은 뺀다.
    why 가 '손 상수 — 벤치 근거 없음' 이면 근거 아님 → 미달로 남기고 hand 목록(measure_task 대상)에도 적는다."""
    miss = []
    raw = raw or {}
    root_why = raw.get("why") if isinstance(raw.get("why"), dict) else {}

    def skip(path):
        p = ".".join(path)
        return p in from_packs or any(p.startswith(q + ".") for q in from_packs)

    def note(path, handed):
        miss.append(".".join(path))
        if handed and hand is not None:
            hand.append(".".join(path))

    def walk(v, path, has, handed):
        if skip(path):
            return
        if isinstance(v, dict):
            ws = [v[k] for k in ("why", "_from", "made_by") if k in v]
            h = has or any(_is_why(w) for w in ws)
            hd = handed or any(not _is_why(w) for w in ws)
            for k, x in v.items():
                if not str(k).startswith("_"):
                    walk(x, path + [str(k)], h, hd)
        elif isinstance(v, list):
            if any(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v) and not has:
                note(path, handed)
            else:
                for i, x in enumerate(v):
                    if isinstance(x, dict):
                        walk(x, path + [str(i)], has, handed)
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and not has:
            note(path, handed)
    for k, v in raw.items():
        if k == "packs":    # 팩 칸 숫자(rank·enter_cover…)는 pack_map 생성 값 — made_by 가 있으면 기계 산출, 없어도 packs 서브트리는 셈에서 뺀다(페이블 지시 10-25)
            continue
        if not str(k).startswith("_") and k not in ("script", "why"):
            ws = [w for w in (root_why.get(k), raw.get(f"_why_{k}")) if w is not None]   # 뿌리 칸 근거 = 판 머리 why 사전 · 옛 꼴 _why_<칸>
            walk(v, [k], any(_is_why(w) for w in ws), any(not _is_why(w) for w in ws))
    return sorted(set(miss))


def facts(O: dict, recs: list[dict]) -> dict:
    docs = O["line_reads"]
    strict_err = sum(len(kal_analyze.check_doc(d, strict=True)["errors"]) for d in docs if isinstance(d, dict))
    st = O["style"] or {}
    pre = O["preset"]
    eng = pre.get("engine") or {}
    pack = _get(st, "caption.pack")
    mem = pre.get("member") or {}
    G = O["gate"]
    hand = []
    no_why = _no_why(O["style_raw"], _pack_paths(O["style_name"]), hand) if O["style_raw"] else None
    return {
        "hand_const": sorted(set(hand)),      # why = '손 상수' 자백 칸 — 근거 아님(no_why 에 남음), measure_task 로 센다
        "line_reads": len(docs), "line_reads_strict_errors": strict_err,
        "rules_freq": O["rules_freq"] is not None, "style_analysis": O["style_analysis"], "palette": O["palette"] is not None,
        "sfx_events": O["sfx_events"] is not None,
        "style_file": eng.get("style_file"), "style_file_exists": O["style"] is not None, "renderer": st.get("renderer") or eng.get("renderer"),
        "caption_pack": pack, "caption_pack_ok": bool(pack) and pack in pack_keys(),
        "counted_n": _get(st, "placement.counted.n_videos"), "no_why": no_why,
        "hand_scripts": [h for h in eng.get("hand_scripts") or [] if not DEPRECATED_RE.search(str(h))],
        "hand_scripts_reference": [h for h in eng.get("hand_scripts") or [] if DEPRECATED_RE.search(str(h))],
        "unmeasured": sum(1 for r in recs if r["confidence"] == "미측정"),
        "quality_gate_ok": bool((G.get("품질관문.json") or {}).get("ok")),
        "match_ok": bool((G.get("재현일치도.json") or {}).get("ok")),
        "eye": G.get("눈검수.json"),
        "upgrade": (lambda u: {"better": u.get("better_n") or 0, "worse": u.get("worse_n"), "l3_ok": u.get("l3_ok") is True})(((G.get("품질관문.json") or {}).get("gates") or {}).get("upgrade") or (G.get("업그레이드_측정.json") or {}).get("gates", {}).get("upgrade") or {}),   # gates.upgrade(관문 04·업그레이드 자 05) — L3 판정 주인 = upgrade_table.l3_verdict(여기선 읽기만, 표준 §11-2 ⑱)
        "member": mem, "line_json_exists": bool(mem.get("line_json")) and (ROOT / str(mem.get("line_json"))).exists(),
        "member_live_ok": bool((O["member_live"] or {}).get("ok")),
        "results_n": len(O["results"]), "results_pass_n": sum(1 for it in O["results"] if "페이블 판정 통과" in str(it.get("judge") or "")),
        "owner_pass": any(result_state(it.get("judge"), fine=True) == "사장님 승인" for it in O["results"]),   # 판정 글 주인 = calcopy_board.result_state(표준 §11 ⑧)
    }


def _eye_ok(eye, items) -> bool:
    if not isinstance(eye, dict):
        return False
    src = eye.get("items") if isinstance(eye.get("items"), dict) else eye
    return all(str((src.get(i) or {}).get("v") if isinstance(src.get(i), dict) else src.get(i)) == "○" for i in items)


def level(card: dict) -> tuple[str, list[str]]:
    """(판단 주인) 표준 §6 L0~L4 판정 → (단계, 빠진 것 전부). 단계 = 처음부터 끊김 없이 채운 마지막 단계."""
    F = card["facts"]
    conds = {
        "L0": [("줄판독≥6", F["line_reads"] >= LINE_READS_MIN), ("줄판독 strict 오류0", F["line_reads"] > 0 and F["line_reads_strict_errors"] == 0),
               ("규칙빈도", F["rules_freq"]), ("스타일분석", F["style_analysis"]), ("팔레트", F["palette"]), ("sfx_events", F["sfx_events"])],
        "L1": [("판파일", F["style_file_exists"]), ("renderer=bench", F["renderer"] == "bench"),
               ("숫자칸 why", F["no_why"] == []), (f"counted≥{COUNTED_MIN}", (F["counted_n"] or 0) >= COUNTED_MIN),
               ("자막팩", F["caption_pack_ok"]), ("rules 미측정0", F["unmeasured"] == 0)],
        "L2": [("품질관문 ○", F["quality_gate_ok"]), ("재현일치도 ○", F["match_ok"]), ("눈검수 E1~E8", _eye_ok(F["eye"], [f"E{i}" for i in range(1, 9)]))],
        "L3": [("업그레이드 나아짐≥과반∧나빠짐0", isinstance(F["upgrade"], dict) and F["upgrade"].get("l3_ok") is True),
               ("눈검수 E9", _eye_ok(F["eye"], ["E9"])), ("사장님 판정", F["owner_pass"])],
        "L4": [("member line.json", F["line_json_exists"]), ("member preset_name", bool(F["member"].get("preset_name"))),
               ("member flow_format", bool(F["member"].get("flow_format"))), ("회원실측", F["member_live_ok"])],
    }
    reached, missing, broken = "L0 미달", [], False
    for L, cs in conds.items():
        miss = [name for name, ok in cs if not ok]
        missing += miss
        if not miss and not broken:
            reached = L
        elif miss:
            broken = True
    if F["hand_scripts"]:
        missing.append("손스크립트0")
    return reached, missing


# ---------------------------------------------------------------- 카드
def build_card(slug: str, built_at: str | None = None) -> dict:
    O = load_owners(slug)
    recs = rules_of(slug, O)
    pre, st = O["preset"], O["style"] or {}
    eng = pre.get("engine") or {}
    F = facts(O, recs)
    status = {el: element_status([r for r in recs if r["element"] == el]) for el in ELEMENTS}
    axes = {ax: {"value": " ".join(f"{el}{status[el]}" for el in els),
                 "confidence": "미측정" if all(status[el] == "×" for el in els) else "측정"} for ax, els in AXES.items()}
    axes["2제목틀"] = {"value": st.get("title_form") or ("frame.title" if _get(st, "frame.title") else None), "confidence": "판" if st else "미측정"}
    axes["5스토리"] = {"value": sorted(((O["rules_freq"] or {}).get("by_role") or {}).keys()) or None, "confidence": "눈" if O["rules_freq"] else "미측정"}
    axes["10소재"] = {"value": "소재후보.json" if (ROOT / "channel" / slug / "소재후보.json").exists() else None,
                    "confidence": "파일" if (ROOT / "channel" / slug / "소재후보.json").exists() else "미측정"}
    axes["11채널"] = {"value": pre.get("bench_option"), "confidence": "장부"}
    G = O["gate"]
    M = G.get("재현일치도.json") or {}
    U = G.get("업그레이드_측정.json") or {}
    Q = G.get("품질관문.json") or {}
    card = {
        "slug": slug, "made_by": MADE_BY, "built_at": built_at or datetime.now().isoformat(timespec="seconds"),
        "bench": pre.get("bench_option"), "brand": (O["brand"] or {}).get("brand"), "brand_note": pre.get("brand_note"),
        "format": pre.get("format"), "subformat": pre.get("subformat"),
        "format_options": list(pre.get("format_options") or []) + [o for o in (O["brand"] or {}).get("options") or [] if o not in (pre.get("format_options") or [])],
        "sound_style": O["sound"],
        "engine": {"style_file": eng.get("style_file"), "style_error": O["style_err"], "renderer": F["renderer"],
                   "entry": f"tools/calcopy/hybrid/run.py <키> render --version {O['style_name']}" if F["renderer"] == "bench" and O["style_name"] else None,
                   "hand_scripts": F["hand_scripts"], "hand_scripts_reference": F["hand_scripts_reference"], "caption_pack": F["caption_pack"],
                   "voice": _get(st, "voice.name"), "bgm": _get(st, "bgm.id") if isinstance(st.get("bgm"), dict) else st.get("bgm")},
        "sample": {"line_reads": F["line_reads"], "line_reads_strict_errors": F["line_reads_strict_errors"], "rules_freq": F["rules_freq"],
                   "palette": F["palette"], "style_analysis": F["style_analysis"], "sfx_events": F["sfx_events"], "tteutgi": len(O["tteutgi"]),
                   "min_required": LINE_READS_MIN},
        "axes": dict(sorted(axes.items(), key=lambda kv: int(re.match(r"\d+", kv[0]).group()))),
        "elements": status,
        "rules": recs,
        "gates": {"match_first_copy": {"path": G.get("재현일치도.json.path"), "ok": M.get("ok"), "pass": M.get("pass"), "fail": M.get("fail")},
                  "upgrade": {"path": G.get("업그레이드_측정.json.path"), "items": U.get("items") if not isinstance(U.get("items"), list) else len(U["items"]), "better": U.get("better")},
                  "quality_gate": {"path": G.get("품질관문.json.path"), "ok": Q.get("ok")}},
        "member": dict(pre.get("member") or {}),
        "results": {"n": F["results_n"], "judged_pass": F["results_pass_n"], "latest": (O["results"][-1].get("title") if O["results"] else None)},
        "facts": F,
        "inputs": O["inputs"],
    }
    L, missing = level(card)
    if pre.get("status") == "보류":      # 표준 §11-3 ㉓ — 보류는 분모에서 빼지 않고 사유와 함께 드러낸다(완료로 포장 금지)
        L = "보류(%s)" % ((pre.get("hold") or {}).get("short") or "사유 미기재")
    card["done"] = {"level": L, "missing": missing, "rule_unmeasured": F["unmeasured"],
                    "measure_tasks": sorted({r["measure_task"] for r in recs if r.get("measure_task")} | ({f"06-{slug}"} if F["hand_const"] else set())),
                    "hand_const": F["hand_const"],
                    "complete": L == "L4" and not F["hand_scripts"]}
    weak = _emph_weak(O)
    if weak:
        card["emph_weak"] = weak
    return card


def _emph_weak(O: dict) -> dict | None:
    """결정 ㉙: 1차 판(upgrades·회원 패치 없음)의 강조색 문턱이 30 미만이면 '벤치 대비 약함'. 문턱 판단 주인 = placement(판 de_min → emph_threshold)."""
    st, raw = O["style"] or {}, O["style_raw"] or {}
    if not st or raw.get("upgrades") or raw.get("base") or st.get("upgrades"):
        return None
    from tools.calcopy.hybrid import placement
    R = (_get(st, "placement.rules") or {}).get("emph_color") or {}
    if isinstance(R.get("de_min"), (int, float)):
        thr = float(R["de_min"])
    else:
        thr = placement.emph_threshold((st.get("bench") or {}).get("channel"))[0]
    floor = placement.EMPH_DE_FALLBACK
    return {"de_min": round(thr, 2), "threshold": floor, "label": "벤치 대비 약함"} if thr < floor else None


def card_path(slug: str) -> Path:
    return ROOT / "channel" / slug / "_kal" / "카드.json"


def build(slugs: list[str], write_html: bool = True) -> int:
    bad = 0
    cards = []
    stamp = datetime.now().isoformat(timespec="seconds")
    for s in slugs:
        c = build_card(s, stamp)
        errs = validate(c)
        if errs:
            bad += 1
            print(f"✗ {s}: build 거절 — {errs[:3]}")
            continue
        p = card_path(s)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        cards.append(c)
        print(f"{s}: {c['done']['level']} · 미측정 {c['done']['rule_unmeasured']} · 레코드 {len(c['rules'])} → {_rel(p)}")
    if write_html and cards and len(slugs) == len(presets()):
        out = ROOT / "out" / "숏템프리셋_카드.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(cards, stamp), encoding="utf-8")
        print(f"HTML → {_rel(out)}")
    return 1 if bad else 0


def render_html(cards: list[dict], stamp: str) -> str:
    E = html.escape
    head = "".join(f"<th class=el title='{e}'>{e}</th>" for e in ELEMENTS)
    rows = []
    for c in cards:
        els = "".join(f"<td class='s{ {'○': 'o', '△': 't', '×': 'x'}[c['elements'][e]] }'>{c['elements'][e]}</td>" for e in ELEMENTS)
        rows.append(f"<tr><td><b>{E(c['slug'])}</b></td><td>{E(str(c['format']))}<br><small>{E(str(c['subformat']))}</small></td>"
                    f"<td>{E(str(c['brand'] or '-'))}</td><td>{E(str(c['engine']['renderer']))}<br><small>{E(str(c['engine']['style_file'] or '-').split('/')[-1])}</small></td>"
                    f"<td class=lv>{E(c['done']['level'])}</td>{els}<td class=miss>{E(' · '.join(c['done']['missing']))}</td>"
                    f"<td>{E(', '.join(c['done']['measure_tasks']))}</td></tr>")
    return f"""<!doctype html><html lang=ko><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>숏템프리셋 카드</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--line:#ddd;--o:#d9f2df;--t:#fff2cc;--x:#f8d7da}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#eee;--mut:#aaa;--line:#333;--o:#1e4a2a;--t:#4a3e12;--x:#4d1f24}}}}
body{{background:var(--bg);color:var(--fg);font:13px/1.4 system-ui,'Malgun Gothic',sans-serif;margin:16px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid var(--line);padding:4px 6px;vertical-align:top}}
th.el{{writing-mode:vertical-rl;font-weight:500;font-size:11px}}td.so{{background:var(--o);text-align:center}}td.st{{background:var(--t);text-align:center}}
td.sx{{background:var(--x);text-align:center}}td.lv{{font-weight:700;white-space:nowrap}}td.miss{{color:var(--mut);font-size:11px;max-width:320px}}
small{{color:var(--mut)}}.wrap{{overflow-x:auto}}</style></head><body>
<h1>숏템프리셋 카드 ({len(cards)}개)</h1>
<p>생성 {E(stamp)} · <code>tools/calcopy/preset_card.py build --all</code> 생성물(손으로 고치지 않는다) · 기준 = 칼카피_공통규칙표준 §2·§6 · 요소 ○ 분모≥{kal_analyze.MIN_N} k/n 또는 픽셀 · △ 표본부족/분모 없는 신호 · × 미측정(measure_task)</p>
<div class=wrap><table><thead><tr><th>slug</th><th>형식</th><th>브랜드</th><th>엔진</th><th>L</th>{head}<th>빈 칸</th><th>measure_task</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></body></html>
"""


def check(slugs: list[str]) -> int:
    allL4 = True
    print(f"{'slug':18} {'L':8} 미측정 missing")
    for s in slugs:
        c = build_card(s)
        L, missing = c["done"]["level"], c["done"]["missing"]
        allL4 &= (L == "L4")
        print(f"{s:18} {L:8} {c['done']['rule_unmeasured']:>4}  {' · '.join(missing)}")
    return 0 if allL4 else 1


def audit_diff(path: Path) -> int:
    """표준감사 json 의 L0/L1 사실 칸과 이 판정기의 사실 칸 대조 → 어긋난 칸 목록."""
    A = json.loads(path.read_text(encoding="utf-8"))["presets"]
    diffs = 0
    for s, a in A.items():
        c = build_card(s)
        F = c["facts"]
        pairs = [("line_reads", a["L0"]["line_reads"], F["line_reads"]), ("rules_freq", a["L0"]["rules_freq"], F["rules_freq"]),
                 ("style_analysis", a["L0"]["style_analysis"], F["style_analysis"]), ("palette", a["L0"]["palette"], F["palette"]),
                 ("sfx_events", a["L0"]["sfx_events"], F["sfx_events"]), ("style_file_exists", bool(a["L1"]["style_file_exists"]), F["style_file_exists"]),
                 ("caption_pack_ok", a["L1"]["caption_pack_ok"], F["caption_pack_ok"]), ("hand_scripts_n", a["L1"]["hand_scripts_n"], len(F["hand_scripts"])),
                 ("line_reads_ok(≥6)", a["L0"]["line_reads_ok"], F["line_reads"] >= LINE_READS_MIN), ("renderer", a["L1"]["renderer"], F["renderer"]),
                 ("caption_pack", a["L1"]["caption_pack"], F["caption_pack"])]
        bad = [(k, x, y) for k, x, y in pairs if x != y]
        diffs += len(bad)
        print(f"{s:18} {'일치' if not bad else '어긋남 ' + ' · '.join(f'{k} 감사={x} 판정기={y}' for k, x, y in bad)}")
    print(f"어긋난 칸 {diffs}")
    return 1 if diffs else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="주인 장부 뿌리(기본 저장소)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "check"):
        p = sub.add_parser(name)
        p.add_argument("slug", nargs="?")
        p.add_argument("--all", action="store_true")
    ad = sub.add_parser("audit-diff")
    ad.add_argument("path", nargs="?", default="tools/calcopy/표준감사_2026-10-24.json")
    A = ap.parse_args(argv)
    set_root(A.root)
    if A.cmd == "audit-diff":
        return audit_diff(ROOT / A.path if not Path(A.path).is_absolute() else Path(A.path))
    if not A.all and not A.slug:
        ap.error("slug 또는 --all")
    slugs = list(presets()) if A.all else [A.slug]
    return build(slugs) if A.cmd == "build" else check(slugs)


if __name__ == "__main__":
    sys.exit(main())
