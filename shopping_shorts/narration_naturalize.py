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
    # question_roles: 의문형 어미를 물음표로 되돌릴 비트(2026-07-17 사장님 지시,
    # amendment1로 범위 확장). 애초엔 페인포인트만이었다 — 끝음을 올려 되묻는 건
    # 아픈 곳을 찌르는 자리의 문법이라는 근거. 사장님이 같은 날 "의문형은 부호가
    # 없어요 끝을 자연스럽게 올린다"로 훅까지 넓혔다: 실측(기본 프로파일, role=훅)
    # "왜 다들 이걸 살까요."처럼 "?" 없이 의문형으로 끝나는 훅 대본이 `_intonation`의
    # 훅 꼬리 강조 규칙에 그대로 "살까요!"로 덮어써지고 있었다 — 이 코퍼스는 의문문에
    # 부호를 안 다는 게 표준 표기라 페인포인트만으로는 이 사고를 못 막는다.
    "endings":       {"on": True, "intensity": 0.3, "question_roles": ["페인포인트", "훅"]},
    # 뱅크가 감탄·놀람인 이유(2026-07-17 사장님 지시): 옛 뱅크 ["음","아","그","뭐","자"]는
    # 전부 **머뭇거림**이었다 — "저런건 의미없어". 릴스 훅은 말을 더듬는 자리가 아니라
    # 놀라는 자리다. roles=["훅"]인 이유: 감탄사가 반전·실용에 붙으면
    # "헐, 근데 이건…"처럼 톤이 무너진다. 추임새는 문을 여는 도구지 문장을 여는 도구가 아니다.
    "fillers":       {"on": True, "intensity": 0.2,
                      "bank": ["와", "오", "우와", "헐", "이야"],
                      "roles": ["훅"]},
    "emotion_arc":   {"on": True, "intensity": 0.3},
    # 속삭임 — 노브 하나(roles)의 두 설정값이다(설계 2026-07-16 §3): 전체 role을 주면
    # 5비트 다 속삭이는 ASMR 영상, 일부만 주면 그 비트만 속삭이는 강조 도구. 목소리를
    # 낮추면 오히려 귀가 쏠린다는 게 근거다(사장님 프로브 청취: "집중력이 확 쏠린다").
    # 기본값이 ["반전"]인 이유: 일반 톤 영상에서 반전 비트 하나만 속삭이는 게 강조 도구의
    # 기본 쓸모다. 강도(intensity)가 없는 것은 설계다 — 태그는 켜지거나 꺼질 뿐 중간이 없다.
    "whisper":       {"on": True, "roles": ["반전"]},
    # emphasis_roles: 마지막 어절을 "쉼표+느낌표"로 강조할 비트(2026-07-17 사장님 청취 판정 ③).
    # 훅만인 이유: 반전은 속삭이고 CTA는 [excited]가 이미 띄운다 — 거기에 느낌표까지
    # 붙이면 과해진다. 이 노브를 비우면(=[]) 옛 동작(부사 앞 쉼표만)으로 돌아간다.
    "intonation":    {"on": True, "intensity": 0.2, "emphasis_roles": ["훅"]},
    # max_fillers_per_text=1(구값)은 n = min(cap, _take_count(...))에서 cap이 항상
    # 병목이 돼 강도가 뭘 하든 결과가 늘 1개로 고정됐다(2026-07-15 컨트롤러 재현,
    # Task4 리뷰 Critical1 — "슬라이더를 돌렸는데 출력이 똑같다"는 이 재설계 전체의
    # 존재 이유를 기본 설정에서 그대로 재현하는 결함이었다). 실대본은 비트당 1~2
    # 문장이 보통이라 cap=2면 비례가 실제로 드러나고, 문장 수 자체를 넘는 추임새는
    # 어차피 `_take_count`가 막는다. 도배 방지는 캡이 아니라 `_beat_selected`(비트
    # 빈도 게이트)가 담당한다.
    # max_tags_per_beat=2(2026-07-16): [감정][whispers] 두 개를 허용한다. 사장님 청취
    # 판정 "4번이 좋다"(=[curious][whispers])가 근거 — 다만 그 조합은 **기본
    # 프로파일에선 도달 불가**라는 점을 정확히 적는다(리뷰 실측 정정, 이전 주석은
    # "기본값에서 이래서 2가 필요하다"처럼 읽혀 근거를 과장했다). 실제 기본값 실측:
    # ① 훅은 기본 `whisper.roles=["반전"]`에 없고 ② 반전은 기본 emotion_arc
    # intensity 0.3에서 `_role_tag_rank`(rank=2) >= n_tagged(2)라 애초에 감정태그를
    # 못 받는다 → 기본 출력은 `'[whispers] 이건, 진짜 물건이에요…'`뿐, 어떤 비트도
    # 태그 2개 조합이 안 된다. 2가 실제로 필요해지는 자리는 whisper.roles에
    # 훅/CTA가 들어간 프리셋(예: ASMR 톤 프리셋)에서 `[감정][whispers]`가 실제로
    # 만들어질 때다. 값 2 자체는 그대로 맞다 — **3 이상으로 올리지 않는다**(2가
    # 필요한 최대치라는 결론은 유지, 근거만 "기본값"이 아니라 "프리셋"으로 정정).
    "caps": {"max_tags_total": 3, "max_tags_per_beat": 2, "max_fillers_per_text": 2},
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


def _int_to_sino_4digit(n):
    """0~9999 전용 사이노 변환(그룹 단위 재사용 알맹이).

    한국어 숫자는 4자리씩 끊어 읽으므로(만/억/조), 이 함수가 각 그룹의 "자리별
    읽기" 알맹이를 담당하고 `_int_to_sino`가 그룹을 조립한다."""
    if n == 0:
        return ""
    pad = str(n).rjust(4, "0")
    out = ""
    for i, ch in enumerate(pad):
        d = int(ch)
        if d == 0:
            continue
        unit = ["천", "백", "십", ""][i]
        out += ("" if d == 1 and unit else _SINO[d]) + unit
    return out


# 4자리 그룹 단위(만/억/조). 그룹은 오른쪽(1의 자리)부터 4자리씩 끊는다 — 그룹0=일의
# 자리 그룹(단위 없음), 그룹1=만, 그룹2=억, 그룹3=조.
_GROUP_UNITS = ["", "만", "억", "조"]


def _int_to_sino(n):
    """정수 → 사이노 한국어 읽기. 만·억·조까지 지원(2026-07-17 확장).

    한국어는 4자리씩 끊어 읽는다(예: 12,345,678 → "천이백삼십사만 오천육백칠십팔").
    그룹마다 0이면 통째로 건너뛰고, 그룹 사이는 공백 하나로 구분한다(TTS가 끊어
    읽기 좋게).

    ⚠️ 만/억 비대칭은 의도적이다 — "만" 그룹이 1이면 "일만"이 아니라 "만"이라고만
    읽는다(10000원="만원"이 한국어 관용, "일만원"은 부자연스럽다). 반대로 "억"
    그룹이 1이면 "일억"이 자연스럽다(100000000="일억", "억"만 쓰면 어색하다).
    다음 사람이 "일관성 없다"며 이 비대칭을 고치면 오히려 어색해진다 — 고치지
    말 것(지시 원문 그대로 유지).
    """
    if n == 0:
        return "영"
    groups = []
    while n > 0:
        groups.append(n % 10000)
        n //= 10000
    parts = []
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi]
        if g == 0:
            continue
        word = _int_to_sino_4digit(g)
        unit = _GROUP_UNITS[gi] if gi < len(_GROUP_UNITS) else ""
        if gi == 1 and g == 1:
            # "만" 그룹만 1일 때 "일" 생략(한국어 관용) — 억 이상은 생략하지 않는다.
            parts.append(unit)
        else:
            parts.append(word + unit)
    return " ".join(parts)


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
        return _num_to_words(m.group(0).replace(",", ""))
    def numunit(m):
        return f"{_num_to_words(m.group(1).replace(',', ''))} {_UNIT_MAP[m.group(2)]}"
    # 천단위 쉼표(예: "2,847", "12,345,678")를 숫자의 일부로 인식한다 — 반드시
    # `\d{1,3}(?:,\d{3})+` 형태(3자리씩 끊긴 쉼표)만 묶는다. 일반 문장부호 쉼표
    # ("안녕, 1개")나 3자리가 아닌 쉼표("1,2")는 이 패턴에 안 걸려 그대로 남는다
    # (2026-07-17 결함 수정 — 옛 패턴은 쉼표를 아예 몰라 "2,847"을 "2"와 "847"로
    # 따로 잡고 쉼표를 그대로 흘렸다).
    num_pat = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
    unit_pat = r"(" + num_pat + r")(" + "|".join(sorted(_UNIT_MAP, key=len, reverse=True)) + r")"
    text, n1 = re.subn(unit_pat, numunit, text)
    text, n2 = re.subn(num_pat, num_repl, text)
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
# `("ㅂ니다", "요")`는 의도적으로 뺐다(Task3 재리뷰 N-1) — 실제 완성형 한글 텍스트에선
# 이 리터럴 패턴이 절대 매칭되지 않는 죽은 항목이었다: "쉽니다"/"갑니다"/"합니다" 등은
# 전부 완성형 음절(쉽·갑·합)로 저장되고, 여기 쓰인 `ㅂ`은 완성형 종성이 아니라 독립
# 자모 문자(U+3142)라 실제 타이핑된 한글 텍스트엔 나타나지 않는다(2026-07-15 컨트롤러
# 파이썬 재현: `re.search('ㅂ니다', '쉽니다')` → None, `re.search('ㅂ니다', '갑니다')`
# → None). 게다가 우변 `요`는 명사 꼬리(중요/필요)와 충돌해 `_ENDING_SUFFIXES`에 안전하게
# 넣을 수도 없다(단음절 금지 원칙, 아래 참조). 죽은 코드 + 안전하게 못 고치는 우변이라
# 항목 자체를 삭제한다 — "-ㅂ니다"류 종결어미의 실전 형태(완성형 종성 패턴)는 이미
# `습니다`/`합니다`/`겠습니다`가 커버한다.
_SPOKEN_MAP = [
    ("있습니다", "있어요"), ("없습니다", "없어요"), ("좋습니다", "좋아요"),
    ("같습니다", "같아요"), ("합니다", "해요"), ("됩니다", "돼요"),
    ("입니다", "이에요"), ("습니다", "어요"),
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
# ⚠️ 단독 `요`/`다`는 절대 쓰지 마라(2026-07-15 컨트롤러 실측 오탐) —
#   '이거 하나면 다 돼요'는 부사 '다'에, '중요/필요/주요 포인트예요'는 명사 꼬리 '요'에
#   달라붙어 진짜 종결어미(돼요/포인트예요) 대신 엉뚱한 곳에 `…`가 박힌다. 강도가
#   낮을수록(=후보 1개만 취함) 위치상 앞선 오탐이 진짜 종결어미보다 먼저 뽑혀 더 틀린다.
#   `_CONNECTIVES`가 이미 세운 원칙("오탐 0이 더 중요")을 그대로 따라 — 명시적
#   다음절 종결어미만 나열한다(서버 실측 대본 기준).
#   `죠`는 단음절이지만 예외로 남긴다(Task3 재리뷰 Minor — 주석·코드 불일치 수정) —
#   `지요`의 축약형이라 명사 마지막 음절로 실사용되는 사례가 사실상 없다(예:
#   "참고"/"과자"/"의자"는 전부 `자`로 끝나지 `죠`가 아니다). `요`/`다`가 명사·부사
#   음절로 흔한 것과 위험도가 근본적으로 다르므로 유지한다.
#
# `_spoken_style`이 `_endings`보다 먼저 돌며 종결어미를 새로 만들어낸다(됩니다→돼요,
# 드립니다→드려요, `_SPOKEN_MAP` 참조) — 그 산출물을 여기서 못 받으면 파이프라인이
# 자기가 만든 어미를 자기가 못 보는 결함이 된다(2026-07-15 Task3 재리뷰 N-1: 튜닝
# 코퍼스엔 마침표가 없어 tail 경로가 유일한 경로라 이 결함이 그 자리에서만 드러난다).
# `돼요`·`드려요`는 이 이유로 추가한다(둘 다 다음절이라 오탐 0 원칙 위배 없음).
#
# 추가 검토(Task3 재리뷰 N-1 지시, 후보 전부 다음절이라 단독 요/다 금지 원칙과 무관):
#   `져요`(바삭해져요·깨끗해져요·달라져요 — 커머스 카피 상용, 명사·부사 꼬리 충돌
#     없음 → 채택. 우선순위 최상 지시대로 반영).
#   `데요`(좋은데요 — 문장 서술어 끝에서만 쓰이고 명사 꼬리 충돌 없음 → 채택).
#   `봐요`(해 봐요·먹어 봐요 — '봐'로 끝나는 명사가 사실상 없음 → 채택).
#   `게요`(할게요, CTA) → 보류: "집게"·"지게"(도구/운반구 명사) + 구어체 종결 조사
#     '요'가 "집게요"/"지게요"(예: "이거 집게요") 형태로 실사용되어 오탐 위험이
#     있다. 쇼핑 콘텐츠는 소품 명사가 자주 등장하는 도메인이라 특히 위험 — 오탐 0
#     원칙상 보류.
#   `러요`(눌러요 — tests/test_naturalize.py 샘플에 이미 존재) → 보류: "달러"·
#     "트레일러" 등 명사가 "달러요"/"트레일러요"(가격 안내 "몇 달러요?")로 실사용되고,
#     이 엔진의 도메인(쇼핑 나레이션)에서 가격 언급 빈도가 높아 충돌 위험이 크다.
#     오탐 0 원칙상 보류(놓치는 건 안전하니 false negative로 남긴다).
_ENDING_SUFFIXES = ["거든요", "라고요", "세요", "니다", "해요",
                    "어요", "아요", "에요", "예요", "네요", "죠",
                    "돼요", "드려요", "져요", "데요", "봐요"]
_ENDING_TAIL = re.compile(
    "(?:" + "|".join(sorted(_ENDING_SUFFIXES, key=len, reverse=True)) + r")(?=\s|$)"
)


# 의문형이 **확실한** 어미만 넣는다. "세요"는 뺐다 — "해보세요"는 명령형이라 물음표를
# 달면 문장이 뒤집힌다. 확신이 없으면 넣지 않는 쪽으로 실패시킨다(평서문에 물음표가
# 붙는 건 사장님 귀에 바로 걸리지만, 안 붙은 건 현행과 같다 — `_CONNECTIVES`/
# `_ENDING_SUFFIXES`가 이미 세운 "오탐 0이 더 중요" 원칙과 동일).
#
# ㄴ가요 융합형 정정(2026-07-17, 사장님 지시 — Task3 amendment3의 오류 수정).
# amendment3의 "죽은 분기" 진단은 맞았다: `ㄴ가요`라는 리터럴 자모(U+3134)는
# 완성형 한글엔 절대 안 나타난다. 하지만 그 뒤에 붙인 "은가요/는가요가 나머지를
# 커버한다"는 결론은 틀렸다 — `건가요`("것"+"이다"+ㄴ가요가 한 음절로 융합)는
# `건`으로 시작하지 `은`/`는`으로 시작하지 않아 "은가요"/"는가요" 어느 쪽에도
# 안 걸린다(실측: '다들 이러고 사는 건가요.'가 훅에서 "건가요!"로 감탄되고
# 페인포인트에서 "건가요…"로 끝이 처졌다 — 사장님이 직접 지적, 이 정정의 근거).
#
# 두 가지 보강안을 검토했다:
#   (a) 명시적 표면형 나열 — 검증된 안전한 것만 리터럴로 추가.
#   (b) 종성 산술 — `[가-힣]가요$`이고 그 앞 음절 종성이 ㄴ인 모든 경우를 코드로
#       계산(`(ord(ch)-0xAC00)%28==4`). 정규식 하나로 못 쓰고 코드 검사가 필요할
#       뿐 아니라, "가요"는 명사이기도 하다(歌謠="노래") — `이건 국민가요.`에서
#       `가요` 바로 앞 음절 `민`도 종성이 ㄴ이라 (b)를 그대로 쓰면 이 평서문을
#       물음표로 뒤집는다. 실측(`naturalize('이건 국민가요.', merge_profile({}),
#       beat_role='훅')` / `beat_role='페인포인트'`) — 둘 다 기본 프로파일
#       `question_roles`에 있어 이 스테이지를 실제로 통과하므로 이 오발동은
#       도달 가능하다(가정이 아니라 실측).
# → (a) 채택. 아래 4개는 리터럴 문자열이라 "국민가요"(공백으로 분리된 "이건"+
# "국민가요")의 부분문자열이 아니다 — "건가요"/"인가요"/"계신가요"/"큰가요" 중
# 어느 것도 "국민가요"(국,민,가,요) 안에 연속으로 나타나지 않는다. (b)와 달리
# 이 오탐이 구조적으로 안 생긴다.
#   `인가요`("이다"+ㄴ가요, 예: "이거 신상인가요") · `건가요`("이거"+"인가요"의
#   축약, 예: "이게 그건가요") · `계신가요`(높임 "계시다"+ㄴ가요, 예: "안에
#   계신가요") · `큰가요`("크다"+ㄴ가요, 예: "이거 많이 큰가요") — 넷 다
#   "이다/있다/크다"류 어간에서만 만들어지는 종결형이라 명사 꼬리와 충돌할
#   자리가 없다. 더 넓히지 않는다 — 검증 안 된 표면형을 넣으면 `_ENDING_SUFFIXES`가
#   세운 "오탐 0이 더 중요" 원칙이 깨진다(under-fire는 안전, over-fire는 사고).
#
# "까요"가 이미 모든 "-ㄹ까요"류(할까요·갈까요)를 앞 음절과 무관하게 끝에서부터
# 잡으므로("까요" 자체가 끝-2글자 앵커) 그쪽은 실손실 없다.
#
# 을까요도 뺐다(Task3 amendment3 확장검토, "Be conservative" 최종 목록에도 없다) —
# 실측(`있을까요`/`할까요`류로 확인): "까요"가 이미 접미어로 걸리는 위치(끝에서
# 2글자)까지만 실제로 효과가 나므로 "을까요" 앞에 뭐가 오든 재구성 결과(`text[:m.start()]
# + m.group(1) + "?"`)가 바이트 단위로 동일하다 — 매치 시작점만 다르고 끝점이 같아
# 최종 출력이 안 갈린다. 있으나 없으나 행동에 영향이 없는 죽은 분기다.
#
# 까요 정정(재리뷰 Finding1, Critical, 2026-07-17). 위 두 문단은 **회수(recall)만**
# 따졌다 — "이 표면형이 명사/평서형과 겹치는가"(false-fire) 질문을 "까요" 자신에는
# 한 번도 안 던졌다. "나요" 정정(아래)에서 세운 규율을 "까요"에는 적용하지 않은
# 게 재발 원인이다("가요"→국민가요, "나요"→끝나요, "하나요"→하나(수사)에 이어
# 이 트랙에서 네 번째로 같은 사고 클래스가 나온 것). "까요"는 "까다"(껍질을
# 벗기다)의 해요체 평서형과 표면이 완전히 겹치고, 쇼핑 콘텐츠 도메인(과일·채소
# 손질)에서 실사용 빈도가 높은 동사다. 실측(사장님 재현, `merge_profile({})`,
# role=페인포인트):
#   '귤은 손으로 까요.'          -> '귤은 손으로 까요?'          (FLIPPED)
#   '마늘은 이렇게 까요.'        -> '마늘은 이렇게 까요?'        (FLIPPED)
#   '밤을 하나하나 손으로 까요.'  -> '밤을 하나하나 손으로 까요?'  (FLIPPED)
# "가요"/"나요"와 달리 "까요"를 통째로 빼면 진짜 의문형(살까요·될까요류) 회수를
# 전부 잃는다 — 대신 **구조적 판별자**를 쓴다. 한국어 어절(띄어쓰기) 규칙상
# "-(으)ㄹ까요" 의문형 어미는 항상 어간에 공백 없이 융합되고(살까요=사+ㄹ까요,
# 하셨을까요=하+셨+을+까요 — 전부 한 어절), "까다" 평서형의 "까요"는 그 자체가
# 독립된 어절이라 항상 앞에 공백이 온다(예: "손으로 까요"). `(?<=[가-힣])까요`
# (바로 앞에 공백 없이 한글 음절이 붙어있을 때만 매치)로 이 둘을 가른다 —
# 실측: 위 3개 평서문은 전부 매치 안 되고(공백이 앞에 있어서), "살까요"·"될까요"·
# "씨름하셨을까요"(위 을까요/ㄹ까요 코퍼스)는 전부 그대로 매치된다(회수 손실 0).
# 판별자가 못 가르는 잔여 위험(의성어를 공백 없이 붙여 쓰는 비표준 표기, 예:
# "톡까요")은 실사용 코퍼스에 없어 감수한다 — 그 경우도 under-fire(못 잡음)이지
# over-fire(평서문이 뒤집힘)가 아니므로 이 파일의 바인딩 원칙("발동 안 하는 게
# 잘못 발동하는 것보다 안전하다")과 그대로 일치한다.
#
# 나요 정정(리뷰 지적 Finding1, 2026-07-17). 위 가요 계열 분석에서 던진 질문
# ("이 표면형이 명사/평서형과 겹치는가")을 "나요" 자신에는 안 던졌었다 — 옛
# 목록엔 판별 음절 없는 리터럴 그대로 "나요"(2글자)가 있었다. "가요" 계열이
# 위험했던 이유는 "가요"(歌謠, 노래)라는 2음절 명사와 표면이 겹쳐서였고, 채택한
# 안전장치는 "은가요/는가요/인가요/건가요/계신가요/큰가요"처럼 판별 음절을 앞에
# 붙인 표면형이었다. "나요"는 "있다/없다/이다/크다"류 서술격·존재사에만 붙는 어미가
# 아니라 **모든 동사 어간**에 "-나요?"로 붙는 일반 의문형 어미다 — 그런데 해요체
# 평서형은 "-아/어/여요"로 끝나지 "나요"로 안 끝난다. 문제는 어간이 "나"로
# 끝나는 동사(끝나다·늘어나다·만나다·일어나다 — 전부 쇼핑 내레이션 핵심 어휘)의
# 평서형 "-나요"(끝나+요→끝나요)가 어간+"나요" 리터럴과 표면이 완전히 겹치는
# 것이었다. 실측(사장님 재현, `merge_profile({})`, role=페인포인트):
#   '이 세일 곧 끝나요.'      -> '이 세일 곧 끝나요?'      (FLIPPED)
#   '쓸수록 용량이 늘어나요.'  -> '쓸수록 용량이 늘어나요?'  (FLIPPED)
#   '내일 여기서 만나요.'      -> '내일 여기서 만나요?'      (FLIPPED)
#   '아침마다 일찍 일어나요.'  -> '아침마다 일찍 일어나요?'  (FLIPPED)
# → 가요 계열과 같은 해법(a안: 검증된 명시적 표면형만 리터럴로) 적용, 바레 "나요"는 뺀다.
#
# 후보별 판정 — 각 후보로 끝나는 평서문을 직접 구성해봤다:
#   채택 — 있나요/없나요/되나요/맞나요/않나요: "있다/없다/되다/맞다/(-지)않다"의
#     해요체 평서형은 "있어요/없어요/돼요/맞아요/않아요"다(회귀 테스트 코퍼스에
#     이미 있던 "닦기도 귀찮지 않나요." 실측으로 "않나요" 누락이 드러났다 — 좁히는
#     김에 "않으세요"의 평서형 짝을 빠뜨렸었다). 이 다섯 표면형으로 끝나는 평서문을
#     시도했지만 못 만든다 — "-나요" 의문형 어미가 이미 사전 결합돼 있어 평서형과
#     겹칠 표면 자체가 없다.
#   채택 — 았나요/었나요/였나요/셨나요(과거 의문): 해요체 평서 과거형은
#     "-았/었/였어요"·"-으셨어요"다. "써보셨나요"/"봤나요"/"하셨나요"류로
#     과거+나요 조합 평서문도 시도했지만 못 만든다 — 과거 평서형 표면 자체가
#     "나요"로 안 끝난다.
#   기각 — 하나요: "하다"+"-나요"(예: "이용하나요")뿐 아니라 수사 "하나"(1개) +
#     명사 서술 축약 "요"(= "가요"가 "이다"+"요"로 축약되는 것과 동일 구조)가
#     겹친다. 실제로 구성 가능: '사은품은 딱 하나요.'("한 개예요"의 준말)는
#     쇼핑 내레이션에서 완전히 자연스러운 평서문이다 — "국민가요"(노래)와
#     정확히 같은 사고 클래스라 뺀다. 대가는 "구매하나요"/"이용하나요" 같은
#     의문형이 올리개에서 안 걸리는 것뿐이고(under-fire, 안전), 가드는 아래
#     `_QUESTION_GUARD_ALTS`의 바레 "나요"로 여전히 이 표면형을 느슨하게
#     커버한다(무해).
# 목록은 `_QUESTION_TAIL_ALTS`로 한 곳에 모아 가드가 상위집합을 구조적으로
# 보장하게 한다(리뷰 지적 Finding2·Finding3 — 손으로 맞춘 두 목록은 다시 어긋난다).
#
# 않으세요·없으세요 정정(재리뷰 Finding2, Important, 2026-07-17) — **정책 변경**으로
# 올리개(엄격)에서 아예 뺀다. 둘 다 `세요` 계열이라 존댓말 평서형과 표면이 완전히
# 겹친다 — "세요"를 애초에 뺀 이유(해보세요=명령형)와 같은 클래스지만, 이번엔
# 판별자 자체가 없다(재리뷰가 확인, 나도 재확인함): 존댓말에서 평서·의문은 표기가
# 원천적으로 동일하다. 실측(`merge_profile({})`, role=페인포인트):
#   '장인은 기계를 쓰지 않으세요.'            -> '장인은 기계를 쓰지 않으세요?'  (FLIPPED)
#   '사장님은 주말에도 쉬는 날이 없으세요.'   -> '사장님은 주말에도 쉬는 날이 없으세요?'  (FLIPPED)
# 브랜드스토리 내레이션("장인은 기계를 안 쓴다")은 실제 코퍼스 형태라 감수할
# 수 없는 사고다. 대가는 "닦기도 귀찮지 않으세요?"류 표기 하나뿐이다 — 같은
# 페인포인트 질문이 "않나요" 표기(브리프 원 코퍼스가 실제로 쓰는 형태,
# `"...귀찮지 않나요."`)로 이미 살아 있다(위 나요 채택 목록 참조). 가드(느슨)에는
# 계속 남긴다 — `_QUESTION_GUARD_ALTS`에 명시 리터럴로 추가한다(아래). 훅 꼬리
# 강조 억제는 오발동해도 무해하므로 여기서만 넓게 잡는 게 안전하다.
_QUESTION_TAIL_ALTS = (
    "았나요", "었나요", "였나요", "셨나요",
    "있나요", "없나요", "되나요", "맞나요", "않나요",
    "까요", "은가요", "는가요", "던가요",
    "인가요", "건가요", "계신가요", "큰가요",
)
# "까요"만 예외 처리 — Finding1 판별자(위 주석)를 여기서 심는다. 다른 alt는
# 리터럴 그대로 alternation에 넣지만, "까요"는 `(?<=[가-힣])까요`로 바꿔 넣어
# 앞에 공백 없이 한글 음절이 붙어있을 때만 매치하게 한다. 이 함수는 이 파일
# 안에서 **여기서만** 쓰인다 — 가드(`_QUESTION_GUARD_ALTS`/`_QUESTION_GUARD_PAT`)는
# `_QUESTION_TAIL_ALTS`의 리터럴 값("까요" 그대로, 판별자 없음)을 그대로 쓴다
# (의도적으로 느슨함, Finding1 결론 그대로).
def _strict_alt_pattern(alt):
    return r"(?<=[가-힣])까요" if alt == "까요" else alt


_QUESTION_TAIL_PAT = re.compile(
    "(" + "|".join(_strict_alt_pattern(a)
                   for a in sorted(_QUESTION_TAIL_ALTS, key=len, reverse=True)) + ")"
    r"\s*([.…]*)\s*$"
)

# 가드(guard) 전용 — `_intonation`의 훅꼬리 강조 억제. 위 `_QUESTION_TAIL_PAT`
# (올리개, raiser)과 반대 위험 프로필이다(사장님 정정, 2026-07-17 — Task3
# amendment2가 "판정을 한 곳에서 관리한다"까지는 맞았지만, 위험이 반대인 두
# 판정을 문턱 하나로 묶은 게 `건가요` 사고의 근본원인이었다):
#   올리개가 잘못 발동 → 평서문이 물음표로 뒤집힘(의미 사고, 사장님이 바로 듣는다)
#   가드가 잘못 발동  → 훅 꼬리 강조 하나를 놓칠 뿐(무해, 문장은 그대로 읽힌다)
# 그래서 가드는 올리개보다 **의도적으로 넓다**(loose superset — 올리개가 매치하면
# 가드도 반드시 매치한다).
#
# 상위집합을 "주석으로 약속"만 하지 않고 **구조적으로** 만든다(리뷰 지적
# Finding2·Finding3 정정, 2026-07-17 — 옛 코드는 `_QUESTION_TAIL_PAT`과
# `_QUESTION_GUARD_PAT`을 각자 손으로 쓴 리터럴 목록으로 관리했는데, 올리개
# 목록에만 있던 `않으세요`/`없으세요`가 가드 목록엔 안 들어가 있었다(실측:
# '닦기도 귀찮지 않으세요.'/'이런 거 없으세요.'가 raiser=True, guard=False).
# `endings.on=False`(가드가 유일한 방어선)에서 `건가요!`류와 같은 사고 클래스가
# 재현됐다: `[curious] 닦기도 귀찮지, 않으세요!`. `_QUESTION_TAIL_ALTS`를 그대로
# 합집합에 넣으면(아래) 올리개 목록이 앞으로 늘어도 가드가 자동으로 따라온다 —
# 손으로 두 목록을 맞출 필요가 없다. 거기에 원래 목적(아직 리터럴로 못 나열한
# 미지 ㄴ가요 융합형까지 붙잡기)을 위해 순수 리터럴 "가요"/"까요"/"나요"도 계속
# 얹는다 — "나요"는 올리개에서 뺐지만(위 나요 정정 참조) 가드는 오발동해도
# 무해하므로 그대로 유지한다: 이러면 `건가요`류처럼 아직 리터럴로 못 나열한
# ㄴ가요 융합형이 나와도(예: 목록에 없는 새 어간) 가드가 먼저 걸려 최소한
# "느낌표로 덮어쓰기" 사고는 막는다. 대가는 "이건 국민가요."(명사) 같은 평서문도
# 걸려 훅 꼬리 강조 하나를 잃는 것뿐이다 — 표의 판정대로 이쪽이 감수할 만하다.
#
# 이 파일 안에 문턱 두 개를 나란히 정의해두는 것 자체가 이번 정정의 핵심이다:
# "한 자리, 두 문턱"이지 "따로 조립"이 아니다 — 두 판정이 다시 갈라져 각자
# 관리되면 이 트랙 최악의 사고(2026-07-15 10 seams, "같은 것을 두 곳이 각자
# 조립")가 재발한다.
#
# 않으세요·없으세요를 여기 명시로 다시 얹는다(재리뷰 Finding2 정정, 2026-07-17) —
# 위에서 `_QUESTION_TAIL_ALTS`(올리개)에서 이 둘을 정책상 뺐으므로(존댓말
# 평서·의문 표기가 원천적으로 동일해 판별자가 없음), 자동 합집합만으로는 더 이상
# 가드에 안 들어온다. 하지만 가드는 오발동해도 무해하다(훅 꼬리 강조 하나를
# 놓칠 뿐)는 원칙은 그대로이므로, 올리개에서 뺀 것과 무관하게 가드에는 계속
# 명시로 남긴다 — 안 그러면 `endings.on=False`(가드가 유일한 방어선)에서
# `건가요!`류와 같은 사고 클래스가 재현된다(`[curious] 닦기도 귀찮지, 않으세요!`).
_QUESTION_GUARD_ALTS = tuple(sorted(
    set(_QUESTION_TAIL_ALTS) | {"가요", "까요", "나요", "않으세요", "없으세요"},
    # Finding3(Minor, 2026-07-17) 정정 — 기존 `key=len`은 동길이 항목의 순서를
    # set 반복순서(=PYTHONHASHSEED 의존)에 맡겼다. 재리뷰가 576케이스×5시드로
    # 행동상 무해함(digest 동일)을 실측했지만, `key=len`이라는 표기 자체가
    # "순서가 의미 있다"처럼 읽혀 오해를 부른다 — 길이 동률을 문자열 자체로
    # 마저 끊어 완전 결정적으로 만든다(행동은 이미 무해했으므로 이 변경으로
    # 테스트 결과가 바뀌지 않는다 — 위생 정정).
    key=lambda s: (-len(s), s),
))
_QUESTION_GUARD_PAT = re.compile(
    "(" + "|".join(_QUESTION_GUARD_ALTS) + ")" r"\s*([.…!?]*)\s*$"
)


def _question_tail_match(text):
    """의문형 어미(확실한 것만, **엄격** 판정) 매치 — None이면 대상 아님.

    `_endings`(끝음 물음표 되돌리기, 올리개)가 이 판정을 쓴다. 오발동 비용이
    크므로(평서문 의미가 물음표로 뒤집힘) 엄격한 목록(`_QUESTION_TAIL_PAT`)만
    허용한다 — `_is_interrogative`가 쓰는 느슨한 가드(`_QUESTION_GUARD_PAT`)와는
    의도적으로 다른 문턱이다(위 두 패턴 정의 옆 주석 참조)."""
    return _QUESTION_TAIL_PAT.search(text)


def _is_interrogative(text):
    """텍스트가 의문형으로 끝나는가 — '?'로 이미 끝나거나, **느슨한** 의문형 어미
    패턴(`_QUESTION_GUARD_PAT`)에 걸린다(둘 중 하나면 True).

    `_intonation`의 훅 꼬리 강조 가드 전용이다. `_question_tail_match`(올리개,
    엄격)보다 의도적으로 넓게 잡는다 — 잘못 걸려도 강조 하나를 잃을 뿐이라,
    좁혔다가 의문형에 느낌표가 붙는 의미 사고(`건가요!`)가 나는 쪽보다 훨씬
    싸다. 보통은 `_endings`가 이 스테이지보다 먼저 돌아 의문형 어미를 이미
    "?"로 바꿔놔서 첫 조건이 잡지만, `_endings`가 꺼져 있거나(intensity 0·
    해당 role이 question_roles 밖) 아직 "?"가 안 박힌 상태에서도 이 느슨한
    패턴이 독립적으로 판정한다(방어의 이중화)."""
    return "?" in text or _QUESTION_GUARD_PAT.search(text) is not None


def _endings(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity <= 0:
        return text
    # ── 의문형 → 물음표 (사장님 지시 2026-07-17: "의문형은 부호가 없어요 끝을
    # 자연스럽게 올린다" — amendment1로 페인포인트에서 훅까지 범위 확장) ──
    # 애초엔 페인포인트뿐이었다: 끝음을 올려 되묻는 건 아픈 곳을 찌르는 자리의
    # 문법이라는 근거. 그런데 실측(기본 프로파일, role=훅)에서 대본이 "?" 없이
    # 의문형으로 끝나면(예: "왜 다들 이걸 살까요.") `_intonation`의 훅 꼬리 강조
    # 규칙이 그대로 "살까요!"로 덮어써버렸다 — 이 코퍼스는 의문문에 부호를 안 다는
    # 게 표준 표기라 페인포인트만으로는 이 사고를 못 막는다.
    #
    # 기존 dot/tail 치환보다 **먼저** 돌린다.
    # ⚠️ 뮤테이션 실측(M2, Task3): 뒤로 옮겨도 **최종 텍스트는 안 깨진다** — 아래
    # 재구성이 `text[:_m.start()] + _m.group(1) + "?"`로 뒷꼬리 구두점(group 2, "."든
    # "…"든)을 항상 통째로 버리기 때문에, dot/tail이 먼저 "."를 "…"로 바꿔놔도
    # 의문형 블록이 그 "…"까지 다시 삼켜 "?"로 정확히 재구성한다("이거." → "이거…"로
    # 처지는 일은 실제로 안 생긴다 — 이전 버전 이 주석의 주장은 틀렸다). 진짜 이유는
    # **카운트**다: 뒤로 옮기면 dot/tail이 같은 문장 끝에서 1회 `_bump`하고 의문형
    # 블록이 그 결과를 다시 봐서 또 1회 `_bump`해 `applied["endings"]`가 눈에 보이는
    # 변화 1건에 2로 거짓 계상된다(`_intonation`의 `ca92f9c8`류 유령 카운트와 동일
    # 결함 클래스 — `test_question_conversion_counts_once_not_twice` 참조). 순서를
    # 앞에 두면 dot/tail의 후보 목록 계산 시점에 이미 "?"가 박혀 있어 dot 패턴도
    # tail 패턴도 그 위치에 안 걸리므로(둘 다 마침표나 한글 어미 뒤 공백/끝을
    # 요구하는데 "?"가 그 자리를 막는다) 애초에 두 번 셀 후보 자체가 안 생긴다.
    if ctx.get("role_canon") in (cfg.get("question_roles") or []):
        _m = _question_tail_match(text)
        if _m:
            before = text
            text = f"{text[:_m.start()]}{_m.group(1)}?"
            if text != before:
                _bump(ctx, "endings", 1)
    # 후보: ① 마침표 ② 마침표 없는 종결어미. 위치 순으로 앞에서부터 강도 비율만.
    # dot 스팬(".")과 tail 스팬(다음절 어미, 전부 한글 문자)이 절대 겹칠 수 없다는 게 이
    # 정렬의 전제다 — 안전한 이유는 "인접 배제"가 아니라 문자 집합이 서로소라는 것이다
    # (Task3 재리뷰 Minor: 이전 주석은 tail의 (?=\s|$) lookahead가 마침표 바로 앞
    # 위치에서 tail을 못 뜨게 막는다는 인접 배제 논증을 폈지만, 인접은 애초에 위협이
    # 아니다 — 겹치지만 않으면 인접한 두 스팬을 역순 적용해도 서로 침범하지 않는다.
    # 진짜 근거는 dot 매치가 항상 문자 "."이고 tail 매치는 항상 한글 어미 문자열이라
    # 두 문자 집합이 겹치지 않으므로, 같은 위치의 스팬이 dot이면서 동시에 tail일 수
    # 없다는 것뿐이다). 그래서 dot·tail 후보는 항상 서로 다른 위치를 가리키고, 정렬
    # 후 취해도 안전하다.
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


def _sentence_starts(text):
    """문장 시작 오프셋들. 추임새를 문장 앞에 붙이기 위한 후보 목록.

    `…`를 문장 구분자로 인식하는 건 의도적이다(M1) — `_endings`가 이 함수보다
    먼저 돌아 마침표 없는 문장 끝에 `…`를 새로 만들어 넣을 수 있는데(예: tail
    경로), 그 결과물을 여기서 문장 경계로 못 읽으면 파이프라인이 자기가 만든
    구분자를 자기가 못 보는 결함이 된다(`_endings` 주석의 "자기가 만든 걸
    자기가 못 봄" 계열과 동일 원칙). 다만 부작용도 있다 — 마침표 없는 코퍼스에서는
    `_endings`가 넣은 `…` 개수가 그대로 문장 경계 개수가 되므로, 추임새 개수가
    간접적으로 끝음(endings) 강도 슬라이더의 함수가 된다. 의미상 타당한
    트레이드오프라 그대로 둔다."""
    starts = [0]
    for m in re.finditer(r"(?<=[.!?…])\s+", text):
        if m.end() < len(text):
            starts.append(m.end())
    return starts


def _beat_selected(bi, intensity):
    """이 비트가 추임새 발동 대상인지 — Bresenham식 균등분배(I1 수정).

    옛 `every = round(1.0/intensity)`(역수·반올림)는 강도가 클수록 양자화가 거칠어져
    슬라이더 상단이 평지가 됐다(2026-07-15 리뷰 실측: 작업대 10비트·21개 슬라이더
    위치 중 13개가 단 2칸에 갇힘 — 0.40~0.65가 전부 "every=2", 0.70~1.00이 전부
    "every=1"로 뭉쳤다). `_take_count`가 이미 쓰는 철학(선형·단조, "내림이면 슬라이더가
    계단이 된다")을 비트 축에도 그대로 적용한다 — (bi-1, bi] 구간에 발동 경계가
    있는지로 판정하면(고전 Bresenham 직선 알고리즘과 동일한 형태) 강도가 오를수록
    선택 비트 수가 절대 줄지 않고, 역수 양자화 특유의 평지도 생기지 않는다(실측:
    10비트 기준 [0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10] — 최대 2칸 겹침).

    비교 방향을 `bi+1` 대신 `bi-1`로 잡은 이유: bi=0에서 intensity>0이면
    `floor(0*i)=0 != floor(-i)=-1`이라 **항상** 선택된다 — 단일 비트 프리뷰
    (beat_total=1)나 스크립트 맨 첫 비트가 낮은 강도에서 영원히 스킵되는 걸
    막는다(순방향 비교였다면 bi=0은 intensity==1.0이 아닌 한 절대 선택 못 하는
    새 회귀가 생겼을 것). 이 텔레스코핑 항등식 덕에 "몇 번째로 선택됐는가"(뱅크
    순환에 쓰는 sel_idx)는 어느 방향으로 잡아도 `math.floor(bi * intensity)`로
    동일하다."""
    if intensity <= 0:
        return False
    if intensity >= 1.0:
        return True
    return math.floor(bi * intensity) != math.floor((bi - 1) * intensity)


def _fillers(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.2)
    bank = cfg.get("bank") or ["음"]
    cap = ctx["caps"].get("max_fillers_per_text", 1)
    if not text or not text.strip():   # M4: 대상 자체가 없는 빈/공백 텍스트는 손대지 않는다
        return text
    # 역할 게이트 — `_whisper`와 같은 구조(설계 통일). roles가 **없으면** 전 비트에
    # 적용한다(옛 프리셋 호환): 저장된 프리셋엔 이 키가 없고, 없는 걸 "아무 비트도
    # 아님"으로 읽으면 기존 프리셋의 추임새가 조용히 통째로 사라진다.
    roles = cfg.get("roles")
    if roles is not None:
        canon = ctx.get("role_canon")
        if canon is None or canon not in roles:
            return text

    # 멱등 가드 — 대본에 이미 추임새가 있으면 손대지 않는다.
    # ★2026-07-17 실사고: 대본 "와, 요새…"에 엔진이 "[curious] 음,"을 덧붙여
    # "음, 와, 요새…"가 나왔다. 사장님의 "억양이 부자연스럽다"가 이것이었다.
    # 태그 묶음은 emotion_arc가 앞에 붙이므로 벗겨내고 본문 첫 어절만 본다.
    _m = _LEADING_TAGS_PAT.match(text)
    _body = text[_m.end():] if _m else text
    _lead = _LEADING_INTERJECTION_PAT.match(_body)
    if _lead and _lead.group(1) in _INTERJECTIONS:
        return text
    if intensity <= 0 or cap <= 0:
        return text
    bi = ctx.get("beat_index") or 0
    if not _beat_selected(bi, intensity):
        return text
    # 발동 순번(0-index)으로 뱅크를 순환한다(I2 수정) — 비트 인덱스(bi)로 직접
    # 인덱싱하면 gcd(선택주기, len(bank))>1일 때 순환이 붕괴해 항상 같은 추임새만
    # 나왔다(기본값 재현: every=5·bank 5종 → 선택 비트가 {0,5}뿐이라 bank[0],bank[0]
    # = "음","음"만 들림 — 게이트가 없던 시절엔 bi가 0,1,2,3…을 다 훑어 문제가
    # 없었던 게 이 태스크가 게이트를 넣으며 새로 만든 결함이었다). sel_idx는
    # 선택될 때마다 정확히 1씩 늘어나(위 텔레스코핑 항등식) bank 전체를 실제로 순환한다.
    sel_idx = math.floor(bi * intensity) if intensity < 1.0 else bi
    # 텍스트 내 개수: 문장 수 × 강도(올림), cap 이하.
    starts = _sentence_starts(text)
    n = min(cap, _take_count(len(starts), intensity))
    if n <= 0:
        return text
    for k, pos in enumerate(sorted(starts[:n], reverse=True)):
        filler = bank[(sel_idx + (n - 1 - k)) % len(bank)]   # 비트·문장별 결정적 순환
        text = text[:pos] + f"{filler}, " + text[pos:]
    _bump(ctx, "fillers", n)
    return text


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


def _tag_priority(total):
    """태그를 붙일 비트 우선순위(비트 인덱스 순서) — **미지 role 위치폴백 전용**
    (Task5 I1 재리뷰 이후로는 정본 role엔 안 쓰인다, 아래 `_TAG_ROLE_PRIORITY` 참조).

    태그 예산(`n_tagged`, 강도가 정한 "태그 붙는 비트 개수")이 비트 총수보다 적을 때
    어디부터 쓸지의 배분이다 — 첫 비트 → 마지막 비트 → 나머지는 앞에서부터.
    감정곡선상 가장 중요한 자리(오프닝의 호기심, 클로징)를 예산이 적어도 항상 먼저
    채운다. role을 모를 때(작업대 옛 코퍼스의 `body`/`build` 등)만 `_emotion_arc`가
    이 순서의 앞 n_tagged개에 현재 비트가 속하는지로 발동 여부를 결정한다.

    ⚠️ 이 함수 자체는 태그 불가능한 위치(`_pos_tag`가 None인 자리)를 걸러내지
    않는다 — 실제 발동 판정(`_emotion_arc`)은 반드시 `_tag_priority_taggable`을
    통해 걸러진 순서를 써야 한다(Task5 I2, 아래 참조).

    `total <= 0` 분기는 방어 코드다 — 유일한 호출부(`_emotion_arc` 위치폴백 경로)가
    항상 `ctx.get("beat_total") or 1`로 부르므로 실제로는 도달 불가(total>=1 보장).
    """
    if total <= 0:
        return []
    order = [0]
    if total > 1:
        order.append(total - 1)
    order += [i for i in range(1, total - 1)]
    return order


def _pos_tag(bi, total):
    """위치기반 폴백 전용 — (비트 인덱스, 비트 총수)만으로 이 위치가 태그 가능한지,
    가능하다면 무슨 태그인지를 결정적으로 계산한다. 다른 비트의 role을 몰라도
    이 계산은 항상 가능하다(Task5 I2 재리뷰 — 이 사실이 예산 낭비를 막는 근거).

    `_tag_for`(실제 태그 결정)와 `_tag_priority_taggable`(예산 판정용 필터)이
    이 하나의 함수를 공유한다 — 두 곳이 각자 계산하면 정의가 어긋날 위험이 있다."""
    if bi is None or not total:
        return None
    n = max(1, total - 1)
    raw_pos = round((bi / n) * (len(_ARC_BY_POS) - 1))
    pos = min(len(_ARC_BY_POS) - 1, max(0, raw_pos))
    return _ARC_BY_POS[pos]


def _tag_priority_taggable(total):
    """위치폴백 전용 우선순위 — `_tag_priority(total)`에서 애초에 태그를 못 받는
    자리(`_pos_tag`가 None인 위치, 예: total=5일 때 bi=2)를 제거한다(Task5 I2).

    role을 몰라도 "이 위치가 태그 가능한가"는 (bi, total)만으로 결정적으로 계산
    가능하다 — 다른 비트의 role을 알 필요가 없다. 필터링 전에는 태그 불가능한
    위치가 우선순위 슬롯을 차지해, 강도를 올려 예산이 그 슬롯까지 늘어나도 실제
    태그 개수는 그대로인 낭비가 있었다(total=5 실측: 강도 0.7~0.8에서 슬롯
    [0,4,1,2]까지 배정되지만 2번 슬롯이 무태그라 실제 태그는 [0,1,4]에서 멈춤 —
    정본 role 경로에서 I1이 고친 것과 근본이 같은 결함)."""
    return [bi for bi in _tag_priority(total) if _pos_tag(bi, total) is not None]


# 정본 role 전용 태그 우선순위(Task5 I1 수정) — **비트 위치가 아니라 role 그 자체의
# 고정 순위**다. `_tag_priority`(위치기반)와 근본이 다르다: 정본 role은 비트가 몇 번째인지
# 몰라도 자기 role만으로 예산 안에 드는지 스스로 판정할 수 있다(브리프 권장안 채택).
# 페인포인트는 여기 목록에 아예 없다 — `_ARC_BY_ROLE["페인포인트"]=None`이라 태그를 못
# 붙이는데, 순위 슬롯을 차지하면 예산 1자리가 그대로 버려진다(I1이 잡은 실측 버그:
# 정본 5비트 기준 강도 0.3~0.6 네 지점의 출력이 문자 단위로 동일했다 — 3순위 슬롯이
# 페인포인트를 가리켜 예산을 소비만 하고 아무 태그도 못 붙였기 때문). 태그 가능한
# role만 세면(4개) 이 낭비가 원천적으로 사라진다.
_TAG_ROLE_PRIORITY = ["훅", "CTA", "반전", "실용"]


def _role_tag_rank(role_canon):
    """정본 role의 태그 우선순위(0=최우선). 태그불가(페인포인트)·미지 role은 None —
    호출부가 None을 "예산을 소비하지 않고 태그도 안 붙는다"로 처리한다."""
    if role_canon is None or role_canon not in _TAG_ROLE_PRIORITY:
        return None
    return _TAG_ROLE_PRIORITY.index(role_canon)


def _emotion_arc(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.3)
    if intensity <= 0:
        return text
    if ctx["caps"].get("max_tags_per_beat", 1) <= 0:
        return text
    # max_tags_total도 여기서 미리 게이트한다(Important1 수정 — Task5에서도 유지) —
    # 이 캡을 스테이지 루프 밖 `_enforce_total_tag_cap`이 사후에만 걸러버리면, bump는
    # 이미 찍힌 뒤 태그가 지워지는 비대칭이 생긴다(캡을 0으로 내렸는데 "감정×1
    # 적용"이라고 뜨는 거짓말 — 2026-07-15 재현). 이 스테이지는 naturalize_detail
    # 1회 호출당 정확히 1번만 실행되고, 우리가 붙이는 태그는 항상 전체 문자열의 맨
    # 앞(=태그 목록의 0번째)에 남는다 — max_tags_total>=1이면 `_enforce_total_tag_cap`의
    # "앞에서 cap개 보존" 규칙상 우리 태그는 절대 제거되지 않는다.
    # ⚠️ "이후 스테이지(intonation)가 텍스트 앞부분을 건드리지 않는 한"이라는 옛 전제는
    # 틀렸다(Task6 재리뷰 Important1로 드러남) — intonation은 태그 바로 뒤(강조어 앞)에
    # 쉼표를 끼워 넣을 수 있어 실제로 텍스트 맨 앞부분을 건드린다(`]` lookbehind 누락
    # 버그 당시 `[curious], 진짜 대박이에요…`가 그 증거). 그런데도 **결론은 우연히
    # 유지된다** — intonation은 새 `[...]` 태그를 만들거나 기존 태그를 옮기지 않고
    # 쉼표만 삽입하므로, `_enforce_total_tag_cap`이 세는 태그 목록에서 우리 태그의
    # 순번(0번째)은 그대로다. 즉 사후 캡이 실제로 우리 태그를 지우는 경우는 여전히
    # max_tags_total<=0뿐이고, 그 경우만 여기서 미리 걸러내면 bump와 실제 결과가
    # 항상 일치한다(사후 차감 로직 불필요). 이 게이트는 브리프 스냅샷(Task2
    # 이전 시점)엔 없었지만, 여기서 빠지면 Task2가 고친 버그가 되살아나므로 유지한다.
    if ctx["caps"].get("max_tags_total", 3) <= 0:
        return text
    # 강도 = 태그가 붙는 비트의 비율(임계형 → 비례형, Task5). 옛 방식은
    # `intensity < 0.15`면 무태그, 넘으면 항상 태그(0.2든 1.0이든 동일)라 슬라이더가
    # on/off 스위치나 다름없었다.
    #
    # 경로 분기(I1 재수정) — 정본 role이면 role 자체의 고정 순위로 예산을 판정하고,
    # 미지 role(위치폴백)만 예전 위치기반 `_tag_priority`를 쓴다:
    #
    #   role 기반(정본): 비트는 자기 role만 알면 되므로, "태그 가능한 role 수(4개,
    #   페인포인트 제외)"를 모집단으로 `_take_count`를 돌린다. 페인포인트는 애초에
    #   순위가 없어(`_role_tag_rank`→None) 예산을 소비하지 않는다 — 이게 I1이 고친
    #   버그다: 예전엔 비트 "위치"(전체 beat_total 기준)로 예산을 셌고 3순위 슬롯이
    #   우연히 페인포인트를 가리켜 예산 1자리를 그대로 버렸다(정본 5비트 기준
    #   0.3~0.6 네 강도의 출력이 문자 단위로 동일했던 실측 결함, tests 참조).
    #
    #   위치 기반(미지 role): role은 몰라도 "이 위치(bi, total)가 태그 가능한가"는
    #   `_pos_tag`로 결정적으로 계산 가능하다 — 다른 비트의 role을 알 필요가 없다.
    #   (이전 주석은 여기서 "예산 낭비를 막을 방법이 없다"고 적었는데 틀린 서술이었다
    #   — Task5 I2 재리뷰로 정정. `_tag_priority_taggable`이 태그 불가능한 위치를
    #   미리 제거한 순서를 주므로, 정본 role 경로(I1)와 동일한 방식으로 예산 낭비를
    #   막는다. 작업대 옛 코퍼스의 `body`/`build`가 실제로 이 경로를 타는 회귀
    #   스위트다.)
    canon = ctx.get("role_canon")
    if canon:
        rank = _role_tag_rank(canon)
        if rank is None:          # 페인포인트: 설계상 영구 무태그, 예산 안 먹는다
            return text
        n_tagged = _take_count(len(_TAG_ROLE_PRIORITY), intensity)
        if rank >= n_tagged:
            return text
    else:
        total = ctx.get("beat_total") or 1
        bi = ctx.get("beat_index") or 0
        n_tagged = _take_count(total, intensity)
        if bi not in _tag_priority_taggable(total)[:n_tagged]:
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
    return _pos_tag(ctx.get("beat_index"), ctx.get("beat_total"))


# 억양: 강조어 앞에 짧은 포즈(쉼표)를 두면 그 단어에 힘이 실린다("이거, 진짜 대박").
# v3 태그를 더 쓰지 않고 구두점만으로 만든다 — ① 태그 총량 캡(max_tags_total)을
# emotion_arc가 이미 쓰고 있고 ② 미지원 태그를 지어내면 성우가 그 글자를 그대로
# 읽어버릴 위험이 있기 때문(_tag_for 주석과 동일 원칙: 알려진 v3 태그만 쓴다).
#
# ⚠️ 뒤쪽 경계(lookahead) 필수 — 브리프 초안 패턴엔 이게 없어서 "딱"이 "딱딱해요"의
# 앞 두 글자와, "완전"이 "완전체가"의 앞 두 글자와, "절대"가 "절대값이"의 앞 두 글자와
# 겹쳐 오탐한다(강조어가 아닌데 쉼표가 박힘). `_CONNECTIVES`/`_ENDING_SUFFIXES`가 이미
# 세운 원칙과 동일하다 — "오탐 0이 더 중요"(그 두 주석 참조). 앞쪽 경계(이미 쉼표가
# 있는 자리엔 또 넣지 않음)는 기존 lookbehind `(?<=[^\s,.!?…])`가 담당한다: 강조어
# 앞 공백 바로 앞 글자가 이미 쉼표/마침표/공백류면 그 자리는 애초에 후보에서 빠진다.
#
# ⚠️ lookbehind 문자군에 `\]`도 반드시 포함(Task6 재리뷰 Important1) — `_emotion_arc`가
# 이 스테이지보다 먼저 돌며 `[curious] ` 같은 v3 태그를 문장 맨 앞에 붙이는데, `\]`가
# 빠진 lookbehind는 태그의 닫는 대괄호를 "이미 앞에 실질 단어가 있다"로 오인해
# `[curious], 진짜 대박이에요…` 처럼 **문장 맨 앞(선행 단어 없음)에 쉼표를 만든다**
# (컨트롤러 실측: `merge_profile({})` + role=훅/CTA + beat_index=1 → intonation=1로
# 잘못 계상됨, arc를 끄면 재현 안 됨 — 원인 확정). 앞에 아무 단어도 없는 자리의 포즈는
# 설계 의미가 없고, `applied`에 태그 아티팩트를 강조 포즈로 잘못 계상하는 거짓말이 된다.
_EMPHASIS_WORDS = ["진짜", "완전", "역대급", "훨씬", "절대", "딱"]
_EMPHASIS_PAT = re.compile(
    r"(?<=[^\s,.!?…\]])(\s+)(?:" + "|".join(_EMPHASIS_WORDS) + r")(?=[\s,.!?…]|$)"
)

# 훅 마지막 어절 = 강조 대상. `_EMPHASIS_WORDS`(부사)로는 못 잡는다 — 사장님 예시
# "이거!"는 문장 끝 지시어라 이 목록에 없다. 훅의 마지막 어절을 잡는 별도 규칙이 필요하다.
# ⚠️ `(?<=[가-힣])` 가드 필수 — 한글 음절이 앞에 있어야만 매치(단어 1개뿐인 문장 "이거."는 제외).
# 뒤쪽 문장부호(group 3)는 통째로 버리고 "!" 하나로 갈아친다 — "이거….!" 같은 겹침
# 방지. 즉 group 3는 문장부호를 **보존하지 않는다** — 아래 `_intonation`에서 하는
# 유일한 일은 그 안에 "?"가 있는지 검사하는 것뿐이다(리뷰 지적 Critical1, 2026-07-17
# 이전엔 이 검사가 없어 캡처만 하고 안 읽는 죽은 그룹이었다).
_HOOK_TAIL_PAT = re.compile(r"(?<=[가-힣])(\s*,)?\s+([가-힣]{1,5})\s*([.…!?]*)\s*$")


def _intonation(text, cfg, ctx):
    intensity = cfg.get("intensity", 0.2)
    if intensity <= 0:
        return text
    # ── 훅 꼬리 강조 (사장님 판정 ③: 쉼표로 앞글자 띄우고 느낌표로 뒤 받치기) ──
    # 부사 강조(_EMPHASIS_PAT)보다 **먼저** 돌린다.
    # ⚠️ 옛 주석은 "부사 후보 좌표는 그 앞쪽이라 영향받지 않는다"고 적었는데 틀렸다
    # (리뷰 지적 Important, 2026-07-17) — 훅의 마지막 어절 자체가 부사일 때
    # (`_EMPHASIS_WORDS`엔 "진짜"/"완전"/"딱"이 다 있다, 예: "가격이 싼데 완전.")
    # 두 정규식이 같은 글자를 겨눈다. 진짜 이유는 순서가 **텍스트**를 다르게 만드는
    # 게 아니라 **카운트**를 다르게 만든다는 것 — 꼬리를 먼저 치환하면 마지막
    # 어절이 이미 쉼표+느낌표로 바뀌어 있어(뒤에 comma가 생겨) `_EMPHASIS_PAT`의
    # lookbehind(`(?<=[^\s,.!?…\]])`)가 더 이상 그 자리를 후보로 못 잡는다 —
    # `applied["intonation"]`은 1로 정확히 계상된다. 부사를 먼저 돌리면 같은 글자가
    # 부사 쉼표로 먼저 잡혀 1이 찍히고, 이어서 꼬리 규칙이 (겉보기 텍스트가
    # 이미 같아졌어도) 또 `_bump`를 호출해 2로 거짓 계상된다 — `ca92f9c8`이 잡은
    # 유령 카운트와 같은 결함 클래스, "계획한 수(take)가 아니라 실제 바뀐 횟수만
    # 센다" 계약(`_endings`의 해당 주석 참조) 위반이다 — 이 함수(`_intonation`)
    # 자신의 아래 문단이 같은 계약을 재천명한다(리뷰 지적 Finding4·Finding5 정정,
    # 2026-07-17 — 이전 두 차례 모두 이 포인터의 줄 번호가 틀렸었다. 이제부터는
    # 줄 번호 대신 심볼명을 인용한다).
    # 두 순서 모두 최종 텍스트는 동일할 수 있어(리오더 뮤턴트가 텍스트 단언으로는
    # 안 죽는 이유) 카운트를 지키는 게 이 순서의 실제 존재 이유다.
    if (ctx.get("role_canon") in (cfg.get("emphasis_roles") or [])):
        m = _HOOK_TAIL_PAT.search(text)
        # 의문형이면 발동 자체를 접는다(리뷰 지적 Critical1, Task3 amendment2로
        # 판정을 공유 감지기로 교체) — 물음표를 삼켜 느낌표로 갈아치우면 반전의문
        # 훅("이거 뭔지 알아요?")이 하강 느낌표로 읽혀 의미가 바뀐다.
        # `_is_interrogative`(= "?"가 이미 있거나 확실한 의문형 어미로 끝남)를 쓰는
        # 이유는 방어의 이중화다: 보통은 `_endings`가 이 스테이지보다 먼저 돌아
        # 의문형 어미를 이미 "?"로 바꿔놔서 첫 조건("?" in text)이 잡지만,
        # `_endings`가 꺼져 있거나(intensity 0) 이 role이 question_roles 밖이라
        # 아직 "?"가 안 박힌 상태에서도 같은 감지기가 어미만 보고 독립적으로
        # 판정한다 — `_endings`와 이 가드가 각자 "의문형이란 무엇인가"를 따로
        # 조립하면 드리프트가 난다(이 트랙 최악의 사고, 2026-07-15 10 seams의
        # 근본원인이 정확히 "같은 것을 두 곳이 각자 조립"이었다). 엔진 원칙("안
        # 터지는 쪽이 안전")대로 의문형이면 여기서는 아무것도 하지 않는다.
        if m and not _is_interrogative(text):
            before = text
            text = f"{text[:m.start()]}, {m.group(2)}!"
            if text != before:
                _bump(ctx, "intonation", 1)
    cands = [m.start(1) for m in _EMPHASIS_PAT.finditer(text)]
    take = _take_count(len(cands), intensity)
    if take <= 0:
        return text
    # "계획한 수(take)"가 아니라 "실제 바뀐 횟수"만 센다(Task6 재리뷰 Minor3) —
    # `_spoken_style`/`_pronunciation`/`_endings`가 이미 쓰는 `new != s` 전략과 통일.
    # 구조상 쉼표 삽입은 항상 문자열을 바꾸므로(no-op이 될 수 없음) take와 n이 지금은
    # 같은 값이 나오지만, `_endings` 주석의 선례를 따라 계약을 "실제 효과"로 고정해둬야
    # 다른 스테이지와 전략이 어긋나지 않는다. 오프셋이 밀리지 않도록 뒤에서부터 적용
    # (다른 스테이지의 동일 패턴 참조).
    n = 0
    for pos in sorted(cands[:take], reverse=True):
        before = text
        text = text[:pos] + "," + text[pos:]
        if text != before:
            n += 1
    _bump(ctx, "intonation", n)
    return text


# 이미 문자열 맨 앞에 붙어 있는 v3 태그 묶음(emotion_arc가 붙인 `[curious] ` 등).
# 속삭임 태그를 그 **뒤**에 꽂아 설계가 고정한 `[감정][whispers]` 순서를 만든다.
_LEADING_TAGS_PAT = re.compile(r"^((?:\[[^\]]+\])+)\s*")
_WHISPER_TAG = "[whispers]"

# 대본이 이미 데리고 온 추임새 — 여기에 걸리면 `_fillers`는 손을 뗀다.
# 옛 뱅크(음/아/그/뭐/자)도 포함한다: 사장님이 옛 대본을 그대로 붙여넣을 수 있고,
# 그때 "음, 와," 같은 겹침이 나면 안 된다(2026-07-17 실측 사고).
_INTERJECTIONS = {"와", "오", "우와", "헐", "이야", "음", "아", "그", "뭐", "자", "어", "어머"}
# 문두 추임새 = 한글 1~2자 + 쉼표. 태그 묶음은 미리 벗겨내고 본다.
_LEADING_INTERJECTION_PAT = re.compile(r"^\s*([가-힣]{1,2})\s*,")


def _whisper(text, cfg, ctx):
    """roles에 든 role의 비트에 `[whispers]`를 붙인다(설계 2026-07-16 §3).

    **감정 예산과 별개 축이다(§3.1)** — `_emotion_arc`의 intensity·role 우선순위를 전혀
    보지 않는다. 얹었다면 ASMR 톤인데 예산이 모자라 중간 비트가 안 속삭이는 일이 생긴다.
    보는 캡은 `max_tags_per_beat` 하나뿐이고, 그건 "한 비트에 태그 몇 개까지"라는 별개 사실이다.

    **미지 role은 속삭이지 않는다** — `_emotion_arc`와 달리 위치기반 폴백을 하지 않는다.
    속삭임은 비트 역할이 확정될 때만 켜는 게 맞다(모르면 안 켠다). 작업대 옛 코퍼스의
    `body`/`build`가 실제로 이 경로를 탄다.
    """
    canon = ctx.get("role_canon")
    if canon is None or canon not in (cfg.get("roles") or []):
        return text
    # 멱등성 가드(리뷰 지적) — 이미 [whispers]가 있으면 그대로 반환한다. 캡
    # 검사(`max_tags_per_beat`)만으로는 못 막는다: 태그 1개짜리 입력은
    # `len(existing)+1 <= cap`(예: 1+1=2<=2)이 참이라 캡을 통과해버려서
    # "2개 이상 있어야 막는" 캡의 경계를 정확히 피해간다 — 캡은 총량 상한이지
    # 중복 방지가 아니다. `_bump`를 부르지 않는다 — 아무것도 안 붙였는데
    # "속삭임 1건"으로 계상하면 T6에서 이미 고친 거짓말 패턴의 재발이다.
    # 멱등성 가드(리뷰 지적) — 이미 [whispers]가 있으면 그대로 반환한다. 캡
    # 검사(`max_tags_per_beat`)만으로는 못 막는다: 태그 1개짜리 입력은
    # `len(existing)+1 <= cap`(예: 1+1=2<=2)이 참이라 캡을 통과해버려서
    # "2개 이상 있어야 막는" 캡의 경계를 정확히 피해간다 — 캡은 총량 상한이지
    # 중복 방지가 아니다. `_bump`를 부르지 않는다 — 아무것도 안 붙였는데
    # "속삭임 1건"으로 계상하면 T6에서 이미 고친 거짓말 패턴의 재발이다.
    if _WHISPER_TAG in text:
        return text
    # 이 비트에 이미 붙은 태그 수 + 우리 1개가 캡을 넘으면 붙이지 않는다. 붙였다가
    # `_enforce_total_tag_cap`이 사후에 지우면 applied에 "속삭임 1건"이라고 적어놓고
    # 실제로는 없는 거짓말이 된다(T6에서 같은 비대칭을 이미 한 번 고쳤다).
    cap = ctx["caps"].get("max_tags_per_beat", 2)
    if len(re.findall(r"\[[^\]]+\]", text)) + 1 > cap:
        return text
    m = _LEADING_TAGS_PAT.match(text)
    if m:
        out = f"{m.group(1)}{_WHISPER_TAG} {text[m.end():]}"
    else:
        out = f"{_WHISPER_TAG} {text}"
    _bump(ctx, "whisper", 1)
    return out


_STAGES = [("normalize", _normalize), ("spoken_style", _spoken_style),
           ("pronunciation", _pronunciation), ("phrasing", _phrasing),
           ("endings", _endings), ("fillers", _fillers),
           ("emotion_arc", _emotion_arc), ("whisper", _whisper),
           ("intonation", _intonation)]


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
    # beat_index/beat_total 배선 어긋남도 데이터 품질 사실로 1회 경고한다(Minor,
    # role 경고와 동일 패턴) — 위치기반 폴백(미지 role) 경로에서 bi가 범위를 벗어나면
    # `_tag_priority_taggable(total)`엔 애초에 그 인덱스가 없어 실패 모드가 "잘못된
    # 태그"가 아니라 "조용한 무태그"가 된다. 호출부 배선 버그가 나면 감정태그가
    # 통째로 사라지는데 신호가 전혀 없었던 걸 여기서 남긴다.
    #
    # 문구는 결과를 단정하지 않는다(Task5 Minor1 재리뷰) — 정본 role은 이제
    # `_role_tag_rank`가 role만으로 판정하고 beat_index를 아예 보지 않으므로,
    # 이 mismatch가 있어도 태그는 정상 발동할 수 있다. "조용히 무발동"이라고
    # 단정하면 정본 role에서는 거짓이 된다 — 그래서 이 경고는 미지 role
    # 위치폴백에서만 영향이 있다는 사실만 남기고 결과를 예단하지 않는다.
    if beat_index is not None and beat_total and beat_index >= beat_total:
        ctx["warnings"].append(
            f"beat_index({beat_index}) >= beat_total({beat_total}) — 배선 오류 가능성"
            "(정본 role이면 무관 · 미지 role 위치폴백에서만 감정태그에 영향)"
        )
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
