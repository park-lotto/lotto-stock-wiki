"""Dynamically load Gemini API keys from .env by scanning numbered suffixes (_2, _3, ...)."""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
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


# 소진 잠금 유효시간(초). 만료되면 자동으로 풀린다.
# ★2026-09-01: 종전엔 **하루 낙인**이었다(날짜가 바뀔 때만 해제). 실측으로 그게
#   틀렸음이 드러났다 — 잠긴 키 11개를 구글에 직접 찔러보니 8개가 HTTP 200이었다.
#   ①"오늘"이 한국 자정 기준인데 구글은 태평양시 자정(한국 오후 4~5시)에 리셋하고
#   ②분당 한도를 일일 소진으로 잘못 낙인한 것도 섞였다.
#   쇼핑쇼츠 풀은 2026-08-27에 같은 이유로 이미 TTL로 바꿨다(comment_gen._EXHAUST_TTL_S).
#   서버가 'Please retry in 45.5s'로 알려주면 그 값을 쓰고, 없으면 이 기본값.
_EXHAUST_TTL_S = float(os.environ.get("VAULT_KEY_EXHAUST_TTL",
                                     os.environ.get("SHORTS_KEY_EXHAUST_TTL", "1800")))


def _exhausted_map(state) -> dict:
    """state의 exhausted를 {그룹: {인덱스: 만료ts}}로 읽는다.

    ★옛 형식({group: [idx, ...]})도 그대로 받는다 — 배포 순간에 파일이 옛 모양이다.
      옛 항목엔 만료시각이 없는데 '오늘 내내'로 두면 **바로 그 영구 낙인**이라
      배포 직후에도 증상이 그대로다. 그래서 기본 TTL이 붙은 것으로 본다
      (comment_gen이 2026-08-27에 같은 함정을 밟고 배운 것).
    """
    raw = state.get("exhausted") or {}
    out = {}
    for g, v in raw.items():
        if isinstance(v, dict):
            slot = {}
            for k, t in v.items():
                try:
                    slot[int(k)] = float(t)
                except (TypeError, ValueError):
                    continue
            out[g] = slot
        else:                                  # 옛 형식 list[int] — 기본 TTL을 붙인다
            fallback = time.time() + _EXHAUST_TTL_S
            out[g] = {int(i): fallback for i in (v or []) if isinstance(i, (int, float))}
    return out


def _live_exhausted(group: str, state=None) -> dict:
    """그 그룹에서 **아직 유효한** 잠금만 {인덱스: 만료ts}. 만료분은 여기서 걸러진다."""
    st = state if state is not None else _load_state()
    now = time.time()
    return {i: t for i, t in _exhausted_map(st).get(group, {}).items() if t > now}


def _load_state() -> dict:
    """★날짜로 버리지 않는다(2026-09-01) — 만료 판단은 TTL이 한다.
    종전엔 date가 다르면 통째로 버려 '한국 자정에만 해제'가 됐다."""
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state.get("exhausted"), dict):
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


def mark_exhausted(group: str, key: str, retry_after=None) -> None:
    """키를 **한시적으로** 잠근다(그룹별). retry_after(초)를 주면 그만큼, 없으면 기본 TTL.

    ★2026-09-01: '당일 소진'에서 TTL로 바꿨다. 하루 낙인은 멀쩡한 키를 놀렸다
      (실측: 잠긴 11개 중 8개가 HTTP 200). 위 _EXHAUST_TTL_S 주석 참조.
    """
    try:
        ttl = float(retry_after) if retry_after else _EXHAUST_TTL_S
    except (TypeError, ValueError):
        ttl = _EXHAUST_TTL_S
    # ⚠️상한 6시간 — 영구 낙인을 만들지 않는다.
    #   ★함정(아직 안 터졌다): retry_delay_seconds는 **일일** 소진에 '태평양 자정까지'
    #     (최대 24시간)를 주는데 여기서 6시간으로 깎인다. 지금은 호출부가 retry_after를
    #     안 넘겨(전부 2인자 호출) 아무 차이가 없지만, 넘기기 시작하면 일일 소진 키가
    #     6시간 뒤 풀려 또 얻어맞는다. 그때는 이 상한도 같이 올려라(25시간).
    #   ★2026-09-03: 그 함정이 터졌다. mark_failure가 retry_delay_seconds를 넘기기
    #     시작했으므로 상한도 25시간으로 올린다(comment_gen이 09-02에 같은 이유로 24시간).
    ttl = max(30.0, min(ttl, 25 * 3600.0))
    marked_idx = None
    with _FileLock(_LOCK_PATH):
        keys = get_keys(group)
        if key not in keys:
            return
        idx = keys.index(key)
        state = _load_state()
        cur = _exhausted_map(state)
        slot = cur.setdefault(group, {})
        until = time.time() + ttl
        if slot.get(idx, 0.0) < until:
            slot[idx] = until
            state["date"] = _today_str()      # 사람이 파일을 열어볼 때의 참고용
            state["exhausted"] = {g: {str(i): t for i, t in v.items()}
                                  for g, v in cur.items()}
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
                              detail=f"소진 잠금 {int(_EXHAUST_TTL_S)}초(TTL)")
        except Exception:           # noqa: BLE001
            pass


def _key_fingerprint(key: str) -> str:
    """키를 원문 없이 식별하는 지문. 풀 순서(idx)는 회원 키 합류·.env 편집으로 바뀌므로
    '영구 사망' 같은 오래 가는 표시는 반드시 이 지문으로 남긴다.
    (comment_gen._key_fingerprint와 같은 정의 — 상태파일이 서로 달라 각자 계산하지만
     값은 같으므로, 한쪽에서 죽은 키를 다른 쪽 파일에 옮겨 적을 수도 있다)"""
    return hashlib.sha256((key or "").encode()).hexdigest()[:16]


def dead_fingerprints(state=None) -> set:
    """지금 **쓰면 안 되는** 키의 지문 집합 = 영구 사망(401/403) + 사용불가 정지 중(2026-09-25).

    ★정지분을 여기에 합친다 — 이 함수를 보는 곳(get_live_keys·without_dead·쇼츠 풀의
      comment_gen._live_key_indices·되살림 프로브)이 전부 저절로 정지 키를 뺀다.
      빼는 규칙을 소비처마다 또 적지 않는다(0순위-B)."""
    st = state if state is not None else _load_state()
    return set(_active_dead(st)) | suspended_fingerprints(st)


# ★사망 표시도 **3일 뒤 다시 시험**한다(2026-09-25, 검토에서 드러난 실측).
#   403 "Your project has been denied access"는 '대부분 영구, 일부는 회복'이었다 — 회원 57 키
#   …nIWJaw는 09-02~07 403 뒤 09-08부터 하루 45~122번 성공(누적 1,242번). 그런데 이 파일엔
#   09-03 '영구 사망'이 그대로 남아 있었고, 쇼츠 풀이 이 표시를 합쳐 보게 되자 멀쩡한 키가
#   영원히 빠질 뻔했다(배포 전 반박 검토로 잡음). 만료가 지나면 한 번 불려 보고,
#   또 401/403이면 다시 3일(mark_dead가 시각을 새로 박는다), 성공하면 revive가 지운다.
_DEAD_RETEST_S = float(os.environ.get("GEMINI_KEY_DEAD_RETEST", str(3 * 24 * 3600)))


def _dead_map(state) -> dict:
    raw = (state or {}).get("dead_keys") or {}
    if isinstance(raw, dict):
        out = {}
        for f, t in raw.items():
            try:
                out[f] = float(t or 0)
            except (TypeError, ValueError):
                out[f] = 0.0
        return out
    return {f: 0.0 for f in (raw or [])}          # 옛 list 형식 — 시각이 없으니 만료로 본다


def _active_dead(state) -> dict:
    """아직 다시 시험할 때가 안 된 사망 표시만 {지문: 시각}."""
    cut = time.time() - _DEAD_RETEST_S
    return {f: t for f, t in _dead_map(state).items() if t > cut}


def mark_dead(key: str, detail=None, quiet=False) -> None:
    """키를 **사망**으로 뺀다 — 401/403. (2026-09-25부터 3일 뒤 재시험 — 위 _DEAD_RETEST_S 참고)

    ★왜 TTL 잠금과 갈랐나(2026-09-03 실측): 죽은 키 …nIWJaw가 09-01 22:10부터
      사흘째 403 PERMISSION_DENIED("Your project has been denied access")를 내는데도
      매일 다시 호출됐다(09-02 92건, 09-03 21건). 쿼터(429)는 회복되지만 계정
      비활성(401/403)은 회복되지 않는다 — TTL로 잠그면 만료 후 또 얻어맞는다.
      쇼핑쇼츠 comment_gen은 09-02에 같은 처방을 받았는데 vault(대시보드)만 없었다.
      키를 실제로 빼는 것(.env 편집)은 사람 몫이지만, 그때까지 호출을 한 번도 더
      낭비하지 않는다."""
    if not key:
        return
    fp = _key_fingerprint(key)
    newly = False
    with _FileLock(_LOCK_PATH):
        state = _load_state()
        dead = _dead_map(state)
        # 없거나 만료(다시 시험 중 또 죽음)면 시각을 새로 박는다 — 3일 뒤 또 한 번 시험받는다.
        if dead.get(fp, 0.0) <= time.time() - _DEAD_RETEST_S:
            dead[fp] = time.time()
            state["dead_keys"] = dead
            _write_state(state)
            newly = True
    _SUS_CACHE["t"] = 0.0
    if newly and not quiet:      # 관측·경보는 락 밖에서(mark_exhausted와 같은 이유)
        # quiet=True: 쇼츠 풀(comment_gen)이 이미 기록한 사망을 여기 옮겨 적을 때 — 두 번 세지 않는다
        print(f"key_vault: 키 영구 제외 — …{key[-6:]} ({detail or '401/403'})", file=sys.stderr)
        try:
            from shopping_shorts import api_health
            api_health.record("gemini", api_health.OUT_AUTH, pool="vault", key=key,
                              detail=f"영구 제외(dead) {detail or ''}"[:300])
        except Exception:           # noqa: BLE001 — 관측 실패가 제외를 막으면 안 된다
            pass


def without_dead(keys) -> list[str]:
    """목록에서 영구 사망 키만 뺀다(잠금은 건드리지 않는다).

    ★"전부 소진이면 원본 목록으로 최후 시도"하는 폴백 경로용이다. 소진은 시간이
      풀어주니 최후에 한 번 더 찔러볼 값어치가 있지만, 401/403은 몇 번을 찔러도
      실패다 — 폴백에서까지 넣으면 사망 키가 다시 목록 앞에 서게 된다."""
    dead = dead_fingerprints()
    if not dead:
        return list(keys or [])
    return [k for k in (keys or []) if _key_fingerprint(k) not in dead]


def mark_failure(key: str, exc: Exception, group: str = None) -> None:
    """호출 실패 하나를 받아 **어떤 표시를 남길지 여기서만 정한다**(0순위-B).

    401/403 → 영구 제외 / 429 → 서버가 준 재시도 시각만큼 한시 잠금 / 그 외 → 무시.
    ★대기하지 않는다. 표시만 남기면 다음 호출의 get_live_keys가 그 키를 빼주므로,
      호출부는 기다릴 필요 없이 **아직 안 맞은 키로 곧장** 간다(2026-09-03 설계).
    """
    if not key or exc is None:
        return
    # ★기다려도 안 풀리는 실패(계정 사망·선불 소진·월 한도·할당량 0)는 판정 한 곳으로(2026-09-25).
    #   종전엔 402·월 한도가 is_quota_error에 걸려 30분 잠금만 받고 풀리면 또 얻어맞았다.
    if note_failure(key, exc):
        return
    if is_quota_error(exc) or is_daily_exhausted_error(exc):
        owner = group or _owner_group(key)
        if owner:
            mark_exhausted(owner, key, retry_delay_seconds(exc))


def get_live_keys(group: str) -> list[str]:
    """잠긴 키를 뺀 그룹의 키 목록. ★만료된 잠금은 자동으로 풀린다(2026-09-01).
    ★영구 사망 키(401/403)는 지문으로 걸러진다 — 만료가 없다(2026-09-03)."""
    state = _load_state()
    exhausted = _live_exhausted(group, state)  # 만료분은 여기서 걸러진다
    dead = dead_fingerprints(state)
    return [k for i, k in enumerate(get_keys(group))
            if i not in exhausted and (not dead or _key_fingerprint(k) not in dead)]


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
# ★프로세스마다 **다른 지점**에서 출발한다(2026-09-01). 워커는 스레드가 아니라
#   systemd 템플릿 유닛(shopping-shorts-worker@)으로 뜨는 **독립 프로세스 12개**라
#   이 커서를 공유하지 않는다. 0에서 다 같이 출발하면 12개가 동시에 live[0]을 때린다
#   — edit_plan._auto_key_offset이 os.getpid()를 쓰는 것과 같은 이유.
_RR_CURSOR = {"i": os.getpid()}

_KEY_LAST_USED: dict[str, float] = {}
_RPM_PER_KEY = int(os.environ.get("VAULT_RPM_PER_KEY",
                                 os.environ.get("SHORTS_RPM_PER_KEY", "5")))
_MIN_GAP_S = 60.0 / max(1, _RPM_PER_KEY)


def rotated(live):
    """키 목록을 **다음 시작점부터** 돌려준다. 원소는 그대로, 순서만 회전.

    ★왜 필요한가(2026-09-01 사장님 "다같이 1번부터 써서 그런 거 아닌가" → 맞다):
      get_live_keys_cascade는 매번 **같은 순서**를 준다. 그래서 이 목록을 받아
      `for key in keys`로 도는 호출부는 성공하면 **항상 keys[0]**에서 끝난다.
      실측(최근 5분): 쓸 수 있는 키 82개 중 **21개만** 쓰이고 61개가 놀았다.
      rpm 990건의 88%가 "한 주체가 앞쪽 키에 혼자 몰아친" 것이었다.

    ★_pick_key와 짝이다: 저건 클라이언트 1개를 주고(get_client 경로), 이건 목록을
      준다(for문 경로). **커서를 공유**해야 두 경로가 서로 안 겹친다.

    ★호출부마다 offset을 심지 않는 이유(0순위-B): 어느 키부터 쓸지를 8군데에 적으면
      반드시 어긋난다. 2026-08-31에 edit_plan만 고쳐지고 나머지가 안 고쳐진 사고가
      정확히 그 구조의 산물이다. **목록을 나눠주는 곳에서 한 번만** 돌린다.
    """
    live = list(live or [])
    if len(live) < 2:
        return live                      # 0·1개면 돌릴 것이 없다(단일키 크론도 무해)
    i = _RR_CURSOR["i"] % len(live)
    _RR_CURSOR["i"] = i + 1
    return live[i:] + live[:i]


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


def seconds_until_quota_reset() -> float:
    """일일 한도가 풀리는 시각까지 남은 초(구글은 **태평양시 자정**에 리셋).

    ★서머타임 근사로 UTC-7을 쓴다(한국시간 오후 4~5시경). 정확히 몇 분 어긋나도
      "57초 뒤"보다는 비교할 수 없이 낫다 — 여기서 필요한 건 분 단위 정밀도가
      아니라 "오늘은 이 키를 그만 쓴다"는 판단이다.
    """
    now = datetime.now(timezone.utc)
    pac = now - timedelta(hours=7)
    nxt = (pac + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (nxt - pac).total_seconds())


def retry_delay_seconds(exc: Exception):
    """이 키를 **언제 다시 써도 되나**(초). 모르면 None.

    왜 필요한가(2026-08-09 실측): 무료등급 분당 한도 초과 시 서버는 **45초 뒤에
    오라**고 알려주는데, 호출부는 고정 8초만 자고 재시도했다. max_retries=3이면
    24초 만에 시도가 소진돼 조용히 빈 결과를 반환한다 — 태거가 `0/40건`을
    수백 채널 연속으로 찍은 원인. 서버가 알려준 값을 쓰면 한 번만 제대로 자고
    성공한다. None이면 호출부가 기존 기본값을 쓰도록 둔다(동작 보존).

    ★일일 소진이면 그 'retry in'을 **믿지 않는다**(2026-09-02 실사고).
      구글은 하루치를 다 쓴 429에도 'Please retry in 57.4s'를 함께 준다.
      그 값을 그대로 쓰면 57초 뒤 키가 풀려 또 때리고 또 막힌다 — 사장님이 본
      "죽은 키 1개를 18번 헛되이 호출" 경보가 정확히 이 되풀이였다.
      일일 한도는 태평양 자정까지 안 풀리므로 그때까지를 준다.
      ⚠️호출부 27곳이 전부 이 함수를 거친다 — 고칠 곳은 여기 하나다(0순위-B).
    """
    if is_daily_exhausted_error(exc):
        return seconds_until_quota_reset()
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
    # ★무효 키(API_KEY_INVALID)도 영구다(2026-09-04). 종전엔 edit_plan._is_dead_key_error만
    #   따로 잡아 **소진(30분 잠금)**으로 표시해, 죽은 키 …sJbmaQ가 09-03 56건·09-04 4건 다시 불렸다.
    return ("UNAUTHENTICATED" in m or "ACCOUNT_STATE_INVALID" in m
            or "PERMISSION_DENIED" in m
            or "API_KEY_INVALID" in m or "API key not valid" in m
            or "service account is deleted or disabled" in m)


# ── 쓸 수 없는 키 — 판정·정지·해제 (2026-09-25) ─────────────────────────────
# ★왜 생겼나(2026-09-25 실측, 서버 api_events): 공용 풀(사장님 14 + 회원 101)에
#   "몇 번을 불러도 안 되는 키"가 섞여 잠금 0번인 채 계속 불렸다.
#     - 402 선불 크레딧 소진(회원 204 키 …3L0lEA) — 09-04 이후 성공 0, 누적 수천 번
#     - 429 월 지출 한도(회원 346 키 …HLpLEE) — 성공 0, 잠금 0
#     - 429 할당량 0(limit: 0) 키 10개 — 24시간 1,013번 호출에 성공 0
#   셋 다 429/402라 "잠깐 기다리면 풀리는 한도"로 취급됐고, 대부분의 호출부는 PerDay일 때만
#   잠가서 **아무도 안 잠갔다.** 회원 설정 화면엔 여전히 'ok'였다.
# ★판정은 여기 한 곳(0순위-B). 호출부 30여 곳이 아니라 모든 호출이 지나가는
#   usage_meter 깔때기가 note_failure/note_success를 부른다 — 호출부를 안 고쳐도 전부 잡힌다.
# ★401/403(계정 사망)과 다르게 **영구 제외가 아니다.** 선불 충전·지출 한도 상향·결제 연결로
#   회원이 되살릴 수 있다. 그래서 24시간 동안만 빼고, 그 뒤 자연스럽게 한 번 다시 불려
#   되면 해제(note_success), 또 안 되면 다시 24시간 뺀다. 하루 헛호출이 수백 번 → 프로세스당 1번.
UNUSABLE_AUTH = "auth"            # 401/403·무효 키 — 영구(mark_dead)
UNUSABLE_PREPAY = "prepay"        # 402 선불 크레딧 소진 — 충전하면 살아난다
UNUSABLE_SPEND_CAP = "spend_cap"  # 월 지출 한도 도달 — 한도 올리거나 다음 달
UNUSABLE_NO_QUOTA = "no_quota"    # 할당량 0(프로젝트·지역 단위) — 그 프로젝트에 쓸 수 있는 몫이 없다

_SUSPEND_TTL_S = float(os.environ.get("GEMINI_KEY_SUSPEND_TTL", str(24 * 3600)))
# ★할당량 0은 **세부 항목의 quota_limit_value '0'**으로만 판정한다(2026-09-25 서버 원문 실측).
#   실제 원문(키 10개·7일 9,097건)은 문장에 'limit: 0'이 없고("Quota exceeded for quota metric
#   'Generate Content API requests per minute' and limit '...per minute for a region'") 세부에만
#   'quota_limit_value': '0'이 있다 — 처음엔 'limit: 0'만 봐서 하나도 못 잡았다(원문 재생으로 발견).
#   ⚠️문장형 '..., limit: 0, model: X'는 **모델 하나**의 한도다(무료 등급이 없는 모델 등).
#     그걸로 키 전체를 빼면 그 모델 호출 몇 번에 풀이 통째로 비는다 — 반박 검토에서 재현,
#     서버 09-11 이후 19만 건 중 문장형은 0건이라 잃는 것도 없다. 그래서 뺐다.
_LIMIT_ZERO_RE = re.compile(r"quota_limit_value['\"]?\s*:\s*['\"]?0(?![0-9.])")


def unusable_reason(exc) -> str | None:
    """기다려도 안 풀리는 실패면 그 이유(UNUSABLE_*), 아니면 None.

    ⚠️503(구글 과부하)·분당/일일 한도·일반 429는 None이다 — 그건 키 잘못이 아니거나
      시간이 풀어준다. 여기서 True를 내면 **멀쩡한 키를 하루 뺀다**, 좁게 잡는다.
    """
    m = str(exc or "")
    if not m:
        return None
    if is_account_disabled_error(Exception(m)):
        return UNUSABLE_AUTH
    low = m.lower()
    if "prepayment credits are depleted" in low or ("402" in m and "prepay" in low):
        return UNUSABLE_PREPAY
    if "spending cap" in low:
        return UNUSABLE_SPEND_CAP
    if ("429" in m or "RESOURCE_EXHAUSTED" in m) and _LIMIT_ZERO_RE.search(m):
        return UNUSABLE_NO_QUOTA
    return None


def _suspended_map(state) -> dict:
    raw = (state or {}).get("suspended") or {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}


def _write_state(state) -> None:
    tmp_path = _STATE_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp_path, _STATE_PATH)


def suspended_fingerprints(state=None) -> set:
    """지금 **빼 둔**(until 전) 키의 지문. 만료된 항목은 다시 시험받도록 여기서 빠진다."""
    st = state if state is not None else _load_state()
    now = time.time()
    out = set()
    for fp, ent in _suspended_map(st).items():
        try:
            if float(ent.get("until", 0)) > now:
                out.add(fp)
        except (TypeError, ValueError):
            continue
    return out


def suspension_info(state=None) -> dict:
    """화면 표시용 — {지문: {reason, since, last, until}}. **만료분도 포함**한다.
    만료 = '다시 시험 대기'일 뿐 살아난 게 아니다. 살아났으면 note_success가 지운다."""
    st = state if state is not None else _load_state()
    return {fp: dict(ent) for fp, ent in _suspended_map(st).items()}


def unusable_info_for(fingerprints) -> dict:
    """지문들 중 쓸 수 없는 것만 {지문: {reason, since}} — 회원 키 화면·안내가 쓴다.
    영구 사망(401/403)은 reason='auth'로 함께 준다. 판단처는 이 상태파일 하나다."""
    fps = set(fingerprints or [])
    if not fps:
        return {}
    st = _load_state()
    out = {}
    dead = _active_dead(st)                 # 재시험 기간이 지난 옛 사망 표시는 안 보여 준다
    for fp in fps & set(dead):
        out[fp] = {"reason": UNUSABLE_AUTH, "since": dead.get(fp) or None}
    for fp, ent in _suspended_map(st).items():
        if fp in fps and fp not in out:
            out[fp] = {"reason": ent.get("reason"), "since": ent.get("since")}
    return out


def suspend(key: str, reason: str, detail=None, ttl=None) -> bool:
    """쓸 수 없는 키를 ttl(기본 24시간) 동안 **모든 풀·모든 프로세스**에서 뺀다.
    반환: 이번에 새로 빠졌으면 True(이미 빠져 있던 키의 연장이면 False)."""
    if not key or not reason:
        return False
    fp = _key_fingerprint(key)
    now = time.time()
    try:
        ttl_s = float(ttl) if ttl is not None else _SUSPEND_TTL_S
    except (TypeError, ValueError):
        ttl_s = _SUSPEND_TTL_S
    ttl_s = max(60.0, min(ttl_s, 31 * 24 * 3600.0))
    with _FileLock(_LOCK_PATH):
        state = _load_state()
        sus = _suspended_map(state)
        prev = sus.get(fp)
        # ★같은 실패가 깔때기와 호출부(comment_gen._mark_key_exhausted 등)에서 두 번 들어온다 —
        #   60초 안에 같은 이유로 이미 박혔으면 파일 쓰기·기록을 또 하지 않는다(검토에서 발견).
        try:
            if prev and prev.get("reason") == reason and now - float(prev.get("last", 0)) < 60 \
                    and float(prev.get("until", 0)) > now:
                return False
        except (TypeError, ValueError):
            pass
        newly = prev is None
        ent = dict(prev or {})
        ent.setdefault("since", now)
        ent.update({"until": now + ttl_s, "reason": reason, "last": now, "tail": key[-6:]})
        sus[fp] = ent
        state["suspended"] = sus
        _write_state(state)
    _SUS_CACHE["t"] = 0.0
    # 관측·경보는 락 밖에서(mark_exhausted와 같은 이유)
    try:
        from shopping_shorts import api_health
        api_health.record("gemini", api_health.OUT_LOCK, key=key,
                          detail=f"사용불가 정지 {int(ttl_s)}초 ({reason}) {str(detail or '')[:200]}")
    except Exception:               # noqa: BLE001 — 쇼핑쇼츠 없는 환경이면 조용히 통과
        pass
    if newly:
        print(f"key_vault: 쓸 수 없는 키 정지 — …{key[-6:]} ({reason})", file=sys.stderr)
        _tg_alert(f"⚠️ <b>제미니 키 …{key[-6:]} 사용 불가</b> ({_REASON_KO.get(reason, reason)})\n"
                  f"→ 모든 풀에서 {int(ttl_s // 3600)}시간 뺐다. 회원 키면 회원 화면에 교체 안내가 뜬다.")
    return newly


def unsuspend(key: str) -> bool:
    """키가 다시 성공했다 — 정지 **와 사망** 표시를 지운다. 반환: 지운 게 있으면 True.

    ★성공은 가장 강한 증거다(2026-09-25). 403 뒤 되살아난 키(회원 57 …nIWJaw)가 성공해도
      사망 표시가 안 지워져 영영 빠질 뻔했다 — 회원이 [전체 확인]으로 살아 있음을 보여도 그랬다."""
    if not key:
        return False
    fp = _key_fingerprint(key)
    with _FileLock(_LOCK_PATH):
        state = _load_state()
        sus = _suspended_map(state)
        dead = _dead_map(state)
        if fp not in sus and fp not in dead:
            return False
        sus.pop(fp, None)
        dead.pop(fp, None)
        state["suspended"] = sus
        state["dead_keys"] = dead
        _write_state(state)
    _SUS_CACHE["t"] = 0.0
    print(f"key_vault: 멈췄던 키 되살아남 — …{key[-6:]}", file=sys.stderr)
    return True


revive = unsuspend        # 읽는 사람을 위한 별칭 — 사망까지 지운다는 뜻이 이름에 드러나게


_REASON_KO = {
    UNUSABLE_AUTH: "키가 삭제·비활성·무효",
    UNUSABLE_PREPAY: "선불 크레딧 소진",
    UNUSABLE_SPEND_CAP: "월 지출 한도 도달",
    UNUSABLE_NO_QUOTA: "할당량 0",
}

# note_success가 매 성공마다 파일을 읽지 않게 지문 목록을 잠깐 들고 있는다.
_SUS_CACHE = {"t": 0.0, "fps": frozenset()}
_SUS_CACHE_S = 30.0


def _suspended_any_cached() -> frozenset:
    now = time.time()
    if now - _SUS_CACHE["t"] > _SUS_CACHE_S:
        try:
            st = _load_state()
            # 정지 + 사망(만료분 포함) — 성공하면 어느 쪽이든 지운다
            _SUS_CACHE["fps"] = frozenset(_suspended_map(st)) | frozenset(_dead_map(st))
        except Exception as e:      # noqa: BLE001 — 캐시를 못 채우면 이번엔 해제만 늦어진다
            print(f"key_vault: 정지 목록 읽기 실패(무해) {e!r}", file=sys.stderr)
            _SUS_CACHE["fps"] = frozenset()
        _SUS_CACHE["t"] = now
    return _SUS_CACHE["fps"]


def note_failure(key: str, exc) -> str | None:
    """호출 하나가 실패했다 — 쓸 수 없는 키면 빼고 그 이유를, 아니면 None.
    ★usage_meter 깔때기에서만 부른다(모든 제미니 호출이 거기를 지난다).
    ★사망은 quiet — 깔때기가 이미 api_health.record_failure로 OUT_AUTH를 남겼다(두 번 세지 않는다)."""
    if not key or exc is None:
        return None
    reason = unusable_reason(exc)
    if reason == UNUSABLE_AUTH:
        mark_dead(key, detail=str(exc)[:120], quiet=True)
    elif reason:
        suspend(key, reason, detail=str(exc)[:200])
    return reason


def note_success(key: str) -> None:
    """호출 하나가 성공했다 — 정지·사망 표시가 있던 키면(재시험 통과·충전·되살아남) 지운다."""
    if not key:
        return
    if _key_fingerprint(key) in _suspended_any_cached():
        unsuspend(key)


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
