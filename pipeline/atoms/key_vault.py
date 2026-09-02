"""Dynamically load Gemini API keys from .env by scanning numbered suffixes (_2, _3, ...)."""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from google import genai

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"
_STATE_PATH = Path(__file__).parent / ".gemini_key_state.json"
_LOCK_PATH = Path(__file__).parent / ".gemini_key_state.lock"

_GROUP_ENV_PREFIX = {
    "general": "GEMINI_API_KEY",
    "ingest": "GEMINI_INGEST_KEY",
    "embed": "GEMINI_EMBED_KEY",
    "briefing": "GEMINI_BRIEFING_KEY",
}

# ★상한을 30 → 120으로 올린다(2026-08-31 실사고). 회원 키를 .env에 넣어 응급 복구할 때
#   `GEMINI_API_KEY_31` 이상이 **조용히 무시돼** 49개 중 23개만 들어갔다. 화면에도 로그에도
#   아무 표시가 없어 "넣었는데 왜 그대로냐"가 된다. 이 상한은 무한루프 방지용일 뿐이라
#   넉넉히 잡아도 비용이 없다(없는 번호는 그냥 건너뛴다).
_MAX_KEYS_PER_GROUP = 120


def _read_env_file() -> dict[str, str]:
    vals: dict[str, str] = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def _env(name: str, env_vals: dict[str, str]) -> str:
    return os.environ.get(name) or env_vals.get(name, "")


# ★회원 키 합류분(2026-08-24, 쇼핑쇼츠 1기). 회원이 등록한 제미니 키를 여기에 담아두면
#   get_keys가 **각 그룹 뒤에** 붙여준다. 쇼핑쇼츠 app이 기동·키등록/삭제 때 채운다.
#   ⚠️소진 상태파일이 인덱스 기반이라 반드시 **뒤에만** 붙인다 — 앞에 끼면 인덱스가
#     밀려 엉뚱한 키가 죽은 것으로 기록된다.
#   ⚠️주식위키 파이프라인도 이 모듈을 쓴다 — 기본값이 비어 있어 안 부르면 종전과 같다.
_member_keys: list[str] = []


def set_member_keys(keys) -> int:
    """회원 합류 키를 갈아끼운다(누적 아님 — 두 번 불러도 중복 안 쌓인다). 반환: 개수."""
    global _member_keys
    _member_keys = [k for k in (keys or []) if k]
    return len(_member_keys)


def get_keys(group: str) -> list[str]:
    """그룹의 활성 키 전부(존재하는 _N 넘버링을 동적으로 스캔, 순서 보존).
    회원 합류 키(set_member_keys)가 있으면 **뒤에** 붙는다(중복 제거)."""
    prefix = _GROUP_ENV_PREFIX[group]
    env_vals = _read_env_file()
    keys = []
    for i in range(1, _MAX_KEYS_PER_GROUP + 1):
        name = prefix if i == 1 else f"{prefix}_{i}"
        v = _env(name, env_vals)
        if v:
            keys.append(v)
    seen = set(keys)
    for k in _member_keys:
        if k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_state() -> dict:
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
        if state.get("date") == _today_str() and isinstance(state.get("exhausted"), dict):
            return state
    except Exception:
        pass
    return {"date": _today_str(), "exhausted": {}}


class _FileLock:
    """파일 락(Windows=msvcrt, POSIX=fcntl) — 상태 파일 read-modify-write 동시성 보호.
    이전엔 msvcrt만 써서 리눅스 서버에서 키 로테이션마다 ModuleNotFoundError로 죽었었다
    (2026-07-05 실서버 인제스트 크래시로 발견 — 원격 서버 pytest 회귀에 이미 잡혀있었으나
    v1 daily_verify가 "발견만" 하고 고치지 않아 며칠간 방치됨)."""

    def __init__(self, path: Path, timeout: float = 5.0):
        self._path = path
        self._timeout = timeout
        self._fh = None

    def __enter__(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a+")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() > deadline:
                    return self  # 타임아웃 시 락 없이 진행(최선 시도, 완전 원자성 포기)
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            if sys.platform == "win32":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self._fh.close()


def mark_exhausted(group: str, key: str) -> None:
    """키를 당일 소진으로 기록(그룹별). 이후 프로세스는 재시도하지 않는다."""
    marked_idx = None
    with _FileLock(_LOCK_PATH):
        keys = get_keys(group)
        if key not in keys:
            return
        idx = keys.index(key)
        state = _load_state()
        bucket = state["exhausted"].setdefault(group, [])
        if idx not in bucket:
            bucket.append(idx)
            tmp_path = _STATE_PATH.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp_path, _STATE_PATH)
            marked_idx = idx
    # ★기록은 락 **밖**에서(2026-09-01 리뷰 확정) — DB가 붐비면 record가 수 초를
    #   먹는데 그동안 락을 쥐면 다른 프로세스가 5초 타임아웃 후 '락 없이 진행'으로
    #   떨어져 소진표시가 유실될 수 있다(comment_gen도 락 밖에서 기록한다).
    if marked_idx is not None:
        try:                        # 관측판 — 쇼핑쇼츠 없는 환경이면 조용히 통과
            from shopping_shorts import api_health
            api_health.record("gemini", api_health.OUT_LOCK,
                              pool=f"vault-{group}", key_idx=marked_idx, key=key,
                              detail="당일 낙인(vault엔 TTL 없음)")
        except Exception:           # noqa: BLE001
            pass


def get_live_keys(group: str) -> list[str]:
    """당일 소진 기록된 키를 제외한 그룹의 키 목록."""
    state = _load_state()
    exhausted = set(state["exhausted"].get(group, []))
    return [k for i, k in enumerate(get_keys(group)) if i not in exhausted]


def _cascade_groups(group: str) -> list[str]:
    """폴백 순서: 해당 그룹 먼저 → 나머지 그룹(정의 순서)."""
    return [group] + [g for g in _GROUP_ENV_PREFIX if g != group]


def _owner_group(key: str) -> str | None:
    """키가 속한 그룹을 찾는다(cross-group 소진 기록용)."""
    for g in _GROUP_ENV_PREFIX:
        if key in get_keys(g):
            return g
    return None


def get_live_keys_cascade(group: str) -> list[str]:
    """primary 그룹 라이브 키 우선, 소진 시 다른 그룹 라이브 키로 순차 폴백(18개 전체 풀).
    한 작업의 그룹이 다 말라도 놀고 있는 다른 그룹 키를 빌려 쓴다."""
    seen: set[str] = set()
    out: list[str] = []
    for g in _cascade_groups(group):
        for k in get_live_keys(g):
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


_client_cache: dict[str, genai.Client] = {}
_active_idx: dict[str, int] = {}


def get_client_for_key(key: str) -> genai.Client:
    # 키마다 클라이언트를 캐시 — 중복 생성 방지
    if key not in _client_cache:
        cl = genai.Client(api_key=key)
        # 토큰 사용량 계측(2026-08-16). key_vault는 주식위키 파이프라인도 쓰므로
        # shopping_shorts에 하드 의존하면 안 된다 — 없으면 조용히 원본을 쓴다.
        try:
            from shopping_shorts import usage_meter
            # pool/key(2026-09-01, API 관측판): 어느 풀의 어느 키인지 귀속.
            # 그룹은 여기서 모르므로 vault로 뭉뚱그린다 — 그룹 구분은 스냅샷이 한다.
            cl = usage_meter.wrap(cl, pool="vault", key=key)
        except Exception:      # noqa: BLE001 — 계측은 있으면 좋고 없어도 돈다
            pass
        _client_cache[key] = cl
    return _client_cache[key]


# ── 분산(2026-09-01) — 키가 많아도 1개만 때리던 것을 고친다 ────────────────
# ★실측(최근 6시간, api_events): 쇼핑쇼츠 web은 68개 키로 360콜에 rpm 0건인데
#   주식위키 server는 13개 키로 983콜에 rpm 398건이었다. report_ingest는 키 1개로
#   64콜을 쳐서 **64건 전부** 분당한도. 같은 시각·같은 구글 한도인데 결과가 정반대다.
#   차이는 나눠 쓰느냐뿐이었다 — 키를 더 살 문제가 아니다.
#
# comment_gen이 쓰는 방식을 그대로 가져온다(그쪽은 실측 rpm 0~1건):
#   ① 호출마다 다음 키로 넘기는 라운드로빈 커서
#   ② 키마다 최소 간격을 둬서 **애초에 429를 안 맞게** 한다
#      (무료등급 실측 상한은 키당 분당 5건 — comment_gen._RPM_PER_KEY와 같은 근거)
_RR_CURSOR = {"i": 0}
_KEY_LAST_USED: dict[str, float] = {}
_RPM_PER_KEY = int(os.environ.get("VAULT_RPM_PER_KEY",
                                 os.environ.get("SHORTS_RPM_PER_KEY", "5")))
_MIN_GAP_S = 60.0 / max(1, _RPM_PER_KEY)


def _pick_key(live: list[str]) -> str:
    """라이브 키 중 '지금 쓸 수 있는' 것을 하나 고른다(라운드로빈 + 최소 간격).

    전부 쿨다운 중이면 가장 빨리 풀리는 키가 풀릴 때까지만 잔다(최대 _MIN_GAP_S).
    키가 많아질수록 대기는 0에 수렴한다 — 키를 늘리면 그대로 빨라진다.
    ⚠️프로세스 로컬이다(comment_gen도 같다). 여러 프로세스가 같이 돌면 실효 RPM이
      프로세스 수만큼 곱해질 수 있다 — 그래도 '1개만 때리기'보다는 압도적으로 낫다.
    """
    if not live:
        return ""
    while True:
        now = time.monotonic()
        start = _RR_CURSOR["i"] % len(live)
        _RR_CURSOR["i"] = start + 1
        soonest = None
        for off in range(len(live)):
            k = live[(start + off) % len(live)]
            ready_at = _KEY_LAST_USED.get(k, 0.0) + _MIN_GAP_S
            if ready_at <= now:
                _KEY_LAST_USED[k] = now
                return k
            if soonest is None or ready_at < soonest:
                soonest = ready_at
        time.sleep(min(max(0.0, (soonest or now) - now), _MIN_GAP_S))


def pick_paced_key(live: list[str]) -> str:
    """키 목록에서 **지금 쓸 수 있는** 키를 하나 고른다(라운드로빈 + 분당 최소 간격).

    ★왜 공개하나(2026-09-01): 목록을 직접 순회하는 호출부(script_generate·seo_generate·
      thumb_title·pattern_bank)는 get_client(group)를 안 거쳐 **페이서를 통째로 우회**했다.
      실측(오늘 KST 12·15시 피크): 대본생성 web 407콜 중 429 분당한도 149건(36.6%).
      `for key in keys:`가 간격 0으로 연타하고, 429가 나면 대기 없이 다음 키로 넘어가
      키 76개를 순식간에 다 태운다.

    ★get_client_for_key 안에 넣지 않는 이유: 그 함수는 클라이언트만 얻고 실제로는
      호출하지 않는 자리에서도 불린다 — 거기서 재우면 엉뚱한 곳이 느려진다.
      **호출 직전에** 이 함수로 키를 고르는 게 맞다.

    내부 구현은 _pick_key 하나뿐이다(0순위-B: 같은 판단을 두 번 적지 않는다).
    """
    return _pick_key(live)


def get_client(group: str) -> genai.Client:
    """그룹의 키로 클라이언트 반환. 그룹이 다 소진되면 다른 그룹 키로 폴백.

    ★2026-09-01: 늘 live[0]을 주던 것을 **라운드로빈 + 분당 페이서**로 바꿨다
      (_pick_key). 위 주석의 실측 참조 — 이 한 줄이 rpm 398건의 원인이었다.
    """
    all_keys = get_keys(group)
    if not all_keys:
        raise RuntimeError(f"key_vault: '{group}' 그룹에 설정된 Gemini 키가 없습니다 (.env 확인)")
    live = get_live_keys_cascade(group)  # cross-group 폴백
    if not live:
        live = all_keys[-1:]  # 전체 소진 시 최후로 마지막 키 시도
    return get_client_for_key(_pick_key(live))


client = get_client  # 드롭인 헬퍼 별칭 — genai.Client(api_key=...) 대체용


def reset(group: str) -> None:
    """세션 시작 시 인덱스 초기화(당일 소진 기록 자체는 유지)."""
    _active_idx[group] = 0


def rotate(group: str) -> bool:
    """현재 활성 키를 소진 처리하고 다음 살아있는 키로 교체(그룹 소진 시 다른 그룹으로 폴백).
    18개 전체 풀에 살아있는 키가 남으면 True, 전부 소진이면 알림 후 False."""
    live_before = get_live_keys_cascade(group)
    total = sum(len(get_keys(g)) for g in _GROUP_ENV_PREFIX)
    if not live_before:
        _tg_alert(f"🚨 <b>[{group}] Gemini 키 전체 소진</b>\n전 그룹 총 {total}개 모두 일일 한도 초과")
        return False

    idx = min(_active_idx.get(group, 0), len(live_before) - 1)
    old_key = live_before[idx]
    owner = _owner_group(old_key) or group
    old_num = get_keys(owner).index(old_key) + 1
    mark_exhausted(owner, old_key)  # 빌려 쓴 키는 소유 그룹에 소진 기록

    live_after = get_live_keys_cascade(group)
    if live_after:
        _active_idx[group] = 0
        note = "" if owner == group else f" [{owner} 그룹 키 차용]"
        _tg_alert(
            f"⚠️ <b>[{group}] Gemini 키 #{old_num}{note} 일일 한도 소진</b>\n"
            f"→ 다음 키로 교체 (전체 풀 잔여 {len(live_after)}개)"
        )
        return True
    _tg_alert(f"🚨 <b>[{group}] Gemini 키 전체 소진</b>\n전 그룹 총 {total}개 모두 일일 한도 초과")
    return False


def is_daily_exhausted_error(exc: Exception) -> bool:
    m = str(exc)
    return ("429" in m or "RESOURCE_EXHAUSTED" in m) and ("PerDay" in m or "limit: 500" in m)


def retry_delay_seconds(exc: Exception):
    """429 본문의 'Please retry in 45.5s' → 45.5. 없으면 None.

    왜 필요한가(2026-08-09 실측): 무료등급 분당 한도 초과 시 서버는 **45초 뒤에
    오라**고 알려주는데, 호출부는 고정 8초만 자고 재시도했다. max_retries=3이면
    24초 만에 시도가 소진돼 조용히 빈 결과를 반환한다 — 태거가 `0/40건`을
    수백 채널 연속으로 찍은 원인. 서버가 알려준 값을 쓰면 한 번만 제대로 자고
    성공한다. None이면 호출부가 기존 기본값을 쓰도록 둔다(동작 보존)."""
    m = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)\s*s", str(exc), re.IGNORECASE)
    return float(m.group(1)) if m else None


def is_quota_error(exc: Exception) -> bool:
    m = str(exc)
    return "429" in m or "RESOURCE_EXHAUSTED" in m


def is_account_disabled_error(exc: Exception) -> bool:
    """키의 바운드 서비스 계정 자체가 삭제/비활성화된 경우(429 쿼터가 아니라
    401 UNAUTHENTICATED / 403 PERMISSION_DENIED) — 재시도해도 절대 안 풀리므로
    소진과 동일하게 영구 제외해야 한다(2026-07-10, 쇼핑쇼츠 신규 키 추가 후에도
    계속 빈 결과가 나오던 원인 진단 중 발견 — 기존 is_daily_exhausted_error/
    is_quota_error 둘 다 이 에러를 못 잡아서 같은 죽은 키만 계속 재시도하고 있었음).

    ★403 PERMISSION_DENIED 추가(2026-08-10 실사고): 서비스계정 27/28개가 구글에
      의해 무더기 비활성화됐는데, 죽은 키가 401이 아니라 403 PERMISSION_DENIED로도
      떨어졌다. 401만 잡던 탓에 403 키는 어느 판정에도 안 걸려 소진표시가 안 됐고,
      제작소가 _current_key_and_idx()로 늘 같은 죽은 live[0]을 다시 잡아 매 job
      실패했다("로테이션이 바로 안 됨"의 진짜 원인). 403도 계정 문제라 영구 제외한다."""
    m = str(exc)
    return ("UNAUTHENTICATED" in m or "ACCOUNT_STATE_INVALID" in m
            or "PERMISSION_DENIED" in m
            or "service account is deleted or disabled" in m)


def _tg_alert(text: str) -> None:
    """API 에러·키 소진 등을 텔레그램으로 즉시 발송. 실패해도 호출부 중단 없음."""
    env_vals = _read_env_file()
    token = _env("BOT_TOKEN", env_vals)
    chat_id = _env("CHAT_ID", env_vals)
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass
