# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 **판 등록 한 곳** — 판마다 설정 파일 하나 `tools/calcopy/hybrid/styles/<판>.json` (관제 097, 2026-10-19).

왜 여기(채널 폴더가 아니라): 판 설정을 읽는 쪽이 전부 이 폴더(run.py·렌더러·script_audit·briefs)라 판 목록 = 이 폴더 목록 한 곳이 된다.
잇썸홈판·재미썸홈판처럼 벤치 채널 폴더가 없는 판도 같은 자리에 같은 꼴로 둔다. 채널 폴더(channel/<slug>/)는 근거(스타일분석·줄판독·판설계)만 두고
판 설정이 그 경로를 가리킨다(bench.*). 같은 값을 두 곳에 적지 않는다 — 렌더러 DEF·대본 브리프의 판별 절은 여기서 읽는다.

꼴(필수 칸): name · renderer('itssum'|'jaemi'|'bench') · voice · bgm · loudness · length · script · (bench 판) frame·caption·cuts·timing·placement·sfx_files
_common.json 은 모든 판에 먼저 깔린다(대본 금지어 등) — 판 파일 값이 이긴다(사전은 깊게 합침, 목록은 판 것이 대신함).

    PYTHONUTF8=1 py tools/calcopy/hybrid/styles.py list
    PYTHONUTF8=1 py tools/calcopy/hybrid/styles.py brief <판>      # 대본 쓰기 지시문의 판별 절(briefs/script.md 가 부른다)

상속 판(base) 목록 칸(표준 §11-2 ⑰, 관제 263 지시서 11): `script.audit`·`script.brief` 는 1차 판이 유일 주인 — 상속 판은 통째로 적지 않고
`script.audit_patch{add:[규칙], remove:[id], replace:{id: 규칙}}` · `script.brief_patch{add:[줄], remove:[앞 12자], replace:{앞 12자: 줄}}` 만 적는다.
load 가 바탕 목록에 패치를 적용한다(통째 목록이 있으면 거절 — 조용한 두 벌 금지). audit 규칙 id 없으면 `kind:순번` 자동.
팩 칸(표준 §10-2): `packs` 가 정본 — load 가 pack_map.apply_to_style 로 옛 칸(caption.pack·sfx_files·bgm.id/candidates)을 채운다(다르면 오류).
회원 patch(load(name, patch=…)): 지금은 `packs` 만(합치기 주인 pack_map.merge) — 다른 칸은 지시서 12 apply_patch 몫이라 거절."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DIR = Path(__file__).with_name("styles")
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:          # CLI 로 직접 돌릴 때도 tools.calcopy… 가 잡히게(pack_map import)
    sys.path.insert(0, str(_ROOT))
REQUIRED = ("name", "renderer", "voice", "bgm", "loudness", "length", "script", "thumb_card_face")   # thumb_card_face: 연예인 채널이면 true — 판마다 명시(사장님 10-25 "연예인 얼굴 통일·앞으로 칼카피 모두", 관문 ⑥)


# ── 판 리듬 실측 4칸(관제263 10-25 페이블 눈검수 E1·E2·E4 — 모든 판 필수, 값은 그 채널 벤치 실측 + why) ──────────────
#   판 파일 rhythm{cut_median{v,why} · hook_cuts_3s{min,why} · plain_share{v,tol,why} · photo_share_max{v,why}}.
#   읽는 곳은 rhythm() 하나 — 렌더 전 관문(render_bench.rhythm_gate·photo_gate)·배치(placement.plain_step)·관문(quality_gate rhythm 행)·카드(preset_card L1)·재현(kal_analyze.style_targets).
RHYTHM_KEYS = {"cut_median": "v", "hook_cuts_3s": "min", "plain_share": "v", "photo_share_max": "v"}


def rhythm(st: dict) -> dict:
    """(판단 주인 — 판 리듬 칸 읽기) {키: 칸 dict} — 값 칸·why 가 다 있는 것만. 빠진 키는 rhythm_missing 이 말한다(조용한 기본값 없음)."""
    R = st.get("rhythm") or {}
    return {k: R[k] for k, f in RHYTHM_KEYS.items() if isinstance(R.get(k), dict) and isinstance(R[k].get(f), (int, float)) and R[k].get("why")}


def rhythm_missing(st: dict) -> list[str]:
    have = rhythm(st)
    return [k for k in RHYTHM_KEYS if k not in have]


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


class StyleError(ValueError):
    """판 설정 오류 — 상속 판 통째 목록·패치 대상 없음 등(조용히 넘기지 않는다)."""


def audit_ids(audit: list) -> list:
    """audit 규칙마다 id(없으면 `kind:순번`) — 패치가 규칙 단위로 가리키는 이름."""
    out = []
    for i, a in enumerate(audit or []):
        a = dict(a)
        a.setdefault("id", f"{a.get('kind')}:{i}")
        out.append(a)
    return out


def apply_list_patch(base: list, patch: dict, kind: str, where: str) -> list:
    """목록 패치 하나(audit = id 단위 · brief = 앞 12자 단위). 가리킨 대상이 없거나 id 가 겹치면 StyleError."""
    if kind == "audit":
        cur = audit_ids(base)
        key = lambda x: x["id"]          # noqa: E731
        norm = lambda x: x               # noqa: E731
    else:
        cur = list(base or [])
        key = lambda x: str(x)[:12]      # noqa: E731
        norm = lambda x: str(x)[:12]     # noqa: E731
    bad = set(patch) - {"add", "remove", "replace"}
    if bad:
        raise StyleError(f"{where}: {kind}_patch 에 모르는 칸 {sorted(bad)} — add·remove·replace")
    have = [key(x) for x in cur]
    for r in patch.get("remove") or []:
        if norm(r) not in have:
            raise StyleError(f"{where}: {kind}_patch.remove '{r}' — 바탕 목록에 없음(있는 것 {have})")
    cur = [x for x in cur if key(x) not in {norm(r) for r in patch.get("remove") or []}]
    for k, v in (patch.get("replace") or {}).items():
        idx = [i for i, x in enumerate(cur) if key(x) == norm(k)]
        if not idx:
            raise StyleError(f"{where}: {kind}_patch.replace '{k}' — 바탕 목록에 없음")
        if kind == "audit":
            v = dict(v)
            if v.setdefault("id", k) != k:
                raise StyleError(f"{where}: audit_patch.replace '{k}' 의 규칙 id '{v['id']}' 가 다르다")
        cur[idx[0]] = v
    for v in patch.get("add") or []:
        if kind == "audit":
            v = audit_ids([v])[0] if "id" in v else {**v, "id": f"{v.get('kind')}:{len(cur)}"}
        if key(v) in [key(x) for x in cur]:
            raise StyleError(f"{where}: {kind}_patch.add '{key(v)}' — 이미 있는 {'id' if kind == 'audit' else '줄'}")
        cur.append(v)
    return cur


def _raw(name: str, seen: tuple = ()) -> dict:
    """판 파일 한 장 — `base`(바탕 판 이름)가 있으면 바탕 판을 먼저 깔고 이 파일이 덮는다(변형판: 뼈대는 바탕 판 그대로, 겉모양만 덮기, 10-20).
    목록 칸 script.audit·brief 는 상속 판이 통째로 못 적는다 — *_patch 로만(⑰)."""
    if name in seen:
        raise SystemExit(f"판 설정 base 가 돌고 돈다: {' → '.join(seen + (name,))}")
    raw = json.loads(path_of(name).read_text(encoding="utf-8"))
    if not raw.get("base"):
        return raw
    S = raw.get("script") or {}
    whole = [k for k in ("audit", "brief") if k in S]
    if whole:
        raise StyleError(f"상속 판 {name}(base {raw['base']}) 이 script.{whole} 를 통째로 적었다 — 1차 판 목록의 두 벌. "
                         f"script.audit_patch / brief_patch{{add,remove,replace}} 로 바꿔 적어라(표준 §11-2 ⑰)")
    base = _raw(raw["base"], seen + (name,))
    st = _merge(base, raw)
    SS = st.get("script") or {}
    for kind in ("audit", "brief"):
        pt = SS.pop(f"{kind}_patch", None)
        if pt is not None:
            SS[kind] = apply_list_patch((base.get("script") or {}).get(kind) or [], pt, kind, f"판 {name}")
            SS.setdefault("_patched", []).append(f"{kind} ← {name}.{kind}_patch")
    return st


def load(name: str, patch: dict | None = None, _skip_packs: bool = False) -> dict:
    """판 설정(_common ← base ← 판 파일 ← 목록 패치) + 팩 칸 변환(pack_map.apply_to_style). patch = 회원 맞춤(지금은 packs 만 — 12)."""
    raw = _raw(name)
    common = json.loads((DIR / "_common.json").read_text(encoding="utf-8")) if (DIR / "_common.json").exists() else {}
    st = _merge(common, raw)
    miss = [k for k in REQUIRED if k not in st]
    if miss:
        raise SystemExit(f"판 설정 {name} 에 칸이 없다: {miss}")
    if patch:
        bad = sorted(set(patch) - {"packs"})
        if bad:
            raise StyleError(f"회원 patch 칸 {bad} — 지금은 packs 만 받는다(나머지는 지시서 12 styles.apply_patch 몫, 조용히 무시하지 않음)")
    if not _skip_packs:
        from tools.calcopy.hybrid import pack_map
        pack_map.apply_to_style(st, (patch or {}).get("packs"), name)
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
            P = st.get("packs") or {}
            pk = f"cap={P['caption'].get('pack')} motion={P['motion'].get('pack')} sfx={P['sfx'].get('pack')} bgm={P['bgm'].get('id')} meme={P['meme'].get('pack')}"
            gap = sum(len((P.get(k) or {}).get("gap") or []) for k in P if not k.startswith("_"))
            print(f"{n:8s} renderer={st['renderer']:6s} voice={st['voice'].get('name')} length={st['length']['min']}~{st['length']['max']} | packs {pk} gap={gap}")
        return
    if sys.argv[1] == "brief":
        print(brief(sys.argv[2]))


if __name__ == "__main__":
    main()
