"""모션 프리셋 팩: 정책 → 렌더 계획.

팩은 {전환·스티커·색감·텍스트모션} 한 세트이고, 이 모듈은 팩 정책과 비트 타임라인만으로
레이어 배치를 계산하는 **순수 함수**다(ffmpeg·Node·DB 의존 0).
자산 파일 해석은 motion_assets.resolve_layers의 몫 — 여기선 asset_id만 다룬다.
"""
import json
from pathlib import Path

DEFAULT_ASSETS_DIR = str(Path(__file__).parent / "assets" / "motion")


def load_packs(assets_dir=DEFAULT_ASSETS_DIR):
    """assets_dir/packs.json을 읽어 {pack_id: pack}으로 인덱싱. 없으면 {}.
    packs.json(큐레이션)은 manifest.json(자산 빌드산출물)과 수명주기가 달라 파일을 분리한다.
    """
    ppath = Path(assets_dir) / "packs.json"
    if not ppath.exists():
        return {}
    data = json.loads(ppath.read_text(encoding="utf-8"))
    return {p["id"]: p for p in data.get("packs", []) if p.get("id")}


def _boundaries(timeline):
    """비트 경계 시각 리스트(첫 비트 시작 0.0은 경계가 아니다)."""
    return [b["t0"] for b in timeline[1:]]


def _pick(items, policy):
    """policy에 따라 배치 대상만 고른다."""
    if not items or policy == "none":
        return []
    if policy == "every_beat":
        return items
    if policy == "hook_climax":
        return [items[0]] if len(items) == 1 else [items[0], items[-1]]
    return []


def build_plan(pack, timeline):
    """팩 + 타임라인 → {layers, color_filter, caption_effect, headcopy_enable}.

    - 전환: 비트 경계마다 start = 경계 - lead (0 아래 clamp), dur = transition.dur
    - 스티커: 대상 비트 **시작**에 start = t0, dur = sticker.dur
    - layers는 motion_assets.resolve_layers 입력형({asset_id, start, dur}) — 위치는 매니페스트 default.
    """
    pack = pack or {}
    layers = []

    tr = pack.get("transition") or {}
    if tr.get("asset_id"):
        lead = float(tr.get("lead") or 0)
        dur = float(tr.get("dur") or 0.5)
        for t in _pick(_boundaries(timeline), tr.get("policy")):
            layers.append({"asset_id": tr["asset_id"],
                           "start": max(0.0, t - lead),
                           "dur": dur})

    st = pack.get("sticker") or {}
    if st.get("asset_id"):
        dur = float(st.get("dur") or 1.0)
        for b in _pick(list(timeline), st.get("policy")):
            layers.append({"asset_id": st["asset_id"],
                           "start": b["t0"],
                           "dur": dur})

    return {
        "layers": layers,
        "color_filter": pack.get("color_filter") or None,
        "caption_effect": (pack.get("caption") or {}).get("effect") or None,
        "headcopy_enable": _headcopy_enable(pack, timeline),
    }


def _headcopy_enable(pack, timeline):
    """헤드카피 노출 정책 → ffmpeg enable 식(또는 None=전체 표시).
    hook_only: 첫 비트 구간에만.
    """
    policy = (pack.get("headcopy") or {}).get("policy")
    if policy != "hook_only" or not timeline:
        return None
    first = timeline[0]
    return f"between(t,0,{first['t0'] + first['dur']:.3f})"
