"""블로그(네이버·티스토리) 배포 페이지를 열어 안에 있는 실제 다운로드 링크(구글드라이브·티스토리 첨부 등)를 뽑아
catalog.json 의 각 항목에 resolved_links 로 넣는다. 실측(2026-09-13):
  - 네이버 블로그는 PC 주소가 iframe 껍데기라 본문이 없다 → m.blog.naver.com 으로 바꿔 받으면 본문·링크가 나온다
  - 티스토리는 글 주소를 직접 받으면 본문이 나온다(루트 주소만 있는 건 글을 못 찾음 → manual)
  - 네이버 MYBOX(mybox.naver.com/share)·naver.me 는 API가 따로라 여기선 manual 표시만
"""
import json, re, subprocess, html, concurrent.futures as cf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
DL = re.compile(r'https?://(?:drive\.google\.com|docs\.google\.com/uc|blog\.kakaocdn\.net/dn/|t1\.daumcdn\.net/cfile/tistory|[a-z0-9.-]+\.tistory\.com/attachment|dropbox\.com|mega\.nz|1drv\.ms)[^\s"\'<>\)\]]+')
MANUAL = re.compile(r'https?://(?:mybox\.naver\.com|naver\.me|cafe\.naver\.com|docs\.google\.com/forms)[^\s"\'<>\)\]]+')


def fetch(u):
    try:
        r = subprocess.run(["curl", "-sL", "-A", UA, "-m", "40", u], capture_output=True, timeout=60)
        return html.unescape(r.stdout.decode("utf-8", "ignore"))
    except Exception:
        return ""


def blog_urls(r):
    out = []
    for u in r["links"]:
        u = u.rstrip("​").rstrip("/")
        if re.search(r"blog\.naver\.com/[^/]+/\d+", u):
            out.append(re.sub(r"https?://(m\.)?blog\.naver\.com", "https://m.blog.naver.com", u))
        elif re.search(r"tistory\.com/(\d+|entry/|m/)", u):
            out.append(u)
        elif re.search(r"tistory\.com/?$", u):
            out.append(None)   # 루트만 있음 → 글을 못 찾음
    return out


def resolve(r):
    res, manual, root_only = [], [], False
    for u in blog_urls(r):
        if u is None:
            root_only = True; continue
        h = fetch(u)
        res += [x.replace("&amp;", "&") for x in DL.findall(h)]
        manual += MANUAL.findall(h)
    # 유튜브 설명란에 있던 mybox/naver.me 도 manual 로
    manual += [u for u in r["links"] if MANUAL.search(u)]
    seen, uniq = set(), []
    for x in res:
        k = x.split("?")[0]
        if k not in seen:
            seen.add(k); uniq.append(x)
    return r["id"], uniq, sorted(set(manual)), root_only


if __name__ == "__main__":
    cat = json.load(open("catalog.json", encoding="utf-8"))
    todo = [r for r in cat if blog_urls(r) or any(MANUAL.search(u) for u in r["links"])]
    print("blog packs", len(todo), flush=True)
    with cf.ThreadPoolExecutor(6) as ex:
        results = {vid: (links, manual, root) for vid, links, manual, root in ex.map(resolve, todo)}
    n_ok = n_manual = n_root = 0
    for r in cat:
        if r["id"] in results:
            links, manual, root = results[r["id"]]
            r["resolved_links"] = links
            r["manual_links"] = manual
            r["blog_root_only"] = root
            n_ok += bool(links); n_manual += bool(manual and not links); n_root += root
    json.dump(cat, open("catalog.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"resolved: 다운로드 링크 찾음 {n_ok} / 수동(mybox·naver.me·카페·폼) {n_manual} / 티스토리 루트만 {n_root}")
