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


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    m = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    return int(round(m)) if all(isinstance(x, int) for x in xs) else round(m, 1)


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
        if path in ALWAYS_PER_VIDEO:
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
                         "became_variables": became, "caption_style": caption_style,
                         "frame_sha1": hashlib.sha1(schema.canonical(new).encode("utf-8")).hexdigest()[:12]})
    (preset_dir / "sources").mkdir(exist_ok=True)
    (preset_dir / "sources" / f"{source_id}.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    if caption_style:
        cap = next((l for l in new["layers"] if l.get("role") == "caption"), None)
        caption_style_entry(M, caption_style, None if "text:caption" in exclude else cap, source_id, caption_note)
    M["variable_stats"] = variable_stats(preset_dir, M, preset)
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


def apply(preset: dict, per_video: dict | None = None, overrides: dict | None = None,
          defaults: dict | None = None, caption_style: dict | None = None) -> dict:
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
        F = apply(preset, per, ov, M.get("variable_stats") if a.defaults else None, cs)
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
