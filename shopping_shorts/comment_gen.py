"""Gemini로 릴스 캡션 기반 자연스러운 댓글 후보 생성.

전용 키 풀(SHORTS_GEMINI_KEYS)을 직접 로테이션한다 — 주식위키 본체가 쓰는
pipeline.atoms.key_vault의 공유 풀과 분리(2026-07-09, 공유 풀이 다른 작업들과
하루 종일 같이 소모되다 예고 없이 소진된 사고 이후). 소진 판정 로직(429/
PerDay 문자열 매칭)만 key_vault의 순수 함수를 재사용하고, 로테이션·상태
저장은 이 모듈 자체 상태 파일로 완전히 독립."""
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from google import genai
from google.genai import types
from pipeline.atoms import key_vault
from shopping_shorts.config import SHORTS_GEMINI_KEYS

_MODEL = "gemini-3.1-flash-lite"
_STATE_PATH = Path(__file__).parent / "data" / "shorts_gemini_state.json"
_client_cache = {}


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_state():
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        data = {}
    if data.get("date") != _today_str():
        return {"date": _today_str(), "exhausted": []}
    data.setdefault("exhausted", [])
    return data


def _save_state(state):
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


def _mark_key_exhausted(idx):
    state = _load_state()
    if idx not in state["exhausted"]:
        state["exhausted"].append(idx)
        _save_state(state)


def _live_key_indices():
    exhausted = set(_load_state()["exhausted"])
    return [i for i in range(len(SHORTS_GEMINI_KEYS)) if i not in exhausted]


def _client_for_key(key):
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
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
            if key_vault.is_daily_exhausted_error(e):
                _mark_key_exhausted(idx)  # 확실한 일일 한도 소진만 영구 제외
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
