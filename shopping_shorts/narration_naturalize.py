"""나레이션 텍스트를 사람 목소리(서울 20대 여성)에 가깝게 다듬는 순수 규칙 엔진.

API·Gemini 무호출. naturalize(text, profile, ...) -> text. 결정적(같은 입력=같은 출력).
프로파일(dict)이 8스테이지를 구동한다. 규칙 자체는 시작점이고, 실제 정교 튜닝은
튜닝 작업대에서 프로파일 값(강도·사전)을 조절해 완성한다(스펙 §3)."""
import copy
import math
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


def _bump(ctx, name, n=1):
    """스테이지가 실제로 적용한 횟수를 누적. 0이면 기록하지 않는다(=아무 일도 안 함)."""
    if n:
        ctx["applied"][name] = ctx["applied"].get(name, 0) + n


def _take_count(n_candidates, intensity):
    """후보 n개 중 강도 비율만큼 앞에서부터 적용할 개수(결정적).

    올림(ceil)을 쓴다 — 내림이면 후보가 1개인 짧은 문장은 1.0에서만 발동해 슬라이더가
    계단이 된다(2026-07-15 실측 버그). intensity 0이면 0.
    """
    if n_candidates <= 0 or intensity <= 0:
        return 0
    if intensity >= 1.0:
        return n_candidates
    return min(n_candidates, math.ceil(n_candidates * intensity - 1e-9))


def normalize_reading(text):
    """숫자·단위·기호를 한국어 읽기로 바꾼다 → (변환텍스트, 적용횟수).

    정규화 스테이지의 순수 알맹이. **오독경보(asr_check)도 이 함수를 재사용한다** —
    Whisper가 '삼 점 오 킬로그램'을 다시 '3.5kg'로 표기해버려서, 양쪽을 같은 표기로
    맞추지 않으면 성우가 제대로 읽었는데도 전부 오독으로 뜬다(2026-07-15 실측).
    """
    def num_repl(m):
        return _num_to_words(m.group(0))
    def numunit(m):
        return f"{_num_to_words(m.group(1))} {_UNIT_MAP[m.group(2)]}"
    unit_pat = r"(\d+(?:\.\d+)?)(" + "|".join(sorted(_UNIT_MAP, key=len, reverse=True)) + r")"
    text, n1 = re.subn(unit_pat, numunit, text)
    text, n2 = re.subn(r"\d+(?:\.\d+)?", num_repl, text)
    n3 = 0
    for sym, word in _SYMBOL_MAP.items():
        n3 += text.count(sym)
        # 앞뒤 공백(N-5) — 기호 앞에만 공백을 넣으면 뒤 단어가 읽기말에 들러붙는다
        # (예: "1+1" → "일 플러스일"). asr_check가 이 함수 출력을 오독판정 정본으로
        # 재사용하므로 표기 오류가 곧 판정 오류가 된다. 앞뒤 다 띄우고 아래에서
        # 중복공백·양끝을 정리한다.
        text = text.replace(sym, " " + word + " ")
    text = re.sub(r" {2,}", " ", text).strip()
    return text, n1 + n2 + n3


def _normalize(text, cfg, ctx):
    text, n = normalize_reading(text)
    _bump(ctx, "normalize", n)
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
    # 앞에서부터 intensity 비율만 변환(결정적) — 올림이라 후보 1개짜리 짧은 문장도
    # 낮은 강도에서 반영된다(내림이면 0이라 1.0에서만 발동하는 계단이 됨).
    take = _take_count(len(hits), intensity)
    chosen = set(hits[:take])
    # len(chosen)이 아니라 실제 치환 성공 횟수를 센다(Minor2 재리뷰) — chosen의 모든
    # 셀이 실제로 바뀐다는 건 "히트 판정 루프와 치환 루프가 같은 패턴을 쓰고 모든
    # (a,b) 쌍이 a!=b"라는 암묵 불변식일 뿐이다. _SPOKEN_MAP에 항등 쌍이 섞이면
    # 깨지므로, 여기서 직접 `new != s`를 확인해 센다.
    n = 0
    for i in chosen:
        s = parts[i]
        for a, b in _SPOKEN_MAP:
            new = re.sub(a + r"(?=[.!?…]?$)", b, s)
            if new != s:
                parts[i] = new
                n += 1
                break
    _bump(ctx, "spoken_style", n)
    return "".join(parts)


def _pronunciation(text, cfg, ctx):
    d = cfg.get("dict") or {}
    # 참가 판정은 원문(orig) 기준(Minor1) — 유령 매칭 차단용. 발음사전은 작업대에서
    # 사장님이 채우는 열린 입력이라 키끼리 서로 부분집합인 게 표준 사용법이다
    # (예: {"AS센터":"...", "AS":"..."}, {"AI칩":"...", "AI":"..."}) — "긴 키 먼저"
    # 주석 자체가 그 전제 위에 있다. `orig`는 이 함수 호출 동안 절대 바뀌지 않으므로
    # 앞선 치환이 만든 유령 문자열이 뒤 키에 다시 매칭되는 일은 없다.
    # 다만 orig 게이트만으로는 부족하다(N-1 재리뷰) — 긴 키가 먼저 통째로 삼켜버리면
    # 뒤 키는 원문엔 있었지만(게이트 통과) 지금 `text`에는 이미 없어 실제로는
    # no-op인 치환이 남는다. 그래도 게이트만 보고 세면 "치환 안 됐는데 적용됐다"는
    # 거짓말이 된다. 그래서 게이트(유령매칭 차단)와 실효과 계수(no-op 배제)를 함께
    # 적용한다 — `_spoken_style`이 이미 쓰는 `new != s` 전략과 동일한 원칙이다.
    orig = text
    n = 0
    for k in sorted(d, key=len, reverse=True):   # 긴 키 먼저(부분매칭 방지)
        if k in orig:
            nt = text.replace(k, d[k])
            if nt != text:      # 실제로 뭔가 바뀌었을 때만 계수(no-op 제외)
                n += 1
            text = nt
    _bump(ctx, "pronunciation", n)
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
    # intensity로 삽입할 연결어미 종류 수를 제한(결정적: 앞에서부터). _take_count가
    # 이미 올림(ceil)이라 낮은 강도에서도 최소 1종은 활성 — max(1, ...)은 intensity==0
    # 방어용(위에서 이미 걸러지지만 이중 안전장치).
    take = max(1, _take_count(len(_CONNECTIVES), intensity))
    active = _CONNECTIVES[:take]
    n = 0
    for c in sorted(active, key=len, reverse=True):
        text, k = re.subn(r"(" + c + r")(\s+)(?=[^\s,.!?…])", r"\1,\2", text)
        n += k
    _bump(ctx, "phrasing", n)
    return text


# 종결어미(마침표 없이 끝나는 대본에서도 끝음을 흐릴 수 있게). 튜닝 코퍼스엔 마침표가
# 없고 실제 대본엔 있다 — 양쪽 다 동작해야 작업대에서 들은 것이 실제와 같아진다.
# ⚠️ 단독 `요`/`다`/`죠`는 절대 쓰지 마라(2026-07-15 컨트롤러 실측 오탐) —
#   '이거 하나면 다 돼요'는 부사 '다'에, '중요/필요/주요 포인트예요'는 명사 꼬리 '요'에
#   달라붙어 진짜 종결어미(돼요/포인트예요) 대신 엉뚱한 곳에 `…`가 박힌다. 강도가
#   낮을수록(=후보 1개만 취함) 위치상 앞선 오탐이 진짜 종결어미보다 먼저 뽑혀 더 틀린다.
#   `_CONNECTIVES`가 이미 세운 원칙("오탐 0이 더 중요")을 그대로 따라 — 명시적
#   다음절 종결어미만 나열한다(서버 실측 대본 기준). 놓치는 어미(false negative,
#   예: 조사축약형 "돼요"·"라고요" 밖의 변형)는 안전하니 목록을 함부로 넓히지 마라.
_ENDING_SUFFIXES = ["거든요", "라고요", "세요", "니다", "해요",
                    "어요", "아요", "에요", "예요", "네요", "죠"]
_ENDING_TAIL = re.compile(
    "(?:" + "|".join(sorted(_ENDING_SUFFIXES, key=len, reverse=True)) + r")(?=\s|$)"
)


def _endings(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity <= 0:
        return text
    # 후보: ① 마침표 ② 마침표 없는 종결어미. 위치 순으로 앞에서부터 강도 비율만.
    # dot 스팬(".")과 tail 스팬(다음절 어미)이 서로 겹칠 수 없다는 게 이 정렬의 전제다:
    # tail은 (?=\s|$)로 "다음 글자가 공백/끝"일 때만 매칭되므로, 어미 바로 뒤에 마침표가
    # 오는 위치("...세요.")에서는 tail이 애초에 발동하지 않는다(다음 글자가 "."라서) —
    # 그래서 dot·tail 후보는 항상 서로 다른 위치를 가리키고, 정렬 후 취해도 안전하다.
    cands = [(m.start(), m.end(), "dot") for m in re.finditer(r"\.(?=\s|$)", text)]
    cands += [(m.start(), m.end(), "tail") for m in _ENDING_TAIL.finditer(text)]
    cands.sort()
    take = _take_count(len(cands), intensity)
    if take <= 0:
        return text
    # 오프셋이 밀리지 않도록 뒤에서부터 적용. 어미가 단음절(요/다)에서 다음절(세요/거든요
    # 등)로 늘어나도 안전하다 — 여기 start/end는 치환 전 원본 문자열 기준으로 전부
    # 미리 계산돼 있고(re.finditer는 원본을 스캔), 뒤(큰 start)부터 앞으로 적용하므로
    # 아직 처리 안 된(=앞쪽) 후보의 좌표는 그 뒤 어떤 치환에도 영향받지 않는다. 즉
    # 스팬 길이 자체는 오프셋 안전성과 무관하다(중요한 건 적용 "순서"뿐).
    #
    # "계획한 수(take)"가 아니라 "실제 바뀐 횟수"만 센다(Important2) — `_spoken_style`·
    # `_pronunciation`이 이미 쓰는 `new != s` 전략과 통일. 구조상 dot 치환(문자 교체)과
    # tail 삽입(문자 추가)은 항상 실효과가 나므로(no-op이 될 수 없음) 지금 당장은 take와
    # n이 같은 값이 나오지만, 어미 목록이 앞으로 바뀌어도 계약이 "실제 효과"로 고정돼
    # 있어야 다른 스테이지와 전략이 어긋나지 않는다.
    n = 0
    for start, end, kind in sorted(cands[:take], key=lambda c: c[0], reverse=True):
        before = text
        if kind == "dot":
            text = text[:start] + "…" + text[end:]
        else:
            text = text[:end] + "…" + text[end:]
        if text != before:
            n += 1
    _bump(ctx, "endings", n)
    return text


def _fillers(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.2)
    bank = cfg.get("bank") or ["음"]
    cap = ctx["caps"].get("max_fillers_per_text", 1)
    # intensity 임계: 낮으면 아예 삽입 안 함(오버금지 기본)
    if intensity < 0.15 or cap <= 0:
        return text
    bi = ctx["beat_index"] or 0
    filler = bank[bi % len(bank)]         # 비트별 결정적 순환
    # _bump는 Task 4~6 중 배선 예정(현재 미배선 — 죽은 스테이지 아님. 근거는 _endings 주석 참조).
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
    # max_tags_total도 여기서 미리 게이트한다(Important1 수정) — 이전엔 이 캡을
    # 스테이지 루프 밖 `_enforce_total_tag_cap`이 사후에만 걸러서, bump는 이미
    # 찍힌 뒤 태그가 지워지는 비대칭이 있었다(캡을 0으로 내렸는데 "감정×1 적용"이라고
    # 뜨는 거짓말 — 2026-07-15 재현). 이 스테이지는 naturalize_detail 1회 호출당
    # 정확히 1번만 실행되고, 우리가 붙이는 태그는 이후 스테이지(intonation)가 텍스트
    # 앞부분을 건드리지 않는 한 항상 전체 문자열의 맨 앞(=태그 목록의 0번째)이 되므로
    # — max_tags_total>=1이면 `_enforce_total_tag_cap`의 "앞에서 cap개 보존" 규칙상
    # 우리 태그는 절대 제거되지 않는다. 즉 사후 캡이 실제로 우리 태그를 지우는 경우는
    # max_tags_total<=0뿐이고, 그 경우만 여기서 미리 걸러내면 bump와 실제 결과가
    # 항상 일치한다(사후 차감 로직 불필요).
    if ctx["caps"].get("max_tags_total", 3) <= 0:
        return text
    tag = _tag_for(ctx)
    if not tag:
        return text
    _bump(ctx, "emotion_arc", 1)
    return f"{tag} {text}"


def _tag_for(ctx):
    """정본 role → 태그. 미지 role은 위치기반으로 폴백.

    ⚠️ 경고는 여기서 내지 않는다(Critical1 수정) — 이 함수는 emotion_arc 스테이지가
    ON이고 intensity/캡 조건을 통과했을 때만 호출되므로, 감정태그를 끈 상태에서는
    호출 자체가 안 돼 경고가 조용히 사라진다. 경고는 `naturalize_detail`이 스테이지
    루프를 돌기 전에 1회 판정한다(감정태그 여부와 무관한 데이터 품질 사실이므로).

    canon 판정은 `naturalize_detail`이 ctx["role_canon"]에 1회 미리 넣어둔 값을
    재사용한다(재리뷰 Minor4 — normalize_role을 호출당 2곳에서 독립 판정하면
    한쪽만 바뀌었을 때 "경고는 나는데 태그는 정본" 드리프트가 생길 수 있었다)."""
    canon = ctx.get("role_canon")
    if canon:
        return _ARC_BY_ROLE[canon]
    if ctx.get("beat_index") is None or not ctx.get("beat_total"):
        return None
    n = max(1, ctx["beat_total"] - 1)
    raw_pos = round((ctx["beat_index"] / n) * (len(_ARC_BY_POS) - 1))
    pos = min(len(_ARC_BY_POS) - 1, max(0, raw_pos))
    return _ARC_BY_POS[pos]


def _intonation(text, cfg, ctx):
    # 최소 구현: 물음표 종결 보존(상승억양). 강조는 v2에서. 현재는 무변경에 가깝게.
    # _bump는 Task 4~6 중 배선 예정(현재 미배선 — 죽은 스테이지 아님. 근거는 _endings 주석 참조).
    # 지금은 실제로 텍스트를 바꾸지 않는 무변경 스텁이라 bump할 것 자체가 없다(v2 예정).
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
           "caps": p.get("caps", {}), "applied": {}, "warnings": [],
           "role_canon": normalize_role(beat_role)}
    # role 정규화 실패는 감정태그 슬라이더와 무관한 데이터 품질 사실이다(Critical1) —
    # 스테이지 루프(emotion_arc on/intensity/캡에 종속) 밖에서 1회 판정·경고한다.
    # role_canon도 여기서 1회만 판정해 ctx에 실어두고 _tag_for가 재사용한다(Minor4 —
    # 이전엔 이 게이트와 _tag_for가 각자 normalize_role을 불러 독립 판정이었다).
    #
    # 문구는 "폴백함"(결과)이 아니라 "별칭표에 없음"(사실)을 말한다(재리뷰 Important2) —
    # 이 경고는 스테이지 루프 밖에서 나오므로 emotion_arc.on=False·intensity<0.15·
    # max_tags_per_beat<=0·beat_index=None 등 폴백이 실제로는 전혀 일어나지 않는
    # 경우에도 뜬다. "위치기반으로 폴백함"이라고 단정하면 거짓이 된다.
    if beat_role and ctx["role_canon"] is None:
        ctx["warnings"].append(f"미지 role '{beat_role}' — 별칭표에 없음(감정태그 사용 시 위치기반 폴백)")
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
