"""훅 자동수확(P2) — 크롤 우승작의 캡션/제목 첫 줄에서 훅 후보를 뽑아 hook 버킷 pending으로.

부품은행의 훅이 시드 8개뿐이라 로테이션해도 단조롭다(사장님 '8개뿐'). 대본 전체가 추출된
우승작만 8버킷 분해(pattern_bank.ingest_script)를 타므로 대부분의 크롤아이템은 훅을 안 남긴다.
여기서는 대본이 없어도 **캡션 첫 줄**을 훅 후보로 긁어 풀을 키운다. 품질은 사람 승인 게이트가
거른다(pending으로만 넣는다 — 자동승인 금지). 순수함수 + store 쓰기, Gemini 없음(무과금)."""
import re

_MIN_LEN = 6      # 너무 짧으면(감탄사·해시태그) 훅으로 못 씀
_MAX_LEN = 40     # 훅은 한 호흡 — 길면 캡션 문장(설명문)이라 제외
_MAX_PER_RUN = 40  # 한 배치에 밀어넣는 상한(pending 폭주 방지)

_HANGUL = re.compile(r"[가-힣]")


def clean_hook_candidate(caption):
    """캡션 → 훅 후보 한 줄. 첫 줄/첫 해시태그 앞까지, 선행 이모지·공백 제거, 길이·한글 필터.
    부적격이면 ''(해시태그만·영어만·너무 짧거나 긺)."""
    if not caption:
        return ""
    line = caption.splitlines()[0]
    line = line.split("#", 1)[0]                       # 인라인 해시태그 앞까지
    # 선행 이모지/기호 제거(한글·영숫자·따옴표로 시작할 때까지 앞을 깎는다)
    line = re.sub(r"^[^\w가-힣\"'(]+", "", line).strip()
    if not (_MIN_LEN <= len(line) <= _MAX_LEN):
        return ""
    if not _HANGUL.search(line):                       # 한글 없으면(영어·해시태그) 제외
        return ""
    return line


# 훅 유형(taxonomy) — 결정적 키워드 분류. 사장님 예시 '자~ OO하시는 분들'=target_callout 신설.
# 승인 큐레이션에서 유형별로 보고, 생성 프롬프트가 유형 다양성을 확보하는 데 쓴다.
_TYPE_RULES = [
    ("target_callout", ("하시는 분", "쓰시는 분", "분들", "님들", "주목", "이신 분")),
    ("warning", ("하지 마", "절대", "주의", "조심")),
    ("discovery", ("이제 알", "왜 이제", "몰랐", "이런 게 있", "알고 보니")),
    ("praise", ("천재", "최고", "인생템", "역대급", "갓")),
    ("shock", ("와 ", "헐", "대박", "세상에", "미쳤", "깜짝")),
    ("confession", ("저만", "저 이거", "제가 손해", "몰라서")),
]


def classify_hook(text):
    """훅 문구 → 유형(target_callout/shock/discovery/warning/praise/confession/question) or None.
    질문형은 물음표로, 나머지는 키워드로. 여러 개 걸리면 _TYPE_RULES 순서 우선."""
    t = (text or "").strip()
    if not t:
        return None
    for htype, kws in _TYPE_RULES:
        if any(k in t for k in kws):
            return htype
    if t.endswith("?") or "나요" in t or "까요" in t:
        return "question"
    return None


# 참여유도(engagement-bait) 판별어 — 인스타 댓글유도 멘트는 훅이 아니라 은행 오염원.
# 부분일치 하나라도 걸리면 bait. 오늘 실측 26% 오염이 전부 이 부류였다(2026-07-22).
_BAIT_KEYWORDS = (
    "댓글", "프로필", "팔로우", "DM", "디엠", "남겨주", "정보 전송", "정보 보내",
    "링크 No", "링크 no", "아무 글자", "아무글자", "두 글자", "두글자", "요청함", "숨김함",
)


def is_engagement_bait(text):
    """훅 문구가 인스타 참여유도 멘트인가(=은행에 넣으면 안 되는 오염). 부분일치 판별.
    빈 값은 False(짧은 것은 clean_hook_candidate가 이미 거른다)."""
    if not text:
        return False
    return any(k in text for k in _BAIT_KEYWORDS)


def harvest_hooks_from_crawl(store, platforms=("youtube", "tiktok", "instagram"),
                             grades=("S", "A"), max_per_run=_MAX_PER_RUN):
    """우승작(grade in grades) 캡션에서 훅 후보를 뽑아 hook 버킷 pending으로 추가 → 추가 건수.
    dedup은 store.add_pattern_item이(같은 canonical=freq+1) 처리. 개별 실패는 삼킨다."""
    added = 0
    for platform in platforms:
        if added >= max_per_run:
            break
        try:
            items, _ = store.load_last_run_platform(platform)
        except Exception:
            continue
        for it in items:
            if added >= max_per_run:
                break
            try:
                if it.get("grade") not in grades:
                    continue
                hook = clean_hook_candidate(it.get("caption") or "")
                if not hook:
                    continue
                if is_engagement_bait(hook):        # 참여유도 멘트는 훅 아님 — 은행 오염 차단
                    continue
                htype = classify_hook(hook)
                tags = {"hook_type": htype, "source": "harvest"} if htype else {"source": "harvest"}
                store.add_pattern_item("hook", hook, tags=tags)   # 기본 status=pending
                added += 1
            except Exception:
                continue
    return added
