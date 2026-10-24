# -*- coding: utf-8 -*-
"""판 `packs` 칸 — 프리셋 = 숏템메이커 팩에서 고른 기본 선택의 묶음 (관제 263 지시서 11 · 표준 §10-1·§10-2).

판단 주인(이 파일 한 곳):
  ① 팩 합치기 `merge(엔진 기본, 판 packs, 회원 patch.packs)` — styles.load 가 부른다(회원 PC 는 저장·전달만, 합치지 않는다 — §10-3).
  ② 팩 칸 → 옛 칸 변환 `apply_to_style` — `caption.pack`·`sfx_files`·`bgm.id`·`bgm.candidates`·`placement.rules.meme.tone/pack` 는
     **packs 가 정본, 옛 칸은 변환만**. 둘 다 있고 다르면 `PackError`(조용히 덮지 않는다).
  ③ 렌더 스냅샷 칸 `snapshot_fields(st)` — captionPack·motionPack(render_bench.snapshot 이 부른다 — 연결은 02, 아래 '연결').
  ④ 벤치 측정값 → 팩 항목 거리 `map_all(판)` — cap_look·cap_enter·transition·sfx·bgm·meme. 결과 `packs.*.from` 에 근거, 팩에 없으면 `gap`
     + `channel/<slug>/_kal/팩요청.md`(요청서). 팩 자체(caption-motions.js·sfx_packs·bgm_lib·motion)는 **안 고친다**.

팩 자리(실측 10-25):
  자막팩      shopping_shorts/static/caption-motions.js /*PACKS*/ (키 = scene_style.caption_pack_keys)
  등장 효과팩  같은 파일 /*MPACKS*/ 1~20번 — **snapshot.motionPack 이 받는 값은 이것**("off"·"1"~"20", scene_style.validate_snapshot)
  모션그래픽팩 shopping_shorts/assets/motion/packs.json (dynamic_pop·minimal_chic — 전환 swipe·sparkle 겹·색감) — mix_pipeline 길만 그린다.
              render_bench 에는 그리는 길이 없다 → `packs.motion.graphics` 가 off 가 아니면 snapshot_fields 가 거절(조용히 무시 금지).
  효과음팩    shopping_shorts/assets/sfx_packs/packs.json(slots 7 한글 이름) + 폴더 팩NN/<slot>.wav (파일 이름 = sfx_pack.SLOTS, 같은 순서)
  배경음      shopping_shorts/assets/bgm_lib/catalog.json tracks[].id
  짤          칼카피 길 = 로컬 팩(material_auto.MEME_*) · 회원 길 = 서버 /api/meme/prefs — render_bench 는 로컬만(server 는 거절)

packs 칸 꼴(styles/README.md 'packs 칸' 절이 문서 주인):
  caption {pack, stand_in?, rank[], enter_cover{}, from, gap[]}
  motion  {pack: "off"|"1".."20", graphics: "off"|<모션그래픽팩 id>, from, gap[]}
  sfx     {pack: "팩NN"|null, map{kind: 한글 slot}, outside{kind: 팩 밖 파일}, gain_db, why?, ncc{}, from, gap[]}
  bgm     {id, candidates[], from}
  meme    {pack: "local"|"server"|"none", tone?, dir?, from, gap[]}   ※ 짤 빈도 rate 는 placement.rules.meme.rate(뼈대 — 두 벌 금지)

    PYTHONUTF8=1 py tools/calcopy/hybrid/pack_map.py <판> --dry        # 표만
    PYTHONUTF8=1 py tools/calcopy/hybrid/pack_map.py <판> --write      # 판 파일 packs 칸 + 팩요청.md
    PYTHONUTF8=1 py tools/calcopy/hybrid/pack_map.py --all --write
    PYTHONUTF8=1 py tools/calcopy/hybrid/pack_map.py rank <판>         # 자막팩 거리 표(1~5위)

연결(render_bench.snapshot — 02 파일): `snapshot(st)` 안에서 `"captionPack"/"motionPack"` 을 `pack_map.snapshot_fields(st)` 로.
"""
from __future__ import annotations

import copy
import glob
import json
import math
import re
import statistics as stt
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CAPTION_JS = ROOT / "shopping_shorts/static/caption-motions.js"
SFX_DIR = ROOT / "shopping_shorts/assets/sfx_packs"
BGM_CATALOG = ROOT / "shopping_shorts/assets/bgm_lib/catalog.json"
FONT_DIR = ROOT / "shopping_shorts/static/fonts"
H = 1920


class PackError(ValueError):
    """packs 칸 오류 — 없는 팩 항목·두 벌 불일치·렌더러가 못 그리는 팩."""


# ── 팩 목록(읽기만 — 주인은 각 팩 파일) ───────────────────────────────────────
_cache: dict = {}


def caption_packs() -> dict:
    if "cap" not in _cache:
        _cache["cap"] = json.loads(CAPTION_JS.read_text(encoding="utf-8").split("/*PACKS*/")[1])
    return _cache["cap"]


def motion_pack_ids() -> list[str]:
    """등장 효과팩 번호(snapshot.motionPack 이 받는 값) — 개수 주인 scene_style.caption_motion_pack_count."""
    from shopping_shorts import scene_style
    return ["off"] + [str(k) for k in range(1, scene_style.caption_motion_pack_count() + 1)]


def graphics_packs() -> dict:
    from shopping_shorts.motion_packs import load_packs
    return load_packs()


def sfx_slots() -> dict:
    """한글 slot 이름 → 파일 이름(packs.json slots 와 sfx_pack.SLOTS 는 같은 순서 — 실측 10-25 팩01 폴더)."""
    from shopping_shorts import sfx_pack
    ko = json.loads((SFX_DIR / "packs.json").read_text(encoding="utf-8"))["slots"]
    if len(ko) != len(sfx_pack.SLOTS):
        raise PackError(f"효과음 slot 수 다름: packs.json {len(ko)} ≠ sfx_pack.SLOTS {len(sfx_pack.SLOTS)}")
    return dict(zip(ko, sfx_pack.SLOTS))


def sfx_pack_names() -> list[str]:
    return sorted(p.name for p in SFX_DIR.iterdir() if p.is_dir())


def bgm_ids() -> list[str]:
    return [t["id"] for t in json.loads(BGM_CATALOG.read_text(encoding="utf-8"))["tracks"]]


# 효과음 종류(placement 가 쓰는 이름) → 팩 slot. 종류 이름 = 파일 이름(sfx_pack.SLOTS)이면 그 slot.
KIND_SLOT = {"pop": "뽁", "ding": "띠링", "whoosh": "휙", "transition": "휙", "dung": "둥", "opener": "오프너", "tick": "틱", "click2": "딸깍2"}

ENGINE_DEFAULT = {"caption": {}, "motion": {"pack": "off", "graphics": "off"}, "sfx": {}, "bgm": {}, "meme": {"pack": "local"}}
PACK_KEYS = ("caption", "motion", "sfx", "bgm", "meme")


# ── ① 합치기 · 검사 ──────────────────────────────────────────────────────
def _deep(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _deep(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def merge(*layers: dict | None) -> dict:
    """엔진 기본 ← 판 packs ← 회원 patch.packs (뒤가 이긴다, 사전은 깊게·목록은 대신). 원본은 안 바뀐다(깊은 복사)."""
    out = copy.deepcopy(ENGINE_DEFAULT)
    for L in layers:
        if not L:
            continue
        bad = [k for k in L if k not in PACK_KEYS and not k.startswith("_")]
        if bad:
            raise PackError(f"packs 에 없는 요소 {bad} — 허용 {PACK_KEYS}")
        out = _deep(out, L)
    errs = check(out)
    if errs:
        raise PackError("packs 항목 오류: " + " / ".join(errs))
    return out


def check(P: dict) -> list[str]:
    """팩에 실제로 있는 항목인가(없는 항목을 적으면 렌더가 조용히 기본값으로 갈 수 있다 — 여기서 막는다)."""
    errs = []
    c = P.get("caption") or {}
    if c.get("pack") is not None and c["pack"] not in caption_packs():
        errs.append(f"caption.pack '{c['pack']}' 자막팩에 없음")
    m = P.get("motion") or {}
    if str(m.get("pack", "off")) not in motion_pack_ids():
        errs.append(f"motion.pack '{m.get('pack')}' — 등장 효과팩 번호(off·1~{len(motion_pack_ids()) - 1})가 아님")
    if m.get("graphics", "off") != "off" and m["graphics"] not in graphics_packs():
        errs.append(f"motion.graphics '{m['graphics']}' 모션그래픽팩에 없음")
    s = P.get("sfx") or {}
    if s.get("pack") is not None:
        if s["pack"] not in sfx_pack_names():
            errs.append(f"sfx.pack '{s['pack']}' 폴더 없음")
        slots = sfx_slots()
        for kind, slot in (s.get("map") or {}).items():
            if slot not in slots:
                errs.append(f"sfx.map {kind}→'{slot}' slot 아님({list(slots)})")
            elif not (SFX_DIR / s["pack"] / f"{slots[slot]}.wav").exists():
                errs.append(f"sfx 파일 없음 {s['pack']}/{slots[slot]}.wav")
    elif s.get("map"):
        errs.append("sfx.map 이 있는데 sfx.pack 없음")
    b = P.get("bgm") or {}
    ids = bgm_ids()
    if b.get("id") is not None and b["id"] not in ids:
        errs.append(f"bgm.id '{b['id']}' 배경음 목록에 없음")
    for x in b.get("candidates") or []:
        if x not in ids:
            errs.append(f"bgm.candidates '{x}' 배경음 목록에 없음")
    me = P.get("meme") or {}
    if me.get("pack", "local") not in ("local", "server", "none"):
        errs.append(f"meme.pack '{me.get('pack')}' — local·server·none")
    return errs


# ── ② 옛 칸 변환 ─────────────────────────────────────────────────────────
def old_fields(P: dict) -> dict:
    """packs → 옛 칸 값(점 경로 → 값). packs 가 그 값을 안 정하면 그 칸은 없다(옛 판 동작 그대로)."""
    out = {}
    c = P.get("caption") or {}
    if "pack" in c:
        out["caption.pack"] = c["pack"]
    s = P.get("sfx") or {}
    if "map" in s or "outside" in s:
        slots = sfx_slots()
        sf = {k: f"{s['pack']}/{slots[v]}.wav" for k, v in (s.get("map") or {}).items()}
        sf.update(s.get("outside") or {})
        if "gain_db" in s:
            sf["gain_db"] = s["gain_db"]
        if "why" in s:
            sf["why"] = s["why"]
        out["sfx_files"] = sf
    b = P.get("bgm") or {}
    if "id" in b:
        out["bgm.id"] = b["id"]
    if "candidates" in b:
        out["bgm.candidates"] = b["candidates"]
    me = P.get("meme") or {}
    if "tone" in me:
        out["placement.rules.meme.tone"] = me["tone"]
    if "dir" in me:
        out["placement.rules.meme.pack"] = me["dir"]
    return out


_MISSING = object()


def _get(d: dict, path: str):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return _MISSING
        d = d[k]
    return d


def _set(d: dict, path: str, v):
    ks = path.split(".")
    for k in ks[:-1]:
        d = d.setdefault(k, {})
    d[ks[-1]] = v


def apply_to_style(st: dict, patch_packs: dict | None = None, name: str = "?") -> dict:
    """styles.load 가 부른다: st['packs'] = merge(엔진 기본, 판 packs, 회원 patch) · 옛 칸을 packs 에서 채움.
    판 파일에 옛 칸도 있으면 같아야 한다(다르면 PackError — 두 벌 불일치). 회원 patch 가 있으면 옛 칸은 patch 를 따른다."""
    has = bool(st.get("packs"))
    P = merge(st.get("packs"), patch_packs)
    base = old_fields(merge(st.get("packs"))) if has else {}
    for path, v in old_fields(P).items():
        if path.startswith("placement.rules.meme.") and _get(st, "placement.rules.meme") is _MISSING:
            continue                                    # 짤 규칙이 없는 판(빈도 0)은 짤 칸을 만들지 않는다
        if path.startswith("caption.") and "caption" not in st and v is None:
            continue
        cur = _get(st, path)
        if has and cur is not _MISSING and path in base and cur != base[path]:
            raise PackError(f"판 {name}: 두 벌 불일치 {path} — 옛 칸 {json.dumps(cur, ensure_ascii=False)[:120]} ≠ "
                            f"packs {json.dumps(base[path], ensure_ascii=False)[:120]} (packs 가 정본 — 옛 칸을 지우거나 같게)")
        _set(st, path, copy.deepcopy(v))
    st["packs"] = P
    if P["meme"].get("pack") == "server" and _get(st, "placement.rules.meme") is not _MISSING:
        raise PackError(f"판 {name}: meme.pack server(회원 prefs 짤)는 칼카피 길(render_bench·placement)이 못 받는다 — 지시서 12 연결 전엔 local")
    return st


# ── ③ 렌더 스냅샷 칸 ─────────────────────────────────────────────────────
def snapshot_fields(st: dict) -> dict:
    """render_bench.snapshot 의 팩 칸 — captionPack = packs.caption.pack(옛 칸과 같다), motionPack = packs.motion.pack(off·1~20).
    모션그래픽팩(graphics)은 render_bench 가 그리지 못하므로 off 가 아니면 거절(조용히 무시하면 회원이 고른 팩이 안 나온다)."""
    P = st.get("packs") or merge()
    g = (P.get("motion") or {}).get("graphics", "off")
    if g != "off":
        raise PackError(f"모션그래픽팩 '{g}' — render_bench 에 그리는 길 없음(mix_pipeline 만). 02 에 요청(전환 swipe·sparkle 겹·색감)")
    cap = (P.get("caption") or {}).get("pack")
    if cap is None:
        cap = (st.get("caption") or {}).get("pack")
    return {"captionPack": cap, "motionPack": str((P.get("motion") or {}).get("pack", "off"))}


# ── ④ 벤치 측정 → 팩 항목 거리 ───────────────────────────────────────────
def _hex_lab(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in rgb]
    X = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    Y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    Z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883
    f = [t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116 for t in (X, Y, Z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def delta_e(a: str, b: str) -> float:
    return round(math.dist(_hex_lab(a), _hex_lab(b)), 2)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def font_file(family: str) -> Path | None:
    n = _norm(family)
    if n.endswith("eb"):
        n = n[:-2] + "extrabold"
    for p in sorted(FONT_DIR.glob("*.[ot]tf")):
        if _norm(p.stem) == n:
            return p
    return None


def font_ink(family: str, size: float, sample: str = "한글 자막이 보인다") -> float | None:
    """그 글꼴을 그 크기로 그렸을 때 채움 잉크 높이(px) — 팩 크기 숫자는 글꼴마다 잉크가 달라 직접 잰다."""
    key = ("ink", family, size)
    if key in _cache:
        return _cache[key]
    f = font_file(family)
    if not f:
        _cache[key] = None
        return None
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    ft = ImageFont.truetype(str(f), int(round(size)))
    im = Image.new("L", (int(size * len(sample) * 1.4) + 40, int(size * 2.5)), 0)
    ImageDraw.Draw(im).text((20, int(size * 0.5)), sample, font=ft, fill=255)
    rows = np.where(np.asarray(im).max(axis=1) > 128)[0]
    _cache[key] = float(rows[-1] - rows[0] + 1) if len(rows) else None
    return _cache[key]


def pack_look(key: str, who: str | None = None) -> dict:
    """자막팩 한 벌의 겉모양(화자 who = narr|orig 이면 팩 speakers[who] 가 덮은 값). 잉크는 그 글꼴을 직접 그려 잰다."""
    p = caption_packs()[key]
    sp = ((p.get("speakers") or {}).get(who) or {}) if who else {}
    font, size = sp.get("font") or p["font"], sp.get("size") or p["size"]
    t = _deep(p.get("text") or {}, sp.get("text") or {})
    m = re.match(r"\s*([\d.]+)em\s+(#[0-9A-Fa-f]{3,6})", str((t.get("style") or {}).get("WebkitTextStroke") or ""))
    stroke = round(float(m.group(1)) * size / 2, 1) if m else 0.0        # paint-order stroke fill → 보이는 테 = 반
    ink = font_ink(font, size)
    if ink is None:            # 글꼴 파일이 없는 팩(예 Scene1369) — 바탕 글꼴로 잰다(표에 표시)
        ink = font_ink(p["font"], size)
    return {"font": font, "size": size, "fill": t.get("color"), "stroke_px": stroke, "stroke_hex": m.group(2) if m else None,
            "ink": ink, "outer": ink + 2 * stroke if ink else None, "y": (p.get("place") or {}).get("y")}


_UNKNOWN = re.compile(r"미확정|미측정|추정|계열|근사|확인|\(|/")


def _outline_px(o) -> float | None:
    if isinstance(o, dict):
        v = o.get("px")
        return float(v) if isinstance(v, (int, float)) else None
    m = re.search(r"([\d.]+)\s*px", str(o or ""))
    return float(m.group(1)) if m else None


def _cluster_color(hexes: list[str]) -> tuple[str | None, int]:
    groups: list[list[str]] = []
    for h in hexes:
        for g in groups:
            if delta_e(g[0], h) < 5:
                g.append(h)
                break
        else:
            groups.append([h])
    if not groups:
        return None, 0
    g = max(groups, key=len)
    return Counter(g).most_common(1)[0][0], len(g)


def doc_font(slug: str) -> str | None:
    """스타일분석.md 표의 '글꼴' 줄에서 굵게 적은 등록 글꼴 이름(벤치 실측 문서 — 픽셀·fontmatch·눈 대조 결과)."""
    p = ROOT / f"channel/{slug}/스타일분석.md"
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if re.match(r"\|\s*글꼴", line):
            for b in re.findall(r"\*\*([^*]+)\*\*", line):
                for tok in re.split(r"[\s(（]", b.strip()):
                    if tok and font_file(tok):
                        return tok
            return None
    return None


def _who(sp) -> str | None:
    s = str(sp or "")
    return "narr" if s.startswith("나레") else "orig" if s.startswith("원음") else None


def _agg(L: list[dict]) -> dict:
    out: dict = {"n": len(L), "basis": []}
    spans = [x["y"][1] - x["y"][0] for x in L if isinstance(x.get("y"), list) and len(x["y"]) == 2
             and all(isinstance(v, (int, float)) for v in x["y"]) and 20 < x["y"][1] - x["y"][0] < 150]
    if len(spans) >= 5:
        out["span"] = float(stt.median(spans))
        out["basis"].append(f"잉크 높이 {out['span']:.0f}px({len(spans)}줄 y칸)")
    ys = [(x["y"][0] + x["y"][1]) / 2 for x in L if isinstance(x.get("y"), list) and len(x["y"]) == 2
          and all(isinstance(v, (int, float)) for v in x["y"])]
    if len(ys) >= 5:
        out["y"] = round(float(stt.median(ys)) / H * 100, 2)
        out["basis"].append(f"자리 y{stt.median(ys):.0f}")
    fill, n = _cluster_color([x["fill_hex"] for x in L if isinstance(x.get("fill_hex"), str) and x["fill_hex"].startswith("#")])
    if fill:
        out["fill"] = fill
        out["basis"].append(f"채움 {fill}({n}줄)")
    ol = [v for v in (_outline_px(x.get("outline")) for x in L) if v is not None]
    if len(ol) >= 5:
        out["stroke_px"] = float(stt.median(ol))
        out["basis"].append(f"테 {out['stroke_px']:.0f}px")
    return out


def bench_caption(slug: str, st: dict | None = None) -> dict:
    """벤치 자막 실측 — 줄판독 줄 칸(y·fill_hex·outline)을 화자별(나레·원음)로 + 스타일분석 '글꼴' 줄 + 판 caption._pending.pack 측정 층.
    ※ 줄판독 size_px 는 채널마다 뜻이 달라(채움 잉크 / 글자 크기) 안 쓴다 — y칸 높이를 팩의 채움·테 포함 잉크 둘 다와 대조."""
    L, docs = [], 0
    for f in sorted(glob.glob(str(ROOT / f"channel/{slug}/줄판독/*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:     # noqa: BLE001 — 깨진 줄판독은 docs 수에서 빠진다(표에 보임)
            continue
        docs += 1
        L += [x for x in d.get("lines") or [] if isinstance(x, dict)]
    out: dict = {"slug": slug, "docs": docs, "lines": len(L), "basis": [], "who": {}}
    for w in ("narr", "orig"):
        sub = [x for x in L if _who(x.get("speaker")) == w]
        if len(sub) >= 5 and len(sub) >= 0.1 * len(L):
            a = _agg(sub)
            a["share"] = round(len(sub) / len(L), 3)
            out["who"][w] = a
            out["basis"].append(f"{'나레' if w == 'narr' else '원음'} {len(sub)}줄[{' · '.join(a['basis'])}]")
    if not out["who"] and len(L) >= 5:
        a = _agg(L)
        a["share"] = 1.0
        out["who"]["all"] = a
        out["basis"].append(f"전체 {len(L)}줄[{' · '.join(a['basis'])}]")
    f = doc_font(slug) if slug else None
    if f:
        out["font"] = f
        out["basis"].insert(0, f"글꼴 {f}(스타일분석 §1)")
    pend = str((((st or {}).get("caption") or {}).get("_pending") or {}).get("pack") or "")
    m = re.search(r"\{[^{}]*\"font\"[^{}]*\}", pend)
    if m:
        try:
            lay = json.loads(m.group(0))
        except json.JSONDecodeError:
            lay = {}
        if lay.get("font") and "font" not in out and font_file(Path(lay["font"]).stem):
            out["font"] = Path(lay["font"]).stem
            out["basis"].append(f"글꼴 {out['font']}(판 _pending 측정 층)")
        if lay.get("px"):
            out["font_px"] = float(lay["px"])
            out["basis"].append(f"글자 크기 {lay['px']}px(판 _pending 측정 층)")
        if lay.get("color") and not out["who"]:
            out["who"]["all"] = {"fill": lay["color"], "share": 1.0, "basis": []}
            out["basis"].append(f"채움 {lay['color']}(판 _pending 측정 층)")
    return out


# 거리 항목: 값 1.0 = 문턱(같은 항목으로 칠 수 있는 끝). 표준 §10-2: 글꼴 같음 + px ±10% + ΔE<5.
TOL = {"px": 0.10, "fill": 5.0, "stroke": 3.0, "y": 2.5, "font": 1.5}


def _terms(A: dict, P: dict, font_px: float | None) -> dict:
    t = {}
    if A.get("span") and P["ink"]:
        t["px"] = round(min(abs(A["span"] / P["ink"] - 1), abs(A["span"] / P["outer"] - 1)) / TOL["px"], 2)   # y칸 = 채움 또는 테 포함(채널마다 다름)
    elif font_px:
        t["px"] = round(abs(font_px / P["size"] - 1) / TOL["px"], 2)
    if A.get("fill") and P["fill"]:
        t["fill"] = round(delta_e(A["fill"], P["fill"]) / TOL["fill"], 2)
    if A.get("stroke_px") is not None:
        t["stroke"] = round(abs(A["stroke_px"] - P["stroke_px"]) / TOL["stroke"], 2)
    if A.get("y") is not None:
        t["y"] = round(abs(A["y"] - P["y"]) / TOL["y"], 2) if P["y"] is not None else 1.0   # 자리 없는 팩 = 문턱 하나
    return t


def cap_distance(B: dict, key: str) -> dict:
    """벤치 실측 ↔ 자막팩 한 벌 거리 — 화자별 항목 값을 줄 비율로 가중 평균. same = 표준 §10-2 '같은 항목' 문턱 안."""
    acc: dict = {}
    for w, A in (B.get("who") or {}).items():
        for k, v in _terms(A, pack_look(key, None if w == "all" else w), B.get("font_px")).items():
            acc.setdefault(k, [0.0, 0.0])
            acc[k][0] += v * A["share"]
            acc[k][1] += A["share"]
    terms = {k: round(s / n, 2) for k, (s, n) in acc.items()}
    if not acc and B.get("font_px"):
        terms["px"] = round(abs(B["font_px"] / pack_look(key)["size"] - 1) / TOL["px"], 2)
    if B.get("font"):
        terms["font"] = 0.0 if font_file(B["font"]) == font_file(caption_packs()[key]["font"]) else TOL["font"]
    d = round(sum(terms.values()) / max(1, len(terms)), 3)
    same = terms.get("font", 9) == 0 and terms.get("px", 9) <= 1 and terms.get("fill", 9) <= 1   # 글꼴 미측정이면 '같다'고 못 한다
    return {"pack": key, "d": d, "terms": terms, "same": same}


def cap_rank(B: dict) -> list[dict]:
    return sorted((cap_distance(B, k) for k in caption_packs()), key=lambda r: r["d"])


def _enter_word(e) -> str:
    e = str(e or "").strip()
    for w in ("typing", "append", "instant", "cut", "pop", "fade", "slide"):
        if e.startswith(w):
            return w
    return "기타"


def cap_enter(slug: str, key: str | None) -> dict:
    """벤치 등장 분포 → 팩이 그 등장을 갖고 있나(motion·variants enter 이름표). 정지 등장(cut·instant·append)은 팩 없이도 된다."""
    cnt = Counter()
    for f in glob.glob(str(ROOT / f"channel/{slug}/줄판독/*.json")):
        try:
            cnt.update(_enter_word(x.get("enter")) for x in json.loads(Path(f).read_text(encoding="utf-8")).get("lines") or [])
        except Exception:     # noqa: BLE001
            continue
    n = sum(cnt.values())
    p = caption_packs().get(key) or {}
    names = [str(v) for v in (p.get("motion") or {}).values() if v] + [str(v.get("enter")) for v in (p.get("variants") or {}).values()
                                                                      if isinstance(v, dict) and v.get("enter")]
    cover = {"typing": [x for x in names if re.search(r"type|typing", x, re.I)],
             "pop": [x for x in names if re.search(r"pop|bounce|slam|jelly|grow", x, re.I)],
             "fade": [x for x in names if re.search(r"fade|blur", x, re.I)],
             "slide": [x for x in names if re.search(r"slide|wipe|rise", x, re.I)]}
    out = {}
    for w, k in cnt.most_common():
        share = round(k / n, 3) if n else 0
        item = "정지(팩 불필요)" if w in ("cut", "instant", "append") else (cover.get(w) or [None])[0]
        out[w] = {"share": share, "n": k, "item": item}
    return out


def map_transition(st: dict, slug: str | None) -> dict:
    """벤치 전환 종류(판 cuts.transition.kinds · 줄판독 transition 칸) → 모션그래픽팩 전환 항목(swipe_left 뿐). 맞는 항목 없으면 gap."""
    kinds = {k: v for k, v in ((st.get("cuts") or {}).get("transition") or {}).get("kinds", {}).items() if k != "cut" and v}
    gp = graphics_packs()
    items = sorted({(p.get("transition") or {}).get("asset_id") for p in gp.values()} - {None})
    gap = []
    for k in kinds:
        hit = [a for a in items if k in a or (k in ("slide", "swipe") and "swipe" in a)]
        if not hit:
            gap.append(f"전환 {k} {kinds[k]} — 모션그래픽팩 항목 없음(있는 것 {items}) · 그리기는 엔진 cuts.transition(02)이 하지만 회원이 팩으로 못 바꾼다 → 팩요청")
    return {"kinds": kinds, "items": items, "gap": gap}


def sfx_ncc(slug: str | None, pack: str | None) -> dict:
    """벤치 효과음 ↔ 팩 파일 NCC(engine/sound/sfx_ncc.py 결과 `_kal/sfx_ncc.json`, 1.5~10kHz 대역 정규화 상호상관)."""
    p = ROOT / f"channel/{slug}/_kal/sfx_ncc.json" if slug else None
    if not p or not p.exists():
        return {"measured": False}
    hits = [h for v in json.loads(p.read_text(encoding="utf-8")).get("res", {}).values() for h in v]
    pk = [h for h in hits if str(h.get("file", "")).startswith("sfx_packs:")]
    mine = [h for h in pk if pack and f"/{pack}/" in h["file"]]
    best = max(pk, key=lambda h: h["ncc"]) if pk else None
    return {"measured": True, "hits": len(hits), "pack_hits": len(pk), "ge06": sum(h["ncc"] >= 0.6 for h in pk),
            "max": best["ncc"] if best else None, "max_file": best["file"].split("sfx_packs/")[-1] if best else None,
            "mine_max": max((h["ncc"] for h in mine), default=None)}


def _slot_of_file(path: str) -> tuple[str | None, str | None]:
    """'팩01/pop.wav' → ('팩01', '뽁'). 팩 파일이 아니면 (None, None)."""
    m = re.fullmatch(r"(팩[^/]+)/([a-z0-9]+)\.wav", str(path))
    if not m:
        return None, None
    inv = {v: k for k, v in sfx_slots().items()}
    return (m.group(1), inv.get(m.group(2))) if m.group(2) in inv else (None, None)


def slug_of(st: dict) -> str | None:
    b = st.get("bench") or {}
    if b.get("channel"):
        return b["channel"]
    lr = b.get("line_reads")
    return Path(lr).parent.name if lr else None


def _raw_file(name: str) -> dict:
    from tools.calcopy.hybrid import styles
    return json.loads(styles.path_of(name).read_text(encoding="utf-8"))


def map_all(name: str) -> tuple[dict, list[dict]]:
    """판 하나 → (packs 칸, 팩 요청 목록). 옛 칸이 있으면 그 값이 packs 값(변환 diff 0) — 측정 1위가 다르면 from 에 적고 gap."""
    from tools.calcopy.hybrid import styles
    st = styles.load(name, _skip_packs=True)
    raw = _raw_file(name)
    slug = slug_of(st)
    reqs: list[dict] = []
    P: dict = {"_why": "관제 263 지시서 11 — pack_map.py 가 채움(벤치 측정 → 팩 항목). packs 가 정본, 옛 칸(caption.pack·sfx_files·bgm.id/candidates)은 styles.load 가 packs 에서 채운다(다르면 오류)"}

    # 자막팩
    cap = (st.get("caption") or {}).get("pack")
    C: dict = {"pack": cap, "gap": []}
    if st["renderer"] != "bench":
        C["from"] = f"renderer {st['renderer']} — 자막은 렌더러 자체(render 칸)가 그린다, 자막팩 층 밖(_pending.bench_migration)"
        C["gap"].append("자막팩 길 아님(itssum/jaemi 렌더러) — bench 전환 뒤 pack_map 다시")
    elif raw.get("base") and "caption" in raw and (raw["caption"] or {}).get("pack"):
        C["from"] = f"변형판(base {raw['base']}) — 사람이 고른 우리 변형 팩 '{cap}'(벤치 없음: 자막팩 {cap}.bench = 우리 값 note) · 측정 거리 해당 없음"
    else:
        B = bench_caption(slug, st) if slug else {"basis": []}
        R = cap_rank(B) if B.get("basis") else []
        C["rank"] = [{"pack": r["pack"], "d": r["d"], "terms": r["terms"]} for r in R[:3]]
        top = R[0] if R else None
        mine = next((r for r in R if r["pack"] == cap), None)
        meas = " · ".join(B.get("basis") or []) or "측정 없음"
        if not R:
            C["from"] = f"벤치 자막 측정 없음({slug}) — 사람이 고른 '{cap}' 유지"
            C["gap"].append("자막 측정 0 → 06 줄판독 뒤 pack_map 다시")
        else:
            C["from"] = (f"벤치 {B['docs']}편 {B['lines']}줄 실측 [{meas}] → 1위 {top['pack']}(거리 {top['d']}) · 지금 {cap}"
                         f"(거리 {mine['d'] if mine else '?'}, 순위 {R.index(mine) + 1 if mine else '?'})")
        pend = str(((st.get("caption") or {}).get("_pending") or {}).get("pack") or "")
        own_first = top is not None and mine is top
        if pend and top is not None and top["same"] and not own_first:
            C["stand_in"] = True
            C["gap"].append(f"1위 '{top['pack']}' 가 같은 항목(글꼴·px·색 문턱 안) — 판 caption.pack 을 바꿀지 판 주인(07)·사람 확인(렌더가 달라진다) · 그동안 '{cap}' 임시")
        elif pend or (top is not None and not own_first):
            C["stand_in"] = True
            n = len(reqs) + 1
            reqs.append({"element": "자막팩(caption-motions.js PACKS) — 그 채널 한 벌", "owner": "관제 235(자막팩 세션)", "measure": meas,
                         "rank": C.get("rank"), "stand_in": cap, "want": pend or f"{slug} 벤치 자막 한 벌(위 실측값)",
                         "frames": f"channel/{slug}/줄판독/*.json (y·fill_hex·outline 칸) · channel/{slug}/스타일분석.md §1"})
            C["gap"].append(f"벤치 자막과 같은 팩 없음(같음 기준 글꼴·px±10%·ΔE<5 — 1위 {top['pack'] if top else '?'} same={top['same'] if top else '?'}) "
                            f"→ 팩요청.md {name}#{n}(관제 235) · 그동안 '{cap}' 임시(stand_in)")
        elif own_first and not mine["same"]:
            off = {k: v for k, v in mine["terms"].items() if v > 1}
            if "font" not in mine["terms"]:
                off["font"] = "미측정(스타일분석 글꼴 줄에 등록 글꼴 없음 — 06 fontmatch)"
            n = len(reqs) + 1
            reqs.append({"element": f"자막팩 '{cap}' 보정(문턱 밖 항목 {off})", "owner": "관제 235(자막팩 세션)", "measure": meas,
                         "rank": C.get("rank"), "stand_in": f"'{cap}' 그대로(1위 — 자기 팩)",
                         "want": f"'{cap}' 의 {list(off)} 를 벤치 실측에 맞추거나, 줄판독 측정이 옛 틀이면 새 틀로 재측정(06)",
                         "frames": f"channel/{slug}/줄판독/*.json (y·fill_hex·outline 칸) · channel/{slug}/스타일분석.md §1"})
            C["gap"].append(f"자기 팩 1위지만 문턱 밖 {off}(1.0 = 문턱) → 팩요청.md {name}#{n}(보정 또는 재측정)")
        if slug:
            C["enter_cover"] = cap_enter(slug, cap)
            miss = [w for w, v in C["enter_cover"].items() if v["item"] is None and v["share"] >= 0.05 and w != "기타"]
            if miss:
                n = len(reqs) + 1
                reqs.append({"element": f"자막 등장 {miss}", "owner": "관제 235(자막팩 세션)",
                             "measure": json.dumps({w: C['enter_cover'][w] for w in miss}, ensure_ascii=False),
                             "stand_in": cap, "want": f"{cap} 팩에 {miss} 등장 변형(벤치 줄 비율 위)", "frames": f"channel/{slug}/줄판독/*.json enter·enter_ms 칸"})
                C["gap"].append(f"벤치 등장 {miss}(줄 5% 이상) 팩 '{cap}' 에 없음 → 팩요청.md {name}#{n}")
    P["caption"] = C

    # 모션(등장 효과팩 번호 · 모션그래픽팩)
    T = map_transition(st, slug)
    M = {"pack": "off", "graphics": "off", "gap": [],
         "from": ("등장 효과팩 off — 판 자막팩이 등장까지 정한다(caption-motions.js motionPlan: 팩 motion 이 효과팩 번호보다 이긴다)"
                  if (caption_packs().get(cap) or {}).get("motion") else
                  "등장 효과팩 off — render_bench 옛 고정값 그대로(벤치 등장 = 판 caption.pack_default·placement.rules.enter 가 정함)")
                 + f" · 모션그래픽팩 off — 벤치 전환 {T['kinds'] or '{cut 만}'} 에 맞는 팩 항목 없음(팩 전환 = {T['items']})"}
    for g in T["gap"]:
        n = len(reqs) + 1
        reqs.append({"element": "모션그래픽팩 전환 항목", "owner": "모션팩 주인(assets/motion/packs.json — 팩 세션)", "measure": g,
                     "stand_in": "엔진 cuts.transition(render_bench window_fx)", "want": "벤치 전환과 같은 전환 항목(종류·ms) — 회원이 팩에서 바꿀 수 있게",
                     "frames": f"channel/{slug}/줄판독/*.json transition 칸 · channel/{slug}/_kal/transition_drop.json(있으면)"})
        M["gap"].append(g.split(" → ")[0] + f" → 팩요청.md {name}#{n}")
    P["motion"] = M

    # 효과음
    sf = st.get("sfx_files")
    if sf is None:
        P["sfx"] = {"pack": None, "gap": [], "from": f"renderer {st['renderer']} — 효과음은 렌더러 자체(render 칸)"}
    else:
        packs_used, mp, outside = Counter(), {}, {}
        for k, v in sf.items():
            if k in ("gain_db", "why"):
                continue
            pk, slot = _slot_of_file(v)
            if pk:
                packs_used[pk] += 1
                mp[k] = slot
            else:
                outside[k] = v
        pk = packs_used.most_common(1)[0][0] if packs_used else None
        if len(packs_used) > 1:
            raise PackError(f"판 {name}: sfx_files 가 팩 여러 개 {dict(packs_used)} — packs.sfx 는 팩 하나(사람 확인)")
        S = {"pack": pk, "map": mp}
        if outside:
            S["outside"] = outside
        if "gain_db" in sf:
            S["gain_db"] = sf["gain_db"]
        if "why" in sf:
            S["why"] = sf["why"]
        nc = sfx_ncc(slug, pk)
        S["ncc"] = nc
        kinds = list((((st.get("placement") or {}).get("rules") or {}).get("sfx") or {}).get("kinds") or {}) or \
            [((st.get("placement") or {}).get("rules") or {}).get("sfx", {}).get("kind")]
        kinds = [k for k in kinds if k and k != "none"]
        lab = " · ".join(f"{k}→{mp.get(k) or KIND_SLOT.get(k, '?')}" for k in (kinds or list(mp)))
        if nc.get("measured"):
            ev = f"NCC 벤치↔팩 파일 {nc['pack_hits']}발 중 ≥0.6 {nc['ge06']}개(최대 {nc['max']} {nc['max_file']})"
        else:
            ev = "NCC 미측정(_kal/sfx_ncc.json 없음)"
        S["from"] = f"{ev} → 지문으로 고를 수 없어 종류 이름표로 slot: {lab or '없음'}" + (f" · 팩 {pk}" if pk else " · 팩 없음(종류 미측정)")
        S["gap"] = []
        if outside:
            n = len(reqs) + 1
            reqs.append({"element": f"효과음 {list(outside)}", "owner": "효과음팩 주인(sfx_packs — 팩 세션)", "measure": json.dumps(outside, ensure_ascii=False),
                         "stand_in": "팩 밖 파일 그대로(outside 칸 — 표시된 임시)", "want": "같은 소리를 팩 slot 으로(예 impact = 낮은 쿵)",
                         "frames": f"channel/{slug}/스타일분석.md §7 소리"})
            S["gap"].append(f"팩 밖 효과음 {list(outside)} — slot 없음 → 팩요청.md {name}#{n}")
        if not pk and kinds:
            S["gap"].append(f"효과음 종류 {kinds} 팩 미지정 → 06 측정 뒤")
        P["sfx"] = S

    # 배경음
    Bg = st.get("bgm") or {}
    P["bgm"] = {"id": Bg.get("id"), "from": "id = 사람이 고른 곡(자동 교체 안 함) · candidates = bgm_pick.py recommend 상위 3(02, 벤치 템포·밝기·화성 거리)"}
    if "candidates" in Bg:
        P["bgm"]["candidates"] = Bg["candidates"]

    # 짤
    Mm = ((st.get("placement") or {}).get("rules") or {}).get("meme")
    E = {"pack": "local", "gap": []}
    if Mm is not None:
        if "tone" in Mm:
            E["tone"] = Mm["tone"]
        if "pack" in Mm:
            E["dir"] = Mm["pack"]
        E["from"] = f"벤치 짤 빈도 = placement.rules.meme.rate {Mm.get('rate')}(뼈대 칸 — 여기 안 적음) · 칼카피 길 = 로컬 짤 팩(material_auto.MEME_*) · 톤 {Mm.get('tone') or '없음'}"
    else:
        E["from"] = "짤 규칙 없음(placement.rules.meme 없음 = 짤 0) · 칼카피 길 = 로컬 짤 팩"
    P["meme"] = E
    return P, reqs


# ── 판 파일 쓰기 · 팩요청.md ───────────────────────────────────────────────
DECIDE = ("pack", "graphics", "map", "outside", "gain_db", "why", "id", "candidates", "tone", "dir")


def only_diff(P: dict, base: dict) -> dict:
    """상속 판에 쓸 packs = 바탕 판과 결정 칸(DECIDE)이 다른 요소만."""
    out = {k: v for k, v in P.items() if k.startswith("_")}
    for k in PACK_KEYS:
        a, b = P.get(k) or {}, base.get(k) or {}
        if any(a.get(x) != b.get(x) for x in DECIDE if x in a or x in b):
            out[k] = a
    return out


def write_packs(name: str, P: dict):
    """판 파일에 packs 칸만 넣는다(다른 칸·줄바꿈 꼴 그대로 — 판 파일 주인은 07, packs 칸만 11)."""
    from tools.calcopy.hybrid import styles
    p = styles.path_of(name)
    t = p.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    raw = json.loads(t)
    if json.dumps(raw, ensure_ascii=False, indent=1).replace("\n", nl) + nl != t:
        raise PackError(f"{p.name} 이 indent=1 꼴이 아니다 — 손으로 넣어라(다른 칸 줄바꿈이 바뀐다)")
    raw["packs"] = P
    p.write_bytes((json.dumps(raw, ensure_ascii=False, indent=1).replace("\n", nl) + nl).encode("utf-8"))


def write_requests(name: str, slug: str, reqs: list[dict]) -> Path | None:
    """channel/<slug>/_kal/팩요청.md — 판마다 절 하나(<!-- 판:이름 --> 표식 사이만 다시 쓴다: 한 채널에 판 둘(썰풀다 A·B)이어도 안 덮는다)."""
    if not slug:
        return None
    p = ROOT / f"channel/{slug}/_kal/팩요청.md"
    head = [f"# {slug} 팩 요청 (관제 263 지시서 11 · `pack_map.py <판> --write` 가 씀 — 손으로 고치지 말고 다시 돌려라)", "",
            "> 꼴 = 지침서 §4-2 요청서: 요소 · 벤치 실측값 · 근거 경로 · 원하는 항목 꼴 · 그동안 쓰는 임시(stand_in). 임시는 판 `packs.*.gap` 에 표시(카드 engine_support ×).",
            "> 번호 = `<판>#n` — 판 `packs.*.gap` 의 '팩요청.md <판>#n' 과 짝.", ""]
    sec = [f"<!-- 판:{name} -->", f"## 판 `{name}` — 요청 {len(reqs)}건", ""]
    for i, r in enumerate(reqs, 1):
        sec += [f"### {name}#{i} {r['element']} → {r['owner']}", "", f"- 벤치 실측: {r['measure']}"]
        if r.get("rank"):
            sec.append("- 지금 팩 거리(1.0 = 같음 문턱, 항목별): " + " · ".join(f"{x['pack']} {x['d']} {x['terms']}" for x in r["rank"]))
        sec += [f"- 근거 경로: {r['frames']}", f"- 원하는 항목: {r['want']}", f"- 그동안: {r['stand_in']}", ""]
    sec.append(f"<!-- /판:{name} -->")
    NL = "\n"
    body = p.read_text(encoding="utf-8") if p.exists() else NL.join(head)
    m = re.search(rf"<!-- 판:{re.escape(name)} -->.*?<!-- /판:{re.escape(name)} -->", body, re.S)
    if not reqs:
        if not m:
            return None
        body = body[:m.start()] + body[m.end():]
    elif m:
        body = body[:m.start()] + NL.join(sec) + body[m.end():]
    else:
        body = body.rstrip(NL) + NL + NL + NL.join(sec) + NL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def table(name: str, P: dict) -> str:
    c, m, s, b, e = (P.get(k) or {} for k in PACK_KEYS)
    r = (c.get("rank") or [{}])[0]
    return (f"{name:10s} caption={c.get('pack')}{'(임시)' if c.get('stand_in') else ''} 1위={r.get('pack')}:{r.get('d')} | "
            f"motion={m.get('pack')}/{m.get('graphics')} | sfx={s.get('pack')} {s.get('map')} out={list((s.get('outside') or {}))} | "
            f"bgm={b.get('id')} | meme={e.get('pack')} | gap={sum(len(P[k].get('gap') or []) for k in PACK_KEYS)}")


def main():
    from tools.calcopy.hybrid import styles
    a = sys.argv[1:]
    if a and a[0] == "rank":
        st = styles.load(a[1])
        B = bench_caption(slug_of(st), st)
        print(json.dumps(B, ensure_ascii=False))
        for r in cap_rank(B)[:5]:
            print(f"  {r['pack']:12s} d={r['d']:<6} same={r['same']} {r['terms']}")
        return
    names = styles.names() if "--all" in a else [x for x in a if not x.startswith("--")]
    for n in names:
        P, reqs = map_all(n)
        print(table(n, P))
        if "--write" in a:
            raw = _raw_file(n)
            if raw.get("base"):                       # 상속 판 = 바탕 판 packs 와 다른 요소만(두 벌 금지)
                P = only_diff(P, styles.load(raw["base"]).get("packs") or {})
                if not [k for k in P if not k.startswith("_")]:
                    print(f"   상속 판 — 바탕 {raw['base']} packs 그대로(쓸 것 없음)")
                    continue
            write_packs(n, P)
            st = styles.load(n, _skip_packs=True)
            rp = write_requests(n, slug_of(st), reqs)
            if rp:
                print(f"   팩요청 {len(reqs)}건 → {rp.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
