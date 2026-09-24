# -*- coding: utf-8 -*-
"""커뮤니티 글 → 대본 재료. 제목 + 본문 이미지에 적힌 글 + 댓글 반응.

왜 (사장님 2026-09-13): "제목과 사진의 내용과 댓글의 반응들을 토대로 하면 재밌는게 나올꺼야".

★기존 흐름을 갈아엎지 않는다 — **입구만 하나 더**한다:
    기사 URL   → fetch_article → 본문 글자 ┐
    텍스트 파일 → 그대로            ├→ 대본 → 이미지 → 음성 → 자막 → 영상
    커뮤니티 글 → 여기(fetch_post) ┘
  대본부터 뒤는 전부 같은 코드다.

왜 필요한가: 디시·커뮤니티 글은 **본문이 캡처 이미지**인 경우가 많다.
  실측 2026-09-13(최민식 급여 글): 본문에 글자가 없고 이미지 16장 + 댓글 102개였다.
  지금 파이프라인은 글자를 받아야 대본을 쓰므로 그대로는 못 만든다.
  제미니가 이미지를 읽으므로(검수와 같은 방식) 캡처에서 글을 뽑아 재료로 쓴다.
"""
import os
import re

import requests

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
       "Referer": "https://gall.dcinside.com/"}


def _strip(html):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"[ \t]+", " ", t).strip()


def fetch_post(url, *, timeout=20, max_images=12, max_comments=40):
    """커뮤니티 글 → {"title", "body", "images": [url…], "comments": [글…]}

    ★이미지는 **지연 로딩**이라 `src`만 보면 로딩 gif가 잡힌다 — `data-original`을 함께 본다
      (실측 2026-09-13: src로는 2개, data-original까지 보면 16개).
    """
    html = requests.get(url, headers=_UA, timeout=timeout).text

    m = re.search(r'<span class="title_subject">(.*?)</span>', html, re.S)
    title = _strip(m.group(1)) if m else ""

    # 본문 영역만 자른다 — 사이드바·추천글의 이미지가 섞이지 않게
    w = re.search(r'write_div"[^>]*>(.*?)<div class="appending_file', html, re.S) or \
        re.search(r'write_div"[^>]*>(.*)', html, re.S)
    area = w.group(1)[:60000] if w else html

    imgs, seen = [], set()
    for tag in re.findall(r"<img[^>]+>", area):
        u = None
        for attr in ("data-original", "data-src", "src"):
            mm = re.search(rf'{attr}="([^"]+)"', tag)
            if mm and "dcimg" in mm.group(1):       # 로딩 gif·아이콘 제외
                u = mm.group(1)
                break
        if u and u not in seen:
            seen.add(u)
            imgs.append(u)

    body = _strip(re.sub(r"<img[^>]+>", " ", area))[:2000]

    # 댓글 — 반응이 CHAR 대사 재료가 된다
    comments = []
    for c in re.findall(r'<p class="usertxt[^"]*">(.*?)</p>', html, re.S):
        t = _strip(c)
        if 2 <= len(t) <= 60 and not t.startswith("http"):
            comments.append(t)
        if len(comments) >= max_comments:
            break

    return {"title": title, "body": body, "images": imgs[:max_images],
            "comments": comments, "url": url}


def download(url, out_path, *, timeout=30, min_bytes=3000):
    raw = requests.get(url, headers=_UA, timeout=timeout).content
    if len(raw) < min_bytes:
        raise RuntimeError(f"이미지가 너무 작습니다({len(raw)}B)")
    with open(out_path, "wb") as fh:
        fh.write(raw)
    return out_path


def build_read_request(post):
    """캡처 이미지들을 읽어 **기사 본문처럼** 옮겨 달라는 질문."""
    c = "\n".join(f"  · {x}" for x in post["comments"][:20])
    return (
        "첨부한 그림들은 커뮤니티 글의 **본문 캡처**다. 순서대로 이어지는 한 편의 글이다.\n"
        "거기 적힌 내용을 **기사 본문처럼 한국어 줄글로** 옮겨 써라.\n"
        "\n"
        f"[글 제목] {post['title']}\n"
        + (f"[글에 적힌 글자] {post['body'][:300]}\n" if post["body"] else "")
        + (f"\n[댓글 반응 — 사람들이 뭐라 하는지]\n{c}\n" if c else "")
        + "\n"
        "[지키기]\n"
        "  · 그림에 **실제로 적힌 것만** 옮겨라. 없는 사실·숫자·이름을 지어내지 마라.\n"
        "  · 누가 한 말인지 분명하면 그대로 적어라(«최민식은 …라고 했다»).\n"
        "  · 날짜·금액·나이 같은 숫자는 **그림에 있는 그대로**.\n"
        "  · 댓글은 맨 끝에 «사람들 반응:» 으로 모아 서너 줄 적어라 — 대본이 이걸 대사로 쓴다.\n"
        "  · 읽을 수 없는 그림은 건너뛰고, 못 읽었다고 적지 마라.\n"
        "\n"
        "JSON 하나만: {\"text\": \"옮겨 쓴 글 전체\"}\n"
    )


def read_images(post, workdir, reader, *, log=print):
    """캡처들을 내려받아 모델에게 읽히고 → 대본 재료 글자. reader(prompt, [경로…]) -> str"""
    d = os.path.join(workdir, "post")
    os.makedirs(d, exist_ok=True)
    paths = []
    for i, u in enumerate(post["images"], 1):
        p = os.path.join(d, f"{i:02d}.jpg")
        try:
            download(u, p)
            paths.append(p)
        except Exception as e:  # noqa: BLE001 — 한 장 실패가 편을 멈추면 안 된다
            log(f"[brainbulb.community] 이미지 {i} 내려받기 실패({e!r:.60})")
    if not paths:
        raise RuntimeError("community: 읽을 이미지가 없습니다")
    log(f"[brainbulb.community] 캡처 {len(paths)}장 · 댓글 {len(post['comments'])}개")
    raw = reader(build_read_request(post), paths)
    from .prompt import parse_any
    text = (parse_any(raw).get("text") or "").strip()
    if len(text) < 100:
        raise RuntimeError(f"community: 읽어낸 글이 너무 짧습니다({len(text)}자)")
    return (post["title"] + "\n\n" + text).strip()
