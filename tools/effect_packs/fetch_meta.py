"""all.json 후보 중 팩 배포로 보이는 영상의 설명란을 yt-dlp(android client)로 받아 cand_meta.json에 합친다."""
import json, re, subprocess, concurrent.futures as cf, os, time

allr = json.load(open("all.json", encoding="utf-8"))
meta = json.load(open("cand_meta.json", encoding="utf-8")) if os.path.exists("cand_meta.json") else []
have = {d["id"]: d for d in meta}
kw = re.compile(r"배포|무료|free|템플릿|template|프리셋|preset|소스|pack|효과음|sound|sfx|mogrt|짤|스티커|sticker|전환|transition|공유|다운|download|overlay|alpha|알파|png|mov|asset", re.I)
todo = [d for d in allr if d["title"] and kw.search(d["title"]) and (d["views"] or 0) >= 1000
        and (d["id"] not in have or have[d["id"]].get("desc") is None)]
print("todo", len(todo), flush=True)
url_re = re.compile(r"https?://[^\s\)\]>\"']+")
lic_re = re.compile(r"상업|저작권|출처|개인[ ]?용|2차|재배포|CC|credit|크레딧|무단|판매 금지|유료|라이선스|license|자유롭게|commercial|attribution|royalty|copyright", re.I)
link_re = re.compile(r"drive\.google|docs\.google|notion|dropbox|mega\.nz|naver\.me|blog\.naver|cafe\.naver|gumroad|linktr|bit\.ly|download|1drv|smartstore|payhip|github|tistory|mediafire|terabox|patreon|ko-fi|buymeacoffee|gdrive|motionarray|mixkit|pixabay", re.I)

def fetch(d):
    for attempt in range(2):
        r = subprocess.run(["yt-dlp", "-j", "--no-warnings", "--skip-download", "--extractor-args", "youtube:player_client=android", d["url"]],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        try:
            m = json.loads(r.stdout.strip().splitlines()[-1]); break
        except Exception:
            m = None; time.sleep(3)
    if not m:
        return dict(d, desc=None)
    desc = m.get("description") or ""
    return dict(d, desc=desc, upload=m.get("upload_date"), likes=m.get("like_count"), views=m.get("view_count") or d["views"],
                links=[u for u in url_re.findall(desc) if link_re.search(u)],
                lic_lines=[ln.strip() for ln in desc.splitlines() if lic_re.search(ln)][:8])

done = 0
with cf.ThreadPoolExecutor(4) as ex:
    for row in ex.map(fetch, todo):
        have[row["id"]] = row; done += 1
        if done % 50 == 0:
            json.dump(list(have.values()), open("cand_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("progress", done, flush=True)
json.dump(list(have.values()), open("cand_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total meta", len(have), "with links", sum(1 for d in have.values() if d.get("links")), "desc missing", sum(1 for d in have.values() if d.get("desc") is None))
