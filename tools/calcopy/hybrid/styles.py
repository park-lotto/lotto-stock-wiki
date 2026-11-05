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
import os
import sys
from pathlib import Path

DIR = Path(__file__).with_name("styles")
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:          # CLI 로 직접 돌릴 때도 tools.calcopy… 가 잡히게(pack_map import)
    sys.path.insert(0, str(_ROOT))
REQUIRED = ("name", "renderer", "voice", "bgm", "loudness", "length", "script", "thumb_card_face")   # thumb_card_face: 연예인 채널이면 true — 판마다 명시(사장님 10-25 "연예인 얼굴 통일·앞으로 프리셋 모두", 관문 ⑥)


# ── 판 리듬 실측 4칸(관제263 10-25 페이블 눈검수 E1·E2·E4 — 모든 판 필수, 값은 그 채널 벤치 실측 + why) ──────────────
#   판 파일 rhythm{cut_median{v,why} · hook_cuts_3s{min,why} · plain_share{v,tol,why} · photo_share_max{v,why}}.
#   읽는 곳은 rhythm() 하나 — 렌더 전 관문(render_bench.rhythm_gate·photo_gate)·배치(placement.plain_step)·관문(quality_gate rhythm 행)·카드(preset_card L1)·재현(kal_analyze.style_targets).
RHYTHM_KEYS = {"cut_median": "v", "hook_cuts_3s": "min", "plain_share": "v", "photo_share_max": "v"}


SCREEN = (1080, 1920)


def frame_window(F: dict) -> list[int]:
    """영상 창 [x,y,w,h] 주인 한 곳 — kind 'full'(전체화면 판, 두유노판 등) = 화면 전체(창 칸이 없다), 그 밖 = frame.window.
    10-27 실사고: flow·runner_ops 다섯 곳이 frame['window'] 를 직접 읽어 전체화면 판에서 KeyError(대본 받은 직후 흐름이 죽음).
    렌더러(render_bench.frame_window)·흐름·실행기 모두 이 함수를 부른다."""
    return [0, 0, *SCREEN] if (F.get("kind") or "window") == "full" else list(F["window"])


def window_of(version: str) -> list[int]:
    return frame_window(load(version)["frame"])


def rhythm(st: dict) -> dict:
    """(판단 주인 — 판 리듬 칸 읽기) {키: 칸 dict} — 값 칸·why 가 다 있는 것만. 빠진 키는 rhythm_missing 이 말한다(조용한 기본값 없음)."""
    R = st.get("rhythm") or {}
    return {k: R[k] for k, f in RHYTHM_KEYS.items() if isinstance(R.get(k), dict) and isinstance(R[k].get(f), (int, float)) and R[k].get("why")}


CUT_MEDIAN_TOL = 0.3     # 판 컷 길이 중앙 허용 ±30%(재현 cut.median 과 같은 폭)


def rhythm_bounds(st: dict) -> dict:
    """(판단 주인 — 판 리듬 합격 범위, E 10-26 사장님 '벤치가 못 넘는 문턱은 너무 빡빡 → 벤치 실측 범위로') 렌더 전 rhythm_gate·품질 관문 판 리듬 행이 같이 읽는다.
    cut_median = (v×0.7, max(v×1.3, 칸 max)) — max = 벤치 가장 느린 편(why 의 편별 값). 빠른 쪽은 넓히지 않는다(사장님 10-26 '휙휙 지나가 집중 안 됨').
    hook_min = hook_cuts_3s.min(벤치 가장 적은 편 이하로 적는다) · plain = (min(v−tol, range[0]), max(v+tol, range[1])) — range = 벤치 편별 최소~최대.
    칸이 없으면 그 키는 빠진다(rhythm_missing 이 말한다)."""
    R = rhythm(st)
    out = {}
    if "cut_median" in R:
        v = float(R["cut_median"]["v"])
        out["cut_median"] = (round(v * (1 - CUT_MEDIAN_TOL), 3), round(max(v * (1 + CUT_MEDIAN_TOL), float(R["cut_median"].get("max") or 0)), 3))
    if "hook_cuts_3s" in R:
        out["hook_min"] = int(R["hook_cuts_3s"]["min"])
    if "plain_share" in R:
        v, tol = float(R["plain_share"]["v"]), float(R["plain_share"].get("tol", 0.1))
        rg = R["plain_share"].get("range") or [v - tol, v + tol]
        out["plain"] = (round(min(v - tol, float(rg[0])), 3), round(max(v + tol, float(rg[1])), 3))
    return out


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
    if not p.exists():      # 영문 파일로 옮기는 첫 단계 — 이 판부터 두 이름을 다 읽는다(회원 업데이트 뒤 파일을 옮긴다, 관제 304)
        af = DIR / "_names.json"
        alias = json.loads(af.read_text(encoding="utf-8")).get(name) if af.exists() else None
        p = DIR / f"{alias}.json" if alias else p
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
    return member_frame(st)


def member_font_file(name: str) -> str:
    """화면 글꼴 이름 → 글꼴 파일(fonts 폴더 기준). 주인 = preview_request.font_files. 없으면 멈춘다(조용히 판 글꼴로 돌아가지 않는다)."""
    from tools.calcopy.preview_request import font_files
    hit = font_files().get(name)
    if not hit:
        raise StyleError(f"회원 제목 글꼴 '{name}' 파일이 없다")
    return hit


def member_tempo(st: dict) -> float | None:
    """(판단 주인 — 회원이 말 빠르기를 정했나) 회원이 바꾼 칸(member_voice.tempo)만 본다 — 프리셋 기본값은 회원 팩 member 에 없다(local_settings.packFile).
    정했으면 렌더가 판 cps_target 에 맞추지 않고 그 빠르기로 내고, 길이가 판 범위 밖이어도 경고만 한다(#1893 김만기 1.05 → 판 8.6자/초 맞춤 1.2288 이 덮음 ·
    사장님 11-02 '회원 요청이 판·검사를 이긴다')."""
    t = (st.get("member_voice") or {}).get("tempo")
    return float(t) if t else None


def name_look(items: list, scale, color) -> None:
    """(판단 주인 — 채널명 크기·색, #1631 김유선·#1950 이성택) 채널명을 그리는 세 자리(로고·워터마크·머리띠 글자)에 같은 배율·색.
    안 정했으면 그대로(프리셋 그림). 색은 칸 꼴에 맞춰 — 로고는 rgba(투명도 그대로), 워터마크·머리띠 글자는 color."""
    for it in items:
        if not it:
            continue
        if scale and it.get("px"):
            it["px"] = round(float(it["px"]) * float(scale))
            if it.get("max_w"):
                it["max_w"] = round(float(it["max_w"]) * float(scale))
        if color:
            if "rgba" in it:
                it["rgba"] = [int(color[i:i + 2], 16) for i in (1, 3, 5)] + [list(it["rgba"])[3]]
            else:
                it["color"] = color


MEMBER_EMPH_BENCH = {"color": ("mark", ""), "grow": ("mark", "pop"), "underline": ("underline", "")}   # 회원 강조 → bench 스냅샷 wordFx(style, grow)


def _member_caption_fx(st: dict, text: dict, cap: dict) -> None:
    """(판단 주인 — 회원 자막 등장·강조·외곽선·자막팩 → bench 렌더 칸, 11-05 문인석·박은숙) member_frame 이 부른다.
    등장·외곽선 = cap(→ render_bench.snapshot captionOverride → precision20-ui.js 가 팩 base·variants·speakers 에 입힘).
    강조 = st['member_wordfx'](스냅샷 wordFx — bench 는 핵심 단어 고정 색칠 mark 를 그대로 두고 색·키우기만, 밑줄은 underline).
    자막팩 = st.packs.caption.pack·옛 칸 caption.pack(새 팩에 없는 변형은 뺀다). 이 판에서 영상에 안 닿는 회원 칸은 st['member_unused'] 로 알린다."""
    from shopping_shorts import scene_style
    c = text.get("caption") or {}
    unused = []
    bench = st.get("renderer") == "bench"
    if "enter" in c and c["enter"] is not None:
        spec = scene_style.clean_caption_enter({"kind": "none"} if c["enter"] == "none" else c["enter"])
        if spec:
            cap["enter"] = spec
    if "outline_px" in c or "outline_rgb" in c:
        o = {}
        if isinstance(c.get("outline_px"), (int, float)):
            o["px"] = c["outline_px"]
        if isinstance(c.get("outline_rgb"), list):
            o["rgb"] = "#%02X%02X%02X" % tuple(c["outline_rgb"])
        if o:
            cap["outline"] = o
    m = c.get("emphasis")
    if m == "none":
        st["member_wordfx"] = {"style": "", "color": "", "grow": ""}
    elif isinstance(m, dict) and m.get("style") in MEMBER_EMPH_BENCH:
        style, grow = MEMBER_EMPH_BENCH[m["style"]]
        st["member_wordfx"] = {"style": style, "color": "#%02X%02X%02X" % tuple(m["rgb"]), "grow": grow}
    if c.get("mode") and bench:
        unused.append(f"text.caption.mode(자막 쌓기 {c['mode']}) — 이 프리셋은 판 caption.stack 으로 쌓아 영상에 안 닿는 칸")
    name = text.get("caption_pack")
    if name:
        from tools.calcopy.hybrid import pack_map
        packs = pack_map.caption_packs()
        if name not in packs:
            raise StyleError(f"회원 자막팩 '{name}' 이 자막팩 목록에 없다")
        if not bench:
            unused.append(f"text.caption_pack({name}) — 이 프리셋은 전용 렌더러라 자막팩을 쓰지 않는다")
        else:
            P = st.get("packs") or {}
            if P.get("caption") is not None:
                PC = P["caption"]
                PC["pack"] = name
                have = set((packs[name].get("variants") or {}))
                if PC.get("variants"):
                    PC["variants"] = {a: v for a, v in PC["variants"].items() if v in have}
                errs = pack_map.check(P)
                if errs:
                    raise StyleError("회원 자막팩 반영 뒤 팩 검사 실패: " + " / ".join(errs))
            if isinstance(st.get("caption"), dict):
                st["caption"]["pack"] = name
    if (cap.get("enter") or cap.get("outline") or st.get("member_wordfx")) and not bench:
        unused.append("text.caption 등장·강조·외곽선 — 이 프리셋은 전용 렌더러라 자막팩 스냅샷을 쓰지 않는다")
    if unused:
        st["member_unused"] = unused


def member_frame(st: dict) -> dict:
    """회원 '꾸미기' 값 → 판 틀(주인 한 곳 — 렌더·썸네일·캡컷·관문이 모두 load 로 받는다). SHORTEM_MEMBER_PACK = local_settings.packFile. 없으면 그대로."""
    f = os.environ.get("SHORTEM_MEMBER_PACK")
    if not f:
        return st
    pack = json.loads(open(f, encoding="utf-8").read()).get("member") or {}
    brand, text = pack.get("brand") or {}, pack.get("text") or {}
    tts = {k: v for k, v in (pack.get("tts") or {}).items() if k in ("voice_id", "name", "provider", "tempo", "emotion") and v is not None}
    if tts:          # 소리 단계에서 고른 목소리 — 렌더·계획이 member_voice 로 대본 칸까지 덮는다
        st["voice"] = {**st.get("voice", {}), **tts}
        st["member_voice"] = tts
    bgm = pack.get("bgm") or {}
    if bgm.get("gain") == 0:          # 소리 단계 '배경음악 없음'(음악 크기 0) — 0 은 거짓값이라 or 로 읽지 않는다
        st["member_bgm"] = {"none": True}
    elif (bgm.get("candidates") or [None])[0]:      # 소리 단계에서 고른 곡(11-03: 회원 팩 bgm 이 판에 안 들어가 프리셋 곡만 나왔다)
        st["member_bgm"] = {"id": bgm["candidates"][0]}
    cap = {k: text[f"caption_{k}"] for k in ("font", "color", "dy", "scale") if text.get(f"caption_{k}")}
    _member_caption_fx(st, text, cap)
    if cap:        # 자막 글꼴(꾸미기)·색·세로 위치(Claude 고치기)·크기(#1949 이성택 — 팩 size·강조 size 배율) — 자막팩 위에 덮는다(render_bench.snapshot)
        st["member_caption"] = cap
    F = st.get("frame")
    if not F:      # 전용 렌더러 판(잇썸홈·재미썸홈) — 틀 칸이 없다
        return st
    _member_layout(F, st, text)
    name = brand.get("channel_name")
    wm = brand.get("watermark") if isinstance(brand.get("watermark"), dict) else {}     # 회원 워터마크 자리(없으면 {}) — 본 틀·구간 틀이 같이 쓴다
    bar = (F.get("post") or {}).get("head_bar") or {}
    bar_text = [ic for ic in bar.get("icons") or [] if ic.get("kind") == "text"]
    if bar_text:       # 머리띠 글자 = 회원 채널명 한 칸(고정 글자 포함), 안 넣었으면 비운다 — 프리셋 원래 채널 글자를 내보내지 않는다(사장님 11-02)
        rest = [ic for ic in bar["icons"] if ic.get("kind") != "text"]
        if name:
            cx = sum(float(ic.get("cx") or 0) for ic in bar_text) / len(bar_text)
            rest.append({**bar_text[0], "text": name, "from": "_fixed", "cx": cx, "max_w": max(float(ic.get("max_w") or 0) for ic in bar_text) * len(bar_text)})
        bar["icons"] = rest
    if not name:       # 채널명을 안 넣은 회원 = 로고·워터마크 글자 없음
        F["logo"], F["watermark"] = None, None
    if name:
        if F.get("logo"):
            F["logo"]["text"] = name
        if F.get("watermark"):
            head = F["watermark"]["text"].split(" ", 1)
            F["watermark"]["text"] = f"{head[0]} {name}" if len(head) == 2 and not head[0].isalnum() else name
        if not F.get("logo") and not F.get("watermark") and not bar_text:      # 채널명 자리가 없는 틀 = 상단 가운데(오른쪽 위는 광고 표시 자리, 사장님 11-02) — 머리띠 글자 칸이 있으면 그게 채널명 자리(11-03 김준용 썰템쇼 두 번 찍힘)
            F["watermark"] = {"font": "Pretendard-Regular.otf", "px": 40, "alpha": 170, "cx": 540, "cy": 110, "text": name}
        wm = brand.get("watermark") if isinstance(brand.get("watermark"), dict) else {}
        if wm:     # 회원이 정한 워터마크 자리·크기·투명도(#3951 김효준, 범위 = preview_request.watermark_errors) — 틀 워터마크를 덮거나 새로 만든다
            base = dict(F.get("watermark") or {"font": "Pretendard-Regular.otf", "px": 40, "alpha": 170, "cx": 540, "cy": 110, "text": name})
            if "cx" in wm:
                base.pop("x1", None)      # 오른쪽 맞춤 틀(x1)보다 회원 가운데 자리가 이긴다(render_bench: cx 가 있으면 cx)
            base.update({k: int(wm[k]) for k in ("cx", "cy", "alpha") if k in wm})
            F["watermark"] = base
        name_look([F.get("logo"), F.get("watermark")] + [ic for ic in bar.get("icons") or [] if ic.get("kind") == "text"],
                  brand.get("name_scale"), brand.get("name_color"))
        if wm.get("px"):
            F["watermark"]["px"] = int(wm["px"])     # 회원이 정한 크기는 그대로(채널명 배율 name_scale 을 또 곱하지 않는다)
    bg = (brand.get("colors") or {}).get("bg")
    if bg:
        F["bg"] = list(bg)
    PA = (F.get("post") or {}).get("author_line")
    if PA and isinstance(text.get("post_author"), str):     # 게시글형 작성자 줄 — '' = 그리지 않음, 글 = 그 글로 고정(대본 post.author 보다 먼저, 11-03 강태경 '익명' 빼기)
        if text["post_author"].strip():
            F["post"]["author_line"] = {**PA, "text": text["post_author"].strip(), "member": True}
        else:
            del F["post"]["author_line"]
    _member_titles(F.get("title") or [], text)
    L = brand.get("logo")
    if L:          # 회원 그림 로고 = 팩 폴더 옆 logos/ 의 파일(저장 주인 local_settings.saveLogo)
        F["logo_img"] = {**L, "file": str(Path(f).parent.parent / "logos" / L["file"])}
    for sg in F.get("segments") or []:         # 구간 틀(훅 카드 등)이 덮는 칸에도 회원이 바꾼 칸만 — 안 바꾼 칸은 구간 판 값(#4901 김효준: 첫 장면만 회원 색·채널명 빠짐)
        _member_segment(sg.get("frame") or {}, F, brand, text, name, wm)
    return st


# 회원 전체 화면(text.layout='full') 제목 두 줄 — 11-05 박은숙 회원 Claude 손수정(styles._member_fullscreen·member_fullscreen.json)과 같은 값. 회원 제목 칸(_member_titles)이 그 위에 덮는다
MEMBER_FULL_TITLE = [
    {"font": "Pretendard-Bold.otf", "px": 104, "color": "#FFFFFF", "hi": "#FFE600", "center": 250, "max_w": 980, "stroke": {"px": 10, "color": "#000000"}},
    {"font": "Pretendard-Bold.otf", "px": 116, "color": "#FFE600", "hi": "#FFE600", "center": 385, "max_w": 980, "stroke": {"px": 10, "color": "#000000"}},
]
MEMBER_FULL_DROP = ("window", "window_radius", "post", "band", "credit", "segments")


def _member_layout(F: dict, st: dict, text: dict) -> None:
    """(판단 주인 — 회원 화면 틀·자막 쌓기 자리, 11-05 박은숙 썰템쇼판 9:16 전체 화면) member_frame 이 부른다.
    text.layout='full' = 판 틀을 전체 화면(kind full, 창·게시글·띠·출처·구간 틀 없음)으로 바꾸고 제목 두 줄을 영상 위에(MEMBER_FULL_TITLE).
    text.caption_stack{y,pitch,break} = 판 caption.stack 의 자리·간격·끊기만 덮는다(줄 수 lines 는 판 값). 판에 쌓기가 없으면 member_unused 로 알린다.
    허용 값 검사 = preview_request.check(break 목록 주인 render_bench.STACK_BREAKS)."""
    if text.get("layout") == "full":
        F["kind"] = "full"
        for k in MEMBER_FULL_DROP:
            F.pop(k, None)
        F["full"] = {}
        F["title"] = [dict(t, stroke=dict(t["stroke"])) for t in MEMBER_FULL_TITLE]
    cs = text.get("caption_stack")
    if isinstance(cs, dict) and cs:
        SK = (st.get("caption") or {}).get("stack")
        if isinstance(SK, dict):
            SK.update({k: cs[k] for k in ("y", "pitch", "break") if k in cs})
        else:
            st.setdefault("member_unused", []).append("text.caption_stack — 이 프리셋은 자막을 쌓지 않아(판 caption.stack 없음) 영상에 안 닿는 칸")


def _member_titles(titles: list, text: dict) -> None:
    """회원 제목 꾸미기(글꼴·줄 색·크기·세로 위치) — 본 틀과 구간 틀이 같은 규칙. 안 고른 줄·칸은 그대로."""
    colors = text.get("title_colors") or []
    for i, T in enumerate(titles):
        if text.get("title_font"):
            T["font"] = member_font_file(text["title_font"])
        if i < len(colors) and colors[i]:      # 안 고른 줄은 프리셋 색
            T["color"] = colors[i]
        if text.get("title_scale") and T.get("px"):
            T["px"] = round(T["px"] * float(text["title_scale"]))
        if text.get("title_dy") and "center" in T:   # 미리보기에서 끌어 옮긴 세로 거리(px, 1080×1920 기준)
            T["center"] += int(text["title_dy"])


def _member_segment(Fs: dict, F: dict, brand: dict, text: dict, name, wm: dict) -> None:
    """구간 틀 Fs 가 덮는 칸 중 회원이 바꾼 것만 본 틀과 같은 값으로. 구간 틀이 안 덮는 칸은 합칠 때 본 틀(회원 값)이 그대로 쓰인다."""
    bg = (brand.get("colors") or {}).get("bg")
    if bg and "bg" in Fs:
        Fs["bg"] = list(bg)
    if "title" in Fs:
        _member_titles(Fs.get("title") or [], text)
    if "watermark" in Fs:
        if wm and F.get("watermark"):              # 회원이 워터마크 자리를 정했다 = 구간에서도 같은 자리
            Fs["watermark"] = dict(F["watermark"])
        elif Fs.get("watermark"):
            if name:
                head = str(Fs["watermark"].get("text") or "").split(" ", 1)
                Fs["watermark"] = {**Fs["watermark"], "text": f"{head[0]} {name}" if len(head) == 2 and not head[0].isalnum() else name}
                name_look([Fs["watermark"]], brand.get("name_scale"), brand.get("name_color"))
            else:
                Fs["watermark"] = None
    fb = (Fs.get("post") or {}).get("head_bar")
    if name and isinstance(fb, dict) and not [ic for ic in fb.get("icons") or [] if ic.get("kind") == "text"]:
        # 본 틀 머리띠에만 채널명 자리가 있는 판(썰템쇼판) — 훅 카드 머리띠가 비어 그 구간에 채널명이 안 나왔다(11-05 김효준 #7230). 같은 자리·같은 모양으로
        mine = [dict(ic) for ic in ((F.get("post") or {}).get("head_bar") or {}).get("icons") or [] if ic.get("kind") == "text" and ic.get("text") == name]
        # 구간 제목 줄이 그 자리를 차지하면 붙이지 않는다 — 썰템쇼판 훅 카드 제목 1줄(141~255)이 채널명 자리(143~236)와 겹쳤다(11-05 김미향 #7844, 68f7e7629 회귀)
        def _over(ic):
            a0, a1 = ic["cy"] - ic["px"] / 2, ic["cy"] + ic["px"] / 2
            return any(t.get("center") is not None and t["center"] - t["px"] / 2 < a1 and a0 < t["center"] + t["px"] / 2 for t in Fs.get("title") or [])
        mine = [ic for ic in mine if not _over(ic)]
        if mine:
            fb["icons"] = list(fb.get("icons") or []) + mine
    if "logo" in Fs and Fs.get("logo"):
        if name:
            Fs["logo"] = {**Fs["logo"], "text": name}
            name_look([Fs["logo"]], brand.get("name_scale"), brand.get("name_color"))
        else:
            Fs["logo"] = None


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
