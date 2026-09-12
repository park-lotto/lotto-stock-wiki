# -*- coding: utf-8 -*-
"""실제 사진 조달 — 검색(Serper) → 거르기 → 변형(qwen-image-edit).

왜 필요한가 (사장님 2026-09-13):
  "박수홍 박위 등 유명한 사람들의 기사인데 완전 딴판인 사람이 나와서 이질감이 심하다.
   보통 잘되는 채널들은 구글 이미지에서 다운받아 아주 약간만 변형해서 쓰거나, 좋은 기사는 실제 사진을 쓴다."

세 갈래 (대본이 컷마다 지정):
  real    좋은 얘기(복귀·봉사·성과) → 검색 사진 **그대로**
  variant 안 좋은 얘기(논란·사고·비판) → 검색 사진을 **참조로 변형 생성** (초상권·명예 회피 + 이질감 없음)
  gen     인물 없는 배경·상황 → 지금처럼 생성 (images.py)

★실측 2026-09-13 — 참조 이미지를 지키는 모델은 하나뿐이다:
  · `qwen-image-edit` + **`image_url`** 필드 → 같은 옷·같은 장소 유지, 얼굴만 다름 (원하는 결과)
  · `gpt-image-2`(image 필드) → 참조 무시, 완전 딴 사람·딴 장소
  · `gemini-3.1-flash-image-preview`(images 배열) → 참조 무시
  · `qwen-image-edit`에 `size`를 주면 400 (지원 안 함)
"""
import base64
import json
import os
import re
import time
import urllib.request

import requests

from . import spec

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124"}


# ── 검색 (Serper = 구글 이미지) ───────────────────────────────────────────────────
def serper_key(key_file=None):
    v = os.environ.get("SERPER_API_KEY", "").strip()
    if v:
        return v
    p = key_file or os.path.expanduser("~/.volcano/keys/serper")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def search_images(query, *, num=10, key_file=None, timeout=30):
    """→ [{"url","source","w","h","title"}]. 키 없으면 빈 목록(호출부가 생성으로 폴백)."""
    key = serper_key(key_file)
    if not key:
        return []
    r = requests.post("https://google.serper.dev/images",
                      headers={"X-API-KEY": key, "Content-Type": "application/json"},
                      json={"q": query, "gl": "kr", "hl": "ko", "num": num}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"serper {r.status_code}: {r.text[:160]}")
    out = []
    for i in (r.json().get("images") or []):
        u = i.get("imageUrl")
        if u:
            out.append({"url": u, "source": i.get("source") or "", "title": i.get("title") or "",
                        "w": i.get("imageWidth") or 0, "h": i.get("imageHeight") or 0})
    return out


# ── 거르기 ───────────────────────────────────────────────────────────────────────
# 실측: '박수홍' 검색 상위 10장에 핀터레스트·중국 기업 홈페이지·서울대 교수 페이지가 섞였다.
# 뉴스/연예 매체 결과만 남기면 기사 사진이라 맥락도 맞는다.
_NEWS_HINTS = ("뉴스", "news", "일보", "신문", "경제", "스포츠", "연합", "뉴시스", "헤럴드", "조선",
               "중앙", "동아", "한겨레", "머니투데이", "이데일리", "마이데일리", "osen", "tv리포트",
               "엑스포츠", "스타", "매일", "kbs", "sbs", "mbc", "jtbc", "ytn", "채널", "데일리")
_BAD_HINTS = ("pinterest", "핀터레스트", "aliexpress", "alibaba", "taobao", "amazon", "coupang",
              "쿠팡", "11st", "gmarket", "shop", "쇼핑", "wikipedia", "namu", "나무위키")


def looks_like_news(source):
    s = (source or "").lower()
    if any(b in s for b in _BAD_HINTS):
        return False
    return any(h in s for h in _NEWS_HINTS)


def download(url, out_path, *, timeout=30, min_bytes=8000):
    req = urllib.request.Request(url, headers=_UA)
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    if len(raw) < min_bytes:
        raise RuntimeError(f"사진이 너무 작습니다({len(raw)}B)")
    with open(out_path, "wb") as fh:
        fh.write(raw)
    return out_path


def has_face(path):
    """사람 얼굴이 있나 — 로고·건물·상품 사진을 거른다. OpenCV가 없으면 True(통과)."""
    try:
        import cv2
    except ImportError:
        return True
    try:
        img = cv2.imread(path)
        if img is None:
            return False
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
        return len(faces) > 0
    except Exception as e:  # noqa: BLE001 — 검출 실패를 '얼굴 없음'으로 단정하지 않는다
        print(f"[brainbulb.photos] 얼굴 검출 실패(통과 처리): {e!r}")
        return True


def pick_photo(query, workdir, slot, *, want_face=True, num=10, log=print):
    """검색 → 뉴스 출처 우선 → 얼굴 확인 → 다운로드. 못 찾으면 None."""
    d = os.path.join(workdir, "photo")
    os.makedirs(d, exist_ok=True)
    try:
        hits = search_images(query, num=num)
    except Exception as e:  # noqa: BLE001 — 검색 실패가 편 전체를 멈추면 안 된다
        log(f"[brainbulb.photos] 검색 실패({e!r:.80}) — 생성으로 넘김")
        return None
    if not hits:
        return None
    ranked = [h for h in hits if looks_like_news(h["source"])] + \
             [h for h in hits if not looks_like_news(h["source"])]
    for h in ranked[:6]:
        if h["w"] and h["w"] < 300:
            continue
        path = os.path.join(d, f"{int(slot):02d}.jpg")
        try:
            download(h["url"], path)
        except Exception:  # noqa: BLE001 — 한 장 실패는 다음 후보로
            continue
        if want_face and not has_face(path):
            os.remove(path)
            continue
        log(f"[brainbulb.photos] 슬롯 {slot} «{query}» → {h['source'][:24]} ({h['w']}x{h['h']})")
        return {"path": path, **h}
    log(f"[brainbulb.photos] 슬롯 {slot} «{query}» — 쓸 만한 사진 없음")
    return None


# ── 변형 (참조를 지키는 유일한 길: qwen-image-edit + image_url) ────────────────────
def variant(src_path, out_path, prompt, *, key_file=None, poll_max=60, poll_sec=3, log=print):
    """원본 사진을 참조로 같은 옷·같은 장면을 다시 그린다(얼굴만 다른 사람)."""
    from .images import evolink_key, _extract_urls
    key = evolink_key(key_file)
    if not key:
        raise RuntimeError("photos: EvoLink 키가 없습니다")
    b64 = "data:image/jpeg;base64," + base64.b64encode(open(src_path, "rb").read()).decode()
    H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": spec.VARIANT_MODEL, "prompt": prompt, "image_url": b64}   # ★size 주면 400
    r = requests.post(f"{spec.IMAGE_API}/v1/images/generations", headers=H, json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"variant {r.status_code}: {r.text[:160]}")
    created = r.json()
    task = created.get("id") or created.get("task_id")
    urls = _extract_urls(created) if not task else []
    for _ in range(poll_max):
        if urls:
            break
        time.sleep(poll_sec)
        d = requests.get(f"{spec.IMAGE_API}/v1/tasks/{task}", headers={"Authorization": f"Bearer {key}"}, timeout=60).json()
        st = str(d.get("status") or d.get("state") or "").lower()
        if st in ("completed", "succeeded", "success"):
            urls = _extract_urls(d)
            if not urls:
                raise RuntimeError("variant: 완료인데 주소가 없습니다")
        elif st in ("failed", "error"):
            raise RuntimeError(f"variant: 실패 {d.get('fail_reason') or st}")
    if not urls:
        raise RuntimeError("variant: 시간 안에 안 끝났습니다")
    raw = requests.get(urls[0], headers=_UA, timeout=90).content
    if len(raw) < 1024:
        raise RuntimeError(f"variant: 결과가 너무 작습니다 {len(raw)}B")
    with open(out_path, "wb") as fh:
        fh.write(raw)
    log(f"[brainbulb.photos] 변형 완료 {os.path.basename(out_path)}")
    return out_path
