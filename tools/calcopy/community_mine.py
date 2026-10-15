# -*- coding: utf-8 -*-
"""커뮤니티 반응 좋은 글에서 썰쇼핑 소재 찾기 (2026-10-07 사장님: "창조하지 말고 커뮤니티에서 반응 좋았던 게시물로 주제를 찾자").

수집 대상은 robots.txt 가 허용한 곳만 — 보배드림(전체 허용). ★디시·에펨코리아·클리앙·인스티즈·네이트판은 robots 로 Claude 계열 에이전트를
  막고 있어 수집하지 않는다(2026-10-07 확인). 루리웹은 /search 만 막는데, 게시판 검색 파라미터가 제목 검색으로 동작하지 않아 이번엔 뺐다.

방법: 보배드림 '베스트' 게시판을 식품·제품 낱말로 제목 검색 → 제목·추천·조회·댓글·날짜 수집 → 반응 기준으로 거른다.
사용: PYTHONUTF8=1 py community_mine.py --out <json> [--pages 5] [--delay 1.2]
"""
import argparse, html, json, re, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
KEYWORDS = [
    # 식품
    "라면", "과자", "아이스크림", "음료", "커피", "맥주", "소주", "치킨", "피자", "햄버거", "빵", "소스", "김치", "편의점", "도시락", "젤리", "초콜릿", "우유", "생수",
    "맥도날드", "버거킹", "롯데리아", "스타벅스", "농심", "오뚜기", "삼양", "팔도", "빙그레", "롯데", "해태", "오리온", "CJ", "비비고",
    # 매장·유통
    "다이소", "코스트코", "이케아", "이마트", "쿠팡", "올리브영", "무인양품",
    # 제품
    "제품", "신제품", "출시", "단종", "리뉴얼", "가성비", "발명", "특허", "정체", "비밀", "원래", "몰랐", "비하인드", "역사", "유래", "근황", "레시피",
    "칫솔", "세제", "샴푸", "마스크", "선크림", "텀블러", "에어프라이어", "전자레인지", "냉장고", "청소기", "다리미", "우산",
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "ignore")


def _num(t):
    t = re.sub(r"[^\d]", "", t or "")
    return int(t) if t else 0


def parse_bobae(page_html):
    out = []
    for r in re.findall(r"<tr itemscope.*?</tr>", page_html, re.S):
        a = re.search(r'<a[^>]+href="(/view\?code=best[^"]+)"[^>]*class="bsubject"[^>]*>(.*?)</a>', r, re.S) or \
            re.search(r'class="bsubject"[^>]*href="(/view\?code=best[^"]+)"[^>]*>(.*?)</a>', r, re.S)
        if not a:
            continue
        cells = {k: re.sub("<[^>]+>", "", v) for k, v in re.findall(r'<td class="(date|recomm|count)"[^>]*>(.*?)</td>', r, re.S)}
        rep = re.search(r'class="totreply"[^>]*>\s*(\d+)', r) or re.search(r"\(\s*<[^>]*>?\s*(\d+)\s*<?[^)]*\)", r)
        cat = re.search(r'class="category"[^>]*>(.*?)</', r, re.S)
        out.append({"site": "보배드림", "url": "https://www.bobaedream.co.kr" + html.unescape(a.group(1)),
                    "title": re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", a.group(2)))).strip(),
                    "board": re.sub("<[^>]+>", "", cat.group(1)).strip() if cat else "",
                    "date": re.sub("<[^>]+>", "", cells.get("date", "")).strip(), "recomm": _num(cells.get("recomm")),
                    "views": _num(cells.get("count")), "replies": _num(rep.group(1)) if rep else 0})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--pages", type=int, default=5)
    ap.add_argument("--delay", type=float, default=1.2); ap.add_argument("--keywords", default="")
    a = ap.parse_args()
    kws = [k for k in a.keywords.split(",") if k] or KEYWORDS
    seen, rows = set(), []
    for k in kws:
        got = 0
        for p in range(1, a.pages + 1):
            url = "https://www.bobaedream.co.kr/list?code=best&s_select=Subject&s_key=%s&page=%d" % (urllib.parse.quote(k), p)
            try:
                items = parse_bobae(fetch(url))
            except Exception as e:      # noqa: BLE001 — 한 쪽 실패는 건너뛴다(개수는 아래 출력에 남는다)
                print("실패 %s p%d: %r" % (k, p, e)); items = []
            time.sleep(a.delay)
            new = [x for x in items if x["url"] not in seen]
            for x in new:
                seen.add(x["url"]); x["keyword"] = k; rows.append(x)
            got += len(new)
            if len(items) < 30:
                break
        print("%-8s %3d건 (누적 %d)" % (k, got, len(rows)), flush=True)
    json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("저장 %s — %d건" % (a.out, len(rows)))


if __name__ == "__main__":
    main()
