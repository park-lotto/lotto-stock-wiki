import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_excel as ix


def _sample_results():
    return {
        "수급": {"빈집_A": [{"name": "에코프로비엠", "code": "247540",
                              "osc": -0.42, "pct": 8.0, "trend": "↓ 빈집심화"}]},
        "중소형주수급": {},
        "RS": {"top30": [{"name": "삼성전자", "RS_avg": 1.23, "norm_RS_avg": 0.9}],
               "bottom10": []},
        "추정이익변경": {"results": {
            "TP_Up": [{"name": "삼성전자", "code": "A005930",
                       "tp_old": 80000, "tp_new": 92000}],
            "TP_Down": []}},
        "컨센움직임": {"results": {
            "쇼크": [{"name": "에코프로비엠", "code": "A247540",
                      "csen_chg": -12.0, "surprise_rate": -30.0}]}},
        "가속화모멘텀": {"results": {
            "주당순이익1개+": [{"name": "삼성전자", "score": 0.61}]}},
        "액티브ETF": {"increase": [{"etf": "TIGER", "name": "삼성전자",
                                     "diff": 0.3, "rate": 1.1}], "decrease": []},
        "일정": {"d7": [{"date": "2999-01-01", "related": "삼성전자",
                         "content": "실적발표"}], "d30": []},
    }


def test_build_stock_index_maps_codes_and_fields(tmp_path):
    # 종목명→코드 매핑 고정 (krx_codes.json 의존 제거)
    ix._KRX_NAME2CODE = {"삼성전자": "005930", "에코프로비엠": "247540"}
    dest = tmp_path / "taerini_stock.json"

    out = ix.build_stock_index(_sample_results(), dest=dest)

    assert out["date"]
    s = out["stocks"]
    # 코드 정규화 (A 제거 / 6자리)
    assert "247540" in s and "005930" in s
    # 코드 보유 파서 (오실레이터)
    assert s["247540"]["osc"]["trend"] == "↓ 빈집심화"
    # 종목명만 있는 파서 (RS) → 코드 매핑
    assert s["005930"]["rs"]["bucket"] == "상위"
    # TP 변화율 계산
    assert s["005930"]["tp"]["change_pct"] == 15.0
    assert s["005930"]["tp"]["dir"] == "상향"
    # 컨센 타입
    assert s["247540"]["consensus"]["type"] == "쇼크"
    # 가속/ETF/일정
    assert s["005930"]["accel"]["score"] == 0.61
    assert s["005930"]["etf"]["action"] == "비중증가"
    assert s["005930"]["schedule"]["dday"] is not None
    # 파일 저장 + meta
    assert dest.exists()
    saved = json.loads(dest.read_text(encoding="utf-8"))
    assert saved["meta"]["stock_count"] == 2
    assert isinstance(saved["meta"]["unmatched"], list)


def test_unmatched_names_recorded(tmp_path):
    ix._KRX_NAME2CODE = {}   # 매핑 없음
    out = ix.build_stock_index(
        {"RS": {"top30": [{"name": "없는종목", "RS_avg": 1.0}], "bottom10": []}},
        dest=tmp_path / "x.json")
    assert "없는종목" in out["meta"]["unmatched"]
    assert out["stocks"] == {}


def test_api_taerini_stock(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "dashboard"))
    import server
    from fastapi.testclient import TestClient

    snap = tmp_path / "taerini_stock.json"
    snap.write_text(json.dumps({
        "date": "2026-06-30",
        "stocks": {"247540": {"name": "에코프로비엠",
                              "tp": {"target": 330000, "dir": "하향"}}},
        "meta": {"stock_count": 1, "unmatched": []},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "TAERINI_STOCK_PATH", str(snap))

    c = TestClient(server.app)
    # 존재 코드
    r = c.get("/api/taerini_stock?code=247540").json()
    assert r["found"] is True and r["stock"]["tp"]["dir"] == "하향"
    # 미존재 코드
    r = c.get("/api/taerini_stock?code=000000").json()
    assert r["found"] is False
    # 빈 코드
    assert c.get("/api/taerini_stock?code=").json()["found"] is False
