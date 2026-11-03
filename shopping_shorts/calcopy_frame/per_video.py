# -*- coding: utf-8 -*-
"""틀 설명서의 '편마다 값'($per_video) 자리 다루기 — 고객 묶음에 들어가는 쪽(관제 234). 판단 주인은 이 파일 하나.
프리셋 만들기(tools/calcopy/engine/preset_save.py, 고객 묶음 밖)도 자리 이름(flat/unflat)을 여기서 가져다 쓴다(두 벌 금지).
자리 이름: 맨 위 키 · 'layers[<kind>(:<role>)].<필드>' · 틀 여러 장이면 'frames[<id>].layers[<층>].<필드>'.
"""
from __future__ import annotations

import re

VAR = "$per_video"
NO_DEFAULT = "내용 — 기본값 없음(새 소재는 --set)"


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


def fill_defaults(frame: dict, defaults: dict | None) -> tuple[dict, list[str]]:
    """새 소재로 만들 때 — 변수 자리 중 **잰 기본값이 있는 것만**(제목 크기·위치·색 …) manifest variable_stats 값으로 채운다.
    글 내용 자리(.text, 제목 글자)는 대본이 정하니 그대로 $per_video 로 남긴다(apply 와 달리 멈추지 않는다).
    10-20 라이브 시험(관제 234): 고객 제작 길(calcopy_make.merge_preset_pack)이 이걸 안 해 'layers[2].y = $per_video' 로 틀 검사에서 멈췄다."""
    P = flat(frame)
    filled = []
    for path, v in P.items():
        if v == VAR and not path.endswith(".text") and defaults and path in defaults and defaults[path].get("how") != NO_DEFAULT:
            P[path] = defaults[path]["default"]
            filled.append(path)
    out = unflat(P, layer_order(frame))
    if "made_from" in frame:
        out["made_from"] = frame["made_from"]
    return out, filled
