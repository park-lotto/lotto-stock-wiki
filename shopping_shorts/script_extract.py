"""Gemini 멀티모달로 영상에서 대본 세그먼트(타임코드+텍스트+장면묘사) 추출.

나레이션 음성과 화면 자막을 구분하지 않고 통합 추출한다(설계 §3-1). 전용 키 풀
(SHORTS_GEMINI_KEYS)만 사용 — comment_gen의 로테이션 재사용, 공유 풀 폴백 금지
(2026-07-09 확정). seg_id는 모델이 아니라 코드가 {video_id}-{n}로 부여해 하류
EDL(edit_plan.py)의 참조 무결성을 보장한다.

(구 transcribe_gemini.py를 대체·흡수 — 그쪽은 공유풀(key_vault.get_client)을 써서
컨벤션 위반이었음. 폐기는 Task 8에서.)
"""
import json
import sys
import time

from google.genai import types

from pipeline.atoms import key_vault
from shopping_shorts import action_dict
from shopping_shorts import comment_gen
from shopping_shorts import scene_cut
from shopping_shorts.config import SHORTS_GEMINI_KEYS
from shopping_shorts.video_analysis import _MODEL, _wait_until_active

# _MODEL이 503으로 막혔을 때만 쓰는 대체 모델. 영상 입력을 받고 response_schema도 지키는 것으로
# 실측 확인(2026-07-16 서버: 실제 extract_script를 이 모델로 태워 구간 6개·본문 208자 확보).
# _MODEL(video_analysis 공유)은 건드리지 않는다 — 폴백은 이 함수 안에서만 일어난다.
_FALLBACK_MODEL = "gemini-3.1-flash-lite"

_EMPTY = {"segments": [], "full_text": ""}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "text": {"type": "string"},
                    "scene_desc": {"type": "string"},
                    "action": {"type": "string", "enum": action_dict.ACTION_VOCAB + ["없음"]},
                    "has_effect": {"type": "boolean"},
                    "is_key": {"type": "boolean"},
                    "shot_role": {"type": "string", "enum": ["조리", "완성", "기타"]},
                },
                "required": ["start", "end", "text", "scene_desc"],
            },
        },
        "full_text": {"type": "string"},
    },
    "required": ["segments", "full_text"],
}

_PROMPT = """이 영상을 보고 시간 순서대로 세그먼트로 나눠 대본을 추출해라.

캡션(참고용, 영상 내용이 우선): {caption}

★ 최우선 규칙: 영상 맨 처음(0초)의 '훅'을 절대 빠뜨리지 마라. 첫 세그먼트는 반드시
영상이 시작되는 0초부터 시작하고, 화면 맨 위에 크게 뜨는 제목/자막 문구와 첫 나레이션을
'모두' 포함해라. 문장 중간부터 시작하지 마라 — 예: 첫 마디가 "생선 구울 때 기름 절대
안 돼요"라면 "절대 안 돼요"만 적지 말고 "생선 구울 때 기름"까지 앞부분을 통째로 적어라.

각 세그먼트는 **하나의 행위/동작 단위**로 잘게 끊어라 — 화면 속 동작(반죽 치대기·굴리기·
넣기·뚜껑 열기·찢기 등)이 바뀌면 새 세그먼트다. 아래 '화면 전환 시각'은 영상에서 실제로
화면이 바뀐 지점이니 이 지점들을 세그먼트 경계로 삼아 잘게 나눠라(단, 한 문장이 한 전환을
살짝 넘어 이어지면 그 문장은 쪼개지 말고 가장 걸맞은 세그먼트에 담아라).
화면 전환 시각(초): {boundaries}

세그먼트마다:
- start, end: 영상 내 시작/끝 시각(초, 숫자)
- text: 그 구간에서 **실제로 들리는 나레이션**(없으면 화면 자막 문구). **한 단어도 빠짐없이
  들리는 그대로 받아써라. 요약·의역·생략 절대 금지.** 말이 빠르거나 뭉개져도 최대한 정확히
  받아쓰고, 확실치 않은 부분도 가장 근접한 표기로 채워라(빈칸으로 두지 마라). 화면에 큰
  자막(특히 맨 앞 제목/훅)이 있으면 자막과 음성을 **교차 확인**해 더 완전한 쪽으로 보정하되
  빠진 단어가 없게 하라.
- scene_desc: 그 구간 화면에 무엇이 보이는지 짧게(제품/행동/구도). 화면 속 **주 대상을
  정확히** 적어라 — 헷갈리는 물체를 다른 것으로 단정하지 마라(예: 양파를 참외로, 무를 감자로
  오인 금지). 확실치 않으면 색·형태로만 묘사하고 엉뚱한 이름을 붙이지 마라.
- action: 그 구간의 주요 손동작을 하나 골라라(당기다·붓다·바르다·펴다·자르다·섞다·닦다·
  누르다·끼우다·열다·담다·닫다). 해당 없으면 "없음".
- has_effect: 그 구간에 **원본 제작자가 넣은 지울 수 없는 시각 효과**가 있으면 true. 즉
  화면 전환효과·줌인아웃 연출·분할화면·강한 색보정/필터·스티커/이모지/그래픽 오버레이·
  큰 텍스트 애니메이션이 박혀 있어 **깨끗한 요리/제품 원본이 아닌** 조각이면 true. 평범하게
  촬영된 요리/손동작/완성샷이면 false. (우리가 B롤로 재사용할 때 이물감이 생기는 조각을
  걸러내려는 것 — 확실할 때만 true, 애매하면 false.)
- is_key: 이 구간이 **제품/도구의 기능·성능·장점·효과를 화면으로 실증**하거나(넓다·크다·쏙
  들어간다·때가 빠진다를 실제 행동/결과로 보여줌), 요리·살림의 **핵심 방법을 손동작으로 보여주는**
  구간이면 true. 단순 도입 상황·인물 등장·감상·완성 인사·CTA·링크유도면 false. (원본 제작자가
  "이 대사에 이 장면"으로 맞춰둔 실증 페어를 골라내려는 것 — 대사가 기능을 설명하며 화면이 그걸
  보여주면 true. 애매하면 false.)
- shot_role: 화면의 성격. 손이 재료/도구를 다루는 과정이면 "조리", 완성된 결과물이 화면 주인공이면
  "완성", 그 외(인물·배경·인사 등)면 "기타". (레시피 소재의 화면 결 맞춤 배치에 쓴다.)

full_text에는 모든 세그먼트의 text를 순서대로 이어붙여라. 맨 앞 훅부터 한 단어도 빠짐없이
완전히 이어붙이고, 다른 텍스트는 없이 JSON만 출력."""


def _assign_seg_ids(video_id, raw_segments):
    """모델이 준 세그먼트 목록에 seg_id 부여 + 숫자 필드 float 캐스팅(순수함수)."""
    out = []
    for n, seg in enumerate(raw_segments):
        raw_action = seg.get("action")
        if raw_action in (None, "", "없음") or raw_action not in action_dict.ACTION_VOCAB:
            raw_action = action_dict.tag_action(f"{seg.get('text', '')} {seg.get('scene_desc', '')}")
        out.append({
            "seg_id": f"{video_id}-{n}",
            "start": float(seg.get("start") or 0.0),
            "end": float(seg.get("end") or 0.0),
            "text": seg.get("text", ""),
            "scene_desc": seg.get("scene_desc", ""),
            "action": raw_action,  # str 동사 or None
            "has_effect": bool(seg.get("has_effect")),  # 원본 효과 박힘 → B롤 제외용
            "is_key": bool(seg.get("is_key")),           # 기능·장점 실증 앵커 (fail-open False)
            "shot_role": seg.get("shot_role") or "기타", # 조리/완성/기타 (fail-open 기타)
        })
    return out


def _boundary_hint(video_path):
    """scene_cut 실제 장면전환 경계 → "약 3.6초, 8.5초, …" 힌트 문자열.
    ffmpeg 실감지라 Gemini 자율 분할보다 세분화가 보장된다(실측: 99.8초 영상 5→18조각).
    실패(ffmpeg 오류·컷 0/1개)면 빈 문자열 — 호출부가 경계 없는 기존 프롬프트로 폴백."""
    try:
        fps = scene_cut.video_fps(video_path)
        cuts = scene_cut.detect_cuts(video_path, threshold=0.3)
    except Exception:
        return ""
    if not fps or len(cuts) < 2:
        return ""
    secs = [round(a / fps, 1) for a, _ in cuts if a > 0]
    return ", ".join(f"{s}초" for s in secs)


def extract_script(video_path, video_id, caption="", max_retries=4, quota_sleep=8):
    """영상 파일 → {"segments": [...seg_id 포함...], "full_text": str}. 실패 시 빈 결과.

    전용 키 풀 로테이션(comment_gen 재사용). 전용 풀 소진 시 빈 결과.

    2026-07-16 모델 폴백: _MODEL이 503(UNAVAILABLE/overloaded)로 계속 막히면 _FALLBACK_MODEL로
    갈아탄다. **503은 키가 아니라 모델 용량 문제**라 키 로테이션으로는 절대 안 풀린다 —
    실측(서버, 같은 순간): 키 16개 중 5개를 각각 때려 gemini-3.5-flash가 5/5 전부 503,
    같은 키로 gemini-3.1-flash-lite는 정상(실제 extract_script로 구간 6개·본문 208자 확보).
    폴백 시점: 예전엔 spike 회복을 기대해 primary 503을 2번 겪은 뒤 내려갔으나, 검열 실측
    성공률 29%(100/350, 2026-07-24)로 3.5-flash가 spike가 아니라 지속적으로 막힌 게 드러나
    **첫 503에서 바로** 폴백한다(죽은 모델 재시도 낭비 제거). 폴백 후엔 sleep을 넣지 않는다 —
    다른 모델이라 앞 모델의 혼잡과 무관하다."""
    if not SHORTS_GEMINI_KEYS:
        raise RuntimeError("script_extract: SHORTS_GEMINI_KEY가 설정되지 않았습니다")
    prompt = _PROMPT.format(caption=caption or "(캡션 없음)",
                            boundaries=_boundary_hint(video_path) or "(감지 실패 — 화면·주제 변화로 판단)")
    model = _MODEL
    primary_503 = 0

    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return dict(_EMPTY)
        client = comment_gen._client_for_key(key)
        file_obj = None
        try:
            with open(video_path, "rb") as fh:
                file_obj = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type="video/mp4"))
            file_obj = _wait_until_active(client, file_obj)
            resp = client.models.generate_content(
                model=model,
                contents=[file_obj, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            return {
                "segments": _assign_seg_ids(video_id, data.get("segments", [])),
                "full_text": data.get("full_text", ""),
            }
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(quota_sleep)
                continue
            if any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                if model == _MODEL:
                    primary_503 += 1
                    # 첫 503에서 바로 폴백(2026-07-24). 기존엔 2번 겪은 뒤 내려갔으나(spike면 곧
                    # 살아난다는 가정), 검열 실측 성공률 29%(100/350)로 3.5-flash가 spike가 아니라
                    # 지속적으로 막혀 있음이 드러났다 → 죽은 모델에 재시도를 낭비할수록 손해. 503은
                    # 키가 아니라 모델 용량이라 키 로테이션으로 안 풀리고, lite는 같은 키로 정상.
                    if primary_503 >= 1:
                        model = _FALLBACK_MODEL
                        print(f"script_extract: {_MODEL} 503 → {_FALLBACK_MODEL}로 폴백",
                              file=sys.stderr)
                        continue  # 다른 모델이라 앞 모델의 혼잡과 무관 — 기다리지 않는다
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 5)
                    continue
            print(f"script_extract: 빈 결과 반환(재시도 소진 또는 미분류 오류) — {e!r}", file=sys.stderr)
            return dict(_EMPTY)
        finally:
            if file_obj is not None:
                try:
                    client.files.delete(name=file_obj.name)
                except Exception:
                    pass
    return dict(_EMPTY)
