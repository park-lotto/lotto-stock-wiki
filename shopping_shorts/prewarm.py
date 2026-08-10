"""담기 시 사전분석 예열(2026-07-30) — 설계 §2① `2026-07-29-추출속도-3종묶음-design.md`.

왜 있나: 제작소 1단계에 들어가서야 추출+구조분석이 돌아 사장님이 5분을 기다렸다(실측).
캐시가 있으면 추출 0초라는 것도 실측됐다(job d70ab210 = 1.5분). 그래서 **담는 순간**
백그라운드로 미리 돌려 `script_extracts`(추출 캐시)와 `structure_json`(제미니 구조분석)을
채워둔다. 제작소는 `get_extract`로 캐시히트만 하면 되고 로딩이 사라진다.

왜 워커 큐인가: 서버 BackgroundTasks에 두면 배포 재시작이 진행 중 예열을 SIGKILL한다
(2026-07-29 실사고와 같은 구조). `store.enqueue("prewarm", ...)` → 독립워커가 집는다.

★사고 재발 방지(2026-07-26 무한루프·크레딧 소모 사고 계보 그대로 계승):
  ① 래치는 DB에 — `produce_autoload` 테이블을 autoload와 **공유**한다. 예열이 한 번
     실패한 영상은 autoload도 다시 안 태운다(제미니 두 번 안 쓴다).
  ② 추출 전에 선(先)래치 — 타임아웃·워커 재시작에도 시도 흔적이 남는다.
  ③ full_text가 비면 저장하지 않는다 — 빈 대본이 캐시로 굳으면 영구히 "대본 없음"이 된다.
  ④ 크레딧은 autoload와 똑같이 건다(check_and_count/글로벌캡) — 예열이 유료게이트
     우회로가 되면 안 된다. 실패하면 환불.
  ⑤ 담기는 즐겨찾기보다 남발되므로 **일일 예열 상한**을 추가로 둔다(_PREWARM_DAILY_CAP).
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store

log = logging.getLogger("prewarm")

# 담기 남발 방어 — 하루에 이만큼만 예열한다(넘으면 조용히 스킵, 제작소 진입 시 그때 추출).
_PREWARM_DAILY_CAP = 40
# 1 → 3 (2026-08-04 실사고): 인스타 다운로드는 일시 실패가 흔한데 1회 실패로 영구
# 래치돼 재담기해도 예열이 조용히 스킵됐다(DQohOUqgdRt — 수동 대본뽑기는 즉시 성공
# = 경로는 멀쩡, 래치만 스테일). 어제 '래치 7건 삭제' 사고와 같은 계보.
_PREWARM_MAX_ATTEMPTS = 3        # shortcode당 총 시도(autoload와 같은 래치를 공유)
_DAILY_KEY = "prewarm_daily"     # settings: "YYYY-MM-DD|n"


def _log_tag_qa(shortcode, result):
    """태깅 QA 점수를 로그 한 줄로 — "이 영상이 왜 이상한가"를 나중에 추적하는 실마리.

    tag_audit은 표본 전체의 분포를 보지만, 사장님이 특정 영상 하나를 짚어 물을 때는
    그 job이 그때 몇 점이었는지가 필요하다. 점수만으론 원인을 모르니 flags를 같이 남긴다.
    ★로그 실패가 예열을 죽이면 안 된다(예열은 보조작업) — 통째로 감싼다."""
    try:
        qa = (result or {}).get("tag_qa") or {}
        if not qa:
            return
        flags = "; ".join(qa.get("flags") or []) or "없음"
        log.info("tag_qa %s: %.2f (재시도 %s, flags: %s)",
                 shortcode, float(qa.get("score") or 0.0),
                 "O" if qa.get("retried") else "X", flags)
    except Exception:  # noqa: BLE001
        pass


def _work_dir(shortcode: str) -> Path:
    """autoload와 같은 임시 폴더 규칙(shortcode sha1 16자)."""
    base = Path(DB_PATH).parent / "find_frames"
    return base / hashlib.sha1(shortcode.encode()).hexdigest()[:16]


def _daily_take(store: Store) -> bool:
    """오늘 예열 카운터를 1 올리고 상한 내인지 돌려준다. 날짜가 바뀌면 리셋."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = store.get_setting(_DAILY_KEY, "") or ""
    day, _, n = raw.partition("|")
    used = int(n) if (day == today and n.isdigit()) else 0
    if used >= _PREWARM_DAILY_CAP:
        return False
    store.set_setting(_DAILY_KEY, f"{today}|{used + 1}")
    return True


def _gate():
    """유료게이트·글로벌캡 헬퍼를 app에서 늦게 가져온다(순환 import 방지).
    못 가져오면 (None, None, None, None) — 그 경우 예열을 아예 하지 않는다(무료 소모 금지)."""
    try:
        from shopping_shorts.app import (check_and_count, refund_credit,
                                         global_incr_and_alert, _global_over_cap)
        return check_and_count, refund_credit, global_incr_and_alert, _global_over_cap
    except Exception as e:  # noqa: BLE001 — import 실패는 예열 포기 사유일 뿐
        log.warning("prewarm 게이트 import 실패 — 예열 스킵: %s", e)
        return None, None, None, None


def run_prewarm(shortcode, url, *, caption="", customer_id="0", video_url="",
                category=None, db_path=None):
    """담긴 영상 1건을 미리 추출+구조분석해 캐시에 채운다. 상태 문자열을 돌려준다.

    반환: already | skipped_latched | skipped_cap | skipped_limit | skipped_nogate |
          failed_download | failed_empty | failed_error | done
    예외를 밖으로 던지지 않는다 — 예열은 보조작업이라 실패해도 무해해야 한다."""
    from shopping_shorts.media_download import download_any
    from shopping_shorts.script_extract import extract_auto, storable, KeyPoolExhausted
    from shopping_shorts.structure_analyze import analyze_structure

    code = (shortcode or "").strip()
    if not code:
        return "failed_error"
    store = Store(db_path or DB_PATH)

    # ①-a 이미 유효 캐시가 있으면 아무것도 안 한다(중복 과금 차단).
    cached = store.get_extract(code)
    if cached and (cached.get("full_text") or "").strip():
        if not cached.get("structure"):
            _fill_structure(store, code, cached.get("full_text") or "", analyze_structure)
        return "already"

    # ①-b 래치 — 한 번 실패한 영상은 다시 안 태운다(autoload와 공유).
    if store.autoload_attempts([code]).get(code, 0) >= _PREWARM_MAX_ATTEMPTS:
        return "skipped_latched"

    check_and_count, refund_credit, global_incr_and_alert, over_cap = _gate()
    if check_and_count is None:
        return "skipped_nogate"
    if over_cap("script"):
        return "skipped_limit"
    if not _daily_take(store):
        return "skipped_cap"
    if not check_and_count(customer_id, "script"):
        return "skipped_limit"
    global_incr_and_alert("script")

    store.autoload_mark_attempt(code)        # ②선래치 — 추출 전에
    ok = False
    try:
        src = (video_url or url or "").strip()
        try:
            video_path, dl_caption = download_any(src, str(_work_dir(code)))
        except Exception as e:  # noqa: BLE001 — 만료·비공개·차단
            store.autoload_mark_error(code, f"예열 다운로드 실패: {e}")
            return "failed_download"
        try:
            result = extract_auto(video_path, code, caption=(caption or dl_caption or ""))
        except KeyPoolExhausted as e:
            # 서버 사정(키 풀 잠김)이지 영상 탓이 아니다 → 래치를 돌려준다(2026-08-07).
            # 안 그러면 키가 되살아난 뒤에도 이 영상만 영구히 자동추출에서 빠진다.
            store.autoload_rollback_attempt(code, f"예열 보류: {e}")
            return "deferred_nokey"
        except Exception as e:  # noqa: BLE001
            store.autoload_mark_error(code, f"예열 추출 실패: {e}")
            return "failed_error"
        full_text = (result.get("full_text") or "").strip()
        if not full_text:                    # ③빈 대본은 저장 금지
            store.autoload_mark_error(code, "예열: 전사 결과 없음(음성 없음·자막 불가)")
            return "failed_empty"
        # storable()로 추린다 — 손으로 dict를 다시 만들면 tag_qa가 저장에서 누락된다
        # (담기 예열이 라이브 주경로라 여기서 새면 QA 점수가 아예 안 쌓인다).
        store.save_script(code, storable(result), category=category)
        _log_tag_qa(code, result)
        ok = True
    finally:
        if not ok:
            refund_credit(customer_id, "script")   # ④실패는 환불

    # 제미니 구조분석까지 미리 — 제작소 1단계(build_aipick)가 이걸 읽는다.
    _fill_structure(store, code, full_text, analyze_structure)
    return "done"


def _fill_structure(store, code, full_text, analyze_structure):
    """구조분석을 채운다. 실패는 조용히 — 대본 캐시만으로도 로딩은 크게 줄어든다."""
    if not (full_text or "").strip():
        return
    try:
        structure = analyze_structure(full_text)
    except Exception as e:  # noqa: BLE001 — 제미니 503·쿼터
        log.info("prewarm 구조분석 실패(무해) %s: %s", code, e)
        store.mark_structure_attempted(code)
        return
    if structure:
        store.save_extract_structure(code, structure)
    else:
        store.mark_structure_attempted(code)
