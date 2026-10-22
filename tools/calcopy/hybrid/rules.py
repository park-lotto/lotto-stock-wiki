# -*- coding: utf-8 -*-
"""회원 라인(볼케이노형, 관제 234·097 2026-10-21) — 서버 지시서(flow)와 회원 PC 실행기(runner_ops)가 **같이 부르는** 판단 함수.
파일·영상·네트워크를 만지지 않는다(글·숫자만) — 서버에서도 PC 에서도 같은 답을 낸다(판단 한 곳, 0순위-B).
옛 자리: hybrid/customer.py(10-21 TheRose PC) — 볼케이노형 분해 때 이리로 옮겼다(customer.py 는 지웠다)."""
from __future__ import annotations

import difflib
import re

NO_FACE = {"", "없음", "none", "None"}


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def fingerprint(bench_lines: list[dict], words: list) -> list[dict]:
    """벤치 말(받아쓰기) ↔ 원본 자막 낱말(초, 낱말) — 같은 말이 원본 몇 초에 있나(제작순서 02 §4 '두세 줄 이상 맞으면 확정'). 맞은 토막만."""
    words = [(float(t), norm(w)) for t, w in words if norm(w)]
    out = []
    # 위스퍼는 나레·원음을 한 덩어리로 묶는다(10-21 실측: 2줄, 둘째 줄 80자) → 문장·쉼표·10~16자 토막으로 갈라 토막마다 대조
    chunks = []
    for b in bench_lines:
        for s in re.split(r"[.?!,]\s*", str(b.get("text") or "")):
            n = norm(s)
            while len(n) > 16:
                chunks.append(n[:14]); n = n[10:]
            if len(n) >= 6:
                chunks.append(n)
    for q in dict.fromkeys(chunks):
        if not words:
            break
        best = (0.0, None)
        for i in range(len(words)):
            acc, j = "", i
            while j < len(words) and len(acc) < len(q) + 4:
                acc += words[j][1]; j += 1
            r = difflib.SequenceMatcher(None, q, acc[:len(q) + 4]).ratio()
            if r > best[0]:
                best = (r, words[i][0])
        if best[0] >= 0.7:
            out.append({"bench": q, "origin_t": round(best[1], 2), "score": round(best[0], 2)})
    return out


def word_hits(words: list, terms: list[str], gap: float = 20.0) -> list[dict]:
    """원본 자막 낱말(초, 낱말)에서 장면·제품 낱말이 나온 시각 — 벤치가 내레이션뿐이라 말 지문(fingerprint)이 0일 때 원본 후보를 고르는 단서
    (10-22 고현정 가방: 벤치에 본인 목소리 없음 → 지문 0, 원본 브이로그 20 자막에만 '서촌'). 같은 낱말은 gap 초 안에서 한 번만."""
    words = [(float(t), norm(w)) for t, w in words if norm(w)]
    out, last = [], {}
    for q in dict.fromkeys(norm(t) for t in terms or []):
        if len(q) < 2:
            continue
        for i in range(len(words)):
            acc, j = "", i
            while j < len(words) and len(acc) < len(q) + 6:
                acc += words[j][1]; j += 1
            if acc.startswith(q) or (q in acc and q not in acc[len(words[i][1]):]):
                t = words[i][0]
                if t - last.get(q, -1e9) >= gap:
                    out.append({"term": q, "origin_t": round(t, 2)}); last[q] = t
    return sorted(out, key=lambda h: h["origin_t"])


def caps_vs_tts(S: dict) -> list[str]:
    """나레 줄마다 화면 자막(caps 이어 붙인 글)이 실제로 읽는 글(tts)과 같은가 — 부호·띄어쓰기만 다른 건 같다
    (10-21 선우용여 N3: 자막 '따라 사 봤는데요' ↔ 목소리 '하나 사서 따라 해 봤는데요' — 완성본 눈 검수가 짚었다).
    집 PC 옛 대본은 caps 가 글 목록, 회원 라인은 {"text"} 목록 — 둘 다 받는다(98_오류기록 19)."""
    out = []
    for l in S.get("lines") or []:
        if l.get("kind") != "tts" or not l.get("caps"):
            continue
        cap = norm("".join(str((c.get("text") if isinstance(c, dict) else c) or "") for c in l["caps"]))
        shown, say = norm(str(l.get("text") or "")), norm(str(l.get("tts") or ""))
        if shown and cap != shown:
            out.append(f"{l.get('id')}: 자막 조각을 이으면 '{cap}' — 화면 글(text) '{shown}' 과 다르다")
        # 읽는 글은 숫자·영문 읽기·이름 발음 때문에 달라도 된다(제작순서 07 §4) — 숫자·영문 없는 줄에서 말이 4자 넘게 늘거나 줄면 결함
        if shown and say and not re.search(r"[0-9A-Za-z%]", str(l.get("text") or "")) and abs(len(say) - len(shown)) >= 4:
            out.append(f"{l.get('id')}: 화면 '{l.get('text')}' ↔ 목소리 '{l.get('tts')}' — 말이 더해지거나 빠졌다(자막은 읽는 말 그대로, 발음 고침만 다르게)")
    return out


def title_colors_bad(S: dict, st: dict) -> list[str]:
    """제목 줄마다 판 틀(frame.title[줄])에 있는 색만 썼나 — 'hi' 는 그 줄 틀에 hi 가 있을 때만(10-21 실측: 키치잇판 둘째 줄 상자에 hi → 렌더 KeyError)."""
    spec = (st.get("frame") or {}).get("title") or []
    out = []
    for i, line in enumerate(S.get("title_lines") or []):
        sp = spec[i] if i < len(spec) else {}
        for chunk in line if isinstance(line, list) else []:
            c = chunk[1] if isinstance(chunk, list) and len(chunk) > 1 else None
            if c == "hi" and "hi" not in sp:
                out.append(f"제목 {i + 1}줄 '{chunk[0]}' 에 'hi' — 이 판 제목 {i + 1}줄은 강조색이 없다(null 또는 '#hex')")
    if len(S.get("title_lines") or []) > len(spec):
        out.append(f"제목 줄 수 {len(S['title_lines'])} > 판 틀 {len(spec)}줄")
    return out


def shot_at(shots: list[dict], t: float) -> dict | None:
    return next((s for s in shots or [] if s["a"] - 0.05 <= t < s["b"]), None)


def shot_text(shots: list[dict]) -> str:
    def one(s):
        cx = f" 주인공x {s['cx']:.2f}" if s.get("cx") is not None else ""
        tx = " 글자 " + ",".join("[" + ",".join(f"{v:.2f}" for v in b) + "]" for b in s.get("text") or []) if s.get("text") else ""
        return f"#{s['i']} {s['a']:.2f}~{s['b']:.2f} ({s['b'] - s['a']:.1f}초) {s.get('who')}{' 제품' if s.get('product') else ''}{cx}{tx} {s.get('desc', '')}"
    return "\n".join(one(s) for s in shots or [])


def source_rule_static(M: dict, origin_names: set, bench_id: str, shots_by_src: dict) -> list[str]:
    """재료 출처 규칙 ①② + 다른 출연자 샷(사장님 10-21 "반드시 원본을 찾아서 / 다른 채널의 연예인 영상을 그대로 가져다 쓰면 절대 안 된다").
    ① 벤치(남의 쇼츠)는 재료가 아니다 ② 사람 얼굴 컷은 원본 파일만 ③' 원본 컷 ss 가 주인공 없는 다른 출연자 샷이면 안 된다.
    ③ 장면 전환(프레임 차)은 영상이 있어야 재므로 PC(runner_ops.source_rule_scan)가 재고 서버가 합친다."""
    out = []
    for line, cuts in (M.get("cuts") or {}).items():
        for c in cuts if isinstance(cuts, list) else [cuts]:
            src = str(c.get("src") or "")
            face = str(c.get("face") or "").strip()
            stem = src.rsplit(".", 1)[0]
            if src.startswith("bench") or (bench_id and src.startswith(bench_id)):
                out.append(f"{line}: 벤치(남의 쇼츠) {src} 를 재료로 썼다 — 원본·제품 영상만 쓴다")
            elif face not in NO_FACE and src not in origin_names:
                out.append(f"{line}: 사람 얼굴 컷({c.get('face')})이 원본이 아닌 {src} 에서 왔다 — 연예인 장면은 원본 파일({', '.join(sorted(origin_names))})에서만")
            elif src in origin_names and c.get("ss") is not None and stem in shots_by_src:
                s = shot_at(shots_by_src[stem], float(c["ss"]))
                if s and s.get("who") == "other" and face not in NO_FACE:
                    out.append(f"{line}: ss {c['ss']} 는 원본 샷 #{s['i']}({s['a']}~{s['b']}, {s.get('desc')}) — 주인공이 없는 다른 출연자 샷이다")
    return out


def material_problems(M: dict, known: set, orig_lines: set) -> list[str]:
    """재료.json 컷의 꼴 검사(판정 답을 받은 즉시 — 렌더에서 터지기 전에, 뿌리 10-22). 서버 지시서 계획 단계가 부른다.
    src 가 받은 파일인가 · 영상 컷에 ss(원음 줄은 렌더가 채운다)·숫자인가 · crop 이 'face' 또는 [x,y,w,h] 인가 · dur 이 숫자인가.
    10-22 강주은: 사진 컷 ss·crop 없음 → 렌더 KeyError 'ss' 로 멈춤(칸 있음만 보던 검사가 못 잡음)."""
    out = []
    for line, cuts in (M.get("cuts") or {}).items():
        for i, c in enumerate(cuts if isinstance(cuts, list) else [cuts]):
            tag = f"{line}#{i + 1}"
            if not isinstance(c, dict):
                out.append(f"{tag}: 컷이 객체가 아니다"); continue
            src = str(c.get("src") or "")
            if not src:
                out.append(f"{tag}: src 가 없다"); continue
            if known and src not in known:
                out.append(f"{tag}: src {src} 는 받은 파일이 아니다(있는 파일: {', '.join(sorted(known))[:300]})")
            still = src.lower().endswith(STILL_EXT)
            ss = c.get("ss")
            if not still and ss is None and line not in orig_lines:
                out.append(f"{tag}: 영상 컷 {src} 에 ss(시작 초)가 없다")
            if ss is not None and not isinstance(ss, (int, float)):
                out.append(f"{tag}: ss 가 숫자가 아니다({ss!r})")
            cr = c.get("crop")
            if cr is not None and cr != "face" and not (isinstance(cr, list) and len(cr) == 4 and all(isinstance(v, (int, float)) for v in cr)):
                out.append(f"{tag}: crop 은 'face' 또는 [x, y, w, h](원본 픽셀 정수)여야 한다({cr!r})")
            for k in ("dur", "at"):
                if c.get(k) is not None and not isinstance(c.get(k), (int, float)):
                    out.append(f"{tag}: {k} 가 숫자가 아니다({c.get(k)!r})")
    return out


TEXT_MIN_H = 0.45     # 박힌 글자를 피해 줄일 때 칸 높이 하한(원본 높이 비율) — 더 줄면 화질이 떨어져 그대로 두고 검수에 맡긴다
STILL_EXT = (".jpg", ".jpeg", ".png", ".webp")


def avoid_text(crop: list, boxes: list, fx: float | None, sw: int, sh: int, ar: float) -> list:
    """박힌 글자 상자(원본 픽셀)를 피해 칸을 줄인다 — 위 띠면 칸 위를 띠 아래로, 아래 자막이면 칸 아래를 자막 위로(창 비율 유지, 주인공 가로 가운데 유지).
    집 PC yanshot/plan 이 샷마다 글자 상자를 읽어 크롭 밖으로 빼던 것(10-21 선우용여: 위 제목 띠·아래 자막이 검수마다 새로 걸림, 98 #24)."""
    x, y, w, h = [float(v) for v in crop]
    for _ in range(6):
        hit = [b for b in boxes if b[0] < x + w and b[2] > x and b[1] < y + h and b[3] > y]
        if not hit:
            break
        b = max(hit, key=lambda b: (min(b[2], x + w) - max(b[0], x)) * (min(b[3], y + h) - max(b[1], y)))
        top = (b[1] + b[3]) / 2 < y + h / 2
        ny0, ny1 = (b[3], y + h) if top else (y, b[1])
        nh = ny1 - ny0
        if nh < TEXT_MIN_H * sh:
            break
        nw = min(sw, nh * ar)
        cx = fx if fx is not None else x + w / 2
        x, y, w, h = max(0.0, min(sw - nw, cx - nw / 2)), ny0, nw, nh
    return [int(round(x)), int(round(y)), int(round(w)), int(round(h))]


def fill_shot_max(M: dict, S: dict | None, origin_dims: dict, shots_by_src: dict, ar: float | None) -> dict:
    """원본 컷마다 샷 표로 칸을 채운다(판단 주인 — 집 PC 에선 손으로 적던 칸). origin_dims = {파일 이름: [가로, 세로]}(PC 가 잰 값).
    ① max = 그 샷 끝 − ss — 렌더러의 '컷이 원본 샷보다 길다' 검사가 다른 출연자로 넘어가는 컷을 잡게 한다
    ② 칸이 정해지지 않은 주인공 컷('face'·없음)만 **주인공 얼굴 가운데 + 박힌 글자 피하기**(사장님 10-21 "주인공 가운데").
       숫자로 정한 칸은 절대 덮지 않는다 — 대본·재료 고치기가 정한 칸을 엔진이 되돌리면 같은 칸을 두 곳이 정한다(98 #21·#25, 0순위-B).
    ③ 사진 재료(쿠팡 상품 사진)가 이어지면 움직임을 번갈아(in·left·out·right) — 대본이 정한 move 는 그대로."""
    orig_at = {l["id"]: (l.get("src"), float(l["spans"][0][0])) for l in (S or {}).get("lines") or [] if l.get("kind") == "orig" and l.get("spans")}
    moves, last_still, k = ("in", "left", "out", "right"), None, 0
    for lid, cuts in (M.get("cuts") or {}).items():
        for c in cuts if isinstance(cuts, list) else [cuts]:
            if str(c.get("src") or "").lower().endswith(STILL_EXT):
                k = k + 1 if c.get("src") == last_still else 0
                c.setdefault("move", moves[k % len(moves)])
                last_still = c.get("src")
                continue
            last_still = None
            ss = c.get("ss")
            if ss is None and lid in orig_at:            # 원음 컷 = 그 줄 원음 구간 시작 + at
                ss = orig_at[lid][1] + float(c.get("at") or 0)
                c.setdefault("src", orig_at[lid][0])
            src = str(c.get("src") or "")
            if src not in origin_dims or ss is None:
                continue
            ss = float(ss)
            s = shot_at(shots_by_src.get(src.rsplit(".", 1)[0]) or [], ss)
            if not s:
                continue
            c["max"] = round(s["b"] - ss, 3)
            if isinstance(c.get("crop"), list) and len(c["crop"]) == 4:
                continue
            if not ar or str(c.get("face") or "").strip() in NO_FACE:
                continue
            sw, sh = origin_dims[src]
            cw = min(sw, int(round(sh * ar)))
            fx = s["cx"] * sw if s.get("cx") is not None else sw / 2
            crop = [max(0, min(sw - cw, int(round(fx - cw / 2)))), 0, cw, sh]
            boxes = [[b[0] * sw, b[1] * sh, b[2] * sw, b[3] * sh] for b in s.get("text") or []]
            c["crop"] = avoid_text(crop, boxes, fx, sw, sh, ar) if boxes else crop
            c["center"] = "주인공"
    return M


def fix_crop_units(M: dict, dims: dict) -> list[str]:
    """crop 단위 바로잡기(판단 주인) — 크롭은 원본 픽셀 정수. 판정 답이 0~1 비율로 적으면(샷 표 글자 상자가 비율이라 헷갈림, 10-21 성시경 2차:
    crop=0.45:0.8:0.275:0 → ffmpeg 실패) 그 파일 크기로 픽셀로 바꾸고, 화면 밖은 안으로 넣는다. dims = {파일 이름: [가로, 세로]}. 바꾼 것을 돌려준다."""
    out = []
    for lid, cuts in (M.get("cuts") or {}).items():
        for c in cuts if isinstance(cuts, list) else [cuts]:
            cr, src = c.get("crop"), str(c.get("src") or "")
            if not (isinstance(cr, list) and len(cr) == 4 and all(isinstance(v, (int, float)) for v in cr)) or src not in dims:
                continue
            sw, sh = dims[src]
            if not (sw and sh):
                continue
            x, y, w, h = [float(v) for v in cr]
            if max(x, y, w, h) <= 1.0:
                x, y, w, h = x * sw, y * sh, w * sw, h * sh
            w, h = max(2.0, min(w, sw)), max(2.0, min(h, sh))
            x, y = max(0.0, min(x, sw - w)), max(0.0, min(y, sh - h))
            new = [int(round(x)), int(round(y)), int(round(w)) // 2 * 2, int(round(h)) // 2 * 2]
            if new != cr:
                out.append(f"{lid}: crop {cr} → {new}")
                c["crop"] = new
    return out


PRODUCT_TALK = {   # 제품을 어떻게 찾았나 → 대본이 제품을 말하는 법(사장님 10-21)
    "exact": "원본 화면의 포장과 같은 제품이다 — '○○가 쓰는 그 제품'으로 말해도 된다.",
    "named": "원본 화면엔 상표가 안 보여 포털·유튜브 글로 이름을 찾았다 — 근거 글이 가리키는 만큼만 말한다(지어 붙이지 않는다).",
    "alt": ("같은 제품을 못 찾아 쿠팡에서 같은 종류 중 후기 많고 좋은 제품을 골랐다. ★대본에 이 사실을 말한다 — 예: '영상 보고 쿠팡에서 찾아봤는데 똑같은 건 없어서 "
            "후기 제일 많은 걸로 써 봤는데 좋더라'. ★이 제품을 연예인이 쓴다고 말하지 마라(연예인이 쓴 건 '이런 ○○'까지만)."),
}
