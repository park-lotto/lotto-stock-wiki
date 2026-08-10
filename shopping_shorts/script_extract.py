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
from shopping_shorts import tag_qa
from shopping_shorts.config import SHORTS_GEMINI_KEYS
from shopping_shorts.video_analysis import _MODEL, _wait_until_active

# _MODEL이 503으로 막혔을 때만 쓰는 대체 모델. 영상 입력을 받고 response_schema도 지키는 것으로
# 실측 확인(2026-07-16 서버: 실제 extract_script를 이 모델로 태워 구간 6개·본문 208자 확보).
# _MODEL(video_analysis 공유)은 건드리지 않는다 — 폴백은 이 함수 안에서만 일어난다.
_FALLBACK_MODEL = "gemini-3.1-flash-lite"

_EMPTY = {"segments": [], "full_text": ""}


class KeyPoolExhausted(RuntimeError):
    """전용 Gemini 키 풀이 통째로 잠겨 **호출조차 못 한** 상태.

    ★왜 예외로 올리나(2026-08-07 실사고). 예전엔 여기서 조용히 빈 결과를 돌려줬다 —
    그래서 호출부가 "키가 없다"와 "이 영상엔 음성이 없다"를 **구분할 수 없었고**,
    실패가 `failed_empty`로 기록돼 ①로그에 아무 흔적이 없고(원인 파악에 30분+)
    ②영상 잘못이 아닌데도 재시도 래치(produce_autoload.attempts)를 깎아먹었다.
    3회면 그 영상은 키가 되살아난 뒤에도 자동추출에서 영구 제외됐다.
    빈 결과와 달리 이건 **영상을 다시 시도하면 되는 일시적 상태**라 구분이 필요하다."""

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
                    # ★2026-07-31: 손동작(action)만으론 영상의 진짜 포인트가 안 남는다.
                    #   실측 레퍼런스 3편의 포인트가 전부 사물이 주어인 변화/감각이었다:
                    #   "프린팅이 갈라지다→매끈해지다" / "양념이 튀다·가림막이 막아주다" /
                    #   "촉감이 모찌같다". ACTION_VOCAB 30개는 전부 사람 손동작이라 하나도 못 담는다.
                    "change": {"type": "string"},
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
  ★주 제품 판별: 이 영상이 파는/보여주는 **주 제품**은 영상 전체에서 **반복적으로 클로즈업되거나
  손에 들려 사용되는 물건**이다. 화면 한구석에 잠깐 보이는 **배경 소품(인형·장식품 등)이나
  프레임 안의 진짜 동물·사람**은 맥락일 뿐 제품이 아니다 — 이런 것에 낚여 "강아지 선풍기"처럼
  실제 제품과 무관한 이름을 지어내지 마라. 예: 손에 들고 사용 중인 선풍기 옆에 강아지 인형이나
  진짜 강아지가 보여도, 주 제품은 여전히 "선풍기"다.
- action: 그 구간의 주요 손동작을 하나 골라라(당기다·붓다·바르다·펴다·자르다·섞다·닦다·
  누르다·끼우다·열다·담다·닫다). 해당 없으면 "없음".
- change: ★이 구간에서 **화면 속 사물에 무슨 일이 일어났는지** 한국어 한 줄로 적어라.
  손이 무엇을 했는지(action)가 아니라 **사물이 어떻게 됐는지**다 — 주어가 사물이어야 한다.
  · 상태 변화: "프린팅이 쩍쩍 갈라져 있다" / "크랙이 사라지고 매끈해졌다" / "양념이 사방으로 튄다"
  · 기능 확인: "가림막이 튀는 기름을 막아준다" / "물로 쓱 헹구니 바로 닦인다" / "흔들어도 고정돼 있다"
  · 감각·재질: "손으로 늘리니 모찌처럼 쭉 늘어난다" / "표면이 보송보송해 보인다"
  변화도 감각도 안 보이는 구간(인물 등장·인사·배경·CTA)이면 빈 문자열.
  ★화면에 실제로 보이는 것만. 안 보이는 효능을 지어내지 마라.
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
            # 사물이 주어인 변화·감각 한 줄(2026-07-31). 옛 추출본엔 없어서 ""로 떨어진다(fail-open)
            # — 하류(_build_inventory)가 빈 값이면 그 칸을 통째로 생략하므로 회귀 없음.
            "change": (seg.get("change") or "").strip(),
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


# 이 점수 밑이면 태깅이 지침을 크게 어긴 것으로 보고 **딱 1회** 고쳐 부른다(2026-08-01).
# 0.6 = 가중치가 큰 검사(커버리지 0.20·시간정합 0.20) 두 개가 깨진 수준. 그 이상 깎였다면
# 슬롯(화면조합)이 쓸 재료 자체가 부실하다는 뜻이라 한 번은 다시 물어볼 값어치가 있다.
_QA_RETRY_BELOW = 0.6


def _video_duration(video_path):
    """영상 길이(초). 실패하면 None — QA가 길이 검사만 건너뛰고 계속 돈다(fail-open).

    ★format=duration을 쓰지 않는다: 그건 오디오·비디오 중 긴 값이라 화면 없는 꼬리가
    붙어 커버리지가 부당하게 낮게 나온다(scene_cut.video_frame_count 주석의 실측 근거).
    비디오 스트림 프레임 수 ÷ fps로 **화면이 실제로 있는 길이**를 쓴다."""
    try:
        fps = scene_cut.video_fps(video_path)
        frames = scene_cut.video_frame_count(video_path)
        if fps and frames:
            return frames / fps
    except Exception:
        pass
    return None


def _qa_retry_decision(result, duration, already_retried):
    """(재시도할까, 프롬프트에 얹을 힌트) — 순수 판단이라 Gemini 없이 테스트된다.

    already_retried면 무조건 False: QA 재시도는 **딱 1회**다. 점수가 낮다고 계속 부르면
    비용이 곱절이 되고, 모델이 같은 실수를 반복하면 무한루프가 된다."""
    if already_retried:
        return False, ""
    score, flags = tag_qa.validate_extract(result, duration)
    if score >= _QA_RETRY_BELOW or not flags:
        return False, ""
    return True, "\n★지난 시도의 문제(반드시 고쳐라): " + "; ".join(flags)


def _attach_qa(result, duration, retried, video_path=None):
    """결과에 tag_qa 기록을 붙여 반환. **결과 자체는 절대 안 바꾼다**(빈 대본 금지).
    하류(job 로그·tag_audit)가 이 값으로 '이 영상이 왜 이상한가'를 추적한다.

    video_path가 오고 Layer 2 플래그(`tag_qa_frames_enabled`)가 켜져 있으면 프레임 대조
    점수(frame_score)도 같이 남긴다. **기본은 꺼짐**이라 평소엔 추가 비용이 0이다."""
    score, flags = tag_qa.validate_extract(result, duration)
    result["tag_qa"] = {"score": score, "flags": flags, "retried": bool(retried)}
    _attach_frame_qa(result, video_path)
    return result


def _attach_frame_qa(result, video_path):
    """Layer 2 스팟체크를 붙인다 — 실패·미측정이면 **아무 키도 안 남긴다**.

    ★모르는 것을 0점으로 적지 않는다: 없는 키와 0.0은 하류에서 전혀 다른 뜻이다
    (0.0은 '화면이 전부 틀렸다'는 강한 신호다). 여기서 대충 채우면 기준선이 거짓이 된다.
    ★어떤 예외도 추출을 죽이지 못한다 — QA는 기록 장치지 차단 장치가 아니다."""
    if not video_path:
        return
    import shutil
    import tempfile
    tmp = None
    try:
        from shopping_shorts import tag_qa_frames
        if not tag_qa_frames.flag_on():
            return
        # ★프레임은 판정에만 쓰고 바로 버린다(2026-08-01 리뷰 F6). 처음엔 '영상 옆'에
        #   만들었는데, video_path가 도서관 영구보관본(_WIKI_MEDIA_DIR)일 때는 그 옆 폴더도
        #   영구히 남는다 — 플래그를 켜는 순간 영상마다 jpg가 쌓인다. 수명을 여기서 소유해
        #   finally로 반드시 지운다(디스크 81%인 서버라 누수 여지를 두면 안 된다).
        tmp = tempfile.mkdtemp(prefix="tag_qa_frames_")
        out = tag_qa_frames.spot_check(result, video_path, tmp)
        if out:
            result["tag_qa"].update(out)
    except Exception as e:  # noqa: BLE001
        print(f"script_extract._attach_frame_qa: 건너뜀(무해) — {e!r}",
              file=__import__('sys').stderr)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def storable(result):
    """`script_extracts`에 남길 필드만 추린 dict — **저장 직전에 이걸 통과시켜라.**

    ★왜 헬퍼로 뽑았나(2026-08-01): 저장부 3곳이 각자 `{"full_text":…, "segments":…}`를
    손으로 다시 만들고 있었다. 그래서 `_attach_qa`가 붙인 `tag_qa`가 **저장 순간 버려졌고**,
    tag_audit이 재는 A코호트(실시간 채점 점수)가 영원히 0건이 될 판이었다. 필드를 하나
    늘릴 때마다 세 군데를 같이 고쳐야 하는 구조 자체가 재발의 원인이라 한 곳으로 모은다.

    통째로 저장하지 않는 이유는 그대로 유지한다 — 추출 결과엔 DB에 남길 필요 없는
    중간 부산물이 섞이므로 **화이트리스트**로 간다(새 필드는 여기 추가하면 전 경로에 반영).
    """
    r = result or {}
    return {"full_text": r.get("full_text", "") or "",
            "segments": r.get("segments") or [],
            "tag_qa": r.get("tag_qa") or {}}


def _pick_better_extract(first, second, duration):
    """QA 재시도 결과가 더 나쁘면 첫 시도를 쓴다 — 재시도가 품질을 깎으면 안 된다.
    second가 비었으면(API 실패) 볼 것도 없이 first."""
    if not (second or {}).get("segments"):
        return first
    if not (first or {}).get("segments"):
        return second
    s1, _ = tag_qa.validate_extract(first, duration)
    s2, _ = tag_qa.validate_extract(second, duration)
    return second if s2 > s1 else first


def extract_script(video_path, video_id, caption="", max_retries=4, quota_sleep=8,
                   use_boundaries=True):
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
    # ★use_boundaries=False — 장면전환 힌트를 빼고 모델 자율 분할로 뽑는다(2026-08-06).
    #   힌트는 보통 세분화에 도움되지만(35.8초 영상 실측: 힌트 103% vs 무힌트 73%),
    #   **일부 영상에서는 모델이 힌트 개수를 '세그먼트 상한'처럼 받아들여** 앞쪽 경계만
    #   쓰고 뒤쪽 대사를 거기에 우겨넣는다 → 영상 뒷부분이 통째로 날아간다.
    #   실측(Dbjk5BXToB7, 21.1초): 힌트 있음 **55%**(11.6초에서 끊김, 같은 문장 6번 반복)
    #   vs 힌트 없음 **81%**(17.0초, 마지막 CTA가 15~17초 제자리). 경계 22개를 다 줬는데
    #   모델은 앞 12개만 썼다. 그래서 재추출 때는 **조건을 바꿔서** 다시 뽑는다 —
    #   같은 힌트로 다시 부르면 같은 결과가 나올 뿐이다(그 27초가 순수 낭비였다).
    #   ★_cuts·_fps는 힌트를 끄더라도 계산해 둔다 — 아래 모션레벨 계산이 쓴다.
    #     (여기서 한 번 빠뜨려 UnboundLocalError로 추출이 통째로 빈 결과가 됐다)
    boundary_hint, _cuts, _fps = _boundary_hint(video_path)
    if not use_boundaries:
        boundary_hint = ""
    base_prompt = _PROMPT.format(caption=caption or "(캡션 없음)",
                                 boundaries=boundary_hint or "(감지 실패 — 화면·주제 변화로 판단)")
    prompt = base_prompt
    model = _MODEL
    primary_503 = 0
    # 태깅 QA(2026-08-01): 첫 성공 결과가 지침을 크게 어겼으면 문제를 알려주고 딱 1회 더 부른다.
    # qa_first는 그 첫 결과 — 재시도가 오히려 나쁘면 이쪽으로 되돌린다(재시도가 품질을 깎지 않게).
    duration = _video_duration(video_path)
    qa_first, qa_retried = None, False

    # ★죽은 키(401/403 서비스계정 비활성) 우회는 재시도 예산(max_retries)을 먹지 않는다
    #   (2026-08-10 실사고). 죽은 키가 27개면 max_retries=4로는 살아있는 키에 닿기 전에
    #   재시도가 소진돼 job이 실패했다. 죽은 키는 _mark_key_exhausted로 즉시 풀에서 빠지므로,
    #   여기서는 살아있는 키를 만날 때까지 걸어간다. 풀이 진짜 다 죽으면 _current_key_and_idx가
    #   None을 돌려 KeyPoolExhausted로 빠져나온다. 안전 상한: 실재시도 + 전체 키 수 + 여유.
    attempt = 0
    _walk_guard = 0
    _walk_cap = max_retries + len(SHORTS_GEMINI_KEYS) + 2
    while attempt < max_retries and _walk_guard < _walk_cap:
        _walk_guard += 1
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            # 조용한 빈 결과 금지(2026-08-07) — 호출부가 '음성 없는 영상'으로 오해했다.
            print("script_extract: 키 풀 전체 소진 — 호출 못 함(영상 문제 아님)",
                  file=sys.stderr)
            raise KeyPoolExhausted(
                "Gemini 키 풀이 전부 소진 표시 상태라 대본 추출을 시작하지 못했습니다")
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
            result = {
                "segments": segments,
                "full_text": data.get("full_text", ""),
                "product_benefits": benefits,
            }
            # ★태깅 QA(2026-08-01). 지금까진 스키마만 통과하면 무조건 채택했다 — 프롬프트의
            #   지침(0초 훅·받아쓰기·shot_role·change)이 지켜졌는지 아무도 안 봤다. 슬롯 기반
            #   화면조합이 이 태깅 위에 전부 서므로 여기가 부실하면 위층이 정교해도 소용없다.
            should_retry, hint = _qa_retry_decision(result, duration, qa_retried)
            if should_retry:
                qa_first, qa_retried = result, True
                prompt = base_prompt + hint      # 무엇이 틀렸는지 알려주고 다시 묻는다
                print(f"script_extract: 태깅 QA 재시도 — {hint.strip()}", file=sys.stderr)
                attempt += 1
                continue
            if qa_first is not None:             # 재시도분이 더 나쁘면 첫 결과로 되돌린다
                result = _pick_better_extract(qa_first, result, duration)
            return _attach_qa(result, duration, qa_retried, video_path)
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue  # ★죽은 키 우회는 attempt를 안 올린다 — 살아있는 키까지 걸어간다
            if key_vault.is_quota_error(e):
                time.sleep(quota_sleep)
                attempt += 1
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
                        attempt += 1
                        continue  # 다른 모델이라 앞 모델의 혼잡과 무관 — 기다리지 않는다
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 5)
                    attempt += 1
                    continue
            # ★QA 재시도 중 API가 죽었으면 첫 결과를 살려 돌려준다(2026-08-01). 점수가 낮아도
            #   있는 대본이 빈 대본보다 낫다 — QA는 기록 장치지 차단 장치가 아니다.
            if qa_first is not None:
                print(f"script_extract: QA 재시도 실패 — 첫 결과 유지 ({e!r})", file=sys.stderr)
                return _attach_qa(qa_first, duration, qa_retried, video_path)
            print(f"script_extract: 빈 결과 반환(재시도 소진 또는 미분류 오류) — {e!r}", file=sys.stderr)
            return dict(_EMPTY)
        finally:
            if file_obj is not None:
                try:
                    client.files.delete(name=file_obj.name)
                except Exception:
                    pass
    if qa_first is not None:                     # 재시도가 루프를 소진한 경우도 마찬가지
        return _attach_qa(qa_first, duration, qa_retried, video_path)
    return dict(_EMPTY)


def _frame_flag_on():
    """frame_extract_enabled 설정 조회(실패·미설정 → False, fail-safe로 기존추출)."""
    try:
        from shopping_shorts.store import Store
        from shopping_shorts.config import DB_PATH
        return Store(DB_PATH).get_setting("frame_extract_enabled", "") == "1"
    except Exception:
        return False


def extract_auto(video_path, video_id, caption="", *, use_frames=None,
                 _frames_fn=None, _classic_fn=None):
    """추출 디스패처(2026-07-29): 플래그 켜지면 B1 프레임추출, 아니면 기존 영상추출.
    1단계 모든 추출 호출부가 이걸 쓰면 플래그 하나로 전 경로가 B1으로 전환된다.
    B1이 빈 결과(컷 감지 실패 등)면 기존 추출로 폴백 — 빈 대본 금지.
    use_frames=None이면 설정을 읽는다. _frames_fn/_classic_fn은 테스트 주입용."""
    if use_frames is None:
        use_frames = _frame_flag_on()
    classic = _classic_fn or extract_script
    if not use_frames:
        return classic(video_path, video_id, caption=caption)
    frames = _frames_fn
    if frames is None:
        from shopping_shorts import frame_script
        frames = frame_script.extract_script_frames
    r = frames(video_path, video_id, caption=caption)
    if not (r or {}).get("segments"):
        return classic(video_path, video_id, caption=caption)
    return r
