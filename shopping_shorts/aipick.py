"""AI PICK 사전분석 조립 — 기존 채점/구조분석을 하나의 프론트 계약으로 묶는다.

패키지 한정 import(`from shopping_shorts import ...`) — backbone.py/structure_analyze.py
자신도 이 관례를 쓰고, app.py도 마찬가지다(2026-07-23 확인). 브리프 예시 코드의 bare
import(`from backbone import ...`)는 로컬 pytest(cwd=shopping_shorts/) 한정으로만 우연히
동작해 서버 실행 cwd가 다르면 깨질 수 있어 코드베이스 관례로 맞췄다."""
from shopping_shorts.backbone import pick_backbone, score_backbones
from shopping_shorts.structure_analyze import analyze_structure

_SEG_COLORS = {"훅": "#facc6b", "문제제기": "#7db8f5", "공감": "#c99af5",
               "주변인물등장": "#c99af5", "반전": "#f5a97d", "증거/시연": "#7df5db",
               "결과": "#7df5db", "CTA": "#f5a97d"}


def _parse_approx_sec(approx_sec):
    """analyze_structure의 beats[].approx_sec("0-2" 형태 문자열) → (start, end) float.
    파싱 불가면 None."""
    if not approx_sec:
        return None
    try:
        parts = str(approx_sec).replace(" ", "").split("-")
        if len(parts) == 2:
            return float(parts[0]), float(parts[1])
        if len(parts) == 1:
            v = float(parts[0])
            return v, v
    except (ValueError, TypeError):
        return None
    return None


def _beats_to_segments(beats, target_seconds):
    """analyze_structure()의 실제 반환 키는 segments/pct가 아니라
    beats:[{label,desc,approx_sec}] + target_seconds(초). approx_sec("0-2")를 파싱해
    프론트 계약의 segments:[{label,pct,color}]로 변환한다.

    approx_sec는 structure_analyze._SCHEMA에서 선택 필드라 Gemini가 일부 비트만
    채울 수 있다. pct 산정 기준을 비트마다 다르게(파싱된 애는 dur/total, 안 된
    애는 100/n) 섞으면 합이 100%를 벗어난다(예: 3비트 중 2개만 2s+3s로 파싱되면
    40+60+33.3=133.3%). 그래서 기준을 하나로 통일한다:
    - 전 비트가 파싱되고 총합>0이면 → 전부 dur/total*100
    - 하나라도 못 파싱되거나 총합이 0이면 → 전부 100/n 균등분배
    이렇게 하면 항상 합이 ~100%(반올림 오차 이내)로 맞는다."""
    if not beats:
        return []
    n = len(beats)
    durations = []
    for b in beats:
        rng = _parse_approx_sec(b.get("approx_sec"))
        durations.append((rng[1] - rng[0]) if rng and rng[1] > rng[0] else None)
    total = sum(durations) if all(d is not None for d in durations) else 0
    uniform = total <= 0
    segs = []
    for b, d in zip(beats, durations):
        pct = round(100 / n, 1) if uniform else round(d / total * 100, 1)
        label = b.get("label", "")
        segs.append({"label": label, "pct": pct, "color": _SEG_COLORS.get(label, "#8ea2ff")})
    return segs


def _structure_view(struct_raw):
    """analyze_structure 원형(beats/hook_type/devices) → 프론트 카드용 뷰. 빈 입력이면 {}."""
    struct_raw = struct_raw or {}
    if not struct_raw:
        return {}
    return {
        "segments": _beats_to_segments(struct_raw.get("beats") or [],
                                       struct_raw.get("target_seconds") or 0),
        "hook_type": struct_raw.get("hook_type", ""),
        "devices": struct_raw.get("devices", []),
    }


def build_aipick(sources, meta, forced=None):
    if not sources:
        return {"pick_id": None, "pick_index": -1, "tiles": {}, "structure": {}, "candidates": [], "pick_meta": {}}
    meta = meta or {}
    scored = score_backbones(sources, meta)                 # [{video_id,coverage,engagement,score}] score desc
    pick_id = pick_backbone(sources, meta, forced=forced)    # forced(⭐메인) 우선
    idx = next((i for i, s in enumerate(sources) if str(s.get("video_id")) == str(pick_id)), 0)
    pick = sources[idx]
    views, followers = pick.get("views"), pick.get("followers")
    # comments는 항상 pick(소스)에 이미 실려 있다(_load_work_sources가 키 자체를
    # 빠짐없이 채운다, 값은 None일 수 있어도).
    comments = pick.get("comments")
    # ★진짜 값만 낸다(2026-07-26 사장님: 지표가 매번 바뀌고 추정 같다).
    #   폐기: comments_x_avg = comments/'지금 바구니 평균' → 소스를 담고 뺄 때마다 배수가
    #         흔들려 벤치마크로 무의미(순환참조). engagement_rank = AI PICK은 정의상 최고점이라
    #         거의 항상 '1위'인 동어반복 + 점수가 재조합커버리지 지배라 '참여밀도'와도 어긋남.
    #   대체: engagement_rate = 댓글/팔로워 — 소스 자체의 고정 실측치(=진짜 참여율). 조회수는
    #         이 시스템에 저장 안 돼(항상 None) views_x_followers는 사실상 안 뜬다(그대로 둔다).
    tiles = {
        "views": views,
        "views_x_followers": round(views / followers, 1) if views and followers else None,
        "comments": comments,
        "engagement_rate": round(comments / followers * 100, 1) if comments and followers else None,
        "seconds": pick.get("seconds"),
    }
    # 도서관(script_wiki) 저장 시 analyze_structure가 이미 1회 돌아 structure_json에
    # 캐시돼 있다(app.py api_produce_save_to_wiki). 있으면 재사용 — 매 AI PICK 조회마다
    # Gemini를 다시 태우면 비용·지연이 크고, 재분석 결과가 매번 달라질 수도 있다.
    # 캐시가 없을 때만(source 딕셔너리에 'structure' 키 자체가 없거나 빈 dict) 새로 분석.
    struct_raw = pick.get("structure") or analyze_structure(pick.get("text", "")) or {}
    structure = _structure_view(struct_raw)
    # ★소스 구조 비교(A, 2026-07-29): 사장님이 담긴 3개를 나란히 비교해 백본을 직접 고를 수 있게
    #   candidates에 각 소스의 **캐시된** 구조를 함께 싣는다. 캐시 없는 소스는 structure=None(프론트
    #   가 "분석 전"으로 표시) — 여기서 analyze_structure를 새로 태우지 않는다(전 소스 Gemini 재호출
    #   = 비용·지연 폭증). pick은 위에서 이미 폴백 분석을 거쳤고, autoload·도서관 저장분은 캐시가 있다.
    _by_id = {str(s.get("video_id")): s for s in sources}
    cand_out = []
    for r in scored:
        vid = str(r["video_id"])
        src = _by_id.get(vid) or {}
        cand_out.append({
            "video_id": r["video_id"], "score": r["score"],
            "name": src.get("title") or src.get("name") or "",
            "thumbnail": src.get("thumbnail") or src.get("thumb") or "",
            "structure": _structure_view(src.get("structure")) if src.get("structure") else None,
        })
    return {"pick_id": pick_id, "pick_index": idx, "tiles": tiles,
            "structure": structure, "candidates": cand_out,
            # ★pick의 원본 대본을 같이 실어 보낸다(2026-07-27 사장님 제보 "대본을 확보하지 못했습니다").
            #   프론트(startFromAiPick)는 예전에 /api/produce/picks(도서관 담김 버킷)에서만 대본을
            #   찾았는데, AI PICK 소스가 도서관 교차를 벗어나 script_extracts/reel에서도 오게 되면서
            #   도서관에 없는 영상이 픽되면 대본을 못 찾아 막다른 알럿이 떴다. 숫자·이름·썸네일과
            #   같은 출처에서 대본도 내려줘야 카드와 대본이 어긋나지 않는다(pick_meta와 같은 이유).
            "pick_text": pick.get("text") or "",
            "pick_meta": {
                "title": pick.get("title") or pick.get("name"),
                "category": pick.get("category"),
                "followers": pick.get("followers"),
                "thumbnail": pick.get("thumbnail") or pick.get("thumb"),
            }}
