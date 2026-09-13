"""카탈로그 중 상업 OK + 직접 사용 형식(MOV/PNG/음원)이고 구글드라이브 링크인 팩을 gdown으로 받는다.
저장: <dest>/<id>_<채널>/ + LICENSE_NOTE.txt(설명란 라이선스 문구·출처 영상)."""
import json, os, re, subprocess, sys, time

dest = sys.argv[1]
cat = json.load(open("catalog.json", encoding="utf-8"))
OK = ("상업OK·표기불요", "상업OK·출처표기", "저작권무료(주장)")
ANY_FORMAT = "--all-formats" in sys.argv   # 프리미어·AE 전용 팩도 받는다(폰트처럼 자산으로 보관)
INCLUDE_UNKNOWN = "--include-unknown" in sys.argv   # 라이선스 문구 없는 팩도 받는다(연구 후보, 사용 전 확인)
SLEEP = 10   # ★팩 사이 간격(초). 연속 20팩쯤에서 구글이 "접근 과다"로 막았다(2026-09-13 실측)
ONLY_RESOLVED = "--only-resolved" in sys.argv   # 블로그에서 뽑은 링크(resolved_links)가 있는 팩만
def drive_links(r):
    src = (r.get("resolved_links") or []) if ONLY_RESOLVED else (r["links"] + (r.get("resolved_links") or []))
    return [u for u in src if "drive.google" in u]
todo = [r for r in cat if (r["license"] in OK or (INCLUDE_UNKNOWN and r["license"] != "비상업만(상업은 구매/주의)"))
        and (ANY_FORMAT or r["direct_usable"]) and drive_links(r)]
todo.sort(key=lambda r: (0 if r["license"] in OK else 1, -(r["views"] or 0)))
print("download targets:", len(todo), flush=True)
log = []
for r in todo:
    safe = re.sub(r"[^\w가-힣]+", "_", (r["channel"] or "")[:20]).strip("_")
    d = os.path.join(dest, f"{r['id']}_{safe}")
    os.makedirs(d, exist_ok=True)
    note = [f"영상: {r['url']}", f"제목: {r['title']}", f"채널: {r['channel']}", f"조회수: {r['views']}",
            f"분류: {r['category']} / 형식: {', '.join(r['formats'])}", f"라이선스(설명란 규칙 분류): {r['license']}", "", "설명란 라이선스 문구:"] + r["lic_lines"]
    open(os.path.join(d, "LICENSE_NOTE.txt"), "w", encoding="utf-8").write("\n".join(note))
    if any(f.endswith((".mp3", ".wav", ".mov", ".png", ".mp4", ".zip")) for f in os.listdir(d)):
        log.append((r["id"], "skip(있음)")); continue
    ok = False
    for u in drive_links(r):
        u = u.rstrip("​​").split("?usp")[0]
        is_folder = "/folders/" in u
        cmd = [sys.executable, "-m", "gdown", "--no-cookies", "-O", d + os.sep] + (["--folder"] if is_folder else []) + [u]
        t = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        except subprocess.TimeoutExpired:   # ★대형 폴더 하나가 전체 실행을 죽이지 않게(2026-09-13 실사고)
            print(f"{r['id']} timeout 900s :: {r['title'][:40]}", flush=True)
            continue
        n = sum(len(fs) for _, _, fs in os.walk(d)) - 1
        print(f"{r['id']} {'folder' if is_folder else 'file'} rc={p.returncode} files={n} {int(time.time()-t)}s :: {r['title'][:40]}", flush=True)
        if p.returncode != 0:
            print("   ", (p.stderr or p.stdout)[-300:].replace("\n", " | "), flush=True)
        if n > 0:
            ok = True; break
    log.append((r["id"], "ok" if ok else "fail"))
    time.sleep(SLEEP)
json.dump(log, open(os.path.join(dest, "_download_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done", sum(1 for _, s in log if s == "ok"), "/", len(log))
