"""choPD 소스 다운로드 — 카테고리를 골라서 받는다.

★기본은 라이선스가 깨끗한 것만 받는다(조PD 직접제작: 템플릿·영상소스).
  짤 30개는 **상업 사용 금지 명시**라 기본에서 제외한다(--include-blocked 로만).
  효과음·BGM은 출처 불명/유튜브 전용이라 '연구 후보'로만 받는다(--research).

★구글드라이브는 연속 접근 시 "many accesses"로 막힌다(2026-09-15 실측: 밈 팩 10개 중
  9개가 이 이유로 실패). 그래서 파일 사이 SLEEP 초 쉬고, 링크가 적은 것부터 받는다.

쓰는 법:
  python tools/meme_packs/chopd_fetch.py <카탈로그json> <저장폴더>              # 깨끗한 것만
  python tools/meme_packs/chopd_fetch.py <카탈로그json> <저장폴더> --research    # 효과음·BGM도
"""
import json
import os
import re
import subprocess
import sys
import time

SLEEP = 15
TIMEOUT = 900
# ★`.bin` 을 반드시 넣어라 — gdown 은 드라이브 파일을 우리가 준 이름(`<id>.bin`)으로
#   저장한다. 이걸 빠뜨려 14개를 **다 받았는데 전부 "실패 0개"로 보고**했다(2026-09-15).
#   받은 파일이 디스크에 있는데 리포트가 실패라고 하면 이 목록을 먼저 의심하라.
MEDIA = (".zip", ".rar", ".7z", ".mp4", ".mov", ".png", ".jpg", ".mp3", ".wav",
         ".gif", ".bin")

# 카테고리 → (받나?, 사용조건 메모)
CLEAN = {
    "템플릿": "조PD 직접제작(3D). 유튜브 사용 OK. ★재배포 금지 → 고객 제공용 불가",
    "영상소스": "조PD 직접제작. 유튜브 사용 OK. ★재배포 금지",
}
RESEARCH = {
    "효과음": "⚠️출처불명 — 조PD가 '수천개 받아 120개 엄선'한 재배포. 사용 전 원본 출처 확인 필요",
    "BGM": "⚠️유튜브 전용 — '유투브말고 다른곳/상업적 사용 절대 안됨, 재가공 배포 금지'(원문)",
}
BLOCKED = {
    "짤·밈": "⛔상업 사용 금지 명시 — '저작권은 원작자에게', '상업적으로 사용..자제바랍니다'(원문)",
}


def media_count(d):
    n = 0
    for root, _, files in os.walk(d):
        n += sum(1 for f in files if f.lower().endswith(MEDIA))
    return n


def drive_id(url):
    m = (re.search(r"/d/([\w-]{20,})", url) or re.search(r"[?&]id=([\w-]{20,})", url)
         or re.search(r"/folders/([\w-]{20,})", url))
    return m.group(1) if m else None


def gdown(url, dest):
    fid = drive_id(url)
    if not fid:
        return False, "드라이브 id 없음"
    if "/folders/" in url:
        cmd = [sys.executable, "-m", "gdown", "--no-cookies", "--folder", "-O", dest, fid]
    else:
        cmd = [sys.executable, "-m", "gdown", "--no-cookies", "-O",
               os.path.join(dest, f"{fid}.bin"), fid]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, "시간초과"
    tail = ((p.stderr or "") + (p.stdout or ""))[-200:].replace("\n", " ")
    return p.returncode == 0, tail


def main():
    cat_path, dest_root = sys.argv[1], sys.argv[2]
    research = "--research" in sys.argv
    blocked = "--include-blocked" in sys.argv

    rows = json.load(open(cat_path, encoding="utf-8"))
    plan = []
    for r in rows:
        c = r["category"]
        if c in CLEAN:
            plan.append((r, "깨끗", CLEAN[c]))
        elif c in RESEARCH and research:
            plan.append((r, "연구후보", RESEARCH[c]))
        elif c in BLOCKED and blocked:
            plan.append((r, "사용불가", BLOCKED[c]))
    print(f"대상 {len(plan)}편 (깨끗={sum(1 for x in plan if x[1]=='깨끗')} "
          f"연구후보={sum(1 for x in plan if x[1]=='연구후보')} "
          f"사용불가={sum(1 for x in plan if x[1]=='사용불가')})", flush=True)

    report = []
    for i, (r, grade, memo) in enumerate(plan, 1):
        safe = re.sub(r"[^\w가-힣]+", "_", r["category"]).strip("_")
        d = os.path.join(dest_root, f"{safe}_{r['id']}")
        os.makedirs(d, exist_ok=True)
        # 라이선스 메모를 파일마다 남긴다 — 없으면 그 자산은 쓰지 않는다는 규칙 때문
        with open(os.path.join(d, "LICENSE_NOTE.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join([
                f"영상: {r['url']}", f"제목: {r['title']}", f"카테고리: {r['category']}",
                f"조회수: {r.get('views')}", f"업로드: {r.get('upload')}",
                f"우리 판정: {grade}", f"사용조건: {memo}", "",
                "설명란 라이선스 문구(원문):"] + (r.get("lic_lines") or [])) + "\n")

        have = media_count(d)
        if have:
            print(f"[{i}/{len(plan)}] 건너뜀(이미 {have}개) {r['category']} {r['id']}", flush=True)
            report.append({"id": r["id"], "cat": r["category"], "grade": grade,
                           "status": "이미있음", "files": have})
            continue

        links = [u for u in r["links"] if "drive.google" in u]
        if not links:
            print(f"[{i}/{len(plan)}] 링크없음 {r['category']} {r['id']} — {r['title'][:40]}",
                  flush=True)
            report.append({"id": r["id"], "cat": r["category"], "grade": grade,
                           "status": "링크없음", "files": 0})
            continue

        print(f"[{i}/{len(plan)}] {grade} 받는다 {r['category']} — {r['title'][:42]}", flush=True)
        msgs = []
        for u in links:
            ok, msg = gdown(u, d)
            msgs.append(f"{'OK' if ok else 'X'} {msg}"[:150])
            if media_count(d):
                break
            time.sleep(SLEEP)
        got = media_count(d)
        print(f"      → {'받음' if got else '실패'} (미디어 {got}개) {msgs[-1] if msgs else ''}",
              flush=True)
        report.append({"id": r["id"], "cat": r["category"], "grade": grade,
                       "status": "받음" if got else "실패", "files": got, "msgs": msgs})
        if i < len(plan):
            time.sleep(SLEEP)

    out = os.path.join(dest_root, "_chopd_fetch_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print()
    print("=== 결과 ===")
    for r in report:
        print(f"  {r['status']:8} {r['grade']:6} 미디어{r['files']:3}개  {r['cat']:8} {r['id']}")
    print(f"리포트: {out}")


if __name__ == "__main__":
    main()
