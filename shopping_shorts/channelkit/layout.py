# -*- coding: utf-8 -*-
"""줄 배치 — 글자를 보존하며 줄만 나눈다. 판정(lint)과 분리 (아스트라 (1): "검사는 데이터를 고치지 않는다"와 충돌 방지).

외부 사례는 클라가 보낸 lines를 버리고 서버 함수로 다시 만든다(8편 문서 §4). 우리도 LLM lines를 버린다.
정책(POLICY): 한 줄에 들어가면 1줄 / 안 들어가면 어절 경계에서 2줄, 픽셀 최대폭이 가장 작은 분할, 동률이면 윗줄이 긴 쪽
             (실측: '출발이 1시간 / 늦어졌다', '박수홍은 / 내리겠다 했다', '사과보다 / 복귀가 빨랐다')
             2줄로도 안 들어가면 배치 실패 → lint가 "글자를 줄이거나 두 카드로 쪼개라"로 반려.
"""
import re

from . import spec, measure


def fits(style, text, fonts_dir=None):
    """100%와 108%(등장 순간) 둘 다 화면 안인가. 외곽선 포함 실제 경계."""
    (l1, r1), (l2, r2) = measure.edges([(style, text, 100), (style, text, 108)], fonts_dir)
    x = spec.BODY_X
    return (x + l1 >= 0 and x + r1 <= spec.CANVAS_W and x + l2 >= 0 and x + r2 <= spec.CANVAS_W), \
           {"left100": x + l1, "right100": x + r1, "left108": x + l2, "right108": x + r2}


def candidates(text):
    words = text.split()
    if len(words) < 2:
        return []
    return [(" ".join(words[:k]), " ".join(words[k:])) for k in range(1, len(words))]


_ASCII = re.compile(r"[A-Za-z0-9%.]")


def proxy_width(style, text, fonts_dir=None):
    """서버 줄나눔 판정용 폭 — 숫자·영문을 한글 한 글자('가') 폭으로 센 잉크 폭.
    실측(135컷): 1줄↔2줄 경계가 잉크 폭 ≈700px인데, 678~695px인데도 2줄인 4건이 전부 숫자·영문 포함
    ('부부가 SNS를', '깊이 20미터', '승용차 4800대', '그중 1만2천은') → 서버는 숫자·영문을 한글 폭으로 세는 것으로 보인다."""
    font, _file, size = spec.STYLE_FONT[style]
    return measure.ink_width(font, size, _ASCII.sub("가", text), fonts_dir)


def break_lines(style, text, fonts_dir=None):
    """→ (lines, info). lines가 None이면 2줄로도 못 넣는다."""
    ok, info = fits(style, text, fonts_dir)
    pw = proxy_width(style, text, fonts_dir)
    if ok and pw <= spec.POLICY_LINE_SPLIT_PX:
        return [text], {"mode": "1line", "proxy_px": pw, **info}
    cands = candidates(text)
    if not cands:
        return None, {"mode": "fail", "why": "어절이 하나라 나눌 수 없다", **info}
    # 후보 전부를 한 번에 재서 ffmpeg 1회
    items = []
    for a, b in cands:
        items += [(style, a, 108), (style, b, 108)]
    eg = measure.edges(items, fonts_dir)
    best = None
    for i, (a, b) in enumerate(cands):
        la, ra = eg[2 * i]; lb, rb = eg[2 * i + 1]
        wa, wb = ra - la, rb - lb
        inside = all(spec.BODY_X + l >= 0 and spec.BODY_X + r <= spec.CANVAS_W for l, r in ((la, ra), (lb, rb)))
        if not inside:
            continue
        key = (max(wa, wb), -wa)            # 최대폭 최소, 동률이면 윗줄이 긴 쪽
        if best is None or key < best[0]:
            best = (key, [a, b])
    if best is None and min_scale():
        # 두 줄 우선(사장님 11-04 "아주 긴 문장 아니면 가능한 두 줄로") — 넘치는 만큼 이 컷 글자를 줄인다(하한 POLICY_MIN_FONT_SCALE)
        k = min(range(len(cands)), key=lambda i: max(_w(eg, i)))
        sc = fit_scale(style, list(cands[k]), fonts_dir)
        if sc >= min_scale():
            return list(cands[k]), {"mode": "2lines_shrunk", "fs_scale": sc}
    if best is None:
        more = _break_more(style, text, fonts_dir)
        if more:
            return more, {"mode": f"{len(more)}lines"}
        return None, {"mode": "fail", "why": f"{max_lines()}줄로도 화면에 안 들어간다", **info}
    return best[1], {"mode": "2lines"}


def _w(eg, i):
    (la, ra), (lb, rb) = eg[2 * i], eg[2 * i + 1]
    return (ra - la, rb - lb)


def min_scale():
    """두 줄을 지키려고 글자를 줄일 수 있는 하한(spec.POLICY_MIN_FONT_SCALE). 없으면 0 = 줄이지 않는다(원본 뇌전구)."""
    return float(getattr(spec, "POLICY_MIN_FONT_SCALE", 0) or 0)


def fit_scale(style, lines, fonts_dir=None):
    """줄들이 108% 등장 순간에도 화면 안에 들도록 하는 글자 비율(1 이하). an8 가운데 정렬이라 폭이 비율대로 준다."""
    eg = measure.edges([(style, ln, 108) for ln in lines], fonts_dir)
    s = 1.0
    for l, r in eg:
        if r > 0 and spec.BODY_X + r > spec.CANVAS_W:
            s = min(s, (spec.CANVAS_W - spec.BODY_X) / r)
        if l < 0 and spec.BODY_X + l < 0:
            s = min(s, spec.BODY_X / -l)
    return round(s * 0.98, 3) if s < 1.0 else 1.0


def max_lines():
    """한 컷 최대 줄 수 — 채널 규격(spec.POLICY_MAX_LINES). 원본 뇌전구(9월 실측)는 2줄,
    지금 볼케이노 형식(15컷·긴 문장)은 3~4줄(11-04 천원중국빵 편 sub.ass: y 1271·1358·1445 = 87 간격 3줄)."""
    return int(getattr(spec, "POLICY_MAX_LINES", 2) or 2)


def _break_more(style, text, fonts_dir=None):
    """2줄로 안 들어갈 때 3줄 이상(최대 max_lines()) — 어절 경계, 줄마다 108% 등장 순간까지 화면 안,
    가장 넓은 줄이 가장 좁은 분할. 줄 수는 적을수록 먼저. → lines 또는 None"""
    import itertools
    words = text.split()
    for k in range(3, max_lines() + 1):
        if len(words) < k:
            return None
        splits = [[" ".join(words[a:b]) for a, b in zip((0,) + cut, cut + (len(words),))]
                  for cut in itertools.combinations(range(1, len(words)), k - 1)]
        items = [(style, ln, 108) for s in splits for ln in s]
        eg = measure.edges(items, fonts_dir)
        best, pos = None, 0
        for s in splits:
            es = eg[pos:pos + k]; pos += k
            if not all(spec.BODY_X + l >= 0 and spec.BODY_X + r <= spec.CANVAS_W for l, r in es):
                continue
            key = (max(r - l for l, r in es), [-(r - l) for l, r in es])   # 최대폭 최소, 동률이면 윗줄이 긴 쪽
            if best is None or key < best[0]:
                best = (key, s)
        if best:
            return best[1]
    return None


def layout_groups(groups, fonts_dir=None):
    """groups[{text,color,...}] → 같은 리스트에 lines를 채운 새 리스트 + 실패 목록. 원본은 손대지 않는다."""
    out, fails = [], []
    for i, g in enumerate(groups):
        given = g.get("lines") if getattr(spec, "POLICY_KEEP_SCRIPT_LINES", False) else None
        if given and _given_ok(g["color"], g["text"], given, fonts_dir):
            ng = dict(g, lines=list(given)); ng.pop("fs_scale", None)
            out.append(ng)                              # 사장님이 컨펌한 줄나눔 그대로(관제 322)
            continue
        if given and min_scale() and "".join(given).replace(" ", "") == g["text"].replace(" ", "")                 and 1 <= len(given) <= max_lines():
            sc = fit_scale(g["color"], list(given), fonts_dir)
            if sc >= min_scale():                       # 컨펌한 줄이 넘치면 그 컷 글자만 줄여서 그대로 쓴다
                out.append(dict(g, lines=list(given), fs_scale=sc))
                continue
        lines, info = break_lines(g["color"], g["text"], fonts_dir)
        ng = dict(g)
        if lines is None:
            fails.append({"where": f"groups[{i}]", "found": g["text"], "why": info.get("why")})
            ng["lines"] = [g["text"]]
        else:
            ng["lines"] = lines
            ng.pop("fs_scale", None)
            if info.get("fs_scale"):
                ng["fs_scale"] = info["fs_scale"]
        out.append(ng)
    return out, fails


def _given_ok(style, text, lines, fonts_dir=None):
    """확정 대본의 줄: 글자는 그대로(띄어쓰기만 다름 허용)·줄 수 한도 안·줄마다 108% 등장 순간까지 화면 안."""
    if "".join(lines).replace(" ", "") != text.replace(" ", "") or not (1 <= len(lines) <= max_lines()):
        return False
    eg = measure.edges([(style, ln, 108) for ln in lines], fonts_dir)
    return all(spec.BODY_X + l >= 0 and spec.BODY_X + r <= spec.CANVAS_W for l, r in eg)
