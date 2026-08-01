"""태깅 QA — 추출된 세그먼트가 `script_extract._PROMPT`의 지침을 실제로 지켰는지 채점한다.

왜 필요한가: 프롬프트엔 실사고로 쌓인 규칙이 많은데(0초 훅 강제, 받아쓰기, 오인 금지,
change/is_key/shot_role) **지켜졌는지 확인하는 코드가 한 줄도 없었다**. 스키마만 통과하면
무조건 채택됐다. 슬롯 기반 화면조합(대본퀄v3)이 이 태깅 위에 전부 서 있으므로, 여기가
틀리면 그 위층이 아무리 정교해도 결과가 나쁘다.

원칙 — **기록 장치지 차단 장치가 아니다**: 점수가 낮아도 결과를 버리지 않는다(빈 대본 금지).
호출부는 점수를 보고 ①한 번 고쳐 부르거나 ②그냥 쓰되 기록만 남긴다.
"""
from __future__ import annotations

# 각 검사의 감점 가중치(합=1.0). 훅·시간정합처럼 하류를 직접 깨는 것에 큰 가중을 준다.
_W_HOOK = 0.15          # 0초 훅 누락 — 영상의 첫인상이 통째로 빠진다
_W_COVERAGE = 0.20      # 커버리지 — 세그가 영상 대부분을 안 덮으면 재료 자체가 모자라다
_W_TIME = 0.20          # 시간 정합 — 역전·겹침은 슬롯 순서를 직접 깨뜨린다
_W_TEXT = 0.15          # 받아쓰기 — 원본 대사가 없으면 리라이트할 재료가 없다
_W_FULLTEXT = 0.05      # full_text 이어붙임 일치
_W_ROLE = 0.15          # shot_role/change/is_key 분포 — 붕괴하면 배치·실증 선별이 무의미
_W_DESC = 0.10          # scene_desc 복붙 — 화면 구분이 사라진다

_HOOK_MAX_START = 0.5   # 첫 세그가 이 시각보다 늦게 시작하면 훅 누락으로 본다
_COVERAGE_MIN = 0.75    # Σ(end-start)/duration 하한
_TAIL_MIN = 0.85        # 마지막 end가 duration의 이 비율은 넘어야 한다
_OVERLAP_TOL = 0.5      # 세그 간 겹침 허용치(초) — 반올림 오차는 눈감아준다
_EMPTY_TEXT_MAX = 0.5   # 빈 text 비율이 이보다 크면 받아쓰기 실패
_FULLTEXT_LO, _FULLTEXT_HI = 0.8, 1.2   # full_text 길이 / 세그 이어붙임 길이 허용 범위
_DUP_DESC_MAX = 0.5     # 같은 scene_desc 문구 비율 상한
_DESC_MIN_CHARS = 6     # scene_desc 평균 길이 하한


def _num(v):
    """start/end가 문자열로 와도 숫자로 — 모델이 가끔 "3.0"으로 준다."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _check_hook(segs):
    st = _num(segs[0].get("start"))
    if st is None or st > _HOOK_MAX_START:
        return f"훅 누락: 첫 세그가 {st if st is not None else '?'}초에서 시작(0초부터여야 함)"
    return None


def _check_coverage(segs, duration):
    if not duration or duration <= 0:
        return None                      # duration 모르면 판단 보류(fail-open)
    covered = 0.0
    last_end = 0.0
    for s in segs:
        a, b = _num(s.get("start")), _num(s.get("end"))
        if a is None or b is None or b <= a:
            continue
        covered += b - a
        last_end = max(last_end, b)
    ratio = covered / duration
    if ratio < _COVERAGE_MIN:
        return f"커버리지 부족: 영상 {duration:.0f}초 중 {ratio * 100:.0f}%만 태깅됨"
    if last_end < duration * _TAIL_MIN:
        return f"커버리지 부족: 마지막 세그가 {last_end:.0f}초에서 끝남(영상은 {duration:.0f}초)"
    return None


def _check_time(segs, duration):
    prev_end = None
    for s in segs:
        a, b = _num(s.get("start")), _num(s.get("end"))
        if a is None or b is None:
            return f"시간 정합 오류: {s.get('seg_id')} 의 start/end가 숫자가 아니다"
        if b <= a:
            return f"시간 정합 오류: {s.get('seg_id')} 의 start({a})가 end({b}) 이상이다"
        if prev_end is not None and a < prev_end - _OVERLAP_TOL:
            return f"시간 정합 오류: {s.get('seg_id')} 가 앞 세그와 {prev_end - a:.1f}초 겹친다"
        if duration and b > duration + 1.0:
            return f"시간 정합 오류: {s.get('seg_id')} 의 end({b})가 영상 길이({duration:.0f}초)를 넘는다"
        prev_end = b
    return None


def _check_text(segs, result):
    empty = sum(1 for s in segs if not (s.get("text") or "").strip())
    if empty / len(segs) <= _EMPTY_TEXT_MAX:
        return None
    # 무자막 영상 면제: 프롬프트가 "자막 없어도 benefits는 반드시 채워라"라고 요구하는 경로다.
    # 이 경우 text가 비는 게 정상이고, benefits가 대본 재료 역할을 한다.
    if result.get("product_benefits"):
        return None
    return f"나레이션 누락: 세그 {len(segs)}개 중 {empty}개의 text가 비었다(무자막 특장점도 없음)"


def _check_fulltext(segs, result):
    joined = " ".join((s.get("text") or "").strip() for s in segs).strip()
    full = (result.get("full_text") or "").strip()
    if not joined and not full:
        return None                      # 무자막 영상 — 위 _check_text가 판단한다
    if not full:
        return "full_text 누락: 세그 text는 있는데 full_text가 비었다"
    if not joined:
        return None
    ratio = len(full) / len(joined)
    if not (_FULLTEXT_LO <= ratio <= _FULLTEXT_HI):
        return f"full_text 불일치: 세그 이어붙임 대비 {ratio * 100:.0f}% 길이(누락/중복 의심)"
    return None


def _check_roles(segs):
    roles = [(s.get("shot_role") or "").strip() for s in segs]
    if all(r in ("", "기타") for r in roles):
        return "shot_role 붕괴: 전 세그가 '기타'(장면 배치에 쓸 수 없다)"
    changes = [(s.get("change") or "").strip() for s in segs]
    if not any(changes):
        return "change 전멸: 어느 세그도 사물의 변화를 적지 않았다"
    if not any(s.get("is_key") for s in segs):
        return "is_key 전멸: 기능·방법을 실증하는 구간이 하나도 없다"
    return None


def _check_desc(segs):
    descs = [(s.get("scene_desc") or "").strip() for s in segs]
    filled = [d for d in descs if d]
    if not filled:
        return "scene_desc 누락: 화면 묘사가 전부 비었다"
    top = max(filled.count(d) for d in set(filled))
    if len(filled) > 1 and top / len(filled) > _DUP_DESC_MAX:
        return f"scene_desc 복붙: 같은 묘사가 {top}/{len(filled)}개 세그에 반복된다"
    avg = sum(len(d) for d in filled) / len(filled)
    if avg < _DESC_MIN_CHARS:
        return f"scene_desc 부실: 평균 {avg:.0f}자(화면을 구분할 수 없다)"
    return None


def validate_extract(result, video_duration=None):
    """추출 결과를 프롬프트 지침 대비 채점 → (score 0~1, flags: list[str]).

    순수 계산이다(모델 호출 없음, 0원). video_duration이 None이면 길이에 의존하는 검사
    (커버리지)는 건너뛴다 — ffprobe가 실패해도 QA 자체는 돌아야 하기 때문(fail-open).
    flags는 사람이 읽는 한국어 한 줄이고, 재시도 프롬프트에 그대로 얹어 모델에게 준다.
    """
    segs = (result or {}).get("segments") or []
    if not segs:
        return 0.0, ["세그먼트 없음: 추출이 통째로 실패했다"]
    duration = _num(video_duration)
    checks = [
        (_W_HOOK, _check_hook(segs)),
        (_W_COVERAGE, _check_coverage(segs, duration)),
        (_W_TIME, _check_time(segs, duration)),
        (_W_TEXT, _check_text(segs, result)),
        (_W_FULLTEXT, _check_fulltext(segs, result)),
        (_W_ROLE, _check_roles(segs)),
        (_W_DESC, _check_desc(segs)),
    ]
    flags = [msg for _, msg in checks if msg]
    lost = sum(w for w, msg in checks if msg)
    return round(max(0.0, 1.0 - lost), 3), flags
