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
    return "\n".join(f"#{s['i']} {s['a']:.2f}~{s['b']:.2f} ({s['b'] - s['a']:.1f}초) {s.get('who')}{' 제품' if s.get('product') else ''} {s.get('desc', '')}"
                     for s in shots or [])


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


def fill_shot_max(M: dict, S: dict | None, origin_dims: dict, shots_by_src: dict, ar: float | None) -> dict:
    """원본 컷마다 샷 표로 두 칸을 채운다(판단 주인 — 집 PC 에선 손으로 적던 칸):
    ① max = 그 샷 끝 − ss — 렌더러의 '컷이 원본 샷보다 길다' 검사가 다른 출연자로 넘어가는 컷을 잡게 한다
    ② 주인공 컷(face)은 크롭을 **주인공 얼굴 가운데**로 좌우 이동(사장님 10-21 "등장인물 주인공이 가운데 정렬되게") — 위아래(자막 피하기)는 그대로.
       'face'(자동 얼굴 크롭 = 가장 큰 얼굴)는 다른 출연자에 맞춰질 수 있어 숫자 크롭(높이 전체, 창 비율 ar)으로 바꾼다.
    origin_dims = {파일 이름: [가로, 세로]} (PC 가 잰 값)."""
    orig_at = {l["id"]: (l.get("src"), float(l["spans"][0][0])) for l in (S or {}).get("lines") or [] if l.get("kind") == "orig" and l.get("spans")}
    for lid, cuts in (M.get("cuts") or {}).items():
        for c in cuts if isinstance(cuts, list) else [cuts]:
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
            if s.get("cx") is None or str(c.get("face") or "").strip() in NO_FACE:
                continue
            sw, sh = origin_dims[src]
            crop = c.get("crop")
            if not isinstance(crop, list) or len(crop) != 4:
                if not ar:
                    continue
                cw = min(sw, int(round(sh * ar)))
                crop = [0, 0, cw, sh]
            x = int(round(s["cx"] * sw - crop[2] / 2))
            c["crop"] = [max(0, min(sw - int(crop[2]), x)), int(crop[1]), int(crop[2]), int(crop[3])]
            c["center"] = "주인공"
    return M


PRODUCT_TALK = {   # 제품을 어떻게 찾았나 → 대본이 제품을 말하는 법(사장님 10-21)
    "exact": "원본 화면의 포장과 같은 제품이다 — '○○가 쓰는 그 제품'으로 말해도 된다.",
    "named": "원본 화면엔 상표가 안 보여 포털·유튜브 글로 이름을 찾았다 — 근거 글이 가리키는 만큼만 말한다(지어 붙이지 않는다).",
    "alt": ("같은 제품을 못 찾아 쿠팡에서 같은 종류 중 후기 많고 좋은 제품을 골랐다. ★대본에 이 사실을 말한다 — 예: '영상 보고 쿠팡에서 찾아봤는데 똑같은 건 없어서 "
            "후기 제일 많은 걸로 써 봤는데 좋더라'. ★이 제품을 연예인이 쓴다고 말하지 마라(연예인이 쓴 건 '이런 ○○'까지만)."),
}
