"""채널 프로필 = 프리셋(구조) + 고객 옵션(겉모습) 합치기 — **하나뿐인 합치기 주인**(관제 234, 숏템MCP 설계 §9).

프리셋 = 틀 구조(frame.json — 자리·크기·층), 프로필 = 그 채널의 겉모습(채널명·글꼴·자막 꼴·목소리·효과음 팩·BGM·템플릿).
`claude_portal.assets_for` 가 서버에서 합쳐 고객 PC 로 내려주고, PC 는 그대로 쓴다(PC 에서 다시 합치지 않는다).
원형은 엔진 트랙 `calcopy_make.merge_preset_pack`(:114) — 글꼴·채널명·자막 꼴 덮어쓰기 규칙을 그대로 옮겼다.

★옵션 값은 **서버 자산 id 만** 받는다(파일 경로·URL·임의 글 금지). 모르는 키는 거절한다 — 조용히 버리면
  "저장했는데 안 바뀐다"가 된다(관리자 설정 화이트리스트 사고와 같은 꼴, test_admin_payload).
"""
from __future__ import annotations

import copy
import re

# 자막 등장·강조 움직임 이름 — static/caption-motions.js CAPTION_MOTION_PACKS 에 나오는 이름 전부(2026-10-18 실측).
CAPTION_MOTIONS = ("popBounce", "blurUp", "slide", "jelly", "drop", "typing", "grow", "riseClip",
                   "slam", "rise", "pop", "trackIn", "fade", "wide")
# 자막 쌓기 방식 — 엔진 narr_video.steps_of(mode) 가 아는 두 가지.
CAPTION_MODES = ("accumulate", "replace")
# 자막팩 — static/caption-motions.js CAPTION_PACKS 의 키(6).
CAPTION_PACKS = ("tension", "clean", "premium", "story", "deal", "soft")

# 팩 기본값 — 고객이 안 고른 칸을 채운다. 엔진 트랙 my_packs.json "1"(10-16 통과작 조합)의 서버 자산 id 판.
# 글꼴은 비워 둔다 → 틀(frame.json)에 적힌 글꼴이 그대로 기본이다.
DEFAULT_PACK = {
    "brand": {"channel_name": "", "colors": {}},
    "text": {"caption": {}},
    "tts": {"voice": "tc-piljae-stable", "tempo": 1.36},
    "sfx_pack": "팩01",
    "bgm": {"track": "qiuqiu", "gain_db": -18},
    "meme_pool": {"kinds": []},
    "template": "none",
    "caption_pack": "none",
    "scene_fx": {"auto": False},
}

# 고객에게 안 보내는 틀 키 — 벤치 원본 id(source)·측정 원값·만든 도구 표식. 렌더에 필요 없는 것.
_FRAME_DROP = ("source", "sources", "variable_stats", "bench", "made_by", "notes", "unknown")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class OptionError(ValueError):
    """옵션 검증 실패 — 고객용 한국어 한 문장."""


def _frames(frame: dict) -> list:
    return frame["frames"] if isinstance(frame.get("frames"), list) else [frame]


def _deep_merge(base, over):
    if not isinstance(base, dict) or not isinstance(over, dict):
        return copy.deepcopy(over)
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _deep_merge(out.get(k), v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def validate(options, catalog: dict) -> dict:
    """고객 옵션 검증 → 깨끗한 사본. catalog = {"font","sfx_pack","bgm","template","voice","meme_kind"} 각 id 집합.

    모르는 키·목록 밖 id·범위 밖 숫자는 OptionError. 빈 문자열은 '안 고름'(팩 기본값)이라 뺀다."""
    if options is None:
        return {}
    if not isinstance(options, dict):
        raise OptionError("옵션 형식이 올바르지 않습니다")
    cat = {k: set(v or ()) for k, v in (catalog or {}).items()}
    out = {}

    def _keys(d, allowed, where):
        if not isinstance(d, dict):
            raise OptionError(f"{where} 형식이 올바르지 않습니다")
        bad = sorted(set(d) - set(allowed))
        if bad:
            raise OptionError(f"모르는 옵션입니다: {where}.{bad[0]}")

    def _pick(v, kind, where, extra=()):
        if v in (None, ""):
            return None
        if not isinstance(v, str) or (v not in cat.get(kind, set()) and v not in extra):
            raise OptionError(f"목록에 없는 값입니다: {where}")
        return v

    _keys(options, ("brand", "text", "tts", "sfx_pack", "bgm", "meme_pool", "template", "caption_pack", "scene_fx"), "options")
    if "brand" in options:
        b = options["brand"]
        _keys(b, ("channel_name", "colors"), "brand")
        nb = {}
        if b.get("channel_name") not in (None, ""):
            nm = b["channel_name"]
            if not isinstance(nm, str) or len(nm.strip()) > 20 or any(c in nm for c in "<>\"'`\\"):
                raise OptionError("채널명은 20자 이하 글자만 됩니다")
            nb["channel_name"] = nm.strip()
        if b.get("colors"):
            _keys(b["colors"], ("accent", "header"), "brand.colors")
            cols = {}
            for k, v in b["colors"].items():
                if v in (None, ""):
                    continue
                if not isinstance(v, str) or not _HEX.match(v):
                    raise OptionError("색은 #RRGGBB 꼴만 됩니다")
                cols[k] = v.upper()
            if cols:
                nb["colors"] = cols
        if nb:
            out["brand"] = nb
    if "text" in options:
        t = options["text"]
        _keys(t, ("title_font", "caption_font", "caption"), "text")
        nt = {}
        for k in ("title_font", "caption_font"):
            v = _pick(t.get(k), "font", f"text.{k}")
            if v:
                nt[k] = v
        if t.get("caption"):
            c = t["caption"]
            _keys(c, ("mode", "enter", "emphasis", "outline_px"), "text.caption")
            nc = {}
            if c.get("mode") not in (None, ""):
                if c["mode"] not in CAPTION_MODES:
                    raise OptionError("자막 쌓기 방식이 목록에 없습니다")
                nc["mode"] = c["mode"]
            for k in ("enter", "emphasis"):
                if c.get(k) not in (None, ""):
                    if c[k] != "none" and c[k] not in CAPTION_MOTIONS:
                        raise OptionError("자막 효과가 목록에 없습니다")
                    nc[k] = c[k]
            if c.get("outline_px") not in (None, ""):
                try:
                    px = int(c["outline_px"])
                except (TypeError, ValueError):
                    raise OptionError("자막 외곽선은 0~12 숫자만 됩니다") from None
                if not 0 <= px <= 12:
                    raise OptionError("자막 외곽선은 0~12 숫자만 됩니다")
                nc["outline_px"] = px
            if nc:
                nt["caption"] = nc
        if nt:
            out["text"] = nt
    if "tts" in options:
        t = options["tts"]
        _keys(t, ("voice", "tempo"), "tts")
        nt = {}
        v = _pick(t.get("voice"), "voice", "tts.voice")
        if v:
            nt["voice"] = v
        if t.get("tempo") not in (None, ""):
            try:
                tp = round(float(t["tempo"]), 2)
            except (TypeError, ValueError):
                raise OptionError("말 빠르기는 0.8~1.8 숫자만 됩니다") from None
            if not 0.8 <= tp <= 1.8:
                raise OptionError("말 빠르기는 0.8~1.8 숫자만 됩니다")
            nt["tempo"] = tp
        if nt:
            out["tts"] = nt
    v = _pick(options.get("sfx_pack"), "sfx_pack", "sfx_pack")
    if v:
        out["sfx_pack"] = v
    if "bgm" in options:
        b = options["bgm"]
        _keys(b, ("track", "gain_db"), "bgm")
        nb = {}
        v = _pick(b.get("track"), "bgm", "bgm.track", extra=("none",))
        if v:
            nb["track"] = v
        if b.get("gain_db") not in (None, ""):
            try:
                g = int(b["gain_db"])
            except (TypeError, ValueError):
                raise OptionError("배경음 크기는 -30~-6 숫자만 됩니다") from None
            if not -30 <= g <= -6:
                raise OptionError("배경음 크기는 -30~-6 숫자만 됩니다")
            nb["gain_db"] = g
        if nb:
            out["bgm"] = nb
    if "meme_pool" in options:
        m = options["meme_pool"]
        _keys(m, ("kinds",), "meme_pool")
        kinds = m.get("kinds") or []
        if not isinstance(kinds, list) or len(kinds) > 20:
            raise OptionError("짤 종류 형식이 올바르지 않습니다")
        for k in kinds:
            if k not in cat.get("meme_kind", set()):
                raise OptionError("목록에 없는 짤 종류입니다")
        out["meme_pool"] = {"kinds": list(dict.fromkeys(kinds))}
    v = _pick(options.get("template"), "template", "template", extra=("none",))
    if v:
        out["template"] = v
    if options.get("caption_pack") not in (None, ""):
        if options["caption_pack"] != "none" and options["caption_pack"] not in CAPTION_PACKS:
            raise OptionError("자막팩이 목록에 없습니다")
        out["caption_pack"] = options["caption_pack"]
    if "scene_fx" in options:
        s = options["scene_fx"]
        _keys(s, ("auto",), "scene_fx")
        if "auto" in s:
            if not isinstance(s["auto"], bool):
                raise OptionError("장면 효과 자동은 켬/끔만 됩니다")
            out["scene_fx"] = {"auto": s["auto"]}
    return out


def _rgb(hexv):
    hexv = hexv.lstrip("#")
    return [int(hexv[i:i + 2], 16) for i in (0, 2, 4)]


# 광고 표시 글(예: 썰풀다 brand 자리의 "[광고]")은 채널명이 바뀌어도 지우지 않는다 — 표시 의무 문구다(2026-10-18).
_DISCLOSURE_WORDS = ("광고", "협찬", "유료", "AD", "PPL")


def _is_disclosure(t) -> bool:
    return isinstance(t, str) and any(w in t for w in _DISCLOSURE_WORDS)


def merge(preset: dict, pack_defaults: dict, options: dict) -> dict:
    """판단 한 곳: 프리셋 구조 + 팩 기본값 + 고객 옵션 → 합본.

    preset = {"frame": frame.json 내용}. 반환 {"frame": 축약·덮어쓴 틀, "options": 합친 옵션, "applied": [바꾼 자리],
    "per_video": [편마다 정하는 자리]}. 원본 preset 은 건드리지 않는다(깊은 사본).
    `$per_video` 는 프로필·팩이 값을 가진 자리(채널명)는 그 값으로, 대본이 정하는 자리(제목 글 등)는 None + per_video 목록."""
    eff = _deep_merge(pack_defaults or {}, options or {})
    applied, per_video = [], []
    src = (preset or {}).get("frame")
    frame = None
    if isinstance(src, dict):
        frame = {k: copy.deepcopy(v) for k, v in src.items() if k not in _FRAME_DROP}
        brand, text = eff.get("brand") or {}, eff.get("text") or {}
        cap = text.get("caption") or {}
        new_name = brand.get("channel_name") or ""
        colors = brand.get("colors") or {}
        frs = _frames(frame)
        old_names = {L.get("text") for fr in frs for L in fr.get("layers", [])
                     if L.get("kind") == "text" and L.get("role") == "brand" and isinstance(L.get("text"), str)
                     and L.get("text") != "$per_video" and not _is_disclosure(L.get("text"))}
        for fr in frs:
            fid = fr.get("id") or "frame"
            for k in [k for k in fr if fr.get(k) == "$per_video"]:
                fr[k] = None
                per_video.append(f"{fid}.{k}")
            for L in fr.get("layers", []):
                kind, role = L.get("kind"), L.get("role")
                if kind == "text":
                    if L.get("text") == "$per_video":
                        if role == "brand" and new_name:
                            L["text"] = new_name
                            applied.append(f"{fid} 채널명 → '{new_name}'")
                        else:
                            L["text"] = None
                            per_video.append(f"{fid}.layers[text:{role}].text")
                    elif new_name and role == "brand" and not _is_disclosure(L.get("text")):
                        applied.append(f"{fid} 채널명 '{L.get('text')}' → '{new_name}'")
                        L["text"] = new_name
                    elif new_name and isinstance(L.get("text"), str) and any(o and o in L["text"] for o in old_names):
                        for o in old_names:
                            if o:
                                L["text"] = L["text"].replace(o, new_name)
                        applied.append(f"{fid} 글 속 채널명 → '{new_name}'")
                    if role == "title" and text.get("title_font") and L.get("font") != text["title_font"]:
                        applied.append(f"{fid} 제목 글꼴 {L.get('font')} → {text['title_font']}")
                        L["font"] = text["title_font"]
                    if role == "caption":
                        if text.get("caption_font") and L.get("font") != text["caption_font"]:
                            applied.append(f"{fid} 자막 글꼴 {L.get('font')} → {text['caption_font']}")
                            L["font"] = text["caption_font"]
                        if "outline_px" in cap:
                            L["outline"] = ({"px": cap["outline_px"], "rgb": (L.get("outline") or {}).get("rgb") or [0, 0, 0]}
                                            if cap["outline_px"] else None)
                            applied.append(f"{fid} 자막 외곽선 {cap['outline_px']}px")
                        if cap.get("enter"):
                            ms = (L.get("enter") or {}).get("ms", 300) if isinstance(L.get("enter"), dict) else 300
                            L["enter"] = None if cap["enter"] == "none" else {"kind": cap["enter"], "ms": ms}
                            applied.append(f"{fid} 자막 등장 {cap['enter']}")
                        if cap.get("emphasis"):
                            L["emphasis"] = None if cap["emphasis"] == "none" else cap["emphasis"]
                            applied.append(f"{fid} 자막 강조 {cap['emphasis']}")
                elif kind == "band" and L.get("y") == 0 and (L.get("w") or 0) >= 1000 and colors.get("header"):
                    applied.append(f"{fid} 머리 띠 색 → {colors['header']}")
                    L["rgb"] = _rgb(colors["header"])
    return {"frame": frame, "options": eff, "applied": applied, "per_video": per_video}


def fonts_of(frame) -> list:
    """합본 틀이 그리는 글꼴 이름(등장 순서, 중복 없음) — 자산 목록의 글꼴 참조."""
    if not isinstance(frame, dict):
        return []
    seen = []
    for fr in _frames(frame):
        for L in fr.get("layers", []):
            f = L.get("font") if L.get("kind") == "text" else None
            if isinstance(f, str) and f and f not in seen:
                seen.append(f)
    return seen
