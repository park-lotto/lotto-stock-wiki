"""#4732(11-04 강태경 23495d85016c): 재료 받기에서 영상 하나가 HTTP 403 이면 screen.download 가 예외 → c_download 통째 실패 →
지시서 ph_material_dl 이 dl.error 를 안 보고 쿠팡 사진만으로 진행(이미 받은 다른 영상도 목록에서 빠짐). 조용한 실패.
고친 꼴: 실행기는 영상마다 따로(실패는 fail 로), 지시서는 실패한 영상만 한 번 다시 받고 그래도 실패면 경보 남기고 받은 것으로 진행."""
from pathlib import Path

from tools.calcopy.hybrid import flow as FL
from tools.calcopy.hybrid import runner_ops as RO
from tools.calcopy.hybrid.common import StageError


def test_하나_실패해도_나머지_영상은_남는다(tmp_path, monkeypatch):
    from tools.calcopy.hybrid import screen
    def fake(W, ids, secs=None, prefix="", pad=20.0, log=print):
        if ids[0] == "BAD":
            raise StageError("받기 실패 BAD: HTTP Error 403")
        p = Path(W) / "src" / f"{ids[0]}.mp4"; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"x")
        return [p]
    monkeypatch.setattr(screen, "download", fake)
    monkeypatch.setattr(RO, "dims", lambda p: {"name": Path(p).name, "w": 1, "h": 1, "dur": 1.0})
    monkeypatch.setattr(RO, "CACHE", None)
    r = RO.c_download(tmp_path, {"items": [{"id": "GOOD"}, {"id": "BAD"}]})
    assert [f["name"] for f in r["files"]] == ["GOOD.mp4"] and "BAD" in r["fail"]


def test_지시서는_실패한_영상만_한_번_다시_받는다():
    st = {"tries": {}, "log": [], "screen_pick": {"chosen": [{"id": "GOOD", "sections": []}, {"id": "BAD", "sections": [[1, 5]]}]}}
    m = {"dl": {"files": [{"name": "GOOD.mp4"}], "fail": {"BAD": "403"}}, "stills": {"files": [{"name": "prod_1.jpg"}]}}
    out = FL.ph_material_dl(st, m, {}, {})
    assert out["do"][0]["cmd"] == "download" and out["do"][0]["items"] == [{"id": "BAD", "sections": [[1, 5]]}]
    out2 = FL.ph_material_dl(st, {"dl": {"files": [], "fail": {"BAD": "403"}}}, {}, {})
    assert out2 == {"goto": "asr"}
    assert [f["name"] for f in st["material"]["files"]] == ["GOOD.mp4", "prod_1.jpg"]
    assert any("BAD" in str(w) for w in st.get("warn") or [])
