"""1기 챌린지 — 순수 판정 로직.

DB도 HTTP도 모른다. 여기 있는 함수는 값만 받아 값만 돌려준다.
그래야 규칙이 한 곳에만 존재하고(0순위-B), 테스트가 DB 없이 즉시 돈다.
"""
import re
import urllib.parse
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def kst_day(dt=None):
    """UTC 시각 → 한국 날짜 문자열 'YYYY-MM-DD'.

    ★하루 2영상의 '하루'가 여기서 정해진다. 저장 시점에 한 번 불러
    컬럼에 넣고, 조회할 때 다시 계산하지 않는다 — 계산이 두 군데 있으면
    언젠가 어긋난다(0순위-B).
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d")


def in_period(day, start, end):
    """day가 챌린지 기간 안인가. 전부 'YYYY-MM-DD' 문자열(사전순=시간순).

    start/end가 비어 있으면 그쪽 끝은 열어둔다 — 사장님이 아직 기간을
    설정하지 않았다고 해서 멤버 제출이 막히면 안 된다.
    """
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


_CODE_RES = {
    "instagram": (re.compile(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)"),),
    "youtube": (re.compile(r"(?:youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{6,})"),
                re.compile(r"[?&]v=([A-Za-z0-9_-]{6,})")),
    "tiktok": (re.compile(r"/video/(\d{6,})"),),
}


def video_code(url, platform):
    """URL에서 영상 고유 코드를 뽑는다. 못 뽑으면 빈 문자열.

    ★app.py의 _media_code를 쓰지 않는 이유: 그것은 인스타 전용이고, 매칭
    실패 시 빈 문자열이 아니라 **URL을 통째로** 돌려준다(실측). 그 값을
    shortcode로 쓰면 dedup_key가 'sc:<URL>'이 되어 같은 영상의 다른 URL
    형태를 중복으로 못 잡는다.

    틱톡 단축주소(vt.tiktok.com/ZSxxxx)엔 영상 id가 없다 — 빈 문자열을
    돌려주고 dedup_key가 URL 폴백으로 처리하게 둔다.
    """
    for rx in _CODE_RES.get(platform or "", ()):
        m = rx.search(url or "")
        if m:
            return m.group(1)
    return ""


def embed_url(url, platform, code=""):
    """플랫폼 영상 URL → **화면 안에서 재생되는** 임베드 주소. 못 만들면 빈 문자열.

    왜 필요한가: 관리 화면에서 카드를 누르면 인스타·틱톡으로 **튕겨 나가서**
    100명 영상을 훑는 데 탭이 100개 열린다. 임베드면 나가지 않고 본다.

    ⚠️ 예전에 '임베드를 폐지'한 기록이 있으나(memory: 쇼핑쇼츠_자동화) 그것은
    **검색 결과**를 긁어와 보여주는 이야기였다(관련성 30~50%가 문제). 여기는
    URL이 확정된 특정 영상이라 그 판단이 적용되지 않는다.

    code를 넘기면 그것을 쓴다(DB에 이미 저장된 shortcode 재사용 — 같은 판단을
    두 번 하지 않는다). 없으면 여기서 video_code로 뽑는다.
    """
    c = (code or "").strip() or video_code(url, platform)
    if not c:
        return ""
    if platform == "youtube":
        return "https://www.youtube.com/embed/" + c
    if platform == "instagram":
        # 릴스·게시물 모두 /p/<code>/embed 로 열린다(로그인 불필요).
        return "https://www.instagram.com/p/" + c + "/embed"
    if platform == "tiktok":
        return "https://www.tiktok.com/embed/v2/" + c
    return ""


def dedup_key(url, shortcode=""):
    """같은 영상을 두 번 낸 것인지 판정하는 키. 저장 시점에 확정한다.

    ① shortcode가 있으면 그것으로 — 같은 영상의 다른 URL 형태(쿼리·모바일
       도메인)도 한 건으로 잡힌다.
    ② 없으면(틱톡 단축링크 vt.tiktok.com 등) 정규화한 URL로.

    ⚠️ ②는 완벽하지 않다 — 같은 영상을 단축링크와 원본링크로 각각 내면 둘 다
    통과한다. 틱톡 단건 수집을 붙이면 ①로 수렴한다. 지금은 알고 간다.
    """
    sc = (shortcode or "").strip()
    if sc:
        return "sc:" + sc
    p = urllib.parse.urlparse((url or "").strip())
    host = (p.hostname or "").lower()
    path = (p.path or "").rstrip("/").lower()
    return "url:" + host + path


def day_list(start, end):
    """기간 안의 모든 날짜 ['YYYY-MM-DD', ...]. 달력이 그릴 줄 목록이다.

    ★제출이 없는 날도 줄이 나와야 한다 — 빈칸을 눌러 그날을 채우는 것이
    이 화면의 핵심 기능이라, 제출한 날만 그리면 빈 날에 손댈 방법이 없다.

    start·end 중 하나라도 비면 빈 목록을 돌려준다(달력을 못 그린다).
    그 경우 화면은 목록 탭으로 폴백한다 — 기간 미설정이 제출을 막지는
    않는다(in_period는 열린 끝을 허용한다). 판단이 갈라지지 않게, 여기서도
    '기간이 없으면 달력이 없다'까지만 말하고 제출 가부는 말하지 않는다.
    """
    if not start or not end or start > end:
        return []
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    out, d = [], d0
    while d <= d1:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def streak(by_day, today, goal=2):
    """오늘 기준 연속 달성 일수.

    오늘부터 거꾸로 세되, **오늘이 아직 미달성이면 어제부터** 센다 —
    오전에 열었다고 어제까지의 연속기록이 0으로 보이면 안 된다.
    (하루 목표를 채우기 전엔 오늘이 성공도 실패도 아니기 때문)
    """
    if not today:
        return 0
    d = datetime.strptime(today, "%Y-%m-%d").date()
    if by_day.get(today, 0) < goal:
        d -= timedelta(days=1)          # 오늘은 아직 진행 중 — 판정 보류
    n = 0
    while by_day.get(d.strftime("%Y-%m-%d"), 0) >= goal:
        n += 1
        d -= timedelta(days=1)
    return n


def summarize(subs, goal=2):
    """제출 목록 → {by_day, done_days, total}.

    subs는 'submit_day' 키를 가진 dict 목록(DB 행 그대로 넣어도 된다).
    """
    by_day = {}
    for s in subs:
        d = s.get("submit_day")
        if not d:
            continue
        by_day[d] = by_day.get(d, 0) + 1
    return {
        "by_day": by_day,
        "done_days": sum(1 for n in by_day.values() if n >= goal),
        "total": sum(by_day.values()),
    }
