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


def imread(path):
    """OpenCV로 사진을 읽는다. 못 읽으면 None.

    ★`cv2.imread`를 직접 부르지 마라 — 윈도우에서 **경로에 한글이 있으면 무조건 None**이다
      (실측 2026-09-13 `out/brainbulb/박위_photo/`: 파일 325,823B가 멀쩡히 있는데 imread는 False,
       같은 바이트를 imdecode에 주면 (676,409,3)으로 읽힌다).
      그 바람에 박위 편 7컷이 전부 "얼굴 없음·글자 0%"로 조용히 버려져 수집 0/7이 됐다.
      바이트로 읽어 imdecode에 넘기면 경로 글자와 무관하다. 읽는 곳은 여기 한 군데뿐이다(0순위-B).
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except Exception:  # noqa: BLE001 — 파일이 없거나 못 읽으면 판정 안 함
        return None
    if not buf.size:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def find_seam(path, *, band=(0.35, 0.65), min_ratio=6.0):
    """이어붙인 사진의 경계를 찾는다 → ("v"|"h", 위치) 또는 None.

    왜: 뉴스 사진은 두 장면을 좌우/위아래로 이어붙인 것이 흔하다(실측 2026-09-13 박수홍 편 4장 중 2장).
    그대로 슬롯에 넣으면 같은 사람이 한 화면에 두 번 나오거나 잘려 들어간다.
    판정: 가운데 구간에서 인접 행·열 평균 밝기 차가 전체 평균의 min_ratio배 넘게 튀는 자리.
    실측값 — 좌우 이어붙임 14.6배 / 위아래 23.6배 / 정상 사진 3.2배.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    try:
        a = np.asarray(Image.open(path).convert("L"), dtype=float)
    except Exception:  # noqa: BLE001 — 못 읽으면 경계 판정 안 함
        return None
    h, w = a.shape
    best = None
    for axis, arr, n in (("v", np.abs(np.diff(a.mean(axis=0))), w),
                         ("h", np.abs(np.diff(a.mean(axis=1))), h)):
        if n < 200:
            continue
        lo, hi = int(n * band[0]), int(n * band[1])
        seg = arr[lo:hi]
        if not len(seg):
            continue
        i = lo + int(np.argmax(seg))
        ratio = arr[i] / (arr.mean() + 1e-9)
        if ratio >= min_ratio and (best is None or ratio > best[2]):
            best = (axis, i + 1, ratio)
    return (best[0], best[1]) if best else None


def split_collage(path, out_path=None, *, max_cuts=3, min_side=280):
    """이어붙인 사진이면 **더 큰 쪽 한 칸만** 잘라 저장하고 True. 아니면 손대지 않고 False.

    ★한 번만 자르면 모자란다(실측 2026-09-13 박위 편): 3칸짜리는 한 번 자른 뒤에도 경계가 남아
      사과문 캡처가 사진에 붙은 채로 통과했다. 경계가 사라질 때까지 되풀이하되,
      너무 잘게 잘리면(min_side 미만) 멈춘다 — 슬롯에 넣을 수 없다.
    """
    from PIL import Image
    dst = out_path or path
    cut = False
    for _ in range(max_cuts):
        seam = find_seam(dst if cut else path)     # ★잘라 저장한 뒤엔 **저장된 그 파일**을 다시 잰다
        if not seam:
            break
        axis, pos = seam
        cur = Image.open(dst if cut else path)
        w, h = cur.size
        if axis == "v":
            keep = cur.crop((0, 0, pos, h)) if pos >= w - pos else cur.crop((pos, 0, w, h))
        else:
            keep = cur.crop((0, 0, w, pos)) if pos >= h - pos else cur.crop((0, pos, w, h))
        if min(keep.size) < min_side:
            break
        keep.convert("RGB").save(dst, "JPEG", quality=94)
        cut = True
    return cut


def text_ratio(path, *, sample=500):
    """글자가 덮은 면적 비율(0~1). 자막·가격표가 깔린 방송 캡처를 거른다. OCR 없이 근사한다.

    실측 2026-09-13 (박수홍 편 4장):
      일반 사진 0.2~0.5%  /  홈쇼핑 화면 캡처 14.3%  → 임계 3%면 확실히 갈린다.
    ★엣지 밀도만 보면 유리·바닥 무늬가 글자로 잡혀 사진(20%)과 캡처(19%)가 구분되지 않았다.
      글자는 ①가로로 길고 ②배경 색이 단조롭고(채도 표준편차 낮음) ③잉크 비율이 중간 — 셋을 같이 본다.
    ★잉크는 **어두운 쪽으로 단정하지 마라**(실측 2026-09-13 박위 04번): 검은 바탕에 흰 글씨인
      사과문 캡처가 0.2%로 나와 그대로 통과했다. 밝고 어두운 쪽 중 **적은 쪽**을 잉크로 본다.
    """
    try:
        import cv2
    except ImportError:
        return 0.0
    try:
        img = imread(path)                      # ★한글 경로 대응 — cv2.imread 직접 호출 금지
        if img is None:
            return 0.0
        s = sample / max(img.shape[:2])
        if s < 1:
            img = cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)))
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        conn = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
        cnts, _ = cv2.findContours(conn, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        H, W = g.shape
        area = 0
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if h < 6 or h > H * 0.25 or w < h * 2.0 or w * h < 120:
                continue
            patch = img[y:y + h, x:x + w]
            if cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 1].std() > 45:
                continue                                    # 색이 다채로우면 사진 무늬
            pg = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            _, pb = cv2.threshold(pg, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            dark = (pb == 0).mean()
            ink = min(dark, 1.0 - dark)          # ★글자가 밝을 수도 있다 — 적은 쪽이 잉크다
            if not (0.04 < ink < 0.45):
                continue                                    # 잉크 비율이 글자 범위 밖
            area += w * h
        return area / (H * W)
    except Exception as e:  # noqa: BLE001 — 못 재면 통과(0)로 두고 다른 검사에 맡긴다
        print(f"[brainbulb.photos] 글자 측정 실패(통과 처리): {e!r}")
        return 0.0


def _yunet_model():
    """YuNet onnx 경로 — spec.FACE_MODEL(있으면) → 볼케이노 팩 → None.

    ★경로에 한글이 있으면 OpenCV가 onnx를 못 읽는다(실측 2026-09-13):
      볼케이노 팩이 `~/.volcano/jobs/20260911_뇌전구_박수홍/…`에 있어 **모든 사진에서 검출이 실패**했고,
      실패는 '통과 처리'라 얼굴 판정이 조용히 무력화돼 있었다(박위 편 6컷 전부 미검사 통과).
      그래서 한글이 섞인 경로면 ASCII 전용 자리로 **한 번 복사해 두고** 그 사본을 쓴다.
    """
    for p in (getattr(spec, "FACE_MODEL", None),
              os.path.expanduser("~/.volcano/jobs/20260911_뇌전구_박수홍/framevision/models/face_detection_yunet_2023mar.onnx")):
        if not p or not os.path.exists(p):
            continue
        p = os.path.normpath(os.path.abspath(p))   # ★슬래시가 섞여도 OpenCV가 읽게 한다(실측)
        if p.isascii():
            return p
        cache = os.path.join(os.path.expanduser("~"), ".brainbulb", "models",
                             "face_detection_yunet_2023mar.onnx")
        try:
            if not os.path.exists(cache) or os.path.getsize(cache) != os.path.getsize(p):
                os.makedirs(os.path.dirname(cache), exist_ok=True)
                import shutil
                shutil.copyfile(p, cache)
            return cache
        except Exception as e:  # noqa: BLE001 — 복사 실패면 얼굴 판정만 못 한다(편은 계속 간다)
            print(f"[brainbulb.photos] 얼굴 모델 복사 실패: {e!r}")
            return None
    return None


def has_face(path, *, min_score=0.6):
    """사람 얼굴이 있나 — 로고·건물·상품 사진을 거른다.

    ★OpenCV 5는 `CascadeClassifier`를 뺐다(실측 AttributeError). 볼케이노와 같은 **YuNet**을 쓴다.
    모델이 없거나 검출이 실패하면 True(통과) — 못 잰 것을 '얼굴 없음'으로 단정하지 않는다.
    """
    model = _yunet_model()
    if not model:
        return True
    try:
        import cv2
        img = imread(path)                      # ★한글 경로 대응 — cv2.imread 직접 호출 금지
        if img is None:
            return False
        h, w = img.shape[:2]
        det = cv2.FaceDetectorYN.create(model, "", (w, h), min_score, 0.3, 5000)
        _, faces = det.detect(img)
        return faces is not None and len(faces) > 0
    except Exception as e:  # noqa: BLE001 — 검출 실패를 '얼굴 없음'으로 단정하지 않는다
        print(f"[brainbulb.photos] 얼굴 검출 실패(통과 처리): {e!r}")
        return True


def _fingerprint(path):
    """사진의 지문 — 같은 사진이 두 컷에 들어가는 걸 막는다.

    ★실측 2026-09-13 박위 편: 검색어가 달라도(«케냐 봉사» / «휠체어 들어올리는») 같은 기사 사진이
      와서 슬롯 5와 8에 **바이트까지 똑같은 사진**이 들어갔다. 사장님이 지적한 "두 번 연속 나온다"가 이것이다.
      자른 뒤 모습으로 재야 하므로 픽셀을 8x8 회색조로 줄여 비교한다(리사이즈·재압축에도 견딘다).
    """
    try:
        from PIL import Image
        im = Image.open(path).convert("L").resize((8, 8))
        px = list(im.tobytes())                 # getdata()는 Pillow 14에서 빠진다
        avg = sum(px) / len(px)
        return "".join("1" if v > avg else "0" for v in px)
    except Exception:  # noqa: BLE001 — 지문을 못 내면 중복 검사만 못 한다
        return None


def pick_photo(query, workdir, slot, *, want_face=True, num=10, log=print, seen=None):
    """검색 → 뉴스 출처 우선 → 얼굴 확인 → 다운로드. 못 찾으면 None.

    `seen`에 이미 쓴 사진의 지문을 담아 넘기면 **같은 사진을 두 컷에 넣지 않는다**(호출부가 set 하나를 돌려 쓴다).
    """
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
        note = ""
        if split_collage(path):                    # 이어붙인 사진이면 한 칸만 남긴다
            note = " (이어붙임 → 한 칸만)"
        tr = text_ratio(path)
        if tr > spec.POLICY_PHOTO_TEXT_MAX:        # 자막·가격표 덮인 방송 캡처
            log(f"[brainbulb.photos] 슬롯 {slot} 글자 과다({tr:.0%}) — 다음 후보")
            os.remove(path)
            continue
        if want_face and not has_face(path):
            os.remove(path)
            continue
        fp = _fingerprint(path)
        if seen is not None and fp and fp in seen:
            log(f"[brainbulb.photos] 슬롯 {slot} 앞 컷과 같은 사진 — 다음 후보")
            os.remove(path)
            continue
        if seen is not None and fp:
            seen.add(fp)
        log(f"[brainbulb.photos] 슬롯 {slot} «{query}» → {h['source'][:24]} ({h['w']}x{h['h']}){note}")
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
