"""Apify Instagram Reel Scraper HTTP 클라이언트."""
import json
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shopping_shorts.config import APIFY_TOKENS, APIFY_ACTOR, RESULTS_PER_CHANNEL, ONLY_NEWER_THAN

# run-sync-get-dataset-items는 Apify 서버측 자체 타임아웃(약 5분)이 있어
# 채널이 많으면(443개) 끝나기 전에 408로 끊긴다(2026-07-09 실측). 시작만
# 비동기로 걸고 완료까지 폴링하는 방식으로 전환 — 서버측 시간 제한이 없다.
_RUNS_URL = "https://api.apify.com/v2/acts/{actor}/runs"
_RUN_STATUS_URL = "https://api.apify.com/v2/actor-runs/{run_id}"
_RUN_ABORT_URL = "https://api.apify.com/v2/actor-runs/{run_id}/abort"
_DATASET_ITEMS_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


class ApifyRunFailed(RuntimeError):
    """run이 시작에는 성공했으나 실행 도중 실패(FAILED/ABORTED/TIMED-OUT).

    ★이 실패는 원인이 두 가지로 갈리는데 run status만으로는 구별이 안 된다:
      (a) 실행 도중 계정 소진 → **다음 토큰으로 재시도하면 성공한다**
          (2026-07-09 실사고 — 이것 때문에 로테이션을 넣었다)
      (b) 액터 스키마 변경·잘못된 입력 → 토큰을 바꿔도 똑같이 실패한다
    (b)인데 전 토큰(최대 30개)을 다 돌면 **유료 run이 30번 청구**된다(fetch_reels의
    15워커 병렬과 곱해진다). 그렇다고 (a)를 포기하면 위 실사고가 재발한다.
    → 절충: run 실패로 인한 로테이션만 _MAX_RUN_FAILURE_ROTATIONS로 **횟수를 제한**한다.
      (a)는 다음 토큰에서 곧바로 살아나므로 1회면 충분하고, (b)의 피해는 30run → 2run으로 준다.
    소진이 시작 시점에 드러나는 경우(401/402/429)는 run이 아예 안 뜨므로 공짜다 —
    그건 종전대로 전 토큰을 돈다."""


# run이 도중에 실패했을 때 "다른 토큰이면 될지도" 재시도를 몇 번까지 허용할지.
# 각 재시도는 유료 run 1개다. 1 = 원 사고(계정 소진) 복구엔 충분하고 낭비는 최대 1건.
_MAX_RUN_FAILURE_ROTATIONS = 1

# 계정 하나가 사용량 소진(402)되면 다음 계정으로 자동 로테이션(2026-07-09).
# 마지막으로 성공한 토큰의 인덱스를 저장해 다음 호출부터 그 지점에서 시작
# (매번 소진된 앞 계정부터 다시 두드리지 않음).
_KEY_STATE_PATH = Path(__file__).parent / "data" / "apify_key_index.json"
# 시작 거부(런 미생성=무과금)라 다음 토큰으로 로테이션해야 하는 상태들.
# 403 추가(2026-07-25 실사고): 유료 렌탈 액터(apidojo)는 FREE 계정이 월 $5
# 하드리밋을 넘기면 403 "Monthly usage hard limit exceeded"를 뱉는다. 403을
# 로테이션 대상에 안 넣으면 _start_run이 raise_for_status로 던지고 _run_with_rotation이
# 그대로 재발생시켜 — 아직 예산이 남은 STARTER 토큰을 써보지도 못하고 인스타
# '지금 수집'이 통째로 403으로 즉사했다(라이브 job 2건 403 error 실측).
_EXHAUSTED_STATUSES = {401, 402, 403, 429}


def _load_key_index() -> int:
    try:
        return json.loads(_KEY_STATE_PATH.read_text(encoding="utf-8")).get("index", 0)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def _save_key_index(index: int) -> None:
    _KEY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_STATE_PATH.write_text(json.dumps({"index": index}), encoding="utf-8")


def _start_run(token, payload, actor=APIFY_ACTOR):
    """지정 토큰·액터로 run 시작. 사용량 소진(401/402/429)이면 None 반환(호출부가
    다음 토큰 시도). actor 기본값은 인스타 릴스 스크래퍼(기존 동작 유지) —
    다른 플랫폼 스크래퍼(예: 틱톡)는 호출부가 명시적으로 지정한다(2026-07-09)."""
    headers = {"Authorization": f"Bearer {token}"}
    run = requests.post(
        _RUNS_URL.format(actor=actor), headers=headers, json=payload, timeout=60
    )
    if run.status_code in _EXHAUSTED_STATUSES:
        return None
    run.raise_for_status()
    return headers, run.json()["data"]


def _abort_run(headers, run_id) -> None:
    """진행 중인 run을 중단시킨다. 타임아웃으로 손을 떼기 전 반드시 부른다 —
    안 부르면 그 run은 Apify에서 계속 돌며 과금되는데(우리만 안 볼 뿐) 그 위에
    다음 토큰으로 새 run을 또 띄우므로 **이중 과금**이 된다."""
    try:
        requests.post(_RUN_ABORT_URL.format(run_id=run_id), headers=headers, timeout=30)
    except requests.RequestException:
        pass  # abort 실패로 본 작업을 막을 순 없다. 로테이션은 계속한다.


def _run_to_completion(headers, run_data, timeout, poll_interval):
    """폴링으로 run 완료까지 대기 → 데이터셋 아이템 반환.
    실행 도중 실패(FAILED/ABORTED/TIMED-OUT)는 토큰과 무관한 원인이므로 ApifyRunFailed로
    던져 **로테이션 없이 즉시 포기**시킨다(유료 run 반복 청구 방지).
    타임아웃은 로테이션 대상이지만, 넘기기 전에 기존 run을 abort한다."""
    run_id = run_data["id"]
    deadline = time.monotonic() + timeout
    status = run_data["status"]
    while status not in _TERMINAL_STATUSES:
        if time.monotonic() >= deadline:
            _abort_run(headers, run_id)
            raise TimeoutError(f"Apify run {run_id} 시간초과({timeout}s, 마지막 상태={status})")
        time.sleep(poll_interval)
        poll = requests.get(_RUN_STATUS_URL.format(run_id=run_id), headers=headers, timeout=30)
        poll.raise_for_status()
        run_data = poll.json()["data"]
        status = run_data["status"]

    if status != "SUCCEEDED":
        raise ApifyRunFailed(f"Apify run {run_id} 실패(status={status})")

    dataset_id = run_data["defaultDatasetId"]
    items = requests.get(
        _DATASET_ITEMS_URL.format(dataset_id=dataset_id), headers=headers, timeout=60
    )
    items.raise_for_status()
    return items.json()  # list of reel dicts


# 채널 하나의 run에 유저네임을 너무 많이(443개) 넣으면 액터가 인스타그램 자체
# 차단으로 추정되는 지점(실측: ~124번째 채널)에서 나머지를 아예 시도조차 안 하고
# 조용히 SUCCEEDED로 끝내버린다(2026-07-09 실측 — 443개 중 26개만 결과에 나타남,
# 에러조차 없이 나머지 316개가 그냥 누락됨). 30개 단위 테스트는 항상 전체가
# 정상 처리됐던 것에 근거해 여유있게 청크로 나눠 순차 호출한다.
CHUNK_SIZE = 40


def _run_with_rotation(payload, tokens, timeout, poll_interval, actor=APIFY_ACTOR):
    """지정 payload로 run 시작 → 토큰 로테이션 포함 완료까지 실행.
    fetch_reels(채널 목록)와 fetch_single_reel(단일 URL) 둘 다 이 공통
    로테이션 루프를 재사용한다(2026-07-09). actor를 다르게 지정하면 인스타
    외 다른 플랫폼 스크래퍼(예: tiktok_search.py)도 같은 토큰 풀·로테이션
    로직을 그대로 재사용할 수 있다.

    ★로테이션 정책(ApifyRunFailed 참고): 시작 거부(401/402/429·공짜)는 전 토큰을 돌지만,
    run이 도중에 실패한 경우(유료)는 _MAX_RUN_FAILURE_ROTATIONS번까지만 재시도한다.
    400 입력오류는 토큰 무관이므로 즉시 포기."""
    start = _load_key_index() % len(tokens)
    last_err = None
    run_failures = 0
    for offset in range(len(tokens)):
        idx = (start + offset) % len(tokens)
        current_token = tokens[idx]
        try:
            started = _start_run(current_token, payload, actor=actor)
            if started is None:
                last_err = requests.HTTPError(
                    f"apify 계정 {idx+1}/{len(tokens)} 사용량 소진/거부(시작 거부)"
                )
                continue
            headers, run_data = started
            items = _run_to_completion(headers, run_data, timeout, poll_interval)
            if idx != start:
                _save_key_index(idx)
            return items
        except ApifyRunFailed as e:
            run_failures += 1
            last_err = e
            if run_failures > _MAX_RUN_FAILURE_ROTATIONS:
                raise                   # 토큰 문제가 아니었다 — 더 돌면 유료 run만 쌓인다
            continue                    # 도중 소진이었을 수 있다 — 다음 토큰으로 한 번만
        except requests.HTTPError as e:
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code not in _EXHAUSTED_STATUSES:
                raise                   # 400 입력오류 등 — 토큰 바꿔도 같다
            last_err = e
            continue
        except (requests.RequestException, TimeoutError) as e:
            last_err = e                # 네트워크 오류·타임아웃(run은 abort됨) — 로테이션
            continue
    raise RuntimeError(f"apify 토큰 {len(tokens)}개 전부 실패(마지막 오류: {last_err})")


# apidojo~instagram-scraper-api로 전환(2026-07-13) — reel당 $0.0026(apify 공식
# reel-scraper) 대비 run당 $0.005 고정(151채널 실측 $0.755/회, 5배 절감).
# reel-scraper와 달리 username 배치 입력이 없어 채널당 run 1개 필요, 대신
# 동시실행(ThreadPoolExecutor)으로 속도 확보(151채널 실측 몇 분대).
_APIDOJO_ACTOR = "apidojo~instagram-scraper-api"
_PARALLEL_WORKERS = 15


def _relative_to_until_date(spec):
    """ONLY_NEWER_THAN 같은 상대 표현("2 days") → apidojo용 절대 날짜(YYYY-MM-DD).
    apidojo의 until 파라미터는 절대 날짜만 받아(apify reel-scraper의
    onlyPostsNewerThan 상대표현과 다름, 2026-07-13 확인) 여기서 변환한다."""
    m = re.match(r"\s*(\d+)\s*day", str(spec))
    days = int(m.group(1)) if m else 2
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def _normalize_apidojo_item(it, username):
    """apidojo 원본 아이템 → 기존 apify~instagram-reel-scraper 호환 스키마로 정규화
    (2026-07-13 실측 필드 매핑). ranking.py 등 하위 코드가 기존 필드명을 그대로
    쓰므로 여기서만 흡수하면 호출부 변경이 필요없다."""
    video = it.get("video") or {}
    image = it.get("image") or {}
    return {
        "shortcode": it.get("code", ""),
        "url": it.get("url", ""),
        "timestamp": it.get("createdAt", ""),
        "caption": it.get("caption") or "",
        "commentsCount": it.get("commentCount") or 0,
        "likesCount": it.get("likeCount") or 0,
        "videoViewCount": video.get("playCount") or 0,
        "displayUrl": image.get("url", ""),
        "videoUrl": video.get("url", ""),
        "ownerUsername": username,
    }


def fetch_reels(usernames, token=None, results_per_channel=RESULTS_PER_CHANNEL,
                only_newer_than=ONLY_NEWER_THAN, timeout=180, poll_interval=4,
                chunk_size=CHUNK_SIZE, max_workers=_PARALLEL_WORKERS):
    """usernames 리스트 → reel dict 리스트 (apidojo~instagram-scraper-api 기반,
    2026-07-13 전환). 채널당 run 1개(startUrls=.../reels/)를 동시실행 풀로
    처리 후 기존 스키마로 정규화해 합친다. chunk_size는 이제 미사용(구 시그니처
    호환용, 호출부 변경 불필요)."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정 (환경변수 APIFY_TOKEN)")
    until_date = _relative_to_until_date(only_newer_than)

    def _fetch_one(uname):
        clean = uname.strip().lstrip("@")
        payload = {
            "startUrls": [{"url": f"https://www.instagram.com/{clean}/reels/"}],
            "maxItems": results_per_channel,
            "until": until_date,
        }
        try:
            items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_APIDOJO_ACTOR)
        except RuntimeError:
            return []
        return [_normalize_apidojo_item(it, clean) for it in items]

    all_items = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_fetch_one, u) for u in usernames]
        for fut in as_completed(futures):
            all_items.extend(fut.result())
    return all_items


# 팔로워 조회 액터. 전용 프로필 액터(apify~instagram-profile-scraper)는 유료
# 렌탈이라 계정 체험 소진 시 403이 뜬다(2026-07-12 실측). 일반 스크래퍼
# (apify~instagram-scraper)는 같은 토큰풀로 403 없이 팔로워를 반환해 이걸로 교체.
_PROFILE_ACTOR = "apify~instagram-scraper"


def fetch_profiles(usernames, token=None, timeout=300, poll_interval=5):
    """usernames 리스트 → {username_소문자: {followers, posts, full_name}} (2026-07-12).

    릴스 스크래퍼엔 팔로워 정보가 없어(실측) 발굴 채널의 구독자수·참여밀도를
    채우려면 프로필을 따로 조회한다. apify~instagram-scraper의 details 모드에
    프로필 URL들을 한 run에 넣어 1회로 끝낸다(발굴 채널은 보통 ≤40개)."""
    if not usernames:
        return {}
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정")
    urls = [f"https://www.instagram.com/{u.strip().lstrip('@')}/" for u in usernames]
    payload = {"directUrls": urls, "resultsType": "details", "resultsLimit": len(urls)}
    items = _run_with_rotation(payload, tokens, timeout, poll_interval, actor=_PROFILE_ACTOR)
    out = {}
    for it in items:
        u = it.get("username")
        if not u:
            continue
        out[u.lower()] = {
            "followers": int(it.get("followersCount") or 0),
            "posts": int(it.get("postsCount") or 0),
            "full_name": it.get("fullName") or "",
        }
    return out


def fetch_single_reel(url, token=None, timeout=180, poll_interval=5):
    """추적 채널 목록에 없는 임의의 인스타 릴스 URL 하나를 즉시 조회(2026-07-09,
    제품찾기에서 "우리 목록에 없는 영상"도 분석할 수 있게 추가). "username"
    필드 하나로 유저네임과 직접 릴스 URL을 둘 다 받는다 — 청크 분할
    불필요(항목 1개), 토큰 로테이션은 fetch_reels와 동일 로직 재사용.
    결과 없으면(비공개 계정·삭제된 게시물 등) None.

    2026-07-10: 액터가 이날 새 빌드(0.0.468)로 "directUrls" 필드를 완전히
    없애고 "username" 필드 하나로 통합했음(실측: directUrls로 호출하면
    모든 계정에서 균일하게 400 "input.username is required" — 특정 URL이나
    토큰 문제가 아니라 액터 자체의 스키마 변경이었음). "username" 필드는
    유저네임/프로필URL/ID/릴스URL을 전부 받는다고 액터 설명에 명시됨."""
    tokens = [token] if token else APIFY_TOKENS
    if not tokens:
        raise RuntimeError("APIFY_TOKEN 미설정 (환경변수 APIFY_TOKEN)")
    payload = {
        "username": [url],
        "resultsLimit": 1,
        "skipPinnedPosts": True,
    }
    items = _run_with_rotation(payload, tokens, timeout, poll_interval)
    return items[0] if items else None
