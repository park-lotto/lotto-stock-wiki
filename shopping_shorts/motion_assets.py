"""모션 자산 매니페스트 로드 + 레이어(asset_id) → 실경로·기본배치 해석.
Remotion(Node)과 무관한 순수 Python — 프리렌더된 자산 파일과 manifest.json만 읽는다."""
import json
import os
from pathlib import Path

# 기본 자산 폴더(리포 내 프리렌더 자산). 호출부가 override 가능.
DEFAULT_ASSETS_DIR = str(Path(__file__).parent / "assets" / "motion")


def load_manifest(assets_dir=DEFAULT_ASSETS_DIR):
    """assets_dir/manifest.json을 읽어 {asset_id: entry} dict로 인덱싱. 없으면 {}."""
    mpath = Path(assets_dir) / "manifest.json"
    if not mpath.exists():
        return {}
    data = json.loads(mpath.read_text(encoding="utf-8"))
    return {a["id"]: a for a in data.get("assets", []) if a.get("id")}


def resolve_layers(layers, assets_dir=DEFAULT_ASSETS_DIR):
    """deco.motion.layers(각 {asset_id, start?, dur?, x?, y?, width?, alpha?})를
    실제 합성 가능한 레이어 리스트로 해석한다.
    - 매니페스트의 default 배치를 채우되, 레이어가 준 값이 우선한다.
    - 실제 파일 경로를 '_abspath'로 붙인다.
    - 매니페스트에 없거나 파일 실물이 없는 asset_id는 조용히 skip(관용).
    """
    manifest = load_manifest(assets_dir)
    resolved = []
    for L in layers or []:
        aid = L.get("asset_id")
        entry = manifest.get(aid)
        if not entry:
            continue
        path = Path(assets_dir) / entry.get("file", "")
        if not path.exists():
            continue
        default = entry.get("default") or {}
        merged = {
            "asset_id": aid,
            "_abspath": str(path),
            "start": float(L.get("start") or 0),
            "dur": L.get("dur", None),   # None이면 전체 재생(enable 생략)
            "x": L.get("x", default.get("x", 50)),
            "y": L.get("y", default.get("y", 50)),
            "width": L.get("width", default.get("width")),
            "alpha": L.get("alpha", default.get("alpha", 1)),
        }
        resolved.append(merged)
    return resolved
