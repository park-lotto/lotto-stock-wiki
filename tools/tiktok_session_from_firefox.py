# -*- coding: utf-8 -*-
"""파이어폭스에 로그인된 틱톡 쿠키 → Playwright storage_state (2026-09-08).

■ 왜 이 방법인가 (실측)
Playwright 창으로 직접 로그인하려 했더니 **QR·전화번호·카카오 전부 막혔다**
(카톡은 폰에서 인증했는데 PC 화면이 안 넘어감). 자동화 브라우저가 탐지된 것으로
보인다. 과거 도우인도 같은 벽이었다(+82 SMS 거부, handoff/렌즈CN통합.md).

우리에겐 이미 검증된 우회가 있다 — **파이어폭스 쿠키**다. 유튜브 릴레이가 그렇게
돌고 있다(tools/yt_relay_start.bat: --cookies-from-browser firefox).
★크롬은 안 된다: App-Bound Encryption 때문에 브라우저를 닫아도 못 뽑는다(실측).

■ 왜 yt-dlp를 안 쓰나 (2026-09-08 실측)
처음엔 `yt-dlp --cookies-from-browser firefox`로 뽑으려 했는데 **180초 타임아웃**이
났다. yt-dlp는 쿠키를 뽑은 뒤 URL을 실제로 조회하려 들고, 틱톡이 그걸 붙잡는다.
우리가 필요한 건 쿠키뿐이라 네트워크를 탈 이유가 없다 → cookies.sqlite를 직접 읽는다.
파이어폭스 쿠키는 크롬과 달리 **암호화가 없어** 그냥 읽힌다.

■ 쓰는 법
  1) 파이어폭스로 https://www.tiktok.com 에 로그인해 둔다(평소 하던 대로).
  2) python tools/tiktok_session_from_firefox.py
     ★파이어폭스를 켜 둔 채로도 된다 — DB를 복사해서 읽는다(잠금 회피).
  3) out/tiktok_session.json 이 나온다.
"""
import json
import os
import pathlib
import shutil
import sqlite3
import tempfile

OUT = pathlib.Path(__file__).resolve().parent.parent / "out" / "tiktok_session.json"


def _profile_dirs():
    """파이어폭스 프로필 폴더들 — 최근에 쓴 것부터. 프로필이 여러 개일 수 있다
    (실측: 이 PC에 3개). 어디에 로그인했는지 모르니 전부 뒤진다."""
    root = pathlib.Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    if not root.is_dir():
        return []
    dirs = [d for d in root.iterdir() if (d / "cookies.sqlite").exists()]
    return sorted(dirs, key=lambda d: (d / "cookies.sqlite").stat().st_mtime, reverse=True)


def _expires_sec(expiry):
    """파이어폭스 expiry → Playwright storage_state의 expires(초).

    ★2026-09-08 실측 함정: 이 PC의 moz_cookies.expiry는 **밀리초**로 들어 있었다
      (1788837683853 = 그대로 초로 읽으면 서기 58,000년). 그대로 넘겼더니
      Playwright가 컨텍스트 생성 자체를 거부했다:
        "Cookie should have a valid expires, only -1 or a positive number ..."
      그런데 pw_tiktok은 예외를 통째로 삼켜(except Exception: return []) 화면엔
      그냥 '0건'으로 보였다 — 세션을 넣어도 왜 안 되는지 알 수 없는 모양이다.

    파이어폭스 버전·경로에 따라 초로 들어오는 경우도 있으므로 **값의 크기로**
    판별한다(2^31 ≈ 2038년을 넘으면 밀리초로 본다). 세션 쿠키(0/None)는 -1.
    """
    try:
        v = int(expiry or 0)
    except (TypeError, ValueError):
        return -1
    if v <= 0:
        return -1
    if v > 2 ** 31:            # 2038년 넘는 초 = 사실은 밀리초다
        v //= 1000
    return v


def _read_cookies(profile):
    """cookies.sqlite에서 틱톡 쿠키를 읽는다.

    ★원본을 그대로 열지 않는다 — 파이어폭스가 켜져 있으면 잠겨 있어서
      'database is locked'가 난다. 임시폴더로 복사해 읽는다(WAL 포함)."""
    rows = []
    with tempfile.TemporaryDirectory() as td:
        dst = pathlib.Path(td) / "cookies.sqlite"
        shutil.copy2(profile / "cookies.sqlite", dst)
        for suffix in ("-wal", "-shm"):     # 최근 쓴 내용이 WAL에만 있을 수 있다
            src = profile / ("cookies.sqlite" + suffix)
            if src.exists():
                shutil.copy2(src, str(dst) + suffix)
        con = sqlite3.connect("file:%s?mode=ro" % dst.as_posix(), uri=True)
        try:
            cur = con.execute(
                "SELECT name, value, host, path, expiry, isSecure, isHttpOnly "
                "FROM moz_cookies WHERE host LIKE '%tiktok%'")
            for name, value, host, path, expiry, secure, http_only in cur:
                rows.append({
                    "name": name, "value": value,
                    "domain": host, "path": path or "/",
                    "expires": _expires_sec(expiry),
                    "httpOnly": bool(http_only),
                    "secure": bool(secure),
                    "sameSite": "Lax",
                })
        finally:
            con.close()
    return rows


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    profiles = _profile_dirs()
    if not profiles:
        print("[실패] 파이어폭스 프로필(cookies.sqlite)을 못 찾았다.", flush=True)
        return 1

    best, best_rows = None, []
    for p in profiles:
        try:
            rows = _read_cookies(p)
        except Exception as e:      # noqa: BLE001 — 프로필 하나가 깨져도 나머지를 본다
            print("  (건너뜀) %s: %r" % (p.name, e), flush=True)
            continue
        names = {c["name"] for c in rows}
        print("  프로필 %-28s 틱톡쿠키 %3d개%s"
              % (p.name, len(rows), "  <= sessionid 있음" if "sessionid" in names else ""),
              flush=True)
        if "sessionid" in names and len(rows) > len(best_rows):
            best, best_rows = p, rows

    if not best:
        print("[실패] 로그인된 프로필이 없다(sessionid 없음).", flush=True)
        print("   파이어폭스로 https://www.tiktok.com 에 로그인한 뒤 다시 실행하세요.",
              flush=True)
        return 2

    OUT.write_text(json.dumps({"cookies": best_rows, "origins": []},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("[OK] 저장: %s" % OUT, flush=True)
    print("   프로필 %s · 틱톡 쿠키 %d개 · sessionid 있음" % (best.name, len(best_rows)),
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
