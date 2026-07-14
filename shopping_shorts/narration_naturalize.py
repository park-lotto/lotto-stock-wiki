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
    """유저 프로파일을 DEFAULT_PROFILE 위에 깊게 병합(빈 값은 기본으로 채움)."""
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
    digits = "만천백십"
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


def _normalize(text, cfg):
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


def _spoken_style(text, cfg):
    intensity = cfg.get("intensity", 0.4)
    # 종결(문장부호 앞) 위치를 찾아 앞에서부터 intensity 비율만 변환(결정적)
    sentences = re.split(r"(?<=[.!?…])\s*", text)
    hits = []
    for si, s in enumerate(sentences):
        for a, b in _SPOKEN_MAP:
            if re.search(a + r"(?=[.!?…]?$)", s):
                hits.append(si)
                break
    take = int(len(hits) * intensity + 1e-9)  # 앞에서부터 take개만
    take = min(len(hits), take if intensity < 1.0 else len(hits))
    chosen = set(hits[:take])
    out = []
    for si, s in enumerate(sentences):
        if si in chosen:
            for a, b in _SPOKEN_MAP:
                new = re.sub(a + r"(?=[.!?…]?$)", b, s)
                if new != s:
                    s = new
                    break
        out.append(s)
    return " ".join(x for x in out if x != "").strip() if " " in text else "".join(out)


def _pronunciation(text, cfg):
    d = cfg.get("dict") or {}
    for k in sorted(d, key=len, reverse=True):   # 긴 키 먼저(부분매칭 방지)
        text = text.replace(k, d[k])
    return text


# 연결어미(뒤에 호흡을 두면 자연스러운 지점). 시작점 — 작업대에서 강도로 밀도 조절.
_CONNECTIVES = ["는데", "은데", "지만", "어서", "아서", "라서", "고", "며", "면서"]


def _phrasing(text, cfg):
    intensity = cfg.get("intensity", 0.3)
    if intensity <= 0:
        return text
    # 연결어미 + 공백 경계에 쉼표 삽입(이미 쉼표/문장부호가 붙어있으면 skip)
    # intensity로 삽입할 연결어미 종류 수를 제한(결정적: 앞에서부터)
    take = max(1, int(len(_CONNECTIVES) * intensity + 0.999))
    active = _CONNECTIVES[:take] if intensity < 1.0 else _CONNECTIVES
    for c in sorted(active, key=len, reverse=True):
        text = re.sub(r"(" + c + r")(\s+)(?=[^\s,.!?…])", r"\1,\2", text)
    return text


def _endings(text, cfg):
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


# 비트 역할별 감정 태그 곡선(v3 오디오 태그). 시작점 — 작업대에서 세기 조절.
_ARC_BY_ROLE = {
    "hook": "[curious]", "intro": "[warm]", "build": "[warm]",
    "body": None, "payoff": "[satisfied]", "cta": "[excited]",
}
_ARC_BY_POS = ["[curious]", "[warm]", None, "[satisfied]", "[excited]"]  # 역할 없을 때 위치기반


def _emotion_arc(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity < 0.15:                  # 오버금지: 낮으면 무태그
        return text
    if ctx["caps"].get("max_tags_per_beat", 1) <= 0:
        return text
    tag = None
    role = ctx.get("beat_role")
    if role and role in _ARC_BY_ROLE:
        tag = _ARC_BY_ROLE[role]
    elif ctx.get("beat_index") is not None and ctx.get("beat_total"):
        n = max(1, ctx["beat_total"] - 1)
        pos = round((ctx["beat_index"] / n) * (len(_ARC_BY_POS) - 1))
        tag = _ARC_BY_POS[pos]
    return f"{tag} {text}" if tag else text


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
    keep_end = tags[cap - 1].start() if cap > 0 else 0
    # cap개까지만 남기고 이후 태그 제거
    kept = text[:tags[cap].start()] if cap < len(tags) else text
    rest = re.sub(r"\[[^\]]+\]\s?", "", text[tags[cap].start():]) if cap < len(tags) else ""
    return (kept + rest) if cap > 0 else re.sub(r"\[[^\]]+\]\s?", "", text)


def naturalize(text, profile=None, *, beat_role=None, beat_index=None, beat_total=None):
    """text를 프로파일 규칙으로 다듬어 반환. 스테이지를 순서대로 적용."""
    p = merge_profile(profile)
    ctx = {"beat_role": beat_role, "beat_index": beat_index, "beat_total": beat_total,
           "caps": p.get("caps", {})}
    out = text
    for name, fn in _STAGES:
        cfg = p.get(name, {})
        if cfg.get("on"):
            out = fn(out, cfg) if fn.__code__.co_argcount == 2 else fn(out, cfg, ctx)
    out = _enforce_total_tag_cap(out, p.get("caps", {}).get("max_tags_total", 3))
    return out
