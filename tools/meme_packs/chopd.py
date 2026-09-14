"""choPD 채널(@chopdtv)이 배포하는 소스 전량 수집 — 설명란에서 링크·라이선스를 뽑는다.

★사장님 지시(2026-09-15): "위 채널에서 제공되는 소스들 모아봐 / 효과음 템플릿 짤"
★이 채널이 좋은 이유: 17개 영상이 **전부 무료 소스 배포**이고, 상당수가 "조PD 직접제작
  무료배포"라 라이선스가 깨끗하다(제3자 영화 클립 재배포와 다르다).
★yt-dlp 설명란 대량조회는 150건쯤에서 로그인 벽에 막힌다 → player_client=android 로 우회
  (2026-09-13 실측, handoff/효과팩수집.md). 17건이라 안 걸리겠지만 같은 인자를 쓴다.

쓰는 법:
  python tools/meme_packs/chopd.py <저장폴더>          # 설명란·링크 수집만
"""
import json
import os
import re
import subprocess
import sys

CHANNEL = "https://www.youtube.com/@chopdtv/videos"
YDL = ["yt-dlp", "--no-warnings", "--extractor-args", "youtube:player_client=android"]

# 카테고리 판정 — 제목·설명으로 가른다. 우리가 필요한 순서대로 본다.
CATS = [
    ("짤·밈", r"짤|밈|meme"),
    ("효과음", r"효과음|sound effect|sfx"),
    ("템플릿", r"템플릿|template|구독|좋아요|알림|알람|subscribe"),
    ("BGM", r"bgm|background music|음악"),
    ("영상소스", r"영상 ?소스|뷰파인더|이미지"),
]
LIC_PAT = re.compile(
    r"(저작권|무료|free|copyright|출처|표기|상업|배포|직접 ?제작|credit|license|"
    r"마음껏|가져다|사용하세요|no copyright)", re.I)
URL_PAT = re.compile(r"https?://[^\s<>\"')\]]+")


def run(args, timeout=180):
    p = subprocess.run(YDL + args, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.stdout or ""


def categorize(title, desc):
    t = f"{title}\n{desc[:400]}".lower()
    for name, pat in CATS:
        if re.search(pat, t, re.I):
            return name
    return "기타"


def main():
    dest = sys.argv[1]
    os.makedirs(dest, exist_ok=True)

    ids = []
    for line in run(["--flat-playlist", "--print", "%(id)s\t%(title)s", CHANNEL]).splitlines():
        if "\t" in line:
            vid, title = line.split("\t", 1)
            ids.append((vid.strip(), title.strip()))
    print(f"채널 영상 {len(ids)}개", flush=True)

    rows = []
    for i, (vid, title) in enumerate(ids, 1):
        j = run(["-J", f"https://www.youtube.com/watch?v={vid}"])
        try:
            meta = json.loads(j)
        except json.JSONDecodeError:
            print(f"[{i}/{len(ids)}] 메타 실패 {vid}", flush=True)
            continue
        desc = meta.get("description") or ""
        urls = [u.rstrip(".,)") for u in URL_PAT.findall(desc)]
        # 자기 채널·구독 링크는 소스가 아니다
        urls = [u for u in urls if not re.search(r"youtube\.com/(channel|@|c/|user)|youtu\.be", u)]
        lic = [ln.strip() for ln in desc.splitlines() if LIC_PAT.search(ln)]
        cat = categorize(title, desc)
        rows.append({
            "id": vid, "title": title, "url": f"https://www.youtube.com/watch?v={vid}",
            "category": cat, "views": meta.get("view_count"),
            "upload": meta.get("upload_date"), "duration": meta.get("duration"),
            "links": urls, "lic_lines": lic[:14], "desc": desc,
        })
        print(f"[{i}/{len(ids)}] {cat:8} 링크{len(urls):2}개 라이선스문구{len(lic):2}줄  {title[:44]}",
              flush=True)

    out = os.path.join(dest, "chopd_catalog.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)

    print()
    print("=== 카테고리별 ===")
    for name, _ in CATS + [("기타", "")]:
        g = [r for r in rows if r["category"] == name]
        if g:
            n = sum(len(r["links"]) for r in g)
            print(f"  {name:8} 영상 {len(g):2}개 · 링크 {n:2}개")
    print(f"\n카탈로그: {out}")


if __name__ == "__main__":
    main()
