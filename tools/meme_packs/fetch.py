"""밈 팩 다운로드 — 카탈로그(2026-09-13)의 '밈·짤' 분류 10팩을 받는다.

★09-13 실측 교훈을 그대로 지킨다:
  - 구글드라이브는 연속 20팩쯤에서 "접근 과다"로 막힌다 → 팩 사이 SLEEP 초 대기
  - 이미 받은 팩(미디어 파일이 1개 이상 있는 폴더)은 건너뛴다
  - 폴더만 있고 미디어 0개면 = 지난번 차단으로 실패한 것 → 다시 받는다
★네이버 카페·블로그는 로그인이 필요해 자동 수집 불가 → 건너뛰고 목록에만 남긴다.
★LICENSE_NOTE.txt 를 팩마다 쓴다(출처 영상·채널·설명란 문구 원문). 없으면 그 팩은 쓰지 않는다.

쓰는 법:
  python tools/meme_packs/fetch.py <카탈로그json> <저장폴더>
  python tools/meme_packs/fetch.py <카탈로그json> <저장폴더> --only drive   # 호스트 한정
"""
import json
import os
import re
import subprocess
import sys
import time

MEDIA = (".mp4", ".mov", ".gif", ".webm", ".png", ".zip", ".rar", ".7z")
SLEEP = 12          # 팩 사이 대기(초). 09-13: 간격 없이 돌려 20팩에서 차단됨
TIMEOUT = 600       # 팩당 상한


def media_count(d):
    n = 0
    for root, _, files in os.walk(d):
        n += sum(1 for f in files if f.lower().endswith(MEDIA))
    return n


def host_of(url):
    for h in ("drive.google", "payhip", "mediafire", "bit.ly", "cafe.naver",
              "blog.naver", "mega.nz", "dropbox"):
        if h in url:
            return h
    return "기타"


def write_note(d, r):
    lines = [f"영상: {r['url']}", f"제목: {r['title']}", f"채널: {r['channel']}",
             f"조회수: {r['views']}",
             f"분류: {r['category']} / 형식: {', '.join(r.get('formats') or [])}",
             f"라이선스(설명란 규칙 분류): {r['license']}",
             f"링크: {', '.join(r.get('links') or [])}",
             "", "설명란 라이선스 문구:"] + (r.get("lic_lines") or [])
    with open(os.path.join(d, "LICENSE_NOTE.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def gdown(url, dest):
    """구글드라이브 — 폴더는 --folder, 파일은 그냥. 쿠키 안 쓴다(09-13과 동일)."""
    cmd = [sys.executable, "-m", "gdown", "--no-cookies", "-O", dest]
    if "/folders/" in url:
        cmd = [sys.executable, "-m", "gdown", "--no-cookies", "--folder", "-O", dest, url]
    else:
        m = re.search(r"/d/([\w-]{20,})", url) or re.search(r"id=([\w-]{20,})", url)
        if not m:
            return False, "드라이브 id를 못 찾음"
        cmd = [sys.executable, "-m", "gdown", "--no-cookies", "-O",
               os.path.join(dest, f"{m.group(1)}.bin"), m.group(1)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, "시간초과"
    tail = ((p.stderr or "") + (p.stdout or ""))[-300:].replace("\n", " ")
    return p.returncode == 0, tail


def direct(url, dest):
    """mediafire·bit.ly 등 — 페이지라서 직링이 아니면 실패한다(수동 표시)."""
    out = os.path.join(dest, os.path.basename(url.split("?")[0]) or "download.bin")
    cmd = ["curl", "-sL", "--max-time", str(TIMEOUT), "-o", out, url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT + 30)
    except subprocess.TimeoutExpired:
        return False, "시간초과"
    if p.returncode != 0:
        return False, "curl 실패"
    # HTML 페이지를 받아온 경우(직링 아님) 걸러낸다
    try:
        with open(out, "rb") as fh:
            head = fh.read(400).lower()
        if b"<html" in head or b"<!doctype" in head:
            os.remove(out)
            return False, "직링 아님(HTML 페이지) — 수동 필요"
    except OSError:
        pass
    return True, f"받음 {os.path.getsize(out)}B" if os.path.exists(out) else (False, "파일 없음")


def main():
    cat_path, dest_root = sys.argv[1], sys.argv[2]
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    data = json.load(open(cat_path, encoding="utf-8"))
    items = data if isinstance(data, list) else (data.get("packs") or data.get("items") or [])
    memes = [x for x in items if "밈" in str(x.get("category", ""))]
    print(f"카탈로그 {len(items)}건 중 밈 분류 {len(memes)}팩", flush=True)

    report = []
    for i, r in enumerate(memes, 1):
        safe = re.sub(r"[^\w가-힣]+", "_", (r.get("channel") or "")[:20]).strip("_")
        d = os.path.join(dest_root, f"{r['id']}_{safe}")
        links = r.get("links") or []
        hosts = sorted({host_of(u) for u in links})
        os.makedirs(d, exist_ok=True)
        write_note(d, r)

        have = media_count(d)
        if have:
            print(f"[{i}/{len(memes)}] 건너뜀(이미 {have}개) {r['id']} {hosts}", flush=True)
            report.append({"id": r["id"], "hosts": hosts, "status": "이미있음",
                           "files": have, "license": r["license"]})
            continue

        if only and not any(only in h for h in hosts):
            print(f"[{i}/{len(memes)}] 건너뜀(--only {only}) {r['id']} {hosts}", flush=True)
            continue

        # 네이버는 로그인 벽 — 자동 불가. 목록에만 남긴다.
        if all(h in ("cafe.naver", "blog.naver") for h in hosts):
            print(f"[{i}/{len(memes)}] 수동필요(네이버 로그인) {r['id']}", flush=True)
            report.append({"id": r["id"], "hosts": hosts, "status": "수동필요(네이버)",
                           "files": 0, "license": r["license"]})
            continue

        print(f"[{i}/{len(memes)}] 받는다 {r['id']} {hosts} — {str(r['title'])[:45]}", flush=True)
        msgs = []
        for u in links:
            h = host_of(u)
            if h == "drive.google":
                ok, msg = gdown(u, d)
            elif h in ("mediafire", "bit.ly", "dropbox", "기타"):
                ok, msg = direct(u, d)
            else:                       # payhip = 결제/이메일 페이지
                ok, msg = False, f"{h} 페이지 — 수동 필요"
            msgs.append(f"{h}:{'OK' if ok else 'X'} {msg}"[:160])
            if media_count(d):
                break
        got = media_count(d)
        status = "받음" if got else "실패"
        print(f"      → {status} (미디어 {got}개) {msgs[:2]}", flush=True)
        report.append({"id": r["id"], "hosts": hosts, "status": status, "files": got,
                       "license": r["license"], "msgs": msgs})
        if i < len(memes):
            time.sleep(SLEEP)          # ★구글 차단 회피

    out = os.path.join(dest_root, "_fetch_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print()
    print("=== 결과 ===")
    for r in report:
        print(f"  {r['status']:14} 미디어{r['files']:4}개  {r['id']}  {r['license']}")
    print(f"리포트: {out}")


if __name__ == "__main__":
    main()
