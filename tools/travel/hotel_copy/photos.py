"""사진 정리 — 여러 사이트에서 받은 사진을 하나로: 같은 사진 합치기 → AI 판정(종류·글자·사람·화려함·설명) → 컷마다 고르기·자를 자리.

  · 판정 = travel_build.judge_photos(기존 주인 함수, 제미나이 12장 격자) 그대로 부른다 — 여기서 기준을 새로 적지 않는다
  · 같은 사진 = 차이 지문(dhash) 해밍 6 이하 → 해상도 큰 쪽만 남긴다(사이트마다 같은 공식 사진을 크기만 바꿔 올린다)
  · 고르기 = 대본 줄마다 적힌 '사진 힌트'(예 "로비", "드론 조감도")를 판정 설명·종류와 맞춘다. 한 번 쓴 사진은 다시 안 쓴다
"""
import json
import re
from pathlib import Path

import cv2
import numpy as np

KIND_WORDS = {
    "수영장": ("water", "water_aerial"), "인피니티풀": ("water", "water_aerial"), "풀": ("water", "water_aerial"),
    "노천탕": ("onsen",), "스파": ("onsen", "bath"), "사우나": ("onsen", "bath"), "욕조": ("bath",),
    "객실": ("room",), "침대": ("room",), "방": ("room",), "로비": ("lobby",), "라운지": ("lobby",),
    "식당": ("restaurant",), "조식": ("restaurant",), "레스토랑": ("restaurant",), "바": ("restaurant",),
    "외관": ("exterior",), "건물": ("exterior",), "조감도": ("exterior", "water_aerial", "view"), "드론": ("exterior", "water_aerial", "view"),
    "바다": ("view", "water", "exterior"), "해변": ("view", "exterior"), "일출": ("view",), "야경": ("exterior", "view"),
}
# 판정 종류에 없는 시설은 설명 낱말로 찾는다(판정 kind 는 travel_build 주인 — 거기에 종류를 늘리지 않는다)
DESC_WORDS = {"피트니스": ("피트니스", "헬스", "러닝머신", "운동"), "헬스장": ("피트니스", "헬스", "러닝머신", "운동"),
              "사우나": ("사우나", "탕", "스파", "욕장", "목욕"), "로비": ("로비", "라운지", "리셉션", "프런트"),
              "조감도": ("조감도", "위에서", "항공", "드론", "전경"), "드론": ("조감도", "위에서", "항공", "드론", "전경"),
              "외관": ("외관", "건물", "호텔 전경", "타워"), "건물": ("외관", "건물", "타워")}


def dhash(path):
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    s = cv2.resize(im, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    return int("".join("1" if b else "0" for b in (s[:, 1:] > s[:, :-1]).flatten()), 2)


_col = {}


def collage(path):
    """홈페이지 소개용 합성 그림(흰 바탕에 사진 두 장·테두리) — 네 변 띠가 거의 흰색이면 사진이 아니다(실측: 공식 홈 사우나 2장 합성)."""
    if path not in _col:
        g = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
        h, w = g.shape
        b = max(4, int(min(h, w) * 0.03))
        edges = np.concatenate([g[:b].ravel(), g[-b:].ravel(), g[:, :b].ravel(), g[:, -b:].ravel()])
        _col[path] = bool((edges > 235).mean() > 0.6)
    return _col[path]


_orb = {}


def same_scene(a, b, min_good=60):
    """같은 사진을 사이트마다 다르게 자른 판(실측: 여기어때 1500×1200 ↔ 공식 1920×1280, dhash 18 차이) — ORB 특징점이 많이 맞으면 같은 장면."""
    o = cv2.ORB_create(800)
    for p in (a, b):
        if p not in _orb:
            g = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_GRAYSCALE)
            g = cv2.resize(g, (640, int(640 * g.shape[0] / g.shape[1])))
            _orb[p] = o.detectAndCompute(g, None)[1]
    da, db = _orb[a], _orb[b]
    if da is None or db is None:
        return False
    m = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = sum(1 for x in m if len(x) == 2 and x[0].distance < 0.7 * x[1].distance)
    return good >= min_good


def merge_same(items, max_bits=6):
    """여러 사이트 사진에서 같은 사진을 합친다 — 해상도 큰 쪽이 남고, 나머지 출처는 also 에 적는다."""
    for it in items:
        it["dh"] = dhash(it["file"])
    items = sorted(items, key=lambda x: -(x["w"] * x["h"]))
    keep = []
    for it in items:
        twin = next((k for k in keep if bin(k["dh"] ^ it["dh"]).count("1") <= max_bits), None)
        if twin:
            twin.setdefault("also", []).append({"site": it["site"], "src": it["src"]})
        else:
            keep.append(it)
    for k in keep:
        k.pop("dh", None)
    return keep


def judge(items, work):
    """기존 판정 함수로 종류·글자·사람·화려함·설명을 붙인다. 판정 못 받은 사진은 뺀다(모르는 사진을 고르지 않는다)."""
    from shopping_shorts import travel_build as tb
    got = {j["path"]: j for j in tb.judge_photos([it["file"] for it in items], work)}
    out = []
    for it in items:
        j = got.get(it["file"])
        if j:
            out.append(dict(it, kind=j["kind"], has_text=j["has_text"], has_people=j["has_people"], wow=j["wow"], desc=j["desc_ko"]))
    return out


def auto_cx(path):
    """세로로 자를 가운데 — 윤곽이 가장 많은 칸(건물·사물)에 70%, 사진 가운데에 30%."""
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    h, w = im.shape
    if w / h <= 9 / 16:
        return 0.5
    e = np.abs(cv2.Sobel(cv2.GaussianBlur(im, (0, 0), 2), cv2.CV_32F, 1, 1)).sum(0)
    cw = int(h * 9 / 16)
    cs = np.convolve(e, np.ones(cw), "valid")
    x = (int(np.argmax(cs)) + cw / 2) / w
    return round(float(np.clip(0.7 * x + 0.3 * 0.5, cw / 2 / w, 1 - cw / 2 / w)), 3)


def score(photo, hint):
    words = [w for w in re.split(r"[\s·,/]+", hint) if w]
    s = 0.0
    for w in words:
        if w in photo["desc"]:
            s += 3
        s += 2 * any(x in photo["desc"] for x in DESC_WORDS.get(w, ()))
        if photo["kind"] in KIND_WORDS.get(w, ()):
            s += 2
    s += photo["wow"] / 10 + min(photo["w"], 2000) / 4000
    if photo["has_text"]:
        s -= 10                                    # 간판·글자 사진은 안 쓴다(원본도 글자 없는 사진만)
    if photo["has_people"]:
        s -= 1
    return s


def pick(photos, ep_lines, thumb_hint, used=None):
    """대본 줄마다 'shot_hints' → 사진. 끝 컷 = 썸네일 사진(원본 실측: 마지막 컷이 첫 0.1초 건물 사진)."""
    used = set(used or [])
    best = lambda hint: max((p for p in photos if p["file"] not in used), key=lambda p: score(p, hint))  # noqa: E731
    th = best(thumb_hint)
    used.add(th["file"])
    for li, line in enumerate(ep_lines):
        shots = []
        for hi, hint in enumerate(line["shot_hints"]):
            if li == len(ep_lines) - 1 and hi == len(line["shot_hints"]) - 1:
                p = th
            else:
                p = best(hint)
                used.add(p["file"])
            shots.append({"file": p["file"], "cx": auto_cx(p["file"]), "hint": hint, "desc": p["desc"], "site": p["site"]})
        line["shots"] = shots
    return {"file": th["file"], "cx": auto_cx(th["file"]), "desc": th["desc"]}


SITE_BONUS = {"official": 1.0, "yeogi": 0.6, "trip": 0.3, "agoda": 0.3, "yeogi_review": 0.0}   # 공식 홈 사진이 먼저(손님 사진이 섞이는 곳은 뒤로)


def pick_vision(photos, ep_lines, thumb_hint, work, thumb_kinds=None, end_is_thumb=True):
    """줄마다 후보 12장(낱말·종류 점수 순)을 격자로 → Claude 가 사진을 보고 힌트에 맞는 번호를 고른다.
    실측 2026-10-23: 낱말 맞추기만으로는 '피트니스'에 수영장 외관·'사우나'에 식당·썸네일에 일출이 걸렸다."""
    from shopping_shorts import travel_build as tb
    used = set()
    work = Path(work)

    dh = {}

    def near(a, b, bits=12):
        """비슷한 사진(같은 장면 다른 크기·살짝 다른 각도) — 한 편에 두 번 나오지 않게."""
        if a == b:
            return True
        for p in (a, b):
            if p not in dh:
                dh[p] = dhash(p)
        return bin(dh[a] ^ dh[b]).count("1") <= bits or same_scene(a, b)

    def cands(hints, n=12, only=None):
        """힌트마다 따로 순위를 매겨 번갈아 담는다 — 한 힌트('바다')가 후보를 다 차지하면 다른 컷('사우나') 후보가 사라진다(실측)."""
        pool = [p for p in photos if not p["has_text"] and not collage(p["file"]) and (only is None or only(p))
                and not any(near(p["file"], u) for u in used)]
        ranked = [sorted(pool, key=lambda p, h=h: -(score(p, h) + SITE_BONUS.get(p["site"], 0))) for h in hints]
        out = []
        for k in range(len(pool)):
            for r in ranked:
                if k < len(r) and len(out) < n and not any(near(r[k]["file"], o["file"]) for o in out):
                    out.append(r[k])
            if len(out) >= n:
                break
        return out

    def ask(hints, cs, tag):
        grid = tb.make_grid([c["file"] for c in cs], work / ("pick_%s.jpg" % tag), cell=(384, 256))
        prompt = ("숙소 쇼츠 컷 사진을 고른다. 격자 칸 왼쪽 위 번호가 사진 번호(1부터). 원하는 컷: %s.\n"
                  "컷마다 그 말에 가장 맞는 사진 번호 하나(서로 다르게). 맞는 게 없으면 0. 기준: 말과 장면이 맞는가 > 호텔 공식 사진처럼 "
                  "선명·화려한가(손님 폰 사진·사람 얼굴·글자 간판은 피한다) > 세로로 잘라도 주인공이 남는가.\n"
                  "JSON: {\"picks\": [번호, ...]}" % " / ".join("%d) %s" % (i + 1, h) for i, h in enumerate(hints)))
        got = tb.claude_call([grid], prompt).get("picks") or []
        out = []
        for k, h in zip(got, hints):
            c = cs[int(k) - 1] if isinstance(k, int) and 1 <= k <= len(cs) else None
            if c is None or any(near(c["file"], u) for u in used):
                # 0(맞는 사진 없음)·같은 번호 두 번 → 이 힌트 점수 1등 중 아직 안 쓴 것(조용히 cs[0] 을 되풀이하지 않는다 — 실측: 같은 사진 두 번)
                c = next((x for x in sorted(cs, key=lambda x: -score(x, h)) if not any(near(x["file"], u) for u in used)), cs[0])
                print("  사진 고르기: '%s' 맞는 사진 없음 → 점수 1등 %s" % (h, Path(c["file"]).name), flush=True)
            used.add(c["file"])
            out.append(c)
        return out
    # 썸네일 종류·끝 컷=썸네일 여부는 원본마다 다르다(refs/<id>.json 의 thumb_kinds·end_same_as_thumb) — 1위 온천=건물·끝 컷 같음 / 촌캉스=바비큐·끝 컷 다름
    th = ask([thumb_hint], cands([thumb_hint], only=(lambda p: p["kind"] in thumb_kinds) if thumb_kinds else None), "thumb")[0]
    for li, line in enumerate(ep_lines):
        hints = list(line["shot_hints"])
        last = end_is_thumb and li == len(ep_lines) - 1
        ask_h = hints[:-1] if last else hints
        chosen = ask(ask_h, cands(ask_h), "%d" % (li + 1)) if ask_h else []
        if last:
            chosen.append(th)                       # 끝 컷 = 썸네일 사진(원본 실측)
        line["shots"] = [{"file": c["file"], "cx": auto_cx(c["file"]), "hint": h, "desc": c["desc"], "site": c["site"]}
                         for c, h in zip(chosen, hints)]
    return {"file": th["file"], "cx": auto_cx(th["file"]), "desc": th["desc"]}


def sheet(ep, out_path):
    """고른 사진 한눈에(썸네일 + 컷 순서, 세로로 자른 모양 그대로) — 사장님 확인용."""
    from tools.travel.hotel_copy.render import vertical
    tiles = [(ep["thumb"]["file"], ep["thumb"]["cx"], "썸네일")]
    for li, line in enumerate(ep["lines"]):
        for sh in line["shots"]:
            tiles.append((sh["file"], sh["cx"], "%d %s" % (li + 1, sh["hint"])))
    ims = []
    for f, cx, lab in tiles:
        v = cv2.resize(vertical(f, cx), (216, 384))
        ims.append(v)
    while len(ims) % 7:
        ims.append(np.zeros_like(ims[0]))
    g = np.vstack([np.hstack(ims[i:i + 7]) for i in range(0, len(ims), 7)])
    cv2.imencode(".jpg", g)[1].tofile(str(out_path))
    return [t[2] for t in tiles]


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
