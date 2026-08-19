"""쿠팡 검색 로컬 릴레이(2026-07-29) — 서버가 못 하는 검색을 사장님 PC가 대신 돈다.

왜 필요한가(실측, `coupang_search` 상단 표와 같은 실험):

    사장님 PC(한국 주거용 IP) + 헤드풀 Chrome  → 200 · 상품 58건
    서버 Webshare 출구(독일 보다폰 **주거용**)  → 403
    서버 직결(AWS 데이터센터)                   → 403

즉 쿠팡이 보는 건 "주거용이냐"가 아니라 **"한국이냐"**다. 서버에 한국 출구가 없으면
서버는 영영 못 긁는다. 그래서 방향을 뒤집는다 — **서버가 PC에게 물어본다.**

    [브라우저] ──검색──> [서버 /api/coupang/search]
                              │  큐에 넣고 최대 N초 기다림
                              ▼
                         (대기열)
                              ▲
    [사장님 PC 릴레이] ──롱폴링──┘   scripts/coupang_relay.py
        └ 로컬에서 coupang_search.search() 실행 → 결과를 서버에 POST

서버가 PC로 접속하지 않는다(포트포워딩·공인IP 불필요). **PC가 서버로 나가서** 일감을
받아온다 — 공유기 뒤에서도 그냥 된다.

설계 원칙:
- 큐는 **메모리**다. 재시작하면 비는 게 맞다 — 검색 요청은 사람이 버튼을 누른 그 순간에만
  의미가 있고, 되살려봐야 아무도 안 보는 화면에 답하게 된다.
- 릴레이가 안 떠 있으면(=PC가 꺼져 있으면) 타임아웃으로 접고 `notice`를 돌려준다.
  화면은 그때 기존 수동 흐름(검색 링크 새 탭 + URL 붙여넣기)으로 되돌아간다.
- 토큰(`COUPANG_RELAY_TOKEN`)이 비어 있으면 릴레이 엔드포인트는 **아예 닫는다** —
  빈 토큰이 통과하면 아무나 우리 서버에 검색결과를 밀어넣을 수 있다.
"""
import threading
import time
import uuid


class _Job:
    # ★kind·payload·on_done 추가(2026-08-17) — 일감이 '검색' 하나뿐이 아니게 됐다.
    #   kind="search"  기존 그대로(웹 요청이 결과를 기다린다)
    #   kind="detail"  상품 상세·리뷰 수집 — **아무도 안 기다린다**(1단계에서 미리 걸어둔다).
    #                  결과가 오면 on_done(payload)로 서버가 job에 저장한다.
    __slots__ = ("id", "kind", "q", "limit", "payload", "done", "result", "taken_at", "on_done")

    def __init__(self, q, limit, kind="search", payload=None, on_done=None):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.q = q
        self.limit = limit
        self.payload = payload or {}
        self.done = threading.Event()
        self.result = None
        self.taken_at = 0.0
        self.on_done = on_done


class RelayQueue:
    """검색 요청 대기열. 웹 요청 스레드 여러 개가 동시에 만지므로 락으로 감싼다."""

    def __init__(self):
        self._lock = threading.Lock()
        self._waiting = []          # 아직 아무도 안 가져간 일감
        self._inflight = {}         # id → _Job (릴레이가 가져가 처리 중)
        self.last_seen = 0.0        # 릴레이가 마지막으로 폴링해 온 시각

    # ── 서버(웹 요청) 쪽 ──
    def submit(self, q, limit, timeout):
        """일감을 넣고 결과를 기다린다. 시간 안에 안 오면 None."""
        job = _Job(q, limit)
        with self._lock:
            self._waiting.append(job)
        if job.done.wait(timeout):
            return job.result
        with self._lock:                       # 시간초과 — 흔적을 지운다
            if job in self._waiting:
                self._waiting.remove(job)
            self._inflight.pop(job.id, None)
        return None

    # ── 릴레이(사장님 PC) 쪽 ──
    def take(self, wait_seconds):
        """롱폴링 — 일감이 생길 때까지 최대 wait_seconds 기다렸다 하나 준다."""
        deadline = time.monotonic() + max(0.0, wait_seconds)
        with self._lock:
            self.last_seen = time.time()
        while True:
            with self._lock:
                if self._waiting:
                    job = self._waiting.pop(0)
                    job.taken_at = time.time()
                    self._inflight[job.id] = job
                    return job
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.25)

    def complete(self, job_id, payload):
        """릴레이가 보낸 결과를 기다리던 요청에 꽂는다. 모르는 id면 False."""
        with self._lock:
            job = self._inflight.pop(job_id, None)
            self.last_seen = time.time()
        if job is None:
            return False
        job.result = payload
        job.done.set()
        # ★기다리는 사람이 없는 일감(kind="detail")은 여기서 뒷정리까지 해야 한다 —
        #   결과를 job에 저장하는 건 콜백이 한다. 콜백이 터져도 릴레이 응답은 200이어야
        #   릴레이가 다음 일감으로 넘어간다(저장 실패로 릴레이를 세우지 않는다).
        if job.on_done:
            try:
                job.on_done(payload, job.payload)
            except Exception as e:      # noqa: BLE001
                print("[coupang_relay] on_done 실패: %s %s" % (type(e).__name__, str(e)[:120]))
        return True

    def submit_async(self, kind, payload, q="", on_done=None):
        """결과를 **안 기다리고** 큐에만 넣는다(1단계 선수집용). 넣은 일감 id를 준다.

        기존 submit은 웹 요청이 그 자리에서 결과를 기다리는 구조라, 2~3분 걸리는
        상세·리뷰 수집에는 못 쓴다(사장님을 그만큼 세워둔다). 그래서 넣고 잊는다."""
        job = _Job(q, None, kind=kind, payload=payload, on_done=on_done)
        with self._lock:
            self._waiting.append(job)
        return job.id

    # ── 상태 ──
    def status(self):
        with self._lock:
            return {"waiting": len(self._waiting), "inflight": len(self._inflight),
                    "last_seen": self.last_seen,
                    "online": bool(self.last_seen and time.time() - self.last_seen < 60)}


# 프로세스 하나가 큐 하나를 갖는다(워커를 여러 개로 늘리면 릴레이도 그만큼 붙어야 한다 —
# 지금 서비스는 단일 워커다).
QUEUE = RelayQueue()
