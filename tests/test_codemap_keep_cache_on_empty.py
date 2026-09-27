# -*- coding: utf-8 -*-
"""KRX 갱신이 빈 표를 돌려주면 krx_codes.json을 덮어쓰지 않는다(2026-09-27 실사고: 403 → 44바이트 파일)."""
import json
from pipeline.atoms import codemap as c


def test_empty_download_keeps_existing_file(tmp_path, monkeypatch):
    f = tmp_path / "krx_codes.json"
    f.write_text(json.dumps({"updated": "2026-09-09", "codes": {"삼성전자": "005930", "카카오": "035720"}}), encoding="utf-8")
    monkeypatch.setattr(c, "_KRX_CACHE_FILE", f)
    monkeypatch.setattr(c, "_fetch_krx_market", lambda k: (_ for _ in ()).throw(RuntimeError("403")))
    out = c.refresh_krx_cache()
    assert out == {"삼성전자": "005930", "카카오": "035720"}
    assert json.loads(f.read_text(encoding="utf-8"))["codes"]["삼성전자"] == "005930"   # 파일 그대로


def test_good_download_still_writes(tmp_path, monkeypatch):
    f = tmp_path / "krx_codes.json"
    f.write_text(json.dumps({"updated": "2026-09-09", "codes": {"a": "000001"}}), encoding="utf-8")
    monkeypatch.setattr(c, "_KRX_CACHE_FILE", f)
    calls = []
    monkeypatch.setattr(c, "_fetch_krx_market", lambda k: calls.append(k) or {"종목%d" % len(calls): "%06d" % len(calls)})
    out = c.refresh_krx_cache()
    assert len(out) == len(c._KRX_MARKETS) and json.loads(f.read_text(encoding="utf-8"))["codes"] == out
