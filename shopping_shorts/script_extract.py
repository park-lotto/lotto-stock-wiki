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
                    "shot_role": {"type": "string",
                                  "enum": ["before", "사용중", "after", "완성", "문제", "기타"]},
                    "product_benefits": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["start", "end", "text", "scene_desc"],
            },
        },
        "full_text": {"type": "string"},
        "product_benefits": {"type": "array", "items": {"type": "string"}},
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
- shot_role: 화면의 성격을 하나 골라라(장면 스파인 슬롯 배치에 쓴다):
  · "before" = 사용 전/문제 있는 상태(더러움·부스스한 룩·엉킴 등)
  · "사용중" = 손이 재료/도구를 다루는 과정(조리·바르기·닦기·조립)
  · "after"  = 사용 후 개선된 상태(before와 대비되는 깨끗/완성 룩)
  · "완성"   = 완성된 결과물이 화면 주인공(완성 요리·완성품 클로즈업)
  · "문제"   = 문제 상황을 보여주는 장면(불편·한계 부각)
  · "기타"   = 그 외(인물 등장·배경·인사·CTA)
- product_benefits: **자막도 나레이션도 없어도** 그 구간 화면만 보고 이 제품/도구의 **특장점을
  한국어 문장 1~2개**로 뽑아라(예: "터치 한 번에 자동으로 열린다", "좁은 틈에 쏙 들어가 공간을
  아낀다", "고급스러운 마감"). 요리·살림 소재면 방법 설명 대신 **결과의 매력**을 적어라(예:
  "겉은 바삭 속은 촉촉하게 나온다"). 화면이 특장점을 안 보여주는 구간(인물 등장·인사·배경)이면
  빈 배열. **추측으로 없는 기능을 만들지 마라** — 화면에 실제로 보이는 것만.

★ 최상위 product_benefits: 위 구간별 특장점을 모아 **이 영상이 파는 제품/결과물의 핵심 특장점
2~3개**를 한국어 문장으로 정리해라. 자막이 하나도 없는 영상이라 text가 전부 빈칸이 되더라도
이 필드는 **반드시 채워라** — 이게 없으면 이 영상은 대본 재료로 못 쓰인다.

full_text에는 모든 세그먼트의 text를 순서대로 이어붙여라. 맨 앞 훅부터 한 단어도 빠짐없이
완전히 이어붙이고, 다른 텍스트는 없이 JSON만 출력."""


def _norm_benefits(raw):
    """모델이 준 특장점 → 문장 리스트로 정규화(순수함수, fail-open).
    필드 없음/None → []. 문장 하나(str)로 줘도 리스트로 감싼다(스키마는 배열이지만 모델이
    가끔 문자열로 준다 — 무자막 소스를 살리는 유일한 재료라 여기서 흘리면 안 된다)."""
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [s.strip() for s in raw if isinstance(s, str) and s.strip()]


# 장면 스파인(2026-07-29): shot_role 확장어휘. 옛 추출본('조리')은 '사용중'으로 흡수하고,
# 알 수 없는 값은 '기타'로 떨어뜨린다(fail-open — 스파인 배치가 크래시 없이 돈다).
_SHOT_ROLE_VOCAB = {"before", "사용중", "after", "완성", "문제", "기타"}
_SHOT_ROLE_ALIASES = {"조리": "사용중"}


def _norm_shot_role(raw):
    if raw in _SHOT_ROLE_VOCAB:
        return raw
    return _SHOT_ROLE_ALIASES.get(raw, "기타")


def _collect_benefits(segments):
    """세그먼트별 product_benefits → 소스 단위 집계(순서 보존 중복제거, 순수함수).
    무자막 영상은 full_text가 0자라 이 집계가 대본 생성의 유일한 언어 재료다."""
    out = []
    for seg in segments or []:
        for b in _norm_benefits(seg.get("product_benefits")):
            if b not in out:
                out.append(b)
    return out


def _assign_seg_ids(video_id, raw_segments, motion_map=None):
    """모델이 준 세그먼트 목록에 seg_id 부여 + 숫자 필드 float 캐스팅(순수함수).
    motion_map({seg_id: level|None})이 오면 그 값을 motion_level로 싣는다(P2, 2026-07-29)."""
    out = []
    motion_map = motion_map or {}
    for n, seg in enumerate(raw_segments):
        raw_action = seg.get("action")
        if raw_action in (None, "", "없음") or raw_action not in action_dict.ACTION_VOCAB:
            raw_action = action_dict.tag_action(f"{seg.get('text', '')} {seg.get('scene_desc', '')}")
        sid = f"{video_id}-{n}"
        out.append({
            "seg_id": sid,
            "start": float(seg.get("start") or 0.0),
            "end": float(seg.get("end") or 0.0),
            "text": seg.get("text", ""),
            "scene_desc": seg.get("scene_desc", ""),
            "action": raw_action,  # str 동사 or None
            "has_effect": bool(seg.get("has_effect")),  # 원본 효과 박힘 → B롤 제외용
            "is_key": bool(seg.get("is_key")),           # 기능·장점 실증 앵커 (fail-open False)
            "shot_role": _norm_shot_role(seg.get("shot_role")),  # 확장어휘, 옛값 매핑(fail-open 기타)
            # 무자막 소스용 화면→특장점 문장 (fail-open []) — text가 빈칸이어도 대본 재료가 된다.
            "product_benefits": _norm_benefits(seg.get("product_benefits")),
            "motion_level": motion_map.get(sid),  # scene_cut 매핑 결과 or None(정보없음, fail-open)
        })
    return out


def _boundary_hint(video_path):
    """scene_cut 실제 장면전환 경계 → (힌트문자열, cuts, fps).
    ffmpeg 실감지라 Gemini 자율 분할보다 세분화가 보장된다(실측: 99.8초 영상 5→18조각).
    실패(ffmpeg 오류)면 ("", [], 0.0) — 호출부가 경계 없는 기존 프롬프트로 폴백.
    cuts·fps를 같이 반환하는 이유(P2, 2026-07-29): 모션레벨 계산(_compute_motion_map)이
    같은 detect_cuts 결과를 재사용해 detect_cuts 중복 호출을 없앤다(frame_motion은
    모션레벨 계산에서 별도로 1회 더 돈다 — 전체 ffmpeg 비용이 0이 되는 게 아니다)."""
    try:
        fps = scene_cut.video_fps(video_path)
        cuts = scene_cut.detect_cuts(video_path, threshold=0.3)
    except Exception:
        return "", [], 0.0
    if not fps or len(cuts) < 2:
        return "", cuts, fps
    secs = [round(a / fps, 1) for a, _ in cuts if a > 0]
    return ", ".join(f"{s}초" for s in secs), cuts, fps


def _compute_motion_map(video_path, cuts, fps, raw_segments, video_id):
    """detect_cuts 결과(cuts,fps 재사용) + 추출된 세그먼트(아직 seg_id 없음) + video_path
    → {seg_id: level|None}. ffmpeg로 프레임모션을 재고 seg별 교집합 최대 컷의 레벨을 매핑.
    cuts가 비었거나 어떤 예외든 fail-open(빈 dict, 전부 motion_level=None)."""
    try:
        if not cuts or not fps:
            return {}
        motion = scene_cut.frame_motion(video_path)
        if not motion:
            return {}
        cuts_labeled = scene_cut.cut_motion(cuts, motion)
        tmp_segs = [{"seg_id": f"{video_id}-{n}", "start": s.get("start", 0.0), "end": s.get("end", 0.0)}
                    for n, s in enumerate(raw_segments)]
        return scene_cut.map_segments_to_motion_levels(tmp_segs, cuts_labeled, fps)
    except Exception:
        return {}


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
    boundary_hint, _cuts, _fps = _boundary_hint(video_path)
    prompt = _PROMPT.format(caption=caption or "(캡션 없음)",
                            boundaries=boundary_hint or "(감지 실패 — 화면·주제 변화로 판단)")
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
            motion_map = _compute_motion_map(video_path, _cuts, _fps, data.get("segments", []), video_id)
            segments = _assign_seg_ids(video_id, data.get("segments", []), motion_map=motion_map)
            # 소스 단위 특장점: 모델의 최상위 요약을 우선하고, 없으면 세그별 집계로 폴백.
            # 무자막 영상(full_text 0자)이 대본 생성에서 통째로 빠지던 것을 막는 재료다.
            benefits = _norm_benefits(data.get("product_benefits")) or _collect_benefits(segments)
            return {
                "segments": segments,
                "full_text": data.get("full_text", ""),
                "product_benefits": benefits,
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
