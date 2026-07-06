import sys
import pathlib
import pipeline.atoms.strength_net as sn


def test_scan_heatmap_contract(monkeypatch):
    """scan_heatmap이 엔드포인트가 기대하는 계약(results/metrics/count/updated_at)을
    지키는지 고정. 라이브 KIS 호출은 build_heatmap monkeypatch로 차단."""
    scripts_dir = str(pathlib.Path(sn.__file__).resolve().parents[2] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import sector_heatmap

    fake = {"sectors": [{"name": "반도체", "avg_rate": 5.0, "stocks": [
        {"name": "X", "code": "1", "change_rate": 10.0, "price": 100}]}],
        "updated_at": "09:05:00", "source": "x"}
    monkeypatch.setattr(sector_heatmap, "build_heatmap",
                        lambda top_n=5, mode="regular": fake)
    monkeypatch.setattr(sn._db, "query_atoms", lambda **kw: [])  # atom 없음 → 미귀속

    out = sn.scan_heatmap(top_n=5, days=3)
    assert set(out.keys()) == {"results", "metrics", "count", "updated_at"}
    assert out["count"] == 1
    assert out["results"][0]["status"] == "unattributed"
    assert out["results"][0]["flag"] == "⚠️ 원인 미상 강세 — 추적 요망"
    assert out["metrics"]["silent_miss"] == 0
    assert out["updated_at"] == "09:05:00"
