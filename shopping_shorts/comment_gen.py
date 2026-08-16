"""Gemini로 릴스 캡션 기반 자연스러운 댓글 후보 생성.

전용 키 풀(SHORTS_GEMINI_KEYS)을 직접 로테이션한다 — 주식위키 본체가 쓰는
pipeline.atoms.key_vault의 공유 풀과 분리(2026-07-09, 공유 풀이 다른 작업들과
하루 종일 같이 소모되다 예고 없이 소진된 사고 이후). 소진 판정 로직(429/
PerDay 문자열 매칭)만 key_vault의 순수 함수를 재사용하고, 로테이션·상태
저장은 이 모듈 자체 상태 파일로 완전히 독립."""
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from google import genai
from google.genai import types
from pipeline.atoms import key_vault
from shopping_shorts import usage_meter
from shopping_shorts.config import SHORTS_GEMINI_KEYS

_MODEL = "gemini-3.1-flash-lite"
_STATE_PATH = Path(__file__).parent / "data" / "shorts_gemini_state.json"
_client_cache = {}
# 유사도 채점을 병렬화(2026-07-10, 5개언어 순차수집이 27분+ 걸리던 지연 대응)하며
# 여러 스레드가 이 상태파일을 동시에 읽고-고치고-쓰면 손상/유실될 수 있어 잠금 추가.
_STATE_LOCK = threading.RLock()


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_state():
    with _STATE_LOCK:
        try:
            data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            data = {}
        if data.get("date") != _today_str():
            return {"date": _today_str(), "exhausted": []}
        data.setdefault("exhausted", [])
        return data


def _save_state(state):
    with _STATE_LOCK:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


def _mark_key_exhausted(idx):
    with _STATE_LOCK:
        state = _load_state()
        if idx not in state["exhausted"]:
            state["exhausted"].append(idx)
            _save_state(state)


# 풀이 이 비율 이하로 줄면 '거의 전멸'로 보고 재검증한다(2026-08-09).
# 전멸(0개)까지 기다리면 남은 1~2개에 워커 전부가 몰려 429를 맞고, 그것마저
# 잠긴 뒤에야 재검증이 돌았다 — 그 사이 태깅은 계속 0건이다.
_REVIVE_BELOW_RATIO = float(os.environ.get("SHORTS_KEY_REVIVE_RATIO", "0.2"))


def _live_key_indices():
    exhausted = set(_load_state()["exhausted"])
    live = [i for i in range(len(SHORTS_GEMINI_KEYS)) if i not in exhausted]
    scarce = len(live) <= max(1, int(len(SHORTS_GEMINI_KEYS) * _REVIVE_BELOW_RATIO))
    if scarce and exhausted and SHORTS_GEMINI_KEYS:
        # ★풀이 거의 다 잠겼으면 표시를 믿지 말고 실제로 찔러본다(2026-08-07 실사고).
        #   증상: 제작소가 "담긴 영상의 대본을 아직 분석하지 못했어요"만 띄운다.
        #   실측(서버): 소진표시 20개인데 그 키들을 직접 호출하니 **전부 HTTP 200**이었다.
        #   왜 오탐이 쌓이나 — 이 상태파일은 13개 모듈이 공유하는데(ai_categorize·
        #   product_name·script_extract·video_analysis…) 아침 크론(태거 965건·백필)이
        #   한 바퀴 돌며 키를 잠그면 **그날 하루 종일 아무도 안 풀어준다**. 분당한도
        #   429나 일시적 오류가 PerDay로 잘못 분류돼도 마찬가지로 영구히 남는다.
        #   그래서 "다 죽었다"는 판정만큼은 근거를 다시 확인한다 — 살아있으면 표시를
        #   지운다. 진짜 소진이면 recheck가 실패해 그대로 빈 리스트가 돌아간다.
        revived = _recheck_exhausted_keys()
        if revived:
            # 되살린 것만 쓰면 원래 살아있던 키를 버리게 된다 — 합쳐서 정렬한다.
            live = sorted(set(live) | set(revived))
    return live


# 전 키 소진 판정 시 재검증 — 너무 자주 때리면 그 자체가 한도를 먹으므로 쿨다운을 둔다.
_RECHECK_COOLDOWN_S = float(os.environ.get("SHORTS_KEY_RECHECK_COOLDOWN", "300"))
_last_recheck = {"t": 0.0}


def _probe_key_alive(key, timeout=15):
    """키가 실제로 살아있는지 확인. 살아있으면 True.

    ★REST를 직접 친다 — SDK를 쓰지 않는다(2026-08-07 실측으로 배운 것).
      처음엔 '가장 싼 호출'이라고 `client.models.list()`를 썼는데 **살아있는 키에도
      전부 실패**했다: models.list는 지연 페이저를 돌려주고 그 사이 클라이언트가
      닫혀 `RuntimeError: Cannot send a request, as the client has been closed`가 난다.
      호출이 네트워크를 타지도 못하므로 키 상태와 무관하게 항상 '죽음'으로 보였다 —
      그대로 뒀으면 오탐 해제가 **한 건도 안 되는** 가짜 수리가 될 뻔했다.
      그래서 판정 근거는 실제 HTTP 응답으로 둔다(라이브 실측: 소진표시 키가 200).

    비용: 최소 프롬프트 1회. RPD를 1 먹지만 '전 키 잠김'일 때만·쿨다운을 두고 돈다."""
    body = json.dumps({"contents": [{"parts": [{"text": "hi"}]}],
                       "generationConfig": {"maxOutputTokens": 1}}).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{_MODEL}:generateContent?key={key}")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:                                         # noqa: BLE001
        # 429(진짜 소진)·401·네트워크 오류 → 되살리지 않는다.
        # 보수적으로 간다: 잘못 되살리면 죽은 키를 계속 때린다.
        return False


def _recheck_exhausted_keys():
    """소진 표시된 키를 실제로 찔러 살아있는 것만 표시 해제. 되살아난 인덱스 목록 반환."""
    with _STATE_LOCK:
        if time.monotonic() - _last_recheck["t"] < _RECHECK_COOLDOWN_S:
            return []
        _last_recheck["t"] = time.monotonic()
        marked = list(_load_state()["exhausted"])
    revived = []
    for idx in marked:
        if idx >= len(SHORTS_GEMINI_KEYS):
            continue
        if _probe_key_alive(SHORTS_GEMINI_KEYS[idx]):
            revived.append(idx)
    if revived:
        with _STATE_LOCK:
            state = _load_state()
            state["exhausted"] = [i for i in state["exhausted"] if i not in revived]
            _save_state(state)
        print(f"comment_gen: 소진표시 오탐 해제 — 키 {revived} 되살림(실호출 200 확인)",
              file=sys.stderr)
    return revived


def _client_for_key(key):
    if key not in _client_cache:
        # 타임아웃 미지정 시 Gemini 응답이 느릴 때(영상 업로드+추론 등) 무한 대기할 수 있어
        # 기존 재시도 로직(quota/503 등)이 아예 발동을 못 한다(2026-07-14 실사고: extracting
        # 단계가 5분+ 멈춤, 에러도 안 남음). 타임아웃을 줘서 느린 요청이 예외로 떨어지게 한다.
        _client_cache[key] = usage_meter.wrap(
            genai.Client(api_key=key, http_options=types.HttpOptions(timeout=120_000)))
    return _client_cache[key]

_PROMPT = """너는 인스타에서 활발히 소통하는 진짜 사람이다.
아래 릴스를 방금 본 팔로워처럼, 영상 내용에 실제로 반응하는 한국어 댓글 3개를 만들어라.

[채널] {channel}
[카테고리] {category}
[영상 캡션] {caption}

규칙:
- 먼저 캡션에 "댓글 이벤트/응모/참여" CTA가 있는지 판단하고, 있다면 두 종류 중
  무엇인지 구분하라:
  (A) 고정 키워드형 — 캡션이 특정 단어·문구·이모지를 지정("얼음", "OO 남겨주세요" 등).
  (B) 자유형 — "아무거나", "아무 글자나", "아무 단어나 N글자" 등 특정 단어를
      지정하지 않고 아무 내용이나 남기라는 지시(예: "댓글에 '아무거나 두글자'
      남겨주시면"). 이때 "아무거나 두글자"는 댓글에 그대로 적으라는 문구가
      아니라 "짧게 아무 말이나 남기라"는 뜻이다 — 캡션 본문 속 무관한 단어를
      키워드로 착각해 붙이지 마라(본문 설명 문장과 CTA 지시문을 혼동 금지).
- CTA가 (A) 고정 키워드형이면: 3개 중 2개는 그 지시를 실제로 따르는 참여
  댓글로 만들고, 지정된 단어를 댓글 맨 마지막에 독립적으로(문장 끝에 붙여서,
  앞 문장과 자연스럽게 이어지되 눈에 띄게) 배치하라 — 예: "이거 완전
  필요했어요! 얼음" (O), "얼음 정말 유용하네요" (X, 문장 중간에 묻힘). 문장 안에
  흩어놓지 말고 항상 끝에 한 번, 명확히 노출. 매번 조금씩 다르게·자연스럽게.
  나머지 1개는 영상 내용에 반응하는 일반 댓글.
- CTA가 (B) 자유형이면: 3개 중 2개는 지시된 글자수(또는 짧게)에 맞춰 정말
  짧게 반응하는 댓글로 만들어라(긴 문장에 억지로 끼워넣지 말 것) — 예: "두글자"
  지시면 "굿굿", "오오" 처럼 실제로 짧게. 나머지 1개는 영상 내용에 반응하는
  일반 댓글(길이 제한 없음).
- CTA가 없으면: 3개를 톤 다르게 — 질문형, 공감형, 칭찬/저장 언급형.
- 모든 댓글: 영상 내용에 구체적으로 반응. 내용과 무관한 범용 문구 금지.
- 1~2줄, 짧고 자연스럽게. 존댓말. 이모지는 0~1개만.
- 광고·홍보·링크 금지. 봇처럼 보이는 정형 문구 금지.
- 반드시 JSON 배열로만 출력: ["댓글1", "댓글2", "댓글3"]
"""


def _current_key_and_idx():
    """전용 풀에서 아직 안 살아있는(소진 안 된) 키 중 첫 번째. 다 소진되면 (None, None)."""
    live = _live_key_indices()
    if not live:
        return None, None
    idx = live[0]
    return SHORTS_GEMINI_KEYS[idx], idx


# 라운드로빈 커서 — 호출마다 다음 라이브 키로 넘겨 부하를 분산한다. _current_key_and_idx가
# 늘 live[0]만 줘서 45개 키가 있어도 1번 키만 때리던 버그(성공률 7%)를 고친다(2026-07-23).
_rr_cursor = {"i": 0}


# 키별 최근 호출 시각(분당 한도 회피용, 2026-08-06). 무료등급은 키당 **분당 15건**이
# 상한이라(실측: 16번째 요청에서 429), 병렬로 쏟아부으면 대부분이 429로 버려진다
# — 태거 실측 성공률 20%, 9건/분. 429를 맞고 재시도하는 대신 **애초에 안 맞게**
# 키마다 최소 간격을 두고 내준다. 하루 한도(RPD 500)는 이걸로 못 뚫는다 —
# 그건 키 개수를 늘려야만 는다.
# ★15 → 5 (2026-08-09). 15는 추정이었고 실측 한도는 **분당 5건**이다:
#   429 원문 `limit: 5, model: gemini-3.5-flash / Please retry in 45.5s`
#   (서버에서 한 키를 연타해 8번째 호출에 재현). 15로 두면 페이서가 실제보다
#   3배 빠르게 키를 내줘 **429를 스스로 자초**한다 — 태거가 `0/40건`을 130채널
#   연속으로 찍은 진짜 원인이었다(키는 멀쩡했고 실호출은 200이었다).
_RPM_PER_KEY = int(os.environ.get("SHORTS_RPM_PER_KEY", "5"))
_MIN_GAP_S = 60.0 / max(1, _RPM_PER_KEY)
_key_last_used = {}


def _next_live_key_and_idx():
    """라이브 키를 라운드로빈으로 하나씩 반환(호출마다 다음 키). 다 소진되면 (None, None).

    2026-08-06: 분당 한도를 지키도록 '지금 쓸 수 있는' 키를 고른다. 라이브 키를
    한 바퀴 돌며 마지막 사용 후 _MIN_GAP_S가 지난 키를 찾고, 전부 쿨다운 중이면
    가장 빨리 풀리는 키가 풀릴 때까지 그만큼만 잔다(최대 _MIN_GAP_S).
    키가 많아질수록 대기는 0에 수렴한다 — 키를 늘리면 그대로 빨라진다."""
    live = _live_key_indices()
    if not live:
        return None, None
    while True:
        with _STATE_LOCK:
            now = time.monotonic()
            start = _rr_cursor["i"] % len(live)
            _rr_cursor["i"] = start + 1
            soonest = None
            for off in range(len(live)):
                idx = live[(start + off) % len(live)]
                ready_at = _key_last_used.get(idx, 0.0) + _MIN_GAP_S
                if ready_at <= now:
                    _key_last_used[idx] = now
                    return SHORTS_GEMINI_KEYS[idx], idx
                if soonest is None or ready_at < soonest:
                    soonest = ready_at
            wait = min(max(0.0, soonest - now), _MIN_GAP_S)
        time.sleep(wait)   # 락 밖에서 잔다 — 다른 스레드를 막지 않는다


def build_prompt(caption, channel, category):
    return _PROMPT.format(
        caption=(caption or "(캡션 없음 — 채널·카테고리로 유추)"),
        channel=channel or "",
        category=category or "기타",
    )


def parse_response(raw):
    """Gemini 응답 텍스트 → 댓글 list[str]. 실패 시 []."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict) and isinstance(data.get("comments"), list):
        return [str(x) for x in data["comments"]]
    return []


def generate(caption, channel, category, max_retries=4, quota_sleep=8):
    """캡션→댓글 3개. 전용 키 풀(SHORTS_GEMINI_KEYS) 내에서만 로테이션 —
    공유 풀(key_vault)로는 폴백하지 않는다(2026-07-09, 전용 풀 분리 이유는
    모듈 docstring 참고). 전용 풀이 다 소진되면 그냥 []. 최종 실패 시에도 [].

    quota_sleep: 분당 쿼터 초과 시 대기 시간(초). 로테이션 가능한 키가 있으면
    먼저 로테이션(대기 없음), 전부 소진됐을 때만 짧게 대기."""
    if not SHORTS_GEMINI_KEYS:
        raise RuntimeError("comment_gen: SHORTS_GEMINI_KEY가 설정되지 않았습니다(.env/서비스 환경변수 확인)")
    prompt = build_prompt(caption, channel, category)
    for attempt in range(max_retries):
        key, idx = _current_key_and_idx()
        if key is None:
            return []  # 전용 풀 전체 소진 — 공유 풀로 넘어가지 않고 여기서 멈춤
        try:
            resp = _client_for_key(key).models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return parse_response(resp.text)
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                _mark_key_exhausted(idx)  # 확실한 일일 한도 소진·계정비활성 영구 제외
                continue
            if key_vault.is_quota_error(e):
                # 분당 제한 등 "일일 소진"까지는 확인 안 되는 429 — 키를 영구
                # 제외하면 전용 풀(3개뿐)이 금방 동나므로, 같은 키로 짧게
                # 대기 후 재시도(2026-07-09, "잔여10개가 순식간에 소진" 사고 방지).
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return []
    return []
