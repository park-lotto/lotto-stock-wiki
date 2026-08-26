"""채널 등급제 — 과거 성적으로 방문 주기를 가른다(2026-08-17).

★비용이 나가는 지점은 '문을 여는 순간'이다.
프록시는 오간 바이트로, Apify는 run 횟수로 과금한다(run당 $0.005 고정, apify_client.py:173).
댓글수는 채널 페이지를 열 때 목록 응답에 딸려오므로(instagram_parse.py:130) "댓글 500 넘는
것만 저장"하는 필터로는 한 푼도 안 아낀다. 절감은 **안 여는 것**으로만 된다 — 그래서
과거 성적으로 미리 고른다.

실측 근거(서버 reference.db, 2026-07-22~08-16 26일, 441채널·릴스 6,040건):

    등급   채널   하루방문   하루히트(댓글500+)
    A       75      75        21.7      ← 전체 히트의 94%
    B       61      30         1.2
    C      227      76         0.0      ← 26일간 히트 0건인데 매일 열고 있었다
    D       78       3         0.1

기준을 조회수가 아니라 댓글로 잡은 이유: 사장님이 실제 제작에 쓴 45채널 포착률이
조회10만+2건=49%인데 댓글500+2건=82%다. 실사용 영상의 댓글 중앙값 1,473(전체 P90 579)
— 조회수는 광고로도 오르지만 댓글은 사람이 반응해야 달린다.

⚠️ 기준값은 전부 인자로 뺐다. 재료가 부족하면 hit_min_count=1로 낮춰 A를 넓히면 되고,
코드 수정 없이 되돌릴 수 있어야 라이브에서 실험할 수 있다(feedback_no_unverified_flag_in_live).
"""
import hashlib
from datetime import date, timedelta

from shopping_shorts.config import RESULTS_PER_CHANNEL

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
TIER_D = "D"

#: 등급별 방문 주기(일). A=매일, D=월 1회 생사확인.
PERIOD_DAYS = {TIER_A: 1, TIER_B: 7, TIER_C: 14, TIER_D: 30}

#: 히트 판정 댓글수. 실사용 영상 댓글 중앙값 1,473의 3분의 1 선.
HIT_COMMENTS = 500
#: A 승격에 필요한 히트 건수. 1건은 운, 2건이면 실력.
HIT_MIN_COUNT = 2
#: 이 기간 업로드가 없으면 휴면(D). 매일 열어야 빈손이다.
DORMANT_DAYS = 14

#: 채널당 가져올 개수. C·D는 '승격 감지'만 하므로 1개면 된다.
RESULTS_DEFAULT = RESULTS_PER_CHANNEL
RESULTS_PROBE = 1

_TIER_ORDER = (TIER_A, TIER_B, TIER_C, TIER_D)


def _norm(username):
    return (username or "").strip().lstrip("@").lower()


def _day(value):
    """'2026-08-17' / '2026-08-17T02:53:57+00:00' → date. 파싱 실패는 None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compute_tiers(rows, today=None, hit_comments=HIT_COMMENTS,
                  hit_min_count=HIT_MIN_COUNT, dormant_days=DORMANT_DAYS):
    """수집 이력 → {정규화 username: 등급}.

    rows: [{"username", "comments", "first_seen"}] — reel_history 그대로.
    reel_history는 30일 롤링(store.py 정리)이라 자연히 최근 한 달 성적만 본다.

    판정 순서가 중요하다: **휴면을 먼저 본다.** 지난달 크게 터졌어도 2주째 조용하면
    매일 열어봐야 빈손이라, 히트 이력보다 '지금 올리고 있나'가 앞선다.
    """
    today = _day(today) or date.today()
    dormant_before = today - timedelta(days=dormant_days)

    hits, last_seen = {}, {}
    for r in rows:
        u = _norm(r.get("username"))
        if not u:
            continue
        if (r.get("comments") or 0) >= hit_comments:
            hits[u] = hits.get(u, 0) + 1
        d = _day(r.get("first_seen"))
        if d and (u not in last_seen or d > last_seen[u]):
            last_seen[u] = d

    tiers = {}
    for u in set(hits) | set(last_seen):
        seen = last_seen.get(u)
        if seen is None or seen < dormant_before:
            tiers[u] = TIER_D
        elif hits.get(u, 0) >= hit_min_count:
            tiers[u] = TIER_A
        elif hits.get(u, 0) >= 1:
            tiers[u] = TIER_B
        else:
            tiers[u] = TIER_C
    return tiers


def _slot(username, period):
    """채널을 주기 안의 어느 날에 배정할지 — 이름 해시로 결정적·균등하게.

    날짜로 나누면(예: 목록 순서 % 주기) 채널이 추가·삭제될 때 배정이 통째로 밀려
    어제 본 채널을 오늘 또 보게 된다. 이름 해시는 목록이 바뀌어도 그 채널의 자리가
    안 움직인다.
    """
    if period <= 1:
        return 0
    h = hashlib.md5(username.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % period


def due_today(tiers, day_index, known=None):
    """오늘 방문할 채널 집합.

    day_index: 기준일로부터 며칠째인지(정수). 같은 값이면 항상 같은 결과가 나온다.
    known: 전체 추적 목록. 이력이 없어 등급이 없는 채널(신규·등록 직후)은 **매일** 넣는다
           — 안 긁으면 이력이 안 쌓여 영영 등급이 안 생긴다(select_tracked의 pending과 같은 원리).
    """
    due = set()
    for u, tier in tiers.items():
        period = PERIOD_DAYS.get(tier, 1)
        if _slot(u, period) == day_index % period:
            due.add(u)
    for u in (known or []):
        n = _norm(u)
        if n and n not in tiers:
            due.add(n)
    return due


def fetch_limit(tier, default=None, probe=RESULTS_PROBE):
    """이 등급에서 채널당 몇 개를 가져올지.

    C·D는 재료창고가 아니라 **승격 감지기**다 — 최신 1개만 봐도 터졌는지 알 수 있고,
    터졌으면 다음 계산에서 A로 올라와 다음날부터 매일 긁힌다.
    """
    if default is None:
        default = RESULTS_DEFAULT
    return probe if tier in (TIER_C, TIER_D) else default


def tier_counts(tiers):
    """{등급: 채널수} — 로그·대시보드 표시용."""
    counts = {t: 0 for t in _TIER_ORDER}
    for tier in tiers.values():
        counts[tier] = counts.get(tier, 0) + 1
    return counts
