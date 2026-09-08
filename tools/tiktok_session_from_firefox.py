# -*- coding: utf-8 -*-
"""파이어폭스에 로그인된 틱톡 쿠키 → Playwright storage_state (2026-09-08).

■ 왜 이 방법인가 (실측)
Playwright 창으로 직접 로그인하려 했더니 **QR·전화번호·카카오 전부 막혔다**
(카톡은 폰에서 인증했는데 PC 화면이 안 넘어감). 자동화 브라우저가 탐지된 것으로
보인다. 과거 도우인도 같은 벽이었다(+82 SMS 거부, handoff/렌즈CN통합.md).

우리에겐 이미 검증된 우회가 있다 — **파이어폭스 쿠키 추출**이다. 유튜브 릴레이가
그렇게 돌고 있다(tools/yt_relay_start.bat: --cookies-from-browser firefox).
★크롬은 안 된다: App-Bound Encryption 때문에 브라우저를 닫아도 못 뽑는다(실측).
파이어폭스는 평범한 브라우저라 자동화 탐지가 없어 로그인 인증이 정상 작동한다.

■ 쓰는 법
  1) 파이어폭스로 https://www.tiktok.com 에 로그인해 둔다(평소 하던 대로).
  2) python tools/tiktok_session_from_firefox.py
  3) out/tiktok_session.json 이 나온다.

Netscape cookies.txt → storage_state 변환만 한다. 네트워크를 안 탄다.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

OUT = pathlib.Path(__file__).resolve().parent.parent / "out" / "tiktok_session.json"
# 쿠키만 필요하므로 아무 틱톡 페이지나 된다(다운로드는 --skip-download로 안 한다).
PROBE_URL = "https://www.tiktok.com/@tiktok"


def _dump_cookies(txt_path):
    """yt-dlp에게 파이어폭스 쿠키를 Netscape 형식으로 뱉게 한다."""
    cmd = [sys.executable, "-m", "yt_dlp",
           "--cookies-from-browser", "firefox",
           "--cookies", str(txt_path),
           "--skip-download", "--quiet", "--no-warnings",
           PROBE_URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    # yt-dlp가 영상 추출에 실패해도 쿠키 파일은 이미 쓰였을 수 있다 — 파일로 판정한다.
    return r


def _parse_netscape(txt_path):
    """Netscape cookies.txt → Playwright cookie dict 목록 (틱톡 도메인만)."""
    out = []
    for line in txt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, path, secure, expires, name, value = parts[:7]
        if "tiktok" not in domain:
            continue
        try:
            exp = int(expires)
        except ValueError:
            exp = -1
        out.append({
            "name": name, "value": value, "domain": domain, "path": path or "/",
            "expires": exp if exp > 0 else -1,
            "httpOnly": False,
            "secure": secure.upper() == "TRUE",
            "sameSite": "Lax",
        })
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        txt = pathlib.Path(td) / "tiktok_cookies.txt"
        r = _dump_cookies(txt)
        if not txt.exists():
            print("❌ 쿠키를 못 뽑았다.", flush=True)
            print("   파이어폭스를 **완전히 종료**한 뒤 다시 실행해 보세요"
                  "(열려 있으면 DB가 잠깁니다).", flush=True)
            if r.stderr:
                print("   yt-dlp: " + r.stderr.strip().splitlines()[-1][:200], flush=True)
            return 1
        cookies = _parse_netscape(txt)

    names = {c["name"] for c in cookies}
    if "sessionid" not in names:
        print("❌ 틱톡 쿠키는 %d개 나왔지만 **sessionid가 없다** — 로그인 상태가 아니다."
              % len(cookies), flush=True)
        print("   파이어폭스로 https://www.tiktok.com 에 로그인한 뒤 다시 실행하세요.",
              flush=True)
        return 2

    OUT.write_text(json.dumps({"cookies": cookies, "origins": []},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("✅ 저장: %s" % OUT, flush=True)
    print("   틱톡 쿠키 %d개 · sessionid 있음" % len(cookies), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
