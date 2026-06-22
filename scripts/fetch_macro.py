"""STAGE1 매크로 게이트 + 미국 섹터 강세 산출.

VIX + 미국지수 + 간밤 이벤트(VIX급등·지수급락) → GO/경계/NO.
미국 섹터 ETF 등락 → 한국 섹터 강세 판단(STAGE2용).
가격원: yfinance. 자동(07:55) 또는 수동 실행.

실행: python scripts/fetch_macro.py
출력: output/signal/macro_today.json  (build_signal_snapshot이 읽음)
"""
import json
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
OUT = ROOT / "output" / "signal" / "macro_today.json"

INDEX = {"^GSPC": "S&P500", "^IXIC": "나스닥"}

# 한국 섹터(위키 L5_섹터 폴더 + sector_map.json 기준) → 그 섹터의 미국 대장종목 2~3개.
# 미국 대장주 등락으로 "그 섹터가 미국에서 강한가"를 본다(미장이 한국을 선행).
# 키는 종목 태깅값(sector_map.json)과 위키 폴더명 둘 다 커버(별칭 포함).
KOR_SECTOR_US_LEADERS = {
    "반도체":     ["NVDA", "MU", "AVGO"],   # HBM/메모리·AI반도체 = 삼성·하닉 선행
    "바이오":     ["LLY", "NVO", "VRTX"],
    "이차전지":   ["TSLA", "ALB"],          # EV수요·리튬
    "2차전지ESS": ["TSLA", "ALB"],          # 위키 폴더 별칭
    "로봇":       ["ISRG", "NVDA"],         # 수술로봇·피지컬AI
    "자동차":     ["TSLA", "GM"],
    "화장품":     ["EL", "ELF"],            # 코스메틱
    "미용":       ["ABBV", "ALGN"],         # 보톡스·에스테틱
    "전력":       ["GEV", "ETN", "VRT"],    # 전력인프라·변압기·데이터센터 전력
    "전력기기":   ["GEV", "ETN", "VRT"],    # 위키 폴더 별칭
    "원전":       ["CEG", "VST", "SMR"],
    "신재생":     ["FSLR", "ENPH", "NEE"],  # 태양광·재생에너지
    "방산":       ["LMT", "RTX", "NOC"],
    "우주":       ["RKLB"],                 # 로켓랩 (스페이스X는 비상장→불가)
    "AI소프트웨어": ["PLTR", "MSFT", "GOOGL"],
    "통신":       ["GLW", "LITE", "COHR"],  # 코닝·루멘텀·코히런트 (광부품·AI데이터센터)
    # 미국 대장주 없음/스킵: 테마이벤트·소비내수(국내) / 삭제: 엔터·철강·조선·LNG
}


_CHG_CACHE = {}


def _chg(tk):
    """(종가, 전일대비%, 날짜). 실패 시 (None,None,None). 같은 티커는 1회만 fetch."""
    if tk in _CHG_CACHE:
        return _CHG_CACHE[tk]
    import yfinance as yf
    try:
        h = yf.Ticker(tk).history(period="7d")
        if len(h) < 2:
            res = (None, None, None)
        else:
            last, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
            res = (round(last, 2), round((last - prev) / prev * 100, 2), str(h.index[-1].date()))
    except Exception:
        res = (None, None, None)
    _CHG_CACHE[tk] = res
    return res


def fetch():
    vix, vix_chg, vdate = _chg("^VIX")
    idx = {}
    for tk, nm in INDEX.items():
        _, chg, _ = _chg(tk)
        idx[nm] = chg
    vals = [v for v in idx.values() if v is not None]
    mkt = round(sum(vals) / len(vals), 2) if vals else None

    # 한국 섹터별: 미국 대장주 2~3개 등락 → 평균 = 그 섹터의 미국 강세도
    sectors = {}
    for kor_sec, leaders in KOR_SECTOR_US_LEADERS.items():
        rows = []
        for tk in leaders:
            _, chg, _ = _chg(tk)
            if chg is not None:
                rows.append({"ticker": tk, "chg": chg})
        if rows:
            avg = round(sum(r["chg"] for r in rows) / len(rows), 2)
            sectors[kor_sec] = {"avg": avg, "leaders": rows}
    return {"vix": vix, "vix_chg": vix_chg, "market": mkt,
            "us_sectors": sectors, "data_date": vdate}


def verdict(m):
    """GO / CAUTION / NO + 근거. VIX·미장·간밤이벤트 3축."""
    vix, vix_chg, mkt = m["vix"], m["vix_chg"], m["market"]
    reasons = []
    # 미장
    reasons.append({"label": "미장", "ok": mkt is not None and mkt >= 0.3,
                    "detail": (f"S&P·나스닥 평균 {mkt:+.2f}%" if mkt is not None else "데이터없음")})
    # VIX (18 미만 + 급등 아님)
    vix_ok = vix is not None and vix < 18 and (vix_chg is None or vix_chg < 15)
    reasons.append({"label": "VIX", "ok": vix_ok,
                    "detail": (f"{vix:.1f} ({vix_chg:+.1f}%)" if vix is not None else "데이터없음")})
    # 간밤 이벤트 = VIX 급등 또는 지수 급락 (불확실성 이벤트의 정량 신호)
    event = ((vix is not None and ((vix_chg or 0) >= 20 or vix >= 25))
             or (mkt is not None and mkt <= -1.5))
    reasons.append({"label": "간밤이벤트", "ok": not event,
                    "detail": ("불확실성 급등 감지(VIX/지수)" if event else "특이 이벤트 없음")})
    # 종합 판정
    if event or (mkt is not None and mkt <= -1.5) or (vix is not None and vix >= 25):
        v = "NO"
    elif (mkt is not None and mkt >= 0.3) and vix_ok:
        v = "GO"
    else:
        v = "CAUTION"
    return v, reasons


def strong_us_sectors(m, threshold=0.5):
    """미국 대장주 평균이 threshold% 이상인 한국 섹터, 강한 순."""
    items = [(nm, info["avg"]) for nm, info in m["us_sectors"].items()
             if info.get("avg") is not None and info["avg"] >= threshold]
    items.sort(key=lambda x: x[1], reverse=True)
    return [nm for nm, _ in items]


def main():
    m = fetch()
    v, reasons = verdict(m)
    out = {
        "verdict": v, "reasons": reasons,
        "market": m["market"], "vix": m["vix"], "vix_chg": m["vix_chg"],
        "us_sectors": m["us_sectors"],
        "us_strong_sectors": strong_us_sectors(m),
        "data_date": m["data_date"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    mk = f"{m['market']:+.2f}%" if m["market"] is not None else "?"
    print(f"매크로: {v} | 미장 {mk} | VIX {m['vix']} | 미국강세섹터 {out['us_strong_sectors']}")
    return out


if __name__ == "__main__":
    main()
