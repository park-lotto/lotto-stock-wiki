# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 **판 등록 한 곳** — 판마다 설정 파일 하나 `tools/calcopy/hybrid/styles/<판>.json` (관제 097, 2026-10-19).

왜 여기(채널 폴더가 아니라): 판 설정을 읽는 쪽이 전부 이 폴더(run.py·렌더러·script_audit·briefs)라 판 목록 = 이 폴더 목록 한 곳이 된다.
잇썸홈판·재미썸홈판처럼 벤치 채널 폴더가 없는 판도 같은 자리에 같은 꼴로 둔다. 채널 폴더(channel/<slug>/)는 근거(스타일분석·줄판독·판설계)만 두고
판 설정이 그 경로를 가리킨다(bench.*). 같은 값을 두 곳에 적지 않는다 — 렌더러 DEF·대본 브리프의 판별 절은 여기서 읽는다.

꼴(필수 칸): name · renderer('itssum'|'jaemi'|'bench') · voice · bgm · loudness · length · script · (bench 판) frame·caption·cuts·timing·placement·sfx_files
_common.json 은 모든 판에 먼저 깔린다(대본 금지어 등) — 판 파일 값이 이긴다(사전은 깊게 합침, 목록은 판 것이 대신함).

    PYTHONUTF8=1 py tools/calcopy/hybrid/styles.py list
    PYTHONUTF8=1 py tools/calcopy/hybrid/styles.py brief <판>      # 대본 쓰기 지시문의 판별 절(briefs/script.md 가 부른다)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DIR = Path(__file__).with_name("styles")
REQUIRED = ("name", "renderer", "voice", "bgm", "loudness", "length", "script")


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def names() -> list[str]:
    return sorted(p.stem for p in DIR.glob("*.json") if not p.stem.startswith("_"))


def path_of(name: str) -> Path:
    p = DIR / f"{name}.json"
    if not p.exists():
        raise SystemExit(f"판 '{name}' 이 없다 — 있는 판: {', '.join(names())}")
    return p


def _raw(name: str, seen: tuple = ()) -> dict:
    """판 파일 한 장 — `base`(바탕 판 이름)가 있으면 바탕 판을 먼저 깔고 이 파일이 덮는다(변형판: 뼈대는 바탕 판 그대로, 겉모양만 덮기, 10-20)."""
    if name in seen:
        raise SystemExit(f"판 설정 base 가 돌고 돈다: {' → '.join(seen + (name,))}")
    raw = json.loads(path_of(name).read_text(encoding="utf-8"))
    if raw.get("base"):
        return _merge(_raw(raw["base"], seen + (name,)), raw)
    return raw


def load(name: str) -> dict:
    raw = _raw(name)
    common = json.loads((DIR / "_common.json").read_text(encoding="utf-8")) if (DIR / "_common.json").exists() else {}
    st = _merge(common, raw)
    miss = [k for k in REQUIRED if k not in st]
    if miss:
        raise SystemExit(f"판 설정 {name} 에 칸이 없다: {miss}")
    return st


def save_counted(name: str, counted: dict):
    """placement.count 결과만 그 판 파일에 다시 쓴다(손으로 적은 rules 는 그대로)."""
    p = path_of(name)
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw.setdefault("placement", {})["counted"] = counted
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def brief(name: str) -> str:
    st = load(name)
    S = st["script"]
    out = [f"## {name} — 대본 쓰는 법 (판 설정 tools/calcopy/hybrid/styles/{name}.json script 칸)"]
    out += [f"- {x}" for x in S.get("brief") or []]
    if S.get("example"):
        out.append(f"- 예시: `{S['example']}`")
    out.append(f"- 목소리: {st['voice'].get('name')} `{st['voice'].get('voice_id')}` · 길이 {st['length']['min']}~{st['length']['max']}초 · 음량 {st['loudness']['lufs']} LUFS")
    out.append(f"- 검사: `PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py <대본.json> --version {name}` (규칙 = script.audit {len(S.get('audit') or [])}개)")
    return "\n".join(out)


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "list":
        for n in names():
            st = load(n)
            print(f"{n:8s} renderer={st['renderer']:6s} voice={st['voice'].get('name')} length={st['length']['min']}~{st['length']['max']}")
        return
    if sys.argv[1] == "brief":
        print(brief(sys.argv[2]))


if __name__ == "__main__":
    main()
