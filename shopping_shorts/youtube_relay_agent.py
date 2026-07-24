"""유튜브 로컬 릴레이 에이전트 — 사장님 PC에서 상시 실행(2026-07-24).

왜: 서버(AWS 데이터센터 IP)는 유튜브에 "봇 확인" 차단을 당해 yt-dlp가 통째로 막힌다.
주거용 IP(집/사무실 PC)는 같은 URL을 쿠키 없이도 받는다(memory youtube-shorts-datacenter-block).
그래서 서버는 유튜브 URL을 yt_relay 큐에 넣고, 이 에이전트가 큐를 폴링해 **PC의 주거용 IP로**
다운로드한 뒤 서버에 업로드한다. 크롤봇 client.py와 같은 HTTP 폴링 패턴.

실행(PC):
    set YT_RELAY_KEY=<서버와 동일한 키>
    python -m shopping_shorts.youtube_relay_agent
  또는 서버가 다르면:
    set YT_RELAY_SERVER=https://shoppingshorts.duckdns.org
    set YT_RELAY_KEY=...
    python -m shopping_shorts.youtube_relay_agent

서버는 YT_RELAY_ENABLED=1 + 같은 YT_RELAY_KEY 를 /etc/shopping-shorts.env 에 둔다.
에이전트 PC에서는 YT_RELAY_ENABLED 를 켜지 마라 — 켜면 download_any가 다시 릴레이로 돌아
무한루프가 된다(에이전트는 _download_ytdlp를 직접 부른다)."""
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

import requests

from shopping_shorts.media_download import _download_ytdlp

SERVER = os.getenv("YT_RELAY_SERVER", "https://shoppingshorts.duckdns.org").rstrip("/")
KEY = os.getenv("YT_RELAY_KEY", "")
POLL_INTERVAL = int(os.getenv("YT_RELAY_POLL_INTERVAL", "5"))   # 큐 빌 때 대기(초)


def _next_job():
    """서버에서 대기 중인 요청 1건. 없으면 None. 네트워크 오류도 None(다음 폴링에 재시도)."""
    try:
        r = requests.get(f"{SERVER}/api/yt_relay/next", params={"key": KEY}, timeout=30)
        if r.status_code == 403:
            print("[relay] 인증 실패 — YT_RELAY_KEY가 서버와 다릅니다.", flush=True)
            return None
        return (r.json() or {}).get("job")
    except Exception as e:
        print(f"[relay] next 폴링 실패(재시도): {e}", flush=True)
        return None


def _deliver(req_id, file_path=None, error=None):
    """결과 회신 — 성공이면 mp4 업로드, 실패면 error 문자열."""
    data = {"key": KEY}
    files = None
    fh = None
    try:
        if file_path:
            fh = open(file_path, "rb")
            files = {"file": (Path(file_path).name, fh, "video/mp4")}
        else:
            data["error"] = (error or "알 수 없음")[:500]
        r = requests.post(f"{SERVER}/api/yt_relay/deliver/{req_id}", data=data, files=files, timeout=180)
        print(f"[relay] deliver {req_id} → {r.status_code} {r.text[:120]}", flush=True)
    except Exception as e:
        print(f"[relay] deliver 실패 {req_id}: {e}", flush=True)
    finally:
        if fh:
            fh.close()


def _handle(job):
    req_id, url = job["req_id"], job["url"]
    print(f"[relay] 처리 시작 {req_id}: {url}", flush=True)
    with tempfile.TemporaryDirectory() as td:
        try:
            path, _ = _download_ytdlp(url, td)      # 주거용 IP로 실다운로드
            print(f"[relay] 다운로드 완료 {req_id}: {path}", flush=True)
            _deliver(req_id, file_path=path)
        except Exception as e:
            print(f"[relay] 다운로드 실패 {req_id}: {e}", flush=True)
            _deliver(req_id, error=str(e))


def main():
    # 윈도우 콘솔 기본 코드페이지(cp949)는 '—'·이모지 등을 못 찍어 print에서 UnicodeEncodeError로
    # 죽는다(2026-07-24 실측). yt-dlp 에러 메시지에도 유니코드가 섞이므로 stdio를 utf-8로 강제한다.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if not KEY:
        print("YT_RELAY_KEY 환경변수가 없습니다. 서버와 같은 키를 설정하세요.", file=sys.stderr)
        sys.exit(1)
    print(f"[relay] 에이전트 시작 — 서버={SERVER}, 폴링={POLL_INTERVAL}s", flush=True)
    while True:
        try:
            job = _next_job()
            if job:
                _handle(job)
                continue          # 연속 처리(큐에 더 있을 수 있음)
        except Exception:
            traceback.print_exc()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
