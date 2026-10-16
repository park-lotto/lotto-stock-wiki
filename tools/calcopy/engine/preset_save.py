# -*- coding: utf-8 -*-
"""프리셋 저장·재사용 — 설계 docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §5 (channel/<slug>/preset/<스타일>/).

    저장: PYTHONUTF8=1 py tools/calcopy/engine/preset_save.py <뜯기.json> <frame.json> --slug sseolpulda --style A_흰바탕창 [--exclude caption]
    적용: PYTHONUTF8=1 py tools/calcopy/engine/preset_save.py apply channel/sseolpulda/preset/A_흰바탕창 --from-frame <그 편 frame.json>
                      [--set 'layers[text:title].text="1줄\\n2줄"'] --out <frame.json>

판단 주인: '어느 값이 편마다 달라지나'는 merge() 한 곳 — 같은 틀로 잰 편들(sources)에서 같은 자리 값이 기준 안에서 같으면 고정,
다르면 "$per_video"(변수). 제목 글자처럼 내용인 자리는 처음부터 변수(ALWAYS_PER_VIDEO). 적용(apply)은 변수 자리를 그 편 값으로만
채우고, 못 채운 변수가 남으면 멈춘다(조용히 프리셋 값으로 메우지 않는다).
자리 이름: 맨 위 키('canvas' · 'template_off' · 'source' …) · 'layers[<kind>(:<role>)].<필드>'  예) layers[text:title].line_rgb
manifest.json: 어느 편에서 쟀나(sources: 편·뜯기 파일·분석기·잰 시각·글꼴 판별 점수·미확인 항목·뺀 층) · 변수 목록 · 생성 규칙 표식 · 만든/고친 시각.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402

VAR = "$per_video"
MADE_BY = "preset_save v1"
RULE = ("같은 자리 값이 편마다 기준(숫자 max(4, 3%) · 색 채널 12 · 글·참거짓 같음) 밖이면 $per_video, "
        "제목 글자는 항상 $per_video, --exclude 로 뺀 층은 그 편에서 비교 안 함")
ALWAYS_PER_VIDEO = ("layers[text:title].text",)
NOT_COMPARED = ("source", "made_by")   # 출처 표식 — 틀 값이 아니다(프리셋엔 첫 편 값이 남고 출처 목록은 manifest.sources)
REQUIRED_MANIFEST = ("slug", "style", "made_by", "rule", "created_at", "updated_at", "variables", "sources")


def _key(layer: dict) -> str:
    return layer["kind"] + (":" + layer["role"] if layer.get("role") else "")


def _names(layers: list) -> list[str]:
    names, seen = [], {}
    for layer in layers or []:
        k = _key(layer)
        seen[k] = seen.get(k, 0) + 1
        names.append(k if seen[k] == 1 else f"{k}#{seen[k]}")
    return names


def flat(frame: dict) -> dict:
    """설명서 → {자리: 값}. 층은 kind(:role) 로 이름 붙인다(같은 이름 층이 둘이면 #2…).
    틀 여러 장(frames)이면 'frames[<id>].span' · 'frames[<id>].layers[<층>].<필드>' (게시글형 훅·본문, 10-16)."""
    out = {k: v for k, v in frame.items() if k not in ("layers", "frames", "made_from")}   # canvas·template_off·made_by·source …
    if frame.get("frames"):
        for fr in frame["frames"]:
            pre = f"frames[{fr['id']}]."
            out[pre + "span"] = fr["span"]
            for name, layer in zip(_names(fr["layers"]), fr["layers"]):
                for f, v in layer.items():
                    if f != "kind":
                        out[f"{pre}layers[{name}].{f}"] = v
        return out
    for name, layer in zip(_names(frame.get("layers")), frame.get("layers") or []):
        for f, v in layer.items():
            if f != "kind":
                out[f"layers[{name}].{f}"] = v
    return out


_FR = re.compile(r"^frames\[([^\]]+)\]\.(.+)$")


def _layer_of(name: str) -> dict:
    return {"kind": name.split(":")[0].split("#")[0], **({"role": name.split(":")[1].split("#")[0]} if ":" in name else {})}


def unflat(flat_map: dict, order: list[str]) -> dict:
    """flat 의 거꾸로 — order = 층 이름 순서(프리셋 frame 의 층 순서 유지). 틀 여러 장이면 '<틀 id>/<층 이름>'."""
    if any("/" in n for n in order):
        fids = list(dict.fromkeys(n.split("/", 1)[0] for n in order))
        layers = {n: _layer_of(n.split("/", 1)[1]) for n in order}
        spans = {}
        out = {}
        for path, v in flat_map.items():
            m = _FR.match(path)
            if not m:
                out[path] = v
                continue
            fid, rest = m.group(1), m.group(2)
            if rest == "span":
                spans[fid] = v
            else:
                name, field = rest[len("layers["):].split("].", 1)
                layers[f"{fid}/{name}"][field] = v
        out["frames"] = [{"id": fid, "span": spans[fid], "layers": [layers[n] for n in order if n.split("/", 1)[0] == fid]} for fid in fids]
        return out
    layers = {n: _layer_of(n) for n in order}
    out = {k: v for k, v in flat_map.items() if not k.startswith("layers[")}
    for path, v in flat_map.items():
        if path.startswith("layers["):
            name, field = path[len("layers["):].split("].", 1)
            layers[name][field] = v
    out["layers"] = [layers[n] for n in order]
    return out


def layer_order(frame: dict) -> list[str]:
    if frame.get("frames"):
        return [f"{fr['id']}/{n}" for fr in frame["frames"] for n in _names(fr["layers"])]
    return _names(frame.get("layers"))


def always_per_video(path: str) -> bool:
    """내용인 자리(제목 글자) — 틀 여러 장이면 틀마다 같은 자리(frames[hook].layers[text:title].text).
    틀 시간축(frames[..].span)도 편마다 — 훅 카드 길이 = 그 편 훅 나레 길이(rGFX 3.137·신라면 2.446초). 숫자 기준 max(4,3%)는
    초 단위엔 뜻이 없어 같다고 봤다."""
    return any(path == p or path.endswith("." + p) for p in ALWAYS_PER_VIDEO) or bool(_FR.match(path) and path.endswith("].span"))


def same(a, b, path: str = "") -> bool:
    """기준 안에서 같은가 — 숫자 max(4, 3%), rgb(0~255 정수 셋) 채널 12, 나머지 그대로 같음."""
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= max(4.0, 0.03 * max(abs(a), abs(b)))
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        if len(a) == 3 and all(isinstance(x, int) for x in a + b):
            return max(abs(x - y) for x, y in zip(a, b)) <= 12
        return all(same(x, y, path) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(same(a[k], b[k], path) for k in a)
    return a == b


def merge(preset: dict, new: dict, exclude: tuple = (), fixed: tuple = ()) -> tuple[dict, list[str]]:
    """프리셋 설명서 + 같은 틀의 새 편 설명서 → (합친 프리셋, 이번에 변수가 된 자리). fixed = 대조로 못 박은 자리(안 건드림)."""
    P, N = flat(preset), flat(new)
    became = []
    for path, v in P.items():
        if v == VAR:
            continue
        if path in NOT_COMPARED or path in fixed or any(path.startswith(f"layers[{e}") for e in exclude) or path not in N:
            continue
        if not same(v, N[path], path):
            P[path] = VAR
            became.append(path)
    return unflat(P, layer_order(preset)), became


def variables(frame: dict) -> list[str]:
    return [p for p, v in flat(frame).items() if v == VAR]


def _strip(frame: dict) -> dict:
    f = {k: v for k, v in frame.items() if k != "made_from"}
    return copy.deepcopy(f)


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    m = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    # 소수는 셋째 자리까지 — 첫째 자리로 자르니 비율(lh_ratio 1.03)이 1.0 이 돼 창 y 가 6px 밀렸다(창아래_검정 LED 수도꼭지 실측, 10-16)
    return int(round(m)) if all(isinstance(x, int) for x in xs) else round(m, 3)


NO_DEFAULT = "내용 — 기본값 없음(새 소재는 --set)"


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _shape(v):
    """값의 모양 — 숫자만 '#'로 바꾼 것. 글자·참거짓·null 은 그대로라 모양이 같으면 숫자만 다른 값이다."""
    if _num(v):
        return "#"
    if isinstance(v, list):
        return [_shape(x) for x in v]
    if isinstance(v, dict):
        return {k: _shape(x) for k, x in sorted(v.items())}
    return v


def _elem_median(vs):
    """모양이 같은 값들의 자리별 중앙값(숫자 자리만, 나머지는 그대로)."""
    v0 = vs[0]
    if _num(v0):
        return _median(vs)
    if isinstance(v0, list):
        return [_elem_median([v[i] for v in vs]) for i in range(len(v0))]
    if isinstance(v0, dict):
        return {k: _elem_median([v[k] for v in vs]) for k in v0}
    return v0


def stats(values: dict) -> dict:
    """변수 한 자리의 편별 값 → {values, default, range, how}.
    가장 많은 편이 가진 모양(숫자만 다른 값끼리 한 무리)을 고르고 그 무리의 자리별 중앙값을 기본값으로(숫자 없는 값 = 최빈).
    줄색 [[0,0,0],[251,2,82]] 처럼 숫자만 조금씩 다른 값이 '최빈 1/5' 로 흩어지지 않게(2026-10-16 첫판 실측). 범위는 숫자 하나일 때만."""
    vals = list(values.values())
    groups = {}
    for v in vals:
        groups.setdefault(json.dumps(_shape(v), ensure_ascii=False, sort_keys=True), []).append(v)
    if not groups:
        return {"values": values, "default": None, "range": None, "how": "값 없음"}
    best = max(groups.values(), key=len)
    rng = [min(best), max(best)] if _num(best[0]) else None
    how = ("중앙값" if _num(best[0]) else "자리별 중앙값" if json.dumps(_shape(best[0])).count('"#"') else "최빈") + f"({len(best)}/{len(vals)}편)"
    return {"values": values, "default": _elem_median(best), "range": rng, "how": how}


TITLE_FONT = "layers[text:title].font"


def title_font_stats(M: dict, vals: dict, st: dict) -> dict:
    """하위 스타일 제목 글꼴 = ① 분석기 묶음 판별(fonts.title_pooled — 여러 편 제목을 한 번에 판별, 3판-b)이 있으면 그 1위
    ② 없으면 편별 판별의 최빈 ③ 동률이면 편별 판별 점수(top5)를 글꼴마다 더해 높은 쪽.
    (2026-10-16 관제가 눈으로 확인: ho5·7DY·1_V 제목은 같은 글꼴인데 편별 판별이 Cafe24/yg-jalnan 으로 갈렸다)"""
    from tools.calcopy.engine.to_frame import family_of
    pooled = [s.get("title_pooled") for s in M["sources"] if s.get("title_pooled")]
    for pl in pooled:
        top = (pl.get("top3") or pl.get("top5") or []) if isinstance(pl, dict) else (pl if isinstance(pl, list) else [])
        for x in top:
            fam = family_of(x.get("font", ""))
            if fam:
                return {**st, "default": fam, "how": f"분석기 묶음 판별 fonts.title_pooled 1위 {x['font']}({x.get('score')})"}
    counts = {}
    for v in vals.values():
        counts[v] = counts.get(v, 0) + 1
    if not counts:
        return st
    best = max(counts.values())
    tied = [f for f, c in counts.items() if c == best]
    if len(tied) == 1:
        return {**st, "default": tied[0], "how": f"편별 판별 최빈({best}/{len(vals)}편)"}
    score = {f: 0.0 for f in tied}
    for s in M["sources"]:
        for x in ((s.get("title_fonts") or {}).get("top5") or (s.get("title_fonts") or {}).get("top3") or []):
            fam = family_of(x.get("font", ""))
            if fam in score:
                score[fam] += float(x.get("score") or 0)
    win = max(tied, key=lambda f: (score[f], -tied.index(f)))
    return {**st, "default": win, "how": f"편별 판별 동률 {tied} → 점수 합 {{{', '.join(f'{f}: {score[f]:.3f}' for f in tied)}}} 높은 쪽"}


def variable_stats(preset_dir: Path, M: dict, preset: dict) -> dict:
    """프리셋의 변수 자리마다 출처 편들의 값(sources/<id>.json)으로 stats. 그 편에서 뺀 층(excluded_layers)·없는 자리는 빼고 센다.
    제목 글자처럼 내용인 자리(ALWAYS_PER_VIDEO)는 default 를 두지 않는다(새 소재는 반드시 --set)."""
    out = {}
    flats = {}
    for s in M["sources"]:
        f = preset_dir / "sources" / f"{s['id']}.json"
        if f.exists():
            flats[s["id"]] = (flat(json.loads(f.read_text(encoding="utf-8"))), s["excluded_layers"])
    for path in variables(preset):
        vals = {sid: F[path] for sid, (F, ex) in flats.items()
                if path in F and not any(path.startswith(f"layers[{e}") for e in ex)}
        st = stats(vals)
        if path == TITLE_FONT:
            st = title_font_stats(M, vals, st)
        if path == "layers[text:title].text" or path.endswith(".text"):   # 글 내용(제목·글 제목 문구) — 새 소재는 반드시 --set
            st.update(default=None, range=None, how=NO_DEFAULT)
        out[path] = st
    return out


def caption_style_entry(M: dict, name: str, layer: dict | None, source_id: str, note: str | None) -> None:
    """자막 하위 스타일(같은 틀 안에서 자막만 다른 갈래) — 이름별로 잰 층과 편 목록. 층이 없으면(뜯기 결함으로 뺌) 미측정."""
    styles = M.setdefault("caption_styles", [])
    st = next((x for x in styles if x["name"] == name), None)
    if st is None:
        st = {"name": name, "layer": None, "status": "미측정", "sources": [], "notes": []}
        styles.append(st)
    st["sources"].append(source_id)
    if note:
        st["notes"].append(f"{source_id}: {note}")
    if layer is not None and st["layer"] is None:
        st["layer"], st["status"] = layer, f"잰 편 {source_id}"


def slug_style(preset_dir: Path) -> tuple[str, str]:
    """channel/<slug>/preset/<스타일>[/<하위 스타일>] → (slug, '스타일/하위'). 하위 스타일 = 프리셋 단위(평균 내지 않는다)."""
    parts = list(preset_dir.parts)
    i = len(parts) - 1 - parts[::-1].index("preset") if "preset" in parts else len(parts) - 2
    return parts[i - 1], "/".join(parts[i + 1:])


# ── 관계 규칙(2026-10-16 사장님·관제: 평균 틀은 아무 편도 아니다 — 종속값은 규칙으로) ──
#   편마다 다른 값 중 일부는 다른 값에서 나온다. 기본값은 독립 변수에만 두고 apply 가 종속값을 계산한다.
#     제목 크기 = min(size_cap, 가장 긴 줄이 fill_w 폭이 되는 크기)  · 줄높이 = 크기 × lh_ratio · 제목 위 끝 = title_top
#     창 y = 제목 아래 끝(title_top + 줄수×줄높이) + gap   · 창 아래 끝 = video_bottom(자막 하위 스타일이 정함)
#     자막 y = 창 아래 끝 + cap_dy(창아래면 +, 창안이면 −)
RULE_FORMULA = ("title.size = size_cap(잰 크기 중앙값) — 가장 긴 줄이 fill_w(잰 폭 최대·화면 폭−48 중 큰 값)를 넘으면 자간부터(−15%까지), 그래도 넘으면 크기 · "
                "title.line_h = size×lh_ratio · title.y = title_top · video.y = (video_anchor) 'gap_ink' 면 제목 잉크 아래 끝 + gap_ink(고정), 'constant' 면 video_top, 'gap' 이면 "
                "title.y + lines×line_h + gap — 편마다 덜 흔들리는 쪽(데이터가 고름) · video.h = video_bottom − video.y · caption.y = video_bottom + cap_dy")
EDGE_MARGIN = 48   # 제목 폭 상한의 바닥 = 화면 폭 − 48(양쪽 24px) — 두 편으로 만든 프리셋이 '긴 제목' 예를 못 봤을 때(LOO 1_V 실측: 930 상한 → 84pt)


def _line_w(fam: str, size: float, ls: float, line: str) -> float:
    from tools.calcopy.engine.to_frame import _pil_font
    b = _pil_font(fam, size).getbbox(line, anchor="ls")
    return (b[2] - b[0]) + ls * max(0, len(line) - 1)


def _scales(t: dict) -> list:
    n = int(t.get("lines") or 1)
    sc = t.get("line_scale") or []
    return [sc[i] if i < len(sc) else 1 for i in range(n)]


def title_ink_bottom(t: dict) -> float | None:
    """제목 마지막 줄 잉크 아래 끝(y) — 렌더러 규칙(줄 칸 line_h 안에 글꼴 ascent+descent 상자를 세로 가운데, to_frame.size_and_top 과
    같은 모형)으로 그 글꼴·줄 크기·글을 놓아 잰다. 글이 없으면 None."""
    if not t.get("text"):
        return None
    from tools.calcopy.engine.to_frame import _pil_font
    lines = t["text"].split(chr(10))
    i = len(lines) - 1
    size = t["size"] * _scales({**t, "lines": len(lines)})[i]
    f = _pil_font(t["font"], size)
    asc, desc = f.getmetrics()
    base = t["y"] + i * t["line_h"] + (t["line_h"] - (asc + desc)) / 2 + asc
    return base + f.getbbox(lines[i], anchor="ls")[3]


def derived(frame: dict, caption_ok: bool = True) -> dict:
    """편 설명서 한 장에서 규칙의 독립 값(측정값)을 뽑는다."""
    L = {(l["kind"] + (":" + l["role"] if l.get("role") else "")): l for l in frame.get("layers") or []}   # 틀 여러 장은 관계 규칙 없음(아직)
    t, v, c = L.get("text:title"), L.get("video"), L.get("text:caption")
    out = {}
    if t and v:
        n = t["lines"]
        out.update(title_top=t["y"], gap=v["y"] - (t["y"] + n * t["line_h"]), lh_ratio=round(t["line_h"] / t["size"], 3),
                   size_cap=t["size"], video_bottom=v["y"] + v["h"], video_top=v["y"])
        ib = title_ink_bottom(t)
        if ib is not None:
            out["gap_ink"] = round(v["y"] - ib)          # 제목 마지막 줄 잉크 아래 끝 ~ 창 위 끝(고정 — 관제 10-16)
        if t.get("text"):
            sc = _scales({**t, "lines": len(t["text"].split(chr(10)))})
            out["fill_w"] = round(max(_line_w(t["font"], t["size"] * sc[i], t["letter_spacing"], ln)
                                      for i, ln in enumerate(t["text"].split(chr(10)))))
    if c and v and caption_ok:
        out["cap_dy"] = c["y"] - (v["y"] + v["h"])
    return out


def rule_stats(preset_dir: Path, M: dict) -> dict:
    vals = {}
    for s in M["sources"]:
        f = preset_dir / "sources" / f"{s['id']}.json"
        if f.exists():
            d = derived(json.loads(f.read_text(encoding="utf-8")), "text:caption" not in s["excluded_layers"])
            if s.get("title_ink_w"):          # 프레임에서 잰 제목 가장 긴 줄 잉크 폭(to_frame made_from) — 글꼴로 계산한 값보다 먼저
                d["fill_w"] = s["title_ink_w"]
            for k, x in d.items():
                vals.setdefault(k, {})[s["id"]] = x
    keys = {k: stats(v) for k, v in vals.items()}
    # 제목 크기 = 잰 크기의 중앙값, 폭 상한 = 잰 폭 최대와 화면 폭−48 중 큰 값.
    #   (첫 판은 크기 상한=최대·폭=중앙값이었는데, 잰 폭은 글자 길이를 따라 889~1032 로 흔들리고 크기는 92~102 로 덜 흔들렸다 —
    #    폭 중앙값에 맞추면 긴 제목이 84pt 로 작아졌다, LOO 2026-10-16)
    if "fill_w" in keys:
        W = 1080
        keys["fill_w"]["default"] = max(max(vals["fill_w"].values()), W - EDGE_MARGIN)
        keys["fill_w"]["how"] = f"잰 폭 최대와 화면 폭−{EDGE_MARGIN} 중 큰 값"
    # 창 위 끝: 고정(video_top)과 제목 아래+gap 중 편마다 덜 흔들리는 쪽
    if "gap_ink" in keys:
        # 제목 끝–창 간격은 고정(관제 10-16: 제목 y·줄높이는 편집자가 고르는 변수, 간격은 틀). 창 y 는 제목 잉크 아래 끝 + gap_ink.
        #   (예전: 창 y 고정 vs 상자 gap 중 덜 흔들리는 쪽 — 창 고정이면 제목 2줄이 창으로 내려앉아도 못 막았다, LOO ho5 12px)
        keys["video_anchor"] = {"values": None, "default": "gap_ink", "range": None, "how": "제목 끝–창 간격 고정(gap_ink)"}
    elif "video_top" in keys and "gap" in keys:
        sp = lambda k: max(vals[k].values()) - min(vals[k].values())   # noqa: E731
        anchor = "constant" if sp("video_top") <= sp("gap") else "gap"
        keys["video_anchor"] = {"values": None, "default": anchor, "range": None,
                                "how": f"창 y 폭 {sp('video_top')} vs gap 폭 {sp('gap')} → {anchor}"}
    return {"formula": RULE_FORMULA, "keys": keys}


def apply_rules(F: dict, rules: dict) -> dict:
    """규칙으로 종속값(제목 크기·줄높이·위치, 창 y·h, 자막 y)을 계산해 넣는다. 제목 글자가 있어야 한다."""
    K = {k: v["default"] for k, v in (rules or {}).get("keys", {}).items()}
    L = {(l["kind"] + (":" + l["role"] if l.get("role") else "")): l for l in F.get("layers") or []}
    t, v, c = L.get("text:title"), L.get("video"), L.get("text:caption")
    if t and t.get("text") and "fill_w" in K:
        lines = t["text"].split(chr(10))
        # 크기는 잰 크기(중앙값) 그대로 — 글자 키(띠 높이)가 틀의 모양이다. 폭이 상한(fill_w)을 넘으면 먼저 자간을 줄이고
        #   (크기의 −15% 까지, to_frame.spacing_for 와 같은 바닥), 그래도 넘을 때만 크기를 줄인다.
        #   (2026-10-16 LOO: 폭 맞춤으로 크기부터 줄이니 제목 띠 높이가 원본 91~110 → 75~87 로 작아졌다)
        size = K.get("size_cap") or t["size"]
        sc = _scales({**t, "lines": len(lines)})               # 줄 배율(line_scale) — 줄마다 크기가 다른 제목
        k = max(range(len(lines)), key=lambda i: _line_w(t["font"], size * sc[i], 0, lines[i]))
        n = lines[k]
        nat = _line_w(t["font"], size * sc[k], 0, n)
        gaps = max(1, len(n) - 1)
        ls = t["letter_spacing"]
        if nat + ls * gaps > K["fill_w"]:
            ls = max(-0.15 * size, (K["fill_w"] - nat) / gaps)
            if nat + ls * gaps > K["fill_w"]:
                size = size * (K["fill_w"] - ls * gaps) / max(1, nat)
        t["letter_spacing"] = round(ls, 1)
        t["size"] = round(size, 1)
        t["line_h"] = round(t["size"] * K.get("lh_ratio", 1.15))
        t["lines"] = len(lines)
    if t and "title_top" in K:
        t["y"] = K["title_top"]
    if t and v and K.get("video_anchor") == "gap_ink" and "gap_ink" in K and title_ink_bottom(t) is not None:
        v["y"] = round(title_ink_bottom(t) + K["gap_ink"])
    elif v and K.get("video_anchor") == "constant" and "video_top" in K:
        v["y"] = K["video_top"]
    elif t and v and "gap" in K:
        v["y"] = round(t["y"] + t["lines"] * t["line_h"] + K["gap"])
    if v and "video_bottom" in K:
        v["h"] = K["video_bottom"] - v["y"]
    if c and v and "cap_dy" in K:
        c["y"] = v["y"] + v["h"] + K["cap_dy"]
    return F


def save(J: dict, frame: dict, preset_dir: Path, source_id: str, tteutgi_path: str, exclude: tuple = (),
         caption_style: str | None = None, caption_note: str | None = None) -> dict:
    """프리셋 폴더에 frame.json·manifest.json 을 쓰거나(처음) 합친다(같은 틀 다른 편). 돌려주는 값 = manifest.
    편마다 정규화한 설명서를 sources/<편>.json 으로 남겨, 변수마다 편별 값·기본값·범위(variable_stats)를 다시 센다.
    caption_style = 이 편 자막이 속한 하위 스타일 이름(워커 정답 등 사람이 준 분류) — 자막 층을 뺐으면 그 스타일은 미측정으로 남는다."""
    preset_dir.mkdir(parents=True, exist_ok=True)
    fp, mp = preset_dir / "frame.json", preset_dir / "manifest.json"
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    new = schema.validate(_strip(frame))                    # 형식 검사 + 정규화 모양으로 비교·저장(층마다 같은 키)
    if fp.exists():
        preset = json.loads(fp.read_text(encoding="utf-8"))
        M = json.loads(mp.read_text(encoding="utf-8"))
        if any(s["id"] == source_id for s in M["sources"]):
            raise ValueError(f"{source_id} 는 이미 이 프리셋의 출처입니다")
        preset, became = merge(preset, new, exclude, tuple(M.get("fixed") or {}))
    else:
        preset = new
        P = flat(preset)
        for p in P:
            if always_per_video(p):
                P[p] = VAR
        preset = unflat(P, layer_order(preset))
        became = [p for p in P if always_per_video(p)]
        M = {"slug": None, "style": None, "made_by": MADE_BY, "rule": RULE, "created_at": now, "sources": []}
    mf = frame.get("made_from") or {}
    slug, style = slug_style(preset_dir)
    M.update({"slug": slug, "style": style, "updated_at": now, "variables": variables(preset)})
    M["sources"].append({"id": source_id, "tteutgi": tteutgi_path, "engine": J.get("engine"), "measured_at": J.get("measured_at"),
                         "frame_tool": mf.get("tool"), "font": mf.get("font"), "font_confidence": mf.get("font_confidence"),
                         "notes": mf.get("notes") or [], "unknown": J.get("unknown") or [], "excluded_layers": list(exclude),
                         "became_variables": became, "caption_style": caption_style,
                         "title_ink_w": mf.get("title_ink_w"),
                         # 제목 글꼴 판별(분석기 fonts.title top3·top5)과 묶음 판별(fonts.title_pooled, 3판-b) — 하위 스타일 글꼴을 정할 때 쓴다
                         "title_fonts": {k: v for k, v in ((J.get("fonts") or {}).get("title") or {}).items() if k in ("top3", "top5")} or None,
                         "title_pooled": (J.get("fonts") or {}).get("title_pooled"),   # 프레임 실측(없으면 None → 규칙이 글꼴로 계산, 1_V 1102>1080 같은 오차)
                         "frame_sha1": hashlib.sha1(schema.canonical(new).encode("utf-8")).hexdigest()[:12]})
    (preset_dir / "sources").mkdir(exist_ok=True)
    (preset_dir / "sources" / f"{source_id}.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    if caption_style:
        cap = next((l for l in schema.all_layers(new) if l.get("role") == "caption"), None)
        caption_style_entry(M, caption_style, None if "text:caption" in exclude else cap, source_id, caption_note)
    M["variable_stats"] = variable_stats(preset_dir, M, preset)
    M["rules"] = rule_stats(preset_dir, M)
    fp.write_text(json.dumps(preset, ensure_ascii=False, indent=1), encoding="utf-8")
    mp.write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def fix_value(preset_dir: Path, path: str, value, why: str) -> dict:
    """실측 대조로 정한 값을 프리셋 고정값으로 못 박는다(변수였으면 변수에서 뺀다). manifest.fixed 에 근거와 함께 남긴다.
    다음 save(편 추가)가 같은 자리를 다시 변수로 만들 수 있으므로 merge 는 fixed 자리를 건드리지 않는다."""
    frame, M = load(preset_dir)
    P = flat(frame)
    if path not in P:
        raise ValueError(f"자리 없음: {path}")
    P[path] = value
    frame = unflat(P, layer_order(frame))
    M.setdefault("fixed", {})[path] = {"value": value, "why": why,
                                       "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    M["variables"] = variables(frame)
    M.get("variable_stats", {}).pop(path, None)
    (preset_dir / "frame.json").write_text(json.dumps(frame, ensure_ascii=False, indent=1), encoding="utf-8")
    (preset_dir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


META_KEYS = ("roles", "source_kind", "rules_path", "unfixed", "nearest_template", "source_choice")   # 프리셋 다시 만들 때 이어 붙일 manifest 칸


def set_meta(preset_dir: Path, roles: list | None = None, source_kind: str | None = None, rules_path: str | None = None) -> dict:
    """manifest 의 대본·소재 칸 — 판단 주인 한 곳(10-16 엔진 담당 요청). script_engine(--roles 없을 때)·topic_find(--source-kind 없을 때)가 읽는다.
      roles       = 채널 역할 칸 목록(대본 줄마다 맡는 일)
      source_kind = 소재 출처 유형 — topic_find.SOURCE_KINDS 의 키(그 목록이 주인, 여기서 다시 적지 않는다)
      rules_path  = 갈래 rules.json 경로(저장소 기준 상대) — manifest.rules(관계 규칙 공식 dict)와 다른 것"""
    frame, M = load(preset_dir)
    if roles is not None:
        if not isinstance(roles, list) or not roles or not all(isinstance(r, str) and r.strip() for r in roles):
            raise ValueError("roles: 빈 칸 없는 글 목록이어야 합니다")
        M["roles"] = roles
    if source_kind is not None:
        from tools.calcopy.engine.topic_find import SOURCE_KINDS
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"source_kind: {list(SOURCE_KINDS)} 중 하나여야 합니다(받은 값 {source_kind!r})")
        M["source_kind"] = source_kind
    if rules_path is not None:
        rp = rules_path.replace("\\", "/")
        if not (ROOT / rp).exists():
            raise ValueError(f"rules_path: 저장소에 없는 파일 {rp}")
        M["rules_path"] = rp
    (preset_dir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def unfix_value(preset_dir: Path, path: str, why: str) -> dict:
    """fix_value 를 푼다 — manifest.fixed 에서 빼고 manifest.unfixed 에 근거를 남긴다. 그 자리는 다음 save(또는 프리셋 다시 만들기)
    때 편별 값으로 다시 변수가 된다(10-16: 제목 글꼴을 Cafe24Ohsquare 로 못 박은 판정이 ho5 한 편만 보고 한 것이라 해제)."""
    frame, M = load(preset_dir)
    old = (M.get("fixed") or {}).pop(path, None)
    if old is None:
        raise ValueError(f"고정값 아님: {path}")
    M.setdefault("unfixed", {})[path] = {"was": old, "why": why,
                                         "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    (preset_dir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def load(preset_dir: Path) -> tuple[dict, dict]:
    frame = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    M = json.loads((preset_dir / "manifest.json").read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_MANIFEST if k not in M]
    if missing:
        raise ValueError(f"manifest 필수 항목 없음: {missing}")
    return frame, M


def apply(preset: dict, per_video: dict | None = None, overrides: dict | None = None,
          defaults: dict | None = None, caption_style: dict | None = None, rules: dict | None = None) -> dict:
    """프리셋의 변수 자리를 채운 설명서. 순서: overrides({자리: 값}) → per_video(그 편 설명서, to_frame 결과)
    → defaults(manifest variable_stats — 새 소재로 만들 때). 못 채운 변수가 하나라도 남으면 ValueError(목록).
    caption_style = manifest caption_styles 의 한 항목 — 자막 층을 그 하위 스타일의 잰 층으로 바꾼다(미측정이면 ValueError)."""
    P = flat(preset)
    V = flat(per_video) if per_video else {}
    left = []
    for path, v in P.items():
        if v != VAR:
            continue
        if overrides and path in overrides:
            P[path] = overrides[path]
        elif path in V and V[path] != VAR:
            P[path] = V[path]
        elif defaults and path in defaults and defaults[path].get("how") != NO_DEFAULT:
            P[path] = defaults[path]["default"]          # None(최빈이 '없음')도 값이다 — 예: template_off
        else:
            left.append(path)
    if caption_style is not None:
        if not caption_style.get("layer"):
            raise ValueError(f"자막 스타일 {caption_style.get('name')} 은 미측정 — 잰 층이 없다")
        for f, v in caption_style["layer"].items():
            if f != "kind":
                P[f"layers[text:caption].{f}"] = v
    if left:
        raise ValueError(f"채우지 못한 변수: {left}")
    out = unflat(P, layer_order(preset))
    if rules:
        out = apply_rules(out, rules)       # 종속값은 규칙이 정한다(독립 기본값을 채운 뒤)
    schema.validate(out)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "apply":
        ap = argparse.ArgumentParser()
        ap.add_argument("preset"); ap.add_argument("--from-frame"); ap.add_argument("--set", action="append", default=[])
        ap.add_argument("--defaults", action="store_true", help="그 편 값 대신 manifest 기본값(새 소재)")
        ap.add_argument("--caption-style", help="manifest caption_styles 의 이름")
        ap.add_argument("--out", required=True)
        a = ap.parse_args(argv[1:])
        preset, M = load(Path(a.preset))
        per = json.loads(Path(a.from_frame).read_text(encoding="utf-8")) if a.from_frame else None
        ov = {}
        for s in a.set:
            k, v = s.split("=", 1)
            ov[k] = json.loads(v)
        cs = next((x for x in M.get("caption_styles") or [] if x["name"] == a.caption_style), None) if a.caption_style else None
        if a.caption_style and cs is None:
            raise SystemExit(f"자막 스타일 없음: {a.caption_style}")
        F = apply(preset, per, ov, M.get("variable_stats") if a.defaults else None, cs, M.get("rules") if a.defaults else None)
        F["made_from"] = {"tool": "preset_save apply", "preset": str(a.preset), "variables_filled": M["variables"],
                          "from_frame": a.from_frame, "overrides": list(ov), "defaults": a.defaults, "caption_style": a.caption_style}
        Path(a.out).write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
        print("frame:", a.out, "변수", M["variables"])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("tteutgi"); ap.add_argument("frame"); ap.add_argument("--slug", required=True); ap.add_argument("--style", required=True)
    ap.add_argument("--exclude", action="append", default=[], help="이 편에선 비교하지 않을 층 이름(예 text:caption)")
    ap.add_argument("--caption-style", help="이 편 자막이 속한 하위 스타일 이름(예 창아래_검정)")
    ap.add_argument("--caption-note", help="그 분류의 근거(예 워커 점검.md)")
    a = ap.parse_args(argv)
    J = json.loads(Path(a.tteutgi).read_text(encoding="utf-8"))
    frame = json.loads(Path(a.frame).read_text(encoding="utf-8"))
    src = Path(str(J.get("source") or a.tteutgi)).stem
    M = save(J, frame, ROOT / "channel" / a.slug / "preset" / a.style, src, a.tteutgi.replace("\\", "/"), tuple(a.exclude),
             a.caption_style, a.caption_note)
    print(json.dumps({"variables": M["variables"], "sources": [s["id"] for s in M["sources"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
