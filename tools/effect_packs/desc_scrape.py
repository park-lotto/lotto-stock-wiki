"""watch 페이지 HTML에서 shortDescription만 뽑는다(yt-dlp가 로그인 확인에 막힐 때 대체)."""
import json, re, subprocess, sys, time, concurrent.futures as cf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
_re = re.compile(r'"shortDescription":"((?:[^"\\]|\\.)*)"')


def fetch(vid):
    r = subprocess.run(["curl", "-sL", "-A", UA, "-H", "Accept-Language: ko", f"https://www.youtube.com/watch?v={vid}"],
                       capture_output=True, timeout=60)
    h = r.stdout.decode("utf-8", "ignore")
    m = _re.search(h)
    if not m:
        return vid, None
    return vid, json.loads('"' + m.group(1) + '"')


if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids == ["--test"]:
        print(fetch("YpMRud9Yasw")[1][:300].replace("\n", " | "))
        sys.exit()
    meta = json.load(open("cand_meta.json", encoding="utf-8"))
    todo = [d for d in meta if d.get("desc") is None]
    print("todo", len(todo))
    with cf.ThreadPoolExecutor(4) as ex:
        res = dict(ex.map(fetch, [d["id"] for d in todo]))
    url_re = re.compile(r"https?://[^\s\)\]>\"']+")
    lic_re = re.compile(r"상업|저작권|출처|개인[ ]?용|2차|재배포|CC|credit|크레딧|무단|판매 금지|유료|라이선스|license|자유롭게|commercial|attribution", re.I)
    link_re = re.compile(r"drive\.google|docs\.google|notion|dropbox|mega\.nz|naver\.me|blog\.naver|cafe\.naver|gumroad|linktr|bit\.ly|download|1drv|smartstore|payhip|github|tistory|mediafire", re.I)
    n = 0
    for d in todo:
        desc = res.get(d["id"])
        if desc is None:
            continue
        n += 1
        d["desc"] = desc
        d["links"] = [u for u in url_re.findall(desc) if link_re.search(u)]
        d["lic_lines"] = [ln.strip() for ln in desc.splitlines() if lic_re.search(ln)][:6]
    json.dump(meta, open("cand_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("filled", n, "with links", sum(1 for d in todo if d.get("links")))
