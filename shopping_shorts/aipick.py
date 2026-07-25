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


def build_aipick(sources, meta, forced=None):
    if not sources:
        return {"pick_id": None, "pick_index": -1, "tiles": {}, "structure": {}, "candidates": [], "pick_meta": {}}
    meta = meta or {}
    scored = score_backbones(sources, meta)                 # [{video_id,coverage,engagement,score}] score desc
    ranks = {r["video_id"]: i + 1 for i, r in enumerate(scored)}
    pick_id = pick_backbone(sources, meta, forced=forced)    # forced(⭐메인) 우선
    idx = next((i for i, s in enumerate(sources) if str(s.get("video_id")) == str(pick_id)), 0)
    pick = sources[idx]
    m = meta.get(str(pick_id), {})
    views, followers = pick.get("views"), pick.get("followers")
    # comments는 항상 pick(소스)에 이미 실려 있다(_load_work_sources가 키 자체를
    # 빠짐없이 채운다, 값은 None일 수 있어도) — m.get("comments") 기본값은 도달 불가라 제거.
    comments, avg = pick.get("comments"), m.get("avg_comments")
    tiles = {
        "views": views,
        "views_x_followers": round(views / followers, 1) if views and followers else None,
        "comments": comments,
        "comments_x_avg": round(comments / avg, 1) if comments and avg else None,
        "engagement_rank": ranks.get(str(pick_id), 1),
        "seconds": pick.get("seconds"),
    }
    # 도서관(script_wiki) 저장 시 analyze_structure가 이미 1회 돌아 structure_json에
    # 캐시돼 있다(app.py api_produce_save_to_wiki). 있으면 재사용 — 매 AI PICK 조회마다
    # Gemini를 다시 태우면 비용·지연이 크고, 재분석 결과가 매번 달라질 수도 있다.
    # 캐시가 없을 때만(source 딕셔너리에 'structure' 키 자체가 없거나 빈 dict) 새로 분석.
    struct_raw = pick.get("structure") or analyze_structure(pick.get("text", "")) or {}
    structure = {}
    if struct_raw:
        structure = {
            "segments": _beats_to_segments(struct_raw.get("beats") or [],
                                            struct_raw.get("target_seconds") or 0),
            "hook_type": struct_raw.get("hook_type", ""),
            "devices": struct_raw.get("devices", []),
        }
    return {"pick_id": pick_id, "pick_index": idx, "tiles": tiles,
            "structure": structure, "candidates": [{"video_id": r["video_id"], "score": r["score"]} for r in scored],
            "pick_meta": {
                "title": pick.get("title") or pick.get("name"),
                "category": pick.get("category"),
                "followers": pick.get("followers"),
                "thumbnail": pick.get("thumbnail") or pick.get("thumb"),
            }}
