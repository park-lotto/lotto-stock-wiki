"""카탈로그 중 상업 OK + 직접 사용 형식(MOV/PNG/음원)이고 구글드라이브 링크인 팩을 gdown으로 받는다.
저장: <dest>/<id>_<채널>/ + LICENSE_NOTE.txt(설명란 라이선스 문구·출처 영상)."""
import json, os, re, subprocess, sys, time

dest = sys.argv[1]
cat = json.load(open("catalog.json", encoding="utf-8"))
OK = ("상업OK·표기불요", "상업OK·출처표기", "저작권무료(주장)")
ANY_FORMAT = "--all-formats" in sys.argv   # 프리미어·AE 전용 팩도 받는다(폰트처럼 자산으로 보관)
todo = [r for r in cat if r["license"] in OK and (ANY_FORMAT or r["direct_usable"])
        and any("drive.google" in u for u in r["links"])]
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
    for u in [u for u in r["links"] if "drive.google" in u]:
        u = u.rstrip("​​").split("?usp")[0]
        is_folder = "/folders/" in u
        cmd = [sys.executable, "-m", "gdown", "--no-cookies", "-O", d + os.sep] + (["--folder"] if is_folder else []) + [u]
        t = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
        n = sum(len(fs) for _, _, fs in os.walk(d)) - 1
        print(f"{r['id']} {'folder' if is_folder else 'file'} rc={p.returncode} files={n} {int(time.time()-t)}s :: {r['title'][:40]}", flush=True)
        if p.returncode != 0:
            print("   ", (p.stderr or p.stdout)[-300:].replace("\n", " | "), flush=True)
        if n > 0:
            ok = True; break
    log.append((r["id"], "ok" if ok else "fail"))
json.dump(log, open(os.path.join(dest, "_download_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done", sum(1 for _, s in log if s == "ok"), "/", len(log))
