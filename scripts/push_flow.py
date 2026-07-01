"""로컬(키움 보유 PC)의 market_flow를 stockbrain1 서버로 전송.
서버는 키움이 없어 이 데이터(지수 15분봉·투자자·프로그램·거래대금)를 대신 서빙한다.
사용:  python scripts/push_flow.py           # 120초마다 반복 전송 (장중 켜두기)
       python scripts/push_flow.py --once    # 1회만
"""
import sys, time, json, urllib.request
from pathlib import Path

LOCAL  = "http://127.0.0.1:8090/api/market_flow"
SERVER = "https://stockbrain1.duckdns.org/api/push_market_flow"
TOKEN  = (Path(__file__).resolve().parent.parent / "pipeline" / "push_token.txt").read_text(encoding="utf-8").strip()
INTERVAL = 120

def push_once():
    with urllib.request.urlopen(LOCAL, timeout=25) as r:
        data = r.read()
    req = urllib.request.Request(SERVER, data=data, method="POST",
        headers={"Content-Type": "application/json", "X-Push-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r), len(data)

if __name__ == "__main__":
    once = "--once" in sys.argv
    while True:
        try:
            res, sz = push_once()
            print(time.strftime("%H:%M:%S"), f"pushed {sz}B", res)
        except Exception as e:
            print(time.strftime("%H:%M:%S"), "ERR", e)
        if once:
            break
        time.sleep(INTERVAL)
