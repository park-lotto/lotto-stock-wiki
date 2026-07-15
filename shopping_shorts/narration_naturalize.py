"""나레이션 텍스트를 사람 목소리(서울 20대 여성)에 가깝게 다듬는 순수 규칙 엔진.

API·Gemini 무호출. naturalize(text, profile, ...) -> text. 결정적(같은 입력=같은 출력).
프로파일(dict)이 8스테이지를 구동한다. 규칙 자체는 시작점이고, 실제 정교 튜닝은
튜닝 작업대에서 프로파일 값(강도·사전)을 조절해 완성한다(스펙 §3)."""
import copy
import re

DEFAULT_PROFILE = {
    "normalize":     {"on": True},
    "spoken_style":  {"on": True, "intensity": 0.4},
    "pronunciation": {"on": True, "dict": {}},
    "phrasing":      {"on": True, "intensity": 0.3},
    "endings":       {"on": True, "intensity": 0.3},
    "fillers":       {"on": True, "intensity": 0.2, "bank": ["음", "아", "그", "뭐", "자"]},
    "emotion_arc":   {"on": True, "intensity": 0.3},
    "intonation":    {"on": True, "intensity": 0.2},
    "caps": {"max_tags_total": 3, "max_tags_per_beat": 1, "max_fillers_per_text": 1},
    "seed": 42,
    "n_best": 1,
}


def merge_profile(profile):
    """유저 프로파일을 DEFAULT_PROFILE 위에 1단계 병합(빈 값은 기본으로 채움).

    최상위 dict 값(스테이지·caps)은 `.update`로 얕게 합쳐지므로 그 내부에 중첩된
    dict(예: pronunciation.dict)를 부분 지정하면 통째로 교체된다(재귀 병합 아님)."""
    out = copy.deepcopy(DEFAULT_PROFILE)
    for k, v in (profile or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


_SINO = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
_UNIT_MAP = {"kg": "킬로그램", "g": "그램", "cm": "센티미터", "mm": "밀리미터",
             "m": "미터", "ml": "밀리리터", "L": "리터", "l": "리터"}
_SYMBOL_MAP = {"%": "퍼센트", "&": "앤드", "+": "플러스"}


def _int_to_sino(n):
    """정수 → 사이노 한국어 읽기(간이). 0~9999 지원(그 이상은 자리 붙여 읽기 근사)."""
    if n == 0:
        return "영"
    s = str(n)
    if len(s) <= 4:
        pad = s.rjust(4, "0")
        out = ""
        for i, ch in enumerate(pad):
            d = int(ch)
            if d == 0:
                continue
            unit = ["천", "백", "십", ""][i]
            out += ("" if d == 1 and unit else _SINO[d]) + unit
        return out or "영"
    return " ".join(_SINO[int(c)] for c in s)  # 큰 수는 자리별 근사


def _num_to_words(whole):
    if "." in whole:
        a, b = whole.split(".", 1)
        frac = " ".join(_SINO[int(c)] for c in b)
        return f"{_int_to_sino(int(a))} 점 {frac}"
    return _int_to_sino(int(whole))


def _normalize(text, cfg, ctx):
    def num_repl(m):
        return _num_to_words(m.group(0))
    # 단위 먼저(숫자+단위) → 숫자 → 기호
    def numunit(m):
        return f"{_num_to_words(m.group(1))} {_UNIT_MAP[m.group(2)]}"
    unit_pat = r"(\d+(?:\.\d+)?)(" + "|".join(sorted(_UNIT_MAP, key=len, reverse=True)) + r")"
    text = re.sub(unit_pat, numunit, text)
    text = re.sub(r"\d+(?:\.\d+)?", num_repl, text)
    for sym, word in _SYMBOL_MAP.items():
        text = text.replace(sym, " " + word)
    text = re.sub(r" {2,}", " ", text)
    return text


# spoken_style: 문어체 종결어미 → 서울 구어체. 매핑은 시작점(작업대에서 확장).
_SPOKEN_MAP = [
    ("있습니다", "있어요"), ("없습니다", "없어요"), ("좋습니다", "좋아요"),
    ("같습니다", "같아요"), ("합니다", "해요"), ("됩니다", "돼요"),
    ("입니다", "이에요"), ("습니다", "어요"), ("ㅂ니다", "요"),
    ("드립니다", "드려요"), ("겠습니다", "겠어요"),
]


def _spoken_style(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.4)
    # 구분자(문장부호 뒤 공백)를 캡처해 보존 — 짝수 셀=문장, 홀수 셀=구분자.
    # 문장 셀만 변환하고 "".join으로 원본 공백을 그대로 복원(공백 훼손 방지).
    parts = re.split(r"((?<=[.!?…])\s*)", text)
    cell_idxs = list(range(0, len(parts), 2))
    hits = []
    for i in cell_idxs:
        s = parts[i]
        for a, b in _SPOKEN_MAP:
            if re.search(a + r"(?=[.!?…]?$)", s):
                hits.append(i)
                break
    # 앞에서부터 intensity 비율만 변환(결정적)
    take = len(hits) if intensity >= 1.0 else int(len(hits) * intensity + 1e-9)
    chosen = set(hits[:take])
    for i in chosen:
        s = parts[i]
        for a, b in _SPOKEN_MAP:
            new = re.sub(a + r"(?=[.!?…]?$)", b, s)
            if new != s:
                parts[i] = new
                break
    return "".join(parts)


def _pronunciation(text, cfg, ctx):
    d = cfg.get("dict") or {}
    for k in sorted(d, key=len, reverse=True):   # 긴 키 먼저(부분매칭 방지)
        text = text.replace(k, d[k])
    return text


# 연결어미(뒤에 호흡을 두면 자연스러운 지점). 시작점 — 작업대에서 강도로 밀도 조절.
# ⚠️ 단음절 `고`/`며`는 명사 꼬리("최고","참고")와 substring 충돌해 오탐(참고 하세요→참고, 하세요)이
# 나므로 기본 목록에서 제외한다. 남긴 2음절 어미는 명사와 겹치지 않아 안전(트레이드오프:
# "싸고" 같은 진짜 연결어미 뒤 호흡은 놓치지만, 오탐 0이 더 중요).
_CONNECTIVES = ["는데", "은데", "지만", "어서", "아서", "라서", "면서"]


def _phrasing(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity <= 0:
        return text
    # 연결어미 + 공백 경계에 쉼표 삽입(이미 쉼표/문장부호가 붙어있으면 skip)
    # intensity로 삽입할 연결어미 종류 수를 제한(결정적: 앞에서부터).
    # +0.999 = 올림(ceil): 낮은 강도에서도 최소 1종은 활성(다른 곳의 +1e-9 내림과 대비).
    take = max(1, int(len(_CONNECTIVES) * intensity + 0.999))
    active = _CONNECTIVES[:take] if intensity < 1.0 else _CONNECTIVES
    for c in sorted(active, key=len, reverse=True):
        text = re.sub(r"(" + c + r")(\s+)(?=[^\s,.!?…])", r"\1,\2", text)
    return text


def _endings(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity <= 0:
        return text
    # 마침표 위치를 앞에서부터 intensity 비율만 '…'로(결정적)
    positions = [m.start() for m in re.finditer(r"\.(?=\s|$)", text)]
    take = int(len(positions) * intensity + 1e-9)
    take = len(positions) if intensity >= 1.0 else take
    chosen = set(positions[:take])
    out = []
    for i, ch in enumerate(text):
        out.append("…" if (ch == "." and i in chosen) else ch)
    return "".join(out)


def _fillers(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.2)
    bank = cfg.get("bank") or ["음"]
    cap = ctx["caps"].get("max_fillers_per_text", 1)
    # intensity 임계: 낮으면 아예 삽입 안 함(오버금지 기본)
    if intensity < 0.15 or cap <= 0:
        return text
    bi = ctx["beat_index"] or 0
    filler = bank[bi % len(bank)]         # 비트별 결정적 순환
    return f"{filler}, {text}"


# 비트 role 정본 = edit_plan._REQUIRED_ROLES(훅·페인포인트·반전·실용·CTA).
# role은 열린 집합이다 — edit_plan 자유 모드가 Gemini에게 "role 라벨을 자유롭게 정해라"라고
# 지시하므로 새 변종이 계속 생긴다. 아래는 2026-07-15 서버 실측 17변종 기준 별칭표이고,
# 미지 role은 위치기반으로 폴백하되 반드시 경고를 남긴다(조용히 넘어가면 결함이 숨는다).
_ROLE_ALIASES = {
    "훅": "훅", "hook": "훅",
    "페인포인트": "페인포인트", "painpoint": "페인포인트", "pain point": "페인포인트",
    "반전": "반전", "twist": "반전", "reversal": "반전", "reveal": "반전",
    "실용": "실용", "utility": "실용", "practical": "실용", "solution": "실용",
    "cta": "CTA",
}


def normalize_role(role):
    """실제 role(한글/영어/대소문자/동의어) → 정본. 미지면 None."""
    if not role:
        return None
    return _ROLE_ALIASES.get(str(role).strip().lower())


# 정본 role별 감정 태그. **알려진 v3 태그만 사용**(새 태그를 지어내면 그대로 읽힐 위험).
_ARC_BY_ROLE = {
    "훅": "[curious]",
    "페인포인트": None,        # 문제 제기 구간 — 무태그(태그 도배 금지)
    "반전": "[satisfied]",
    "실용": "[warm]",
    "CTA": "[excited]",
}
_ARC_BY_POS = ["[curious]", "[warm]", None, "[satisfied]", "[excited]"]  # role 미지 시 폴백


def _emotion_arc(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity < 0.15:
        return text
    if ctx["caps"].get("max_tags_per_beat", 1) <= 0:
        return text
    tag = _tag_for(ctx)
    return f"{tag} {text}" if tag else text


def _tag_for(ctx):
    """정본 role → 태그. 미지 role은 경고 후 위치기반 폴백."""
    raw = ctx.get("beat_role")
    canon = normalize_role(raw)
    if canon:
        return _ARC_BY_ROLE[canon]
    if raw:
        ctx["warnings"].append(f"미지 role '{raw}' — 위치기반으로 폴백함(별칭표 추가 검토)")
    if ctx.get("beat_index") is None or not ctx.get("beat_total"):
        return None
    n = max(1, ctx["beat_total"] - 1)
    raw_pos = round((ctx["beat_index"] / n) * (len(_ARC_BY_POS) - 1))
    pos = min(len(_ARC_BY_POS) - 1, max(0, raw_pos))
    return _ARC_BY_POS[pos]


def _intonation(text, cfg, ctx):
    # 최소 구현: 물음표 종결 보존(상승억양). 강조는 v2에서. 현재는 무변경에 가깝게.
    return text


_STAGES = [("normalize", _normalize), ("spoken_style", _spoken_style),
           ("pronunciation", _pronunciation), ("phrasing", _phrasing),
           ("endings", _endings), ("fillers", _fillers),
           ("emotion_arc", _emotion_arc), ("intonation", _intonation)]


def _enforce_total_tag_cap(text, cap):
    """전체 v3 태그([...]) 수를 cap 이하로. 초과분은 앞에서부터 유지, 나머지 제거."""
    tags = list(re.finditer(r"\[[^\]]+\]\s?", text))
    if len(tags) <= cap:
        return text
    if cap <= 0:                              # 전부 제거
        return re.sub(r"\[[^\]]+\]\s?", "", text)
    # 여기 도달 = len(tags) > cap > 0 이므로 tags[cap]는 항상 존재.
    # cap개까지만 남기고 그 이후 구간의 태그만 제거(본문은 보존).
    kept = text[:tags[cap].start()]
    rest = re.sub(r"\[[^\]]+\]\s?", "", text[tags[cap].start():])
    return kept + rest


def naturalize_detail(text, profile=None, *, beat_role=None, beat_index=None, beat_total=None):
    """naturalize와 같지만 {"text", "applied", "warnings"}를 반환.

    applied = 스테이지별 실제 적용 횟수. 작업대가 이걸 보여줘서 "슬라이더를 돌렸는데
    왜 그대로냐"가 화면에서 즉시 드러나게 한다(2026-07-15 사고의 재발방지)."""
    p = merge_profile(profile)
    ctx = {"beat_role": beat_role, "beat_index": beat_index, "beat_total": beat_total,
           "caps": p.get("caps", {}), "applied": {}, "warnings": []}
    out = text
    for name, fn in _STAGES:
        cfg = p.get(name, {})
        if cfg.get("on"):
            out = fn(out, cfg, ctx)
    out = _enforce_total_tag_cap(out, p.get("caps", {}).get("max_tags_total", 3))
    return {"text": out, "applied": ctx["applied"], "warnings": ctx["warnings"]}


def naturalize(text, profile=None, *, beat_role=None, beat_index=None, beat_total=None):
    """text를 프로파일 규칙으로 다듬어 반환(문자열). 상세는 naturalize_detail 사용."""
    return naturalize_detail(text, profile, beat_role=beat_role,
                             beat_index=beat_index, beat_total=beat_total)["text"]
