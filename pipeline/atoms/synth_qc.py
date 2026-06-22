"""입력QC: 원자 정제(중복) + asset_level 라우팅. 설계 §4.1."""
from difflib import SequenceMatcher

# generic asset = 종목이 아닌 섹터/테마 키워드 (종목페이지로 못 감)
_GENERIC = {"반도체", "메모리 반도체", "MLCC", "2차전지", "바이오", "조선", "방산"}
_SIM = 0.92  # content 유사도 임계


def dedupe(atoms: list[dict]) -> list[dict]:
    out: list[dict] = []
    for a in atoms:
        hit = None
        for o in out:
            if SequenceMatcher(None, a["content"], o["content"]).ratio() >= _SIM:
                hit = o
                break
        if hit:
            hit.setdefault("sources", [hit.get("raw_file")])
            if a.get("raw_file") and a["raw_file"] not in hit["sources"]:
                hit["sources"].append(a["raw_file"])
        else:
            a = dict(a)
            a["sources"] = [a.get("raw_file")] if a.get("raw_file") else []
            out.append(a)
    return out


def route(atoms: list[dict]) -> dict:
    stock: dict[str, list] = {}
    sector: list = []
    for a in atoms:
        asset = (a.get("asset") or "").strip()
        level = a.get("asset_level") or "sector"
        if level == "stock" and asset and asset not in _GENERIC:
            stock.setdefault(asset, []).append(a)
        else:
            sector.append(a)
    return {"stock": stock, "sector": sector}
