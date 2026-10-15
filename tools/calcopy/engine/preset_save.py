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


def flat(frame: dict) -> dict:
    """설명서 → {자리: 값}. 층은 kind(:role) 로 이름 붙인다(같은 이름 층이 둘이면 #2…)."""
    out = {k: v for k, v in frame.items() if k not in ("layers", "made_from")}   # canvas·template_off·made_by·source …
    seen = {}
    for layer in frame.get("layers") or []:
        k = _key(layer)
        seen[k] = seen.get(k, 0) + 1
        name = k if seen[k] == 1 else f"{k}#{seen[k]}"
        for f, v in layer.items():
            if f != "kind":
                out[f"layers[{name}].{f}"] = v
    return out


def unflat(flat_map: dict, order: list[str]) -> dict:
    """flat 의 거꾸로 — order = 층 이름 순서(프리셋 frame 의 층 순서 유지)."""
    layers = {n: {"kind": n.split(":")[0].split("#")[0], **({"role": n.split(":")[1].split("#")[0]} if ":" in n else {})} for n in order}
    out = {k: v for k, v in flat_map.items() if not k.startswith("layers[")}
    for path, v in flat_map.items():
        if path.startswith("layers["):
            name, field = path[len("layers["):].split("].", 1)
            layers[name][field] = v
    out["layers"] = [layers[n] for n in order]
    return out


def layer_order(frame: dict) -> list[str]:
    names, seen = [], {}
    for layer in frame.get("layers") or []:
        k = _key(layer)
        seen[k] = seen.get(k, 0) + 1
        names.append(k if seen[k] == 1 else f"{k}#{seen[k]}")
    return names


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


def merge(preset: dict, new: dict, exclude: tuple = ()) -> tuple[dict, list[str]]:
    """프리셋 설명서 + 같은 틀의 새 편 설명서 → (합친 프리셋, 이번에 변수가 된 자리)."""
    P, N = flat(preset), flat(new)
    became = []
    for path, v in P.items():
        if v == VAR:
            continue
        if path in NOT_COMPARED or any(path.startswith(f"layers[{e}") for e in exclude) or path not in N:
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


def save(J: dict, frame: dict, preset_dir: Path, source_id: str, tteutgi_path: str, exclude: tuple = ()) -> dict:
    """프리셋 폴더에 frame.json·manifest.json 을 쓰거나(처음) 합친다(같은 틀 다른 편). 돌려주는 값 = manifest."""
    preset_dir.mkdir(parents=True, exist_ok=True)
    fp, mp = preset_dir / "frame.json", preset_dir / "manifest.json"
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    new = _strip(frame)
    schema.validate(new)                                    # 저장하는 편 설명서는 형식이 맞아야 한다
    if fp.exists():
        preset = json.loads(fp.read_text(encoding="utf-8"))
        M = json.loads(mp.read_text(encoding="utf-8"))
        if any(s["id"] == source_id for s in M["sources"]):
            raise ValueError(f"{source_id} 는 이미 이 프리셋의 출처입니다")
        preset, became = merge(preset, new, exclude)
    else:
        preset = new
        P = flat(preset)
        for p in ALWAYS_PER_VIDEO:
            if p in P:
                P[p] = VAR
        preset = unflat(P, layer_order(preset))
        became = [p for p in ALWAYS_PER_VIDEO if p in P]
        M = {"slug": None, "style": preset_dir.name, "made_by": MADE_BY, "rule": RULE, "created_at": now, "sources": []}
    mf = frame.get("made_from") or {}
    M.update({"slug": preset_dir.parent.parent.name, "updated_at": now, "variables": variables(preset)})
    M["sources"].append({"id": source_id, "tteutgi": tteutgi_path, "engine": J.get("engine"), "measured_at": J.get("measured_at"),
                         "frame_tool": mf.get("tool"), "font": mf.get("font"), "font_confidence": mf.get("font_confidence"),
                         "notes": mf.get("notes") or [], "unknown": J.get("unknown") or [], "excluded_layers": list(exclude),
                         "became_variables": became,
                         "frame_sha1": hashlib.sha1(schema.canonical(schema.validate(new)).encode("utf-8")).hexdigest()[:12]})
    fp.write_text(json.dumps(preset, ensure_ascii=False, indent=1), encoding="utf-8")
    mp.write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def load(preset_dir: Path) -> tuple[dict, dict]:
    frame = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    M = json.loads((preset_dir / "manifest.json").read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_MANIFEST if k not in M]
    if missing:
        raise ValueError(f"manifest 필수 항목 없음: {missing}")
    return frame, M


def apply(preset: dict, per_video: dict | None = None, overrides: dict | None = None) -> dict:
    """프리셋의 변수 자리를 그 편 값으로 채운 설명서. per_video = 그 편 설명서(to_frame 결과), overrides = {자리: 값}(먼저 씀).
    못 채운 변수가 하나라도 남으면 ValueError(목록)."""
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
        else:
            left.append(path)
    if left:
        raise ValueError(f"채우지 못한 변수: {left}")
    out = unflat(P, layer_order(preset))
    schema.validate(out)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "apply":
        ap = argparse.ArgumentParser()
        ap.add_argument("preset"); ap.add_argument("--from-frame"); ap.add_argument("--set", action="append", default=[])
        ap.add_argument("--out", required=True)
        a = ap.parse_args(argv[1:])
        preset, M = load(Path(a.preset))
        per = json.loads(Path(a.from_frame).read_text(encoding="utf-8")) if a.from_frame else None
        ov = {}
        for s in a.set:
            k, v = s.split("=", 1)
            ov[k] = json.loads(v)
        F = apply(preset, per, ov)
        F["made_from"] = {"tool": "preset_save apply", "preset": str(a.preset), "variables_filled": M["variables"],
                          "from_frame": a.from_frame, "overrides": list(ov)}
        Path(a.out).write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
        print("frame:", a.out, "변수", M["variables"])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("tteutgi"); ap.add_argument("frame"); ap.add_argument("--slug", required=True); ap.add_argument("--style", required=True)
    ap.add_argument("--exclude", action="append", default=[], help="이 편에선 비교하지 않을 층 이름(예 text:caption)")
    a = ap.parse_args(argv)
    J = json.loads(Path(a.tteutgi).read_text(encoding="utf-8"))
    frame = json.loads(Path(a.frame).read_text(encoding="utf-8"))
    src = Path(str(J.get("source") or a.tteutgi)).stem
    M = save(J, frame, ROOT / "channel" / a.slug / "preset" / a.style, src, a.tteutgi.replace("\\", "/"), tuple(a.exclude))
    print(json.dumps({"variables": M["variables"], "sources": [s["id"] for s in M["sources"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
