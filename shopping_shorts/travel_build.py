"""여행형 제작 — 숙소 상세(travel_source.fetch) → 사진 7장 → 세로 시작 화면 → Veo 클립 → 사진별 대본 한 줄 → 렌더 계획 (관제 239).

강의 6편의 공식(channel/strategy/여행쇼핑쇼츠_프로그램설계.md)을 판단 함수로 옮겼다. 이 파일이 주인인 판단:
  · judge_photos  사진마다 종류·글자/간판·사람·화려함·설명 (비전 판정 1회 = 사진 12장 격자 한 장)
  · pick7         7장 고르기 = 물놀이 3·객실 2·시그니처 2, 글자·사람 사진 제외, 첫 컷 = 가장 화려한 물놀이
  · start_frame   가로 사진 → 720x1280 세로 시작 화면(Veo 입력)
  · write_script  고른 순서의 사진마다 한 줄 — 컷 = 문장이 처음부터 짝지어진다(번개쇼츠 '맞는 컷 없으면 문장 삭제'를 원천 차단)
  · script_issues 대본 금지 검사(숙소 이름·가격 숫자·지역명·길이) — 렌더 전 관문
  · build_plan    줄 i = 클립 s{i}, 클립 4초를 줄 길이에 맞춰 배속(sync_speed ≤ 2.0)
렌더·캡컷은 기존 video_assemble.assemble / capcut_draft.assemble_draft_folder 를 그대로 쓴다(판단 두 벌 금지).
표기(광고·AI 콘텐츠·출처)는 deco_for → video_assemble.disclosure_* 가 그린다.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

KIND_WATER = ("water_aerial", "water", "onsen", "bath")
KIND_ROOM = ("room",)
JUDGE_KINDS = ("water_aerial", "water", "onsen", "bath", "room", "view", "exterior", "lobby", "restaurant", "other")
GRID_N = 12                       # 격자 한 장에 사진 12장(4x3)

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"photos": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "n": {"type": "integer"},
            "kind": {"type": "string", "enum": list(JUDGE_KINDS)},
            "has_text": {"type": "boolean"},
            "has_people": {"type": "boolean"},
            "wow": {"type": "integer"},
            "desc_ko": {"type": "string"},
            "desc_en": {"type": "string"},
        },
        "required": ["n", "kind", "has_text", "has_people", "wow", "desc_ko", "desc_en"]}}},
    "required": ["photos"],
}

_JUDGE_PROMPT = (
    "숙소 예약 사이트의 공식 사진 격자다. 칸마다 왼쪽 위에 번호가 있다. 칸마다 판정해 JSON 으로 답해라.\n"
    "kind: water_aerial(위에서 내려다본 수영장·풀) / water(수영장·인피니티풀·워터파크) / onsen(노천탕·스파·자쿠지) / "
    "bath(실내 욕조·욕실) / room(객실·침대) / view(창밖 풍경·바다·산 뷰) / exterior(건물 외관) / lobby(로비·복도·라운지) / "
    "restaurant(식당·카페·조식) / other\n"
    "has_text: 간판·로고·숙소 이름·큰 글자가 읽히게 보이면 true (작은 안내판·TV 화면도 true)\n"
    "has_people: 사람·얼굴·몸이 보이면 true\n"
    "wow: 쇼츠 첫 화면으로 시선을 끄는 정도 1~5 (야경 수영장·탁 트인 뷰는 높게, 평범한 복도·욕실 소품은 낮게)\n"
    "desc_ko: 한국어 한 줄 묘사(보이는 것만, 지어내지 마라) / desc_en: 같은 내용 영어 한 줄"
)


# ── 사진 판정 ─────────────────────────────────────────────────────────────────
def _load(p):
    from PIL import Image
    return Image.open(p).convert("RGB")


def make_grid(paths, out_path, cell=(384, 216)):
    """사진 여러 장을 번호 붙인 격자 한 장으로(4열). 비전 판정 1회에 12장을 보낸다."""
    from PIL import Image, ImageDraw, ImageOps
    cols = 4
    rows = (len(paths) + cols - 1) // cols
    g = Image.new("RGB", (cols * cell[0], rows * cell[1]), (0, 0, 0))
    d = ImageDraw.Draw(g)
    for i, p in enumerate(paths):
        im = ImageOps.fit(_load(p), cell)
        x, y = (i % cols) * cell[0], (i // cols) * cell[1]
        g.paste(im, (x, y))
        d.rectangle((x, y, x + 34, y + 26), fill=(0, 0, 0))
        d.text((x + 6, y + 4), str(i + 1), fill=(255, 255, 0))
    g.save(out_path, quality=88)
    return str(out_path)


def judge_photos(paths, work, call=None):
    """사진 경로 목록 → [{path, kind, has_text, has_people, wow, desc_ko, desc_en}]. 12장씩 격자로 판정."""
    if call is None:
        from shopping_shorts.edit_plan import _vault_call_image as call
    out = []
    for gi in range(0, len(paths), GRID_N):
        chunk = paths[gi:gi + GRID_N]
        grid = make_grid(chunk, Path(work) / ("grid_%02d.jpg" % (gi // GRID_N)))
        got = call(_JUDGE_PROMPT, _JUDGE_SCHEMA, grid) or {}
        by_n = {int(x.get("n", 0)): x for x in (got.get("photos") or []) if isinstance(x, dict)}
        for i, p in enumerate(chunk, 1):
            x = by_n.get(i)
            if not x:
                continue                     # 판정 못 받은 사진은 쓰지 않는다(모르는 사진을 고르지 않는다)
            out.append({"path": str(p), "kind": x.get("kind") if x.get("kind") in JUDGE_KINDS else "other",
                        "has_text": bool(x.get("has_text")), "has_people": bool(x.get("has_people")),
                        "wow": int(x.get("wow") or 0), "desc_ko": x.get("desc_ko") or "", "desc_en": x.get("desc_en") or ""})
    return out


def _same(a, b):
    """설명이 거의 같으면 같은 장면(중복) — phash 말고 설명 겹침으로(메모리 reference_scene_dup_by_desc_not_phash)."""
    wa, wb = set(a["desc_ko"].split()), set(b["desc_ko"].split())
    return bool(wa) and bool(wb) and len(wa & wb) / max(1, min(len(wa), len(wb))) >= 0.8


def pick7(judged):
    """물놀이 3 · 객실 2 · 시그니처 2 → 7장, 순서 = [가장 화려한 물놀이, 물놀이, 시그니처, 객실, 시그니처, 객실, 물놀이].
    글자·간판·사람이 보이는 사진은 뺀다(이름이 보이면 댓글로 물을 이유가 없고, Veo 가 글자를 본뜬다).
    칸이 모자라면 남은 사진 중 화려한 순으로 채우고 'short' 에 무엇이 모자랐는지 남긴다."""
    ok = [j for j in judged if not j["has_text"] and not j["has_people"]]
    ok.sort(key=lambda j: -j["wow"])
    chosen = []

    def take(pred, n):
        got = []
        for j in ok:
            if len(got) >= n:
                break
            if j in chosen or not pred(j) or any(_same(j, c) for c in chosen):
                continue
            chosen.append(j)
            got.append(j)
        return got

    water = take(lambda j: j["kind"] in KIND_WATER, 3)
    room = take(lambda j: j["kind"] in KIND_ROOM, 2)
    sig = take(lambda j: j["kind"] not in KIND_WATER + KIND_ROOM, 2)
    short = {k: n - len(v) for k, n, v in (("water", 3, water), ("room", 2, room), ("signature", 2, sig)) if len(v) < n}
    fill = take(lambda j: True, 7 - len(chosen))
    # 첫 컷 = 가장 화려한 물놀이(위에서 내려다본 수영장이면 더 좋다)
    water.sort(key=lambda j: (-(j["kind"] == "water_aerial"), -j["wow"]))
    seq = [*water[:2], *sig[:1], *room[:1], *sig[1:2], *room[1:2], *water[2:3], *fill]
    return {"photos": seq[:7], "short": short}


# ── 세로 시작 화면 ────────────────────────────────────────────────────────────
def start_frame(src, out_png, size=(720, 1280)):
    """가로 사진 → 세로 시작 화면. 원본 높이가 충분하면(≥ 960) 가운데를 9:16 으로 자르고,
    낮으면 사진을 폭에 맞춰 가운데 두고 위아래를 같은 사진 흐림으로 채운다. 반환: (경로, 방식)."""
    from PIL import Image, ImageFilter, ImageOps
    im = _load(src)
    w, h = size
    if im.height >= 960:
        ImageOps.fit(im, size, centering=(0.5, 0.5)).save(out_png)
        return str(out_png), "crop"
    bg = ImageOps.fit(im, size).filter(ImageFilter.GaussianBlur(28))
    fg = im.resize((w, int(im.height * w / im.width)))
    bg.paste(fg, (0, (h - fg.height) // 2))
    bg.save(out_png)
    return str(out_png), "blur"


# ── 대본 ─────────────────────────────────────────────────────────────────────
TYPES = ("안티/반전형", "감각/공간 몰입형", "타깃 결핍/혜택형")       # 강의 3유형
# 길이 목표 — 강의 완성본 18~20초. 글자 수는 목소리 속도에서 정한다(미나 1.35배 = 초당 6.87자, voice_presets 주석 실측).
TARGET_SEC = (20.0, 25.5)      # 여행 스타일 카드 '길이': 140~175자 ≈ 20~25초(미나 1.35배)
CHARS_PER_SEC = 6.87


def char_range(n_lines=7):
    """→ (전체 최소, 전체 최대, 줄 최소, 줄 최대) 글자 수."""
    lo, hi = int(TARGET_SEC[0] * CHARS_PER_SEC), int(TARGET_SEC[1] * CHARS_PER_SEC)
    return lo, hi, max(8, lo // n_lines - 4), hi // n_lines + 6
_SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {"versions": {"type": "array", "items": {
        "type": "object",
        "properties": {"type": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}},
        "required": ["type", "lines"]}}},
    "required": ["versions"],
}


# 강의 6편 화면에서 그대로 옮긴 실제 대본(channel/strategy/여행쇼핑쇼츠_강의분석) — 문장 리듬·훅·CTA 의 본보기.
#   ★본보기는 '말투·구조'만 배운다. 시설·사실은 반드시 이번 사진에서만 가져온다(지어낸 사실 금지).
REFERENCE_SCRIPTS = (
    ("안티/반전형", "비행기 표 당장 취소하세요. 국내에 이런 곳이 숨어있을 줄은 상상도 못 했거든요. "
                   "머리 위로 거대한 고래가 헤엄치는 디지털 바다를 걷는 기분이에요. "
                   "날씨 상관없이 유리 돔 천장 아래서 열대 유수풀과 야외 자쿠지까지 싹 다 누릴 수 있다니까요. "
                   "올여름 방 다 차기 전에 무조건 저장부터 해두세요!"),
    ("안티/반전형", "여기 진짜 나만 알고 싶어서 숨겨두려다 겨우 가져왔어요. 비싼 돈 주고 유명 해외 휴양지 갈 필요 전혀 없더라고요. "
                   "통창 너머로 펼쳐지는 미친 뷰에 고급스러운 프라이빗 야외 욕조까지, 숙소 문 열자마자 입이 떡 벌어지는 스케일인데 "
                   "가격까지 듣고 나면 소름 돋을지도 몰라요. 더 소문나서 예약 막히기 전에 일단 저장부터 해두세요!"),
    ("감각/공간 몰입형", "당장 물멍하러 떠나고 싶은 분들, 여긴 꼭 가보셔야 해요. 햇살이 쏟아지는 통유리 돔 아래, "
                       "찰랑거리는 푸른 물소리가 온몸을 감싸요. 어딘지 궁금하시다면 댓글에 '물멍' 남겨주시면 조용히 알려드릴게요."),
    ("타깃 결핍/혜택형", "요즘 업무 스트레스로 지친 사람, 센스 있는 숙소 찾는 연인이라면 집중! 멀리 떠날 필요 없이 온전한 우리만의 아지트에서 "
                        "탁 트인 뷰 바라보며 즐기는 야외 스파와 감성 가득한 불멍까지, 몸만 가면 완벽한 휴식이 완성되는 역대급 숙소예요. "
                        "일정 다 차서 후회하지 말고 지금 저장해뒀다가 꼭 방문해보세요!"),
    ("감각/공간 몰입형", "아무것도 안 하고 조용히 쉬고 싶을 땐 여기가 딱이에요. 자연 속 노천 자쿠지에서 따뜻하게 피로를 풀며 가만히 있으면 "
                       "근심 걱정이 싹 사라지는 곳이에요. 이런 분위기 좋아하시면 꼭 저장해 두세요."),
)

# 유형별 설계(강의 3유형 + 실측 반응: 좋아요보다 댓글이 5~9배 = 댓글 → DM 구조)
TYPE_GUIDE = {
    "안티/반전형": "1줄 = 상식을 뒤집는 명령·고백형 훅에 화면 1의 핵심을 붙인다('비행기 표 취소하세요, 이 풀 보고 나면요'). "
                  "해외·비싼 곳과의 비교는 2줄에 화면 2 묘사와 함께. 가운데 = 화면마다 가장 놀라운 디테일 하나씩. "
                  "끝에서 두 번째 = 가격 궁금증(숫자 없이 '가격 듣고 나면 놀라요'). ",
    "감각/공간 몰입형": "1줄 = 감각을 부르는 호명('당장 물멍하러 떠나고 싶은 분들'). 가운데 = 소리·빛·온도·촉감 묘사로 그 공간에 들어간 느낌. "
                     "과장보다 장면이 그려지는 구체어. ",
    "타깃 결핍/혜택형": "1줄 = 대상 호명 + 결핍('요즘 지친 직장인이라면 집중!'). 가운데 = 그 사람이 얻는 혜택을 화면에 보이는 시설로 하나씩. "
                       "끝에서 두 번째 = '몸만 가면 된다' 식 마무리. ",
}


_DESCRIBE_SCHEMA = {
    "type": "object",
    "properties": {"desc_ko": {"type": "string"}, "desc_en": {"type": "string"},
                   "visible": {"type": "array", "items": {"type": "string"}},
                   "time_of_day": {"type": "string"}},
    "required": ["desc_ko", "desc_en", "visible", "time_of_day"],
}


def describe_picks(picks, call=None):
    """고른 7장은 원본 해상도로 한 장씩 다시 본다 — 격자(작은 칸) 판정의 설명이 틀린다
    (실측 2026-10-19: 격자는 '해질녘 바다', 원본은 '낮 호수'). 대본은 이 설명만 쓴다."""
    if call is None:
        from shopping_shorts.edit_plan import _vault_call_image as call
    out = []
    for p in picks:
        got = call("숙소 공식 사진 한 장이다. 보이는 것만 적어라(추측 금지). desc_ko: 한국어 한 줄 묘사, desc_en: 영어 한 줄, "
                   "visible: 보이는 시설·물건 목록(한국어 명사), time_of_day: 낮/해질녘/밤/알 수 없음.",
                   _DESCRIBE_SCHEMA, p["path"]) or {}
        q = dict(p)
        if got.get("desc_ko"):
            q.update(desc_ko=got["desc_ko"], desc_en=got.get("desc_en") or p["desc_en"],
                     visible=got.get("visible") or [], time_of_day=got.get("time_of_day") or "")
        out.append(q)
    return out


def script_prompt(picks, detail, feedback=None):
    rows = "\n".join("화면 %d: %s%s%s" % (
        i + 1, p["desc_ko"], (" (보이는 것: " + ", ".join(p.get("visible") or []) + ")") if p.get("visible") else "",
        (" [" + p["time_of_day"] + "]") if p.get("time_of_day") and p["time_of_day"] != "알 수 없음" else "")
        for i, p in enumerate(picks))
    fac = ", ".join((detail or {}).get("facilities") or [])
    refs = "\n".join("- [%s] %s" % r for r in REFERENCE_SCRIPTS)
    _lr = char_range(len(picks))
    guide = "\n".join("- %s: %s" % kv for kv in TYPE_GUIDE.items())
    return (
        "너는 조회수가 터진 여행 숙소 쇼츠 대본만 써 온 작가다. 이 숙소로 대본 3개(유형마다 1개)를 써라.\n\n"
        "[본보기 — 실제로 잘 된 대본. 말투·리듬·훅·마무리만 배워라. 시설·사실은 베끼지 마라]\n" + refs + "\n\n"
        "[유형별 설계]\n" + guide + "\n\n"
        "[화면] 아래 화면이 이 순서로 한 장씩 나온다. 유형마다 **정확히 %d줄**, 줄 i 는 화면 i 위에서 읽힌다.\n%s\n\n"
        "[반드시 지킬 것]\n"
        "1. 줄 i 는 화면 i 에 실제로 보이는 것만 말한다. 보이지 않는 시설·서비스·사실(조식 포함, 무료 제공 등)을 지어내지 마라.\n"
        "2. 숙소 이름·지역명·가격 숫자·할인율·성급을 쓰지 마라 — 궁금해서 댓글을 남기게 만드는 것이 목적이다.\n"
        "3. 직접 다녀온 척하지 마라('다녀왔는데', '좋았고요', '먹어봤는데' 금지). 보이는 것을 생생하게 소개하는 말투.\n"
        "4. 마지막 줄 = 댓글 유도. 예: \"어딘지 궁금하면 댓글에 '정보' 남겨 주세요\" (저장 유도는 그 앞줄에 붙여도 된다).\n"
        "5. 한 줄 %d~%d자, 전체 %d~%d자(공백 포함) — 읽으면 18~20초다. 짧고 센 문장, 해요체, 한 줄 = 한 호흡.\n"
        "6. 세 유형의 첫 줄은 서로 완전히 달라야 한다. 본보기 첫 줄을 그대로 쓰지 마라.\n"
        "7. 줄을 밀지 마라 — 훅·비교·가격 궁금증도 그 줄의 화면 내용을 함께 담는다(화면 i 와 상관없는 줄 금지). "
        "시간대([낮]/[밤])도 화면과 맞춘다.\n"
        "참고 시설 목록(그 시설이 보이는 화면에서만 써라): %s"
        % (len(picks), rows, _lr[2], _lr[3], _lr[0], _lr[1], fac or "없음")
        + (("\n\n[지난번 원고의 문제 — 반드시 고쳐라]\n" + "\n".join("- " + f for f in feedback)) if feedback else ""))


_PRICE_RE = re.compile(r"\d[\d,]*\s*(원|만\s*원|만원|%)|\d+\s*성급")


def script_issues(lines, detail, n_expected=None, style=None):
    """대본 금지 검사(렌더 전 관문). 문제 목록(빈 목록 = 통과).
    style 이 화자 창작을 허용하는 채널 말투(STYLES[..]["persona"])면 '가 본 척' 검사는 끄고 그 채널 어미 검사를 켠다."""
    issues = []
    persona = bool((STYLES.get(style or "") or {}).get("persona"))
    if style:
        issues += style_ending_issues(lines, style)
        if (STYLES.get(style) or {}).get("story_gate"):
            issues += story_issues(lines)
    text = " ".join(lines or [])
    if n_expected and len(lines or []) != n_expected:
        issues.append("줄 수 %d (기대 %d)" % (len(lines or []), n_expected))
    for w in (() if persona else ("다녀왔", "좋았고요", "먹어봤", "묵어봤", "가봤는데")):
        if w in text:
            issues.append("가 본 척: " + w)
    if _PRICE_RE.search(text):
        issues.append("가격·등급 숫자: " + _PRICE_RE.search(text).group(0))
    name = (detail or {}).get("name") or ""
    _kind_words = ("호텔", "리조트", "펜션", "풀빌라", "스테이", "레지던스", "모텔", "Hotel", "Resort")
    for tok in re.findall(r"[가-힣A-Za-z]{2,}", name):
        # '네스트호텔' 처럼 붙은 이름은 꼬리(호텔·리조트…)를 떼고 본다 — 대본엔 '네스트'만 나와도 이름이다(시험이 잡은 결함)
        core = re.sub("(" + "|".join(_kind_words) + ")$", "", tok)
        if core in _kind_words or len(core) < 2:
            continue
        if core in text:
            issues.append("숙소 이름: " + core)
    for tok in re.findall(r"[가-힣]{2,}", (detail or {}).get("address") or "")[:3]:
        base = re.sub(r"(특별자치도|특별시|광역시|도|시|군|구|동|읍|면)$", "", tok)
        if len(base) >= 2 and base in text:
            issues.append("지역명: " + base)
    lo, hi, _, _ = char_range(len(lines or []) or 7)
    if not (lo - 10 <= len(text) <= hi + 10):
        issues.append("길이 %d자 ≈ %.1f초(권장 %d~%d자)" % (len(text), len(text) / CHARS_PER_SEC, lo, hi))
    return issues


_LINE_CHECK_SCHEMA = {
    "type": "object",
    "properties": {"checks": {"type": "array", "items": {
        "type": "object",
        "properties": {"v": {"type": "integer"}, "ok": {"type": "boolean"}, "why": {"type": "string"}},
        "required": ["v", "ok"]}}},
    "required": ["checks"],
}


def verify_lines(versions, picks, call=None):
    """줄 i 가 화면 i 사진에 **실제로 보이는 것만** 말하나 — 사진을 직접 보여 주고 되묻는다(렌더 전 관문).
    사진 1장에 세 유형의 i번째 줄을 한꺼번에 묻는다(호출 7번). 반환: {유형: [줄 번호(1부터)·이유]}.
    ★감정·분위기·행동 유도('힐링', '저장해 두세요')는 사실 주장이 아니라 통과. 보이지 않는 시설·소리·서비스만 걸린다."""
    if call is None:
        from shopping_shorts.edit_plan import _vault_call_image as call
    bad = {v.get("type", "?"): [] for v in versions}
    for i, p in enumerate(picks):
        q = "\n".join("%d) %s" % (k + 1, (v.get("lines") or [""] * len(picks))[i] if i < len(v.get("lines") or []) else "")
                      for k, v in enumerate(versions))
        got = call("이 사진 위에 아래 문장이 자막으로 나온다. 문장마다, 사진에 보이지 않는 시설·물건·소리·서비스·사실을 "
                   "말하면 ok=false 와 이유를 적어라. 분위기·감정·추천·행동 유도는 사실 주장이 아니니 ok=true. "
                   "'비행기 표 취소하세요', '해외 갈 필요 없어요' 같은 비유·비교·호명도 사진에 대한 주장이 아니니 ok=true. "
                   "답의 v 는 문장 앞 번호다.\n" + q,
                   _LINE_CHECK_SCHEMA, p["path"]) or {}
        for c in got.get("checks") or []:
            k = int(c.get("v", 0)) - 1
            if 0 <= k < len(versions) and not c.get("ok", True):
                bad[versions[k].get("type", "?")].append("%d줄: %s" % (i + 1, c.get("why") or "사진에 없음"))
    return bad


# ── Claude(오푸스) 창구 — 대본은 사진을 직접 보며 쓰고, 다른 호출이 채점한다 ─────────────────────────
#   왜: 제미나이 대본이 밋밋했고(2026-10-19 네스트호텔 3안: '힐링하세요'·'쉬어가요' 같은 아무 데나 붙는 말) 키 다수 소진.
#   사장님 10-18 "제미나이 쓰지 말고"(칼카피 엔진 claude_cli.py). 방식은 그 파일과 같다: `claude -p`, 표준입력,
#   빈 임시 폴더(프로젝트 폴더면 CLAUDE.md·훅이 붙는다), 그림은 파일로 두고 Read 로 열게 한다.
def claude_call(images, prompt, model="opus", timeout=600):
    """그림 경로 목록 + 프롬프트 → JSON dict(실패하면 RuntimeError, 이유 포함)."""
    import shutil
    import subprocess
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="travel_claude_"))
    try:
        names = []
        for k, p in enumerate(images or []):
            f = d / ("photo_%d.jpg" % (k + 1))
            _load(p).save(f, quality=90)
            names.append(f.name)
        head = ("먼저 Read 도구로 이 폴더의 사진을 순서대로 연다: " + ", ".join(names) + ". 사진에 실제로 보이는 것만 근거로 쓴다.\n\n") if names else ""
        # ★스크립트를 돌리려 하면 승인이 막혀 JSON 대신 설명문이 돌아온다(실측 2026-10-19 "check.py 실행 승인 필요") —
        #   Read 말고는 막고, 글자 수는 머릿속으로 세게 한다.
        full = (head + prompt + "\n\n도구는 Read(사진 열기)만 쓴다. 스크립트 실행·파일 쓰기 금지 — 글자 수는 직접 세라."
                "\n답은 오직 JSON 객체 하나. 앞뒤 설명·마크다운 금지.")
        r = subprocess.run(["claude", "-p", "--model", model, "--output-format", "text", "--allowedTools", "Read",
                            "--disallowedTools", "Bash", "Write", "Edit", "NotebookEdit"],
                           input=full, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=str(d))
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (r.stdout or "").strip())
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise RuntimeError("claude 빈/깨진 답 rc=%s: %s" % (r.returncode, (r.stdout or r.stderr or "")[:200]))
        return json.loads(m.group(0))
    finally:
        shutil.rmtree(d, ignore_errors=True)


JUDGE_CRITERIA = ("훅", "불편→해결", "간접성", "고조", "화면 일치", "댓글 유도")
_JUDGE_PROMPT_SCRIPT = (
    "여행 숙소 쇼츠 대본 후보들을 채점한다. 사진은 화면 1~%d 순서이고, 대본의 줄 i 는 화면 i 위에서 읽힌다.\n"
    "기준(각 1~10, 조회수 터진 인스타 릴스가 8점대): 훅 = 첫 줄에서 손가락이 멈추나(사건·불편·오해로 여나) / "
    "불편→해결 = 구체적인 불편(한 순간의 장면)이 이 숙소에서 사라지는 이야기인가(소개 나열이면 3점 이하) / "
    "간접성 = 이점을 '바다 뷰예요·넓어요'처럼 대놓고 말하지 않고 남의 오해·과거 불편 대비·인물 행동 변화로 보여 주나 / "
    "고조 = '근데 이게 → 이게 대박인 게 → 심지어/소름인 건'처럼 점점 세지나(평평하면 낮게) / "
    "화면 일치 = 숙소 사실(시설·풍경·시간대)이 그 줄 사진에 보이나 — 과거 불편·인물·감정 줄은 사진에 없어도 감점하지 않는다 / "
    "댓글 유도 = 마지막 줄 키워드가 그 이야기의 말이라 남기고 싶나.\n"
    "본보기(실제로 터진 대본 수준 = 8점대): %s\n\n후보:\n%s\n\n"
    "JSON: {\"scores\": [{\"v\": 후보번호, \"훅\": n, \"불편→해결\": n, \"간접성\": n, \"고조\": n, \"화면 일치\": n, \"댓글 유도\": n, "
    "\"bad_lines\": [\"줄번호: 이유\"], \"one_line\": \"한 줄 평\"}]}")


def story_facts_text(detail, limit=2200):
    """숙소 이야기 재료(소개·자주 묻는 질문·리뷰)를 작가·채점자에게 같은 글로 준다 — 한 곳에서 만든다(쓰는 쪽=재는 쪽).
    사진에 없어도 말해도 되는 사실(2026-10-19 사장님 허락). 이름·지역·가격 숫자는 여전히 대본에 쓰지 않는다."""
    f = (detail or {}).get("story_facts") or {}
    parts = []
    if f.get("intro"):
        parts.append("[숙소 소개] " + f["intro"])
    for x in f.get("faq") or []:
        parts.append("[문답] %s → %s" % (x.get("q", ""), x.get("a", "")))
    for r in f.get("reviews") or []:
        parts.append("[실제 후기] " + r)
    return "\n".join(parts)[:limit]


def judge_scripts(versions, picks, call=None, style=None, facts=""):
    """오푸스 채점(5기준) — 쓴 것과 다른 호출이 본다. 반환: {유형: {점수…, total, bad_lines, one_line}}.
    style 이 화자 창작을 허용하는 말투면 그 허용선을 채점자에게도 알린다(쓰는 쪽과 재는 쪽이 다른 규칙이면 안 된다)."""
    call = call or claude_call
    cand = "\n\n".join("%d) [%s]\n%s" % (k + 1, v.get("type", ""), "\n".join("%d. %s" % (i + 1, l) for i, l in enumerate(v["lines"])))
                       for k, v in enumerate(versions))
    prompt = _JUDGE_PROMPT_SCRIPT % (len(picks), REFERENCE_SCRIPTS[1][1], cand)
    st = STYLES.get(style or "")
    if st and st.get("persona"):
        prompt += ("\n\n[이 채널의 창작 허용선] 화자 설정·지인·가족·계기·감상·체감 비유·결과 과장('와이프가 보여줬는데', "
                   "'보는 사람마다 묻더라고요', '말을 잃더라고요')은 이 채널의 결이라 감점하지 마라. 감점은 시설·물건·풍경·시간대가 "
                   "그 화면 사진과 안 맞을 때만. 말투 기준: " + st["guide"][:300])
    if facts:
        prompt += ("\n\n[숙소 사실 — 사진에 없어도 말해도 되는 것] 아래에 있는 사실(사계절 온수 풀·전 객실 발코니·조식·셔틀 등)은 "
                   "그 줄 사진에 안 보여도 화면 일치에서 감점하지 마라. 아래에도 사진에도 없는 사실을 지어내면 감점.\n" + facts)
    got = call([p["path"] for p in picks], prompt) or {}
    out = {}
    for s in got.get("scores") or []:
        k = int(s.get("v", 0)) - 1
        if 0 <= k < len(versions):
            sc = {c: int(s.get(c) or 0) for c in JUDGE_CRITERIA}
            sc.update(total=sum(sc.values()), bad_lines=s.get("bad_lines") or [], one_line=s.get("one_line") or "")
            out[versions[k].get("type", "?")] = sc
    return out


# ── 채널 말투(스타일) — 같은 사진·같은 컷 짝 위에 말투만 갈아 끼운다 ────────────────────────────────
#   근거: channel/homedesignnote/대본설명서/설명서.md (두유노홈디노 원본 49편 실측, 2026-10-16)
#   ★창작 허용선(그 설명서 2판): 화자·지인·가족·계기·극단행동·감상·체감 비유·결과 과장 = 창작 허용(이 채널의 결).
#     근거 필수 = 시설·속성(→ 사진에 보이는 것만)·가격·인기. 그래서 이 말투에선 '가 본 척' 금지를 풀고 사진 검사는 그대로 둔다.
STYLES = {
    "두유노홈디노": {
        "persona": True,
        "endings_own": ("더라고요", "더라구요", "어요", "아요", "세요", "대요", "잖아요", "거든요", "예요", "에요", "해요", "나요", "요"),
        "endings_foreign": ("네요", "는데요", "음", "임", "함", "거"),
        "guide": (
            "말투 = 인스타 '두유노홈디노' 채널. 존댓말 체험담. 어미는 ~더라고요(가장 많이)·~어요·~대요·~잖아요·~거든요·~세요. "
            "~네요·~는데요·~음/임/함 으로 끝내지 마라(남의 어미).\n"
            "★쓰는 순서: ① 먼저 원본처럼 **긴 문장 3개**(문장당 45~55자, 전체 약 150자 — 이 길이에 문장을 4개 넘게 넣으면 짧게 끊긴다)로 이야기를 다 쓴다. 문장 안은 "
            "'~했는데 ~니까 ~어서 ~더라고요'처럼 **이유·계기로** 잇는다. '~하고 ~하고 ~하고', '~하더니 ~하더니' 처럼 줄줄이 나열하지 마라"
            "(원본 이음: 는데 20%·니까 11%·어서 19%, 나열 '고'는 36%뿐). 문장 끝은 더라고요·어요·대요·잖아요·거든요·는 거 있죠를 섞는다. "
            "② 그 글을 자연스러운 쉼에서 정확히 7조각으로 나눠 줄로 낸다 — 조각은 문장 중간에서 끊겨도 되고, 조각 i 가 화면 i 위에서 읽힌다. "
            "문장이 끝나는 조각에는 마침표를 찍는다.\n"
            "[원본 실물 — 말투만 배워라]\n"
            "· 저희 와이프가 벽 코너에 이런걸 해놨는데 보는 사람마다 깜짝 놀라더라구요. 평소에 미니어처 하우스 만들기를 너무 좋아하는데 "
            "그게 세로로 쌓으면 이렇게 할 수 있다면서. 조명까지 달아서 설치해두니까 너무 예쁘더라구요. (600만)\n"
            "· 스탠바이미 사려고 했다가 와이프한테 혼났어요. 전셋집에 집주인이 벽걸이티비 못하게해서 고민했는데 와이프가 이걸로 하면 되지 "
            "왜 돈쓰냐면서 한 소리 하더라고요. … 이거 한번 써보니까 오히려 벽걸이티비보다 편하더라구요. (400만)\n"
            "· 결혼하는 친구가 결혼선물로 이거 사달라고 하더라고요. 요즘 SNS에서 난리 났다는데 가격도 예상보다는 저렴해서 좀 놀랐어요. "
            "… 애기 있는 집들은 빨래하다가 하루 다 가잖아요. (260만)\n"
            "첫 문장 = 주변 사람 계기로 연다: '저희 와이프가 ~ 보여줬는데', '여행 좋아하는 친구가 ~ 하더라고요', "
            "'회사 언니가 ~ 다녀와서 자랑을 하는데'. 또는 고백형('~하려다가 와이프한테 혼났어요').\n"
            "가운데 = 화면마다 보이는 것 + 체감 비유('호텔인데 미술관 같더라고요') + 사회적 반응('보는 사람마다 어디냐고 물어보더라고요'). "
            "말버릇을 1~2번: '보는 사람마다', '심지어 이게', '이거 하나만', '너무 좋아요'.\n"
            "마지막 = 결과 과장 + 댓글 유도('이제 다른 데는 못 가겠더라고요, 어딘지 궁금하면 댓글에 정보 남겨 주세요').\n"
            "화자·지인·계기·감상은 지어내도 되지만, 시설·물건·풍경은 그 화면 사진에 보이는 것만 말한다."),
        "types": ("지인사건형", "고백·체험단정형", "발견·반응형"),
    },
}


# 인스타 스토리형 — 두유노홈디노 말투 위에 '인물·역할 + 중간 사건'을 얹는다(사장님 2026-10-19
#   "가족체험 후회형 등등 스토리가 중간에 들어가고 역할도 들어가고 흥미있게").
#   유형 근거: 두유노 설명서 2판 서사 노드(계기 55%·극단행동 18%·자기위치 22%·체감비유 29%·결과과장 27%·사회반응 51%)
#   + 강의 인스타 예시('네 명이 방 잡고… 침대 자리만 누가 2층 갈지 정하면 싸울 일 없으니').
STORY_TYPES = {
    "가족체험형": "가족 한 명이 주인공(엄마·아빠·아이·시어머니). 계기(생신·첫 여행) → 화면마다 그 사람의 반응·행동 → 끝은 그 사람의 한마디.",
    "후회형": "'여기 모르고 ○○했던 걸 후회했다'로 연다(비싼 해외·다른 숙소). 화면마다 '이걸 몰랐다니' 근거 → 끝은 '진작 올걸'.",
    "커플 갈등·반전형": "남편/남친과 숙소 고르다 티격태격(의심·반대) → 들어가 보니 상대가 먼저 반함 → 끝은 상대의 백기·한마디.",
    "깜짝선물형": "와이프/엄마 몰래 예약 → 들어서는 순간부터 반응이 커진다 → 끝은 눈물·환호 같은 결과 과장.",
    "친구 내기형": "친구들끼리 숙소 고르기 내기·역할 분담(누가 어느 방) → 화면마다 친구들 반응 → 끝은 '다음에도 여기'.",
}
STYLES["인스타 스토리형"] = dict(
    STYLES["두유노홈디노"],
    types=tuple(STORY_TYPES),
    guide=STYLES["두유노홈디노"]["guide"] + (
        "\n[스토리] 대본마다 인물 1~2명(역할: 엄마·남편·친구 등)과 작은 사건이 있다 — 계기(1~2줄) → 사건·갈등·반응이 "
        "화면마다 이어진다(3~5줄) → 반전·결과 과장·인물의 한마디(6줄) → 댓글 유도(7줄). 인물의 행동·반응은 그 화면에 보이는 "
        "시설과 엮는다(예: '엄마가 로비 들어서자마자 이젤 앞에서 사진부터 찍더라고요'). 유형별 설계:\n"
        + "\n".join("- %s: %s" % kv for kv in STORY_TYPES.items())),
)


# ── 말투 실측 자 — 레퍼런스(두유노홈디노 원본 49편 받아쓰기)와 같은 자로 우리 대본을 잰다 ─────────────────
#   실측 2026-10-19(tools/travel/ending_profile.py): 원본 = 문장 4.1개·평균 58자·연결어미/문장 1.71,
#   이음 '고' 36%·'는데' 20%·'니까' 11%·'어서/아서/해서' 19%, 끝 '더라고요/구요' 28%·'어요' 19%·'요' 11%·'세요' 7%·'대요' 5%·'잖아요' 4%.
#   우리 스토리형 첫 5안 = 이음 '고·더니' 75~83%(나열체) · 끝 2종뿐 — 사장님 "어미 자체가 다르잖아"(2026-10-19).
SPEECH_ENDS = ["는 거 있죠", "더라고요", "더라구요", "거든요", "잖아요", "대요", "래요", "세요", "네요", "는데요", "예요", "에요",
               "어요", "아요", "해요", "죠", "요", "다", "음", "임"]
SPEECH_CONNS = ["는데", "은데", "니까", "어서", "아서", "해서", "면서", "다가", "더니", "길래", "고", "며", "지만"]
SPEECH_REF = {"sent_per": 4.1, "sent_len": 57.9, "conn_per_sent": 1.71, "go_deoni_max": 0.5}


def _sentences(text):
    return [s.strip(" '\"") for s in re.split(r"(?<=[.!?])\s+|\n", text or "") if s.strip()]


def _end_of(s):
    t = re.sub(r"[^가-힣 ]+$", "", s).strip()
    return next((e for e in SPEECH_ENDS if t.endswith(e)), "기타")


def _conns_in(s):
    out = []
    for w in re.findall(r"[가-힣]+", s)[:-1]:
        c = next((c for c in SPEECH_CONNS if w.endswith(c) and len(w) > len(c)), None)
        if c:
            out.append(c)
    return out


def lines_text(lines):
    """대본 줄 → 한 글. 줄이 '요·다·죠'로 끝나면 문장 끝(마침표를 안 찍은 대본도 공정하게), 아니면 이어지는 마디."""
    return " ".join((l.strip() + ".") if re.search(r"(요|다|죠)$", l.strip()) else l.strip() for l in lines or [])


def speech_profile(text):
    """한 글(또는 여러 편을 이은 글 목록)의 말투 수치. 레퍼런스와 같은 자."""
    import collections
    texts = text if isinstance(text, list) else [text]
    ends, conns, nsent, lens = collections.Counter(), collections.Counter(), [], []
    for t in texts:
        ss = _sentences(t)
        nsent.append(len(ss))
        for s in ss:
            ends[_end_of(s)] += 1
            lens.append(len(s))
            conns.update(_conns_in(s))
    te, tc, ns = sum(ends.values()) or 1, sum(conns.values()) or 1, sum(nsent) or 1
    return {"sent_per": round(ns / max(1, len(texts)), 2), "sent_len": round(sum(lens) / max(1, len(lens)), 1),
            "conn_per_sent": round(sum(conns.values()) / ns, 2),
            "ends": {k: round(v / te, 3) for k, v in ends.most_common()},
            "conns": {k: round(v / tc, 3) for k, v in conns.most_common()},
            "go_deoni": round((conns["고"] + conns["더니"] + conns["며"]) / tc, 3) if conns else 0.0}


def speech_issues(lines):
    """레퍼런스와 어긋나는 말투 꼴 — 나열체('~고·~더니' 잇기)·문장이 너무 짧음/적음·끝 어미 단조로움."""
    p = speech_profile(lines_text(lines))
    out = []
    if p["go_deoni"] > SPEECH_REF["go_deoni_max"]:
        out.append("말투: 나열체 — '~고·~더니·~며' 이음 %d%%(원본 36%%) → '~는데·~니까·~어서'로 이유를 이어라" % round(p["go_deoni"] * 100))
    if p["sent_per"] < 3 or p["sent_per"] > 6:
        out.append("말투: 문장 %s개(원본 4개 안팎)" % p["sent_per"])
    if p["sent_len"] < 38:
        out.append("말투: 문장 평균 %s자 — 짧게 끊김(원본 58자, 길게 이어 말한다)" % p["sent_len"])
    if len([e for e in p["ends"] if e not in ("세요", "기타")]) < 2:
        out.append("말투: 문장 끝이 단조로움 %s(원본: 더라고요·어요·대요·잖아요·거든요 섞임)" % list(p["ends"]))
    return out


# ── 여행 숙소 인스타형 스타일 카드 — 문서 channel/strategy/여행_대본스타일_카드.md 와 같은 값(문서 = 사람용, 이것 = 기계용) ──
TRAVEL_CARD = {
    # 2판(2026-10-19 사장님 "불편→해결 / 이점을 대놓고 말하지 말고 / 고조연결어 강하게 / 너무 평범") — 전부 대본창고 실측 근거.
    #   실측: tools/travel/escalation_lift.py (인스타 1,417편, 조회수 중앙 43,239)
    "escalation": {   # 고조어 — 그 말을 쓴 편들의 조회수 중앙 / 전체 중앙
        "strong": [("근데 이게", 4.7), ("이게 대박인 게", 4.6), ("소름인 건", 1.6), ("알고 보니", 1.4), ("심지어", 1.4)],
        "weak": [("게다가", 0.75), ("진짜 대박", 0.72), ("대박인 건", 0.76), ("무엇보다", 0.76)],   # 쓰지 않는다
    },
    "hooks": {   # 제목(첫 줄) 틀 사전 — 출처는 문서 표
        "H1": "저 여기 때문에 {인물}한테 등짝 맞을 뻔했어요",                 # 창고 chae2home 631만·295만·235만(혼남 사건)
        "H2": "{인물}이 여기 해외냐고 물어보는 거예요",                        # 오해형 — 창고 '양말 새로 샀냐고'(295만)·'도배 새로 했냐고'(235만)
        "H3": "{인물}이랑 {여행} 갈 때마다 {불편} 때문에 고생했는데",          # 불편 고백 — 창고 '갈 때마다…필수로 챙기는데'(13만)·불편어 첫 80자 1.13배
        "H4": "저 여기 모르고 {다른 선택} 한 거 진짜 후회했어요",            # 창고 68.6만·댓글 3.5만
        "H5": "{인물}이 이 {시설} 사진 합성이라고 우기길래",                 # 의심형(카드 1판 시안 50/60)
        "H6": "{인물} 때문에 진짜 충격먹었어요",                             # 창고 81만
        "H7": "여러분 {상황}이면 비행기 표 당장 취소하세요",                 # 강의 실습 완성본
        "H8": "{전문가} 친구가 여기만은 꼭 가 보라고 하더라고요",            # 창고 46.6만 '5성급 호텔 셰프신데'
    },
    "types": {   # 후킹 유형 = 불편→해결 이야기 설계(인물·사건·회수)
        "혼남 사건형": ("H1", "가족에게 혼날 뻔한 사건(몰래 예약·과소비 오해) → 알고 보니 → 그 가족이 더 좋아함으로 회수"),
        "오해형": ("H2", "남이 해외·비싼 데로 오해(질문) → 사실은 가까운 국내 → 이점을 오해로 보여 줌"),
        "불편 고백형": ("H3", "과거 여행의 구체적 고생 장면 → 이번엔 그 고생이 통째로 사라짐 → 인물 반응"),
        "의심 반전형": ("H5", "인물이 의심·반대 → 먼저 반함 → 백기 한마디"),
        "후회형": ("H4", "다른 선택(해외·다른 숙소)에서 겪은 손해 → 여기서 그 손해가 없음 → '진작'"),
        "지인 추천형": ("H8", "전문가 지인이 '여기만은' → 반신반의 → 알고 보니 → 소름"),
    },
    "slots": [   # 칸 = 사진(줄 i = 사진 i). 불편 칸(②)은 과거 장면이라 사진과 대비로 읽힌다(사진에 없어도 된다)
        ("사건 훅", "인물·사건 또는 불편을 던진다(이점 말하지 않음)", "H 사전"),
        ("불편 장면", "예전 여행에서 겪은 구체적 고생 한 순간(새벽 자리 맡기·주차장 뷰·좁은 방)", "예전엔 ~하느라 ~했는데"),
        ("전환·오해", "이번엔 달랐다 — 남의 질문·오해로 이점을 비춘다", "~보더니 여기 해외냐고 묻는 거예요"),
        ("고조1", "'근데 이게'로 첫 반전(직접 겪은 장면으로)", "근데 이게 ~하니까 ~더라고요"),
        ("고조2", "'이게 대박인 게'로 더 센 카드", "이게 대박인 게 ~거 있죠"),
        ("최강·반응", "'심지어/소름인 건' + 인물 반응으로 첫 줄 사건 회수", "심지어 ~던 {인물}이 먼저 ~하더라고요"),
        ("댓글 유도", "이야기 키워드 + 받는 것", "궁금하면 댓글에 '{키워드}' 남겨 주세요"),
    ],
    "indirect": [   # 이점을 대놓고 말하지 않는 다섯 길 — 창고 상위 대본에서 뗀 꼴
        "남의 오해·질문: '여기 해외냐고 물어보는 거예요'(양말 새로 샀냐고 295만·도배 새로 했냐고 235만)",
        "과거 불편과 대비: '예전엔 새벽 6시에 선베드 맡았는데 여긴 ~'",
        "인물의 행동 변화: '휴대폰만 보던 남편이 커튼부터 열더라고요'",
        "포기·손해의 소거: '애들 데리고 해외 가려던 비행기 값이 그대로 남았어요'",
        "몸의 반응: '들어가자마자 둘 다 말이 없어지는 거예요'",
    ],
    "banned_direct": r"(뷰|풀|수영장|객실|방|침대|욕조|로비|정원|조명|선베드|시설)[^.!?]{0,14}(있어요|있구요|있고요|이에요|예요|좋아요|최고예요|완벽해요|넓어요|예쁘요|예뻐요)",
    "refs": [   # 참고 대본(대본창고 실물) — 말투·구조만
        "이것 때문에 시어머니한테 욕 바가지로 먹을 뻔했어요. 얼마 전에 시어머니가 집에 놀러 오셨는데 화장실 다녀오시더니 이게 뭐냐고 "
        "물어보시는 거예요. … 표정이 싹 굳으시면서 … (631만, chae2home)",
        "저 이거 때문에 엄마한테 욕 바가지 먹을 뻔했어요. 얼마 전에 친정엄마가 집에 놀러왔는데 흰 양말 널어 놓은 걸 보더니 양말 새로 샀냐고 "
        "물어보는 거예요. 그거 몇 년은 신던거라고 … 어쩜 이렇게 새 것처럼 깨끗하냐고 하길래 … (295만, chae2home)",
        "… 밖에 집 안이 다 보이는 것 같아서 커튼 안 달았냐고 물어봤더니 다이소에서 이걸 사서 붙였다는 거에요 이게 대박인게 밖에서 안이 "
        "안 보이고 안에서는 밖이 훤히 보이니까 … (38만, home._.standard)",
        "… 별생각 없이 하나 사왔거든요? 근데 이게 쓱쓱 접으면 손바닥만 하게 작아지는데 … 내 것도 하나 더 사올 걸... 후회하면서 … "
        "궁금하신 분들은 나도 남겨주세요 (68.6만·댓글 3.5만, chae2home)",
        "… 근데 이게 끝이 아니에요. 나중에 지붕 프레임은 책장이나 행거로도 활용할 수 있어서 진짜 버릴 게 없는 거 있죠? 애들도 동화 속 "
        "오두막집 생긴 것 같다며 … (50.6만, reureu_rumi)",
    ],
}


def _travel_card_guide():
    c = TRAVEL_CARD
    hooks = " / ".join("%s %s" % kv for kv in c["hooks"].items())
    types = "\n".join("- %s: 첫 줄 %s · %s" % (k, v[0], v[1]) for k, v in c["types"].items())
    slots = "\n".join("%d. %s — %s (예: %s)" % (i + 1, s[0], s[1], s[2]) for i, s in enumerate(c["slots"]))
    strong = ", ".join("'%s'(%.1f배)" % kv for kv in c["escalation"]["strong"])
    weak = ", ".join("'%s'" % k for k, _ in c["escalation"]["weak"])
    refs = "\n".join("· " + r for r in c["refs"])
    return (
        "말투 = 우리 숏템 인스타 상위 릴스(대본창고 실측). 1인칭 존댓말 수다체 — 친구에게 '나 거기 갔다가 진짜 놀랐잖아' 하듯.\n"
        "[이야기 뼈대 = 불편 → 해결] 과거(또는 지금) 여행의 구체적 불편·사건으로 열고, 이 숙소에서 그 불편이 통째로 사라지는 이야기로 간다. "
        "불편은 한 순간의 장면으로(새벽 6시 선베드 맡기, 창밖이 주차장, 애들 물놀이 자리싸움, 해외 가려다 비행기 값). "
        "인물·계기·불편·감정은 지어내도 되지만 이 숙소의 시설·풍경·시간대는 그 줄의 사진에 보여야 한다.\n"
        "[이점을 대놓고 말하지 마라] '바다 뷰예요', '수영장이 넓어요', '욕조가 있어요' 같은 소개 문장 금지. 이점은 다음 다섯 길로만 보여 준다:\n"
        + "\n".join("- " + x for x in c["indirect"]) + "\n"
        "[고조 계단 — 실측으로 센 말만] " + strong + ". 4줄 '근데 이게' → 5줄 '이게 대박인 게' → 6줄 '심지어' 또는 '근데 진짜 소름인 건' 처럼 "
        "점점 세게 올린다. 약한 말은 쓰지 마라: " + weak + "(조회수 0.7배대).\n"
        "  ★원본의 '이게'는 제품을 가리킨다. 숙소에선 '근데 여기가', '여기가 대박인 게', '근데 이 방이'처럼 가리킬 것을 바꿔 쓰고, "
        "뒤에 반드시 무엇이 왜 센지(이유 → 결과)를 붙여 말을 끝까지 맺는다. '근데 이게 다 멈춰요'처럼 받는 말 없는 '이게' 금지(채점에서 3번 지적됨).\n"
        "[첫 줄 틀 사전] " + hooks + "\n[유형]\n" + types + "\n"
        "[7칸 — 줄 i = 화면 i]\n" + slots + "\n"
        "[댓글 키워드] 그 이야기의 말로(실측: '대박'·'최고'·'촉촉'·'뽀송'). 예) 혼남→'등짝', 오해→'해외아님', 불편→'새벽6시', 의심→'내가졌다'. '정보' 고정 금지.\n"
        "[어미] 끝은 거예요·더라고요·거든요·거 있죠·잖아요·어요를 섞는다. ~네요·~는데요·~음/임/함 금지. "
        "문장 3~4개, 줄은 그 문장의 마디(줄 끝 '~는데/~니까/~어서' 가능), 이유로 잇고 '~하고 ~하고' 나열 금지. 문장 끝 줄에만 마침표.\n"
        "[참고 대본 실물 — 말투·구조만, 문장 베끼기 금지]\n" + refs)


_PAIN_RE = re.compile(r"때문에|고생|불편|힘들|지옥|스트레스|짜증|답답|찝찝|새벽|자리 ?맡|포기|등짝|혼날|혼났|욕 ?먹|뻔했|우기|오해|물어보|묻는|해외냐|후회|실망|낭비|피곤|폰만|지쳤|지친")


def story_issues(lines):
    """여행 스타일 카드 2판 관문 — 불편→해결 뼈대·간접 이점·고조 계단(전부 대본창고 실측 근거, TRAVEL_CARD)."""
    c = TRAVEL_CARD
    text = " ".join(lines or [])
    flat = text.replace(" ", "")
    out = []
    # 숙소에선 '이게' 대신 '여기가·이 방이'로 가리킨다 — 같은 고조어로 센다
    norm = re.sub(r"(여기가|이방이|이풀이|이숙소가|여기)", "이게", flat)
    strong = [k for k, _ in c["escalation"]["strong"] if k.replace(" ", "").replace("인건", "") in norm or k.replace(" ", "") in norm]
    if len(strong) < 2:
        out.append("고조: 센 고조어 %d개(%s) — '근데 이게'(4.7배)·'이게 대박인 게'(4.6배)·'심지어'·'알고 보니' 중 2개 이상으로 계단을 올려라"
                   % (len(strong), ", ".join(strong) or "없음"))
    weak = [k for k, _ in c["escalation"]["weak"] if k.replace(" ", "") in flat]
    if weak:
        out.append("고조: 약한 말 %s(조회수 0.7배대) — 센 말로 바꿔라" % weak)
    # 남이 묻는·오해하는 문장('보정이냐고 묻는 거예요')은 우리가 원하는 간접 화법이라 빼고 잰다(헛걸림 실측 2026-10-19)
    direct = [m.group(0) for l in (lines or []) if not re.search(r"냐고|물어|묻|오해|우기", l)
              for m in re.finditer(c["banned_direct"], l)]
    if direct:
        out.append("간접성: 이점을 대놓고 말함 %s — 오해·과거 불편 대비·인물 행동 변화로 보여 줘라" % direct[:3])
    if not _PAIN_RE.search(" ".join((lines or [])[:2])):
        out.append("불편→해결: 1~2줄에 불편·사건(고생·혼남·오해·의심·후회)이 없다 — 소개로 시작하지 마라")
    return out


STYLES["여행 숙소 인스타"] = dict(STYLES["두유노홈디노"], types=tuple(TRAVEL_CARD["types"]), guide=_travel_card_guide(),
                              pick_types=3, story_gate=True)


def style_ending_issues(lines, style):
    """채널 말투 검사 — 문장 끝 어미(마침표·물음표·느낌표·마지막 줄)가 그 채널 어미인가. 남의 어미면 지적."""
    st = STYLES.get(style or "")
    if not st:
        return []
    text = " ".join(lines or [])
    sents = [x.strip(" '\"") for x in re.split(r"[.!?]\s*", text) if x.strip()]
    issues = []
    for s in sents:
        tail = re.sub(r"[^가-힣]+$", "", s)
        if any(tail.endswith(e) for e in st["endings_foreign"]) and not any(tail.endswith(e) for e in ("어요", "아요")):
            issues.append("말투(남의 어미): …" + tail[-8:])
    own = sum(1 for s in sents if any(re.sub(r"[^가-힣]+$", "", s).endswith(e) for e in st["endings_own"]))
    if sents and own / len(sents) < 0.75:
        issues.append("말투: 채널 어미 문장 %d/%d" % (own, len(sents)))
    issues += speech_issues(lines)
    return issues


def ordered_picks(picks, version):
    """안이 정한 사진 순서(order: 1부터)대로 picks 를 다시 세운다. 순서가 없으면 그대로 — 렌더·채점·검토가 모두 이것만 쓴다."""
    o = (version or {}).get("order")
    if isinstance(o, list) and sorted(int(x) for x in o) == list(range(1, len(picks) + 1)):
        return [picks[int(x) - 1] for x in o]
    return list(picks)


def revise_claude(version, issues, picks, detail, style=None, model="opus"):
    """관문 지적을 그대로 주고 그 안 하나를 고쳐 쓰게 한다(같은 사진을 다시 보며). 반환: 새 lines 또는 None."""
    st = STYLES.get(style or "") or {}
    lo, hi, lmin, lmax = char_range(len(picks))
    prompt = ("여행 숙소 쇼츠 대본 한 편을 고친다. 사진 photo_1~%d 순서이고 줄 i 는 화면 i 위에서 읽힌다(정확히 %d줄 유지).\n"
              "[지금 대본 — %s]\n%s\n\n[고칠 지적 — 전부 고쳐라]\n%s\n\n"
              "[유지할 것] 인물·사건·반전·댓글 키워드는 살린다. 전체 %d~%d자, 줄 %d~%d자. 숙소 이름·지역·가격 숫자 금지.\n"
              "[쓰는 순서] 고친 이야기를 긴 문장 3개로 먼저 쓰고(문장 안은 '~는데/~니까/~어서'로 이유를 잇는다) 그걸 7조각으로 나눈다 — "
              "7개 짧은 문장으로 쪼개 쓰지 마라(고쳐 쓰기에서 나열체로 돌아간 실측 있음). 문장이 끝나는 조각에만 마침표.\n"
              "[말투 기준]\n%s\n\nJSON: {\"lines\": [\"줄1\", ...]}"
              % (len(picks), len(picks), version.get("type", ""), "\n".join("%d. %s" % (i + 1, l) for i, l in enumerate(version["lines"])),
                 "\n".join("- " + x for x in issues), lo, hi, lmin, lmax, (st.get("guide") or "")[:1800]))
    facts = story_facts_text(detail) if st.get("story_gate") else ""
    if facts:
        prompt += "\n\n[숙소 사실 — 사진에 없어도 써도 되는 재료, 지어내기 금지·이름·지역·가격 숫자 금지]\n" + facts
    got = claude_call([q["path"] for q in picks], prompt, model=model)
    lines = got.get("lines")
    return lines if isinstance(lines, list) and len(lines) == len(picks) else None


def write_script_claude(picks, detail, model="opus", style=None, revise=True):
    """오푸스가 사진 7장을 직접 보며 3유형을 쓰고 → 금지 검사 → 다른 오푸스 호출이 채점 → 최고점 + 금지 통과를 추천.
    style = STYLES 의 채널 말투(예: '두유노홈디노') — 말투·유형만 바꾸고 화면 짝·근거 규칙은 그대로."""
    p = script_prompt(picks, detail).replace("아래 화면이 이 순서로", "열어 본 사진(photo_1~)이 이 순서로")
    st = STYLES.get(style or "")
    if st:
        if st.get("pick_types"):     # 유형이 많으면 이 사진에 맞는 것 몇 개만 골라 쓰게 한다(스타일 카드 '시안' 규칙)
            p = p.replace("대본 3개(유형마다 1개)를 써라.", "아래 유형 중 이 사진들에 가장 맞는 %d개를 골라 유형마다 대본 1개씩 써라 — 유형: "
                          % st["pick_types"] + " / ".join(st["types"]) + ".")
        else:
            p = p.replace("대본 3개(유형마다 1개)를 써라.", "대본 %d개를 써라(유형마다 1개) — 유형: " % len(st["types"]) + " / ".join(st["types"]) + ".")
        p = p.replace("3. 직접 다녀온 척하지 마라('다녀왔는데', '좋았고요', '먹어봤는데' 금지). 보이는 것을 생생하게 소개하는 말투.",
                      "3. [말투] " + st["guide"])
        p = p.replace("짧고 센 문장, 해요체, 한 줄 = 한 호흡.", "줄은 긴 문장의 마디(이어지는 연결어미 허용).")
    want = '\n\nJSON: {"versions": [{"type": "유형", "lines": ["줄1", ...]}]}'
    if st and st.get("story_gate"):
        # ★사진 순서는 작가가 정한다(2026-10-19 실측: pick7 순서를 강요하니 3·4줄에서 이야기가 엉뚱한 사진 화제로 샜다)
        p = p.replace("[화면] 아래 화면이 이 순서로 한 장씩 나온다.", "[화면] 아래 사진 7장을 다 쓴다 — 순서는 네가 이야기에 맞게 정한다.")
        p = p.replace("[화면] 열어 본 사진(photo_1~)이 이 순서로 한 장씩 나온다.", "[화면] 열어 본 사진 7장(photo_1~7)을 다 쓴다 — 순서는 네가 이야기에 맞게 정한다.")
        p += ("\n\n[불편 고르기 — 가장 중요] 불편은 **숙소 전체에 걸치는 것**으로 고른다. 사진 7장(물놀이·객실·욕조·정원…)이 "
              "전부 그 불편이 하나씩 사라지는 장면이 되어야 하기 때문이다. 한 장소에만 걸린 불편(선베드 자리)은 3줄부터 이야기가 끊긴다(실측). "
              "좋은 예: '여행 가면 애들이 숙소에서 폰만 봤는데'(→ 화면마다 애들이 폰을 내려놓는 장면), '남편이 호캉스는 돈 낭비라고 했는데'"
              "(→ 화면마다 남편이 먼저 움직이는 장면), '엄마가 여행 가면 늘 피곤하다고만 했는데'(→ 화면마다 엄마가 달라지는 장면). "
              "고조는 그 인물의 변화가 점점 커지는 순서로(작은 변화 → 큰 변화 → 첫 줄 말을 뒤집는 한마디).")
        p += ("\n\n[쓰는 순서 — 반드시] ① 위 불편 하나(또는 사건 하나)를 정하고 그 이야기를 긴 문장 3개로 먼저 쓴다(story). "
              "3~6줄은 전부 그 불편이 이 숙소에서 사라지는 장면이어야 한다 — 다른 화제(그냥 예쁜 로비 등)로 새지 마라. "
              "② story 를 7조각(lines)으로 나눈다. ③ 조각마다 가장 맞는 사진 번호를 order 에 적는다(1~7 을 한 번씩, 조각 i 는 사진 order[i] 위에서 읽힌다). "
              "과거 불편 조각에는 그 불편과 대비되는 사진(예: 선베드가 넉넉한 풀)을 붙인다.")
        want = '\n\nJSON: {"versions": [{"type": "유형", "story": "긴 문장 3개", "lines": ["조각1", ...], "order": [사진번호 7개]}]}'
    facts = story_facts_text(detail) if st and st.get("story_gate") else ""
    if facts:
        # 사진 밖 사실도 이야기 재료(2026-10-19 사장님 "풀어도 된다, 사진 이외에도 스토리성이라 좋다")
        p += ("\n\n[숙소 사실 — 사진에 없어도 써도 되는 이야기 재료] 고조 칸('근데 여기가'·'여기가 대박인 게'·'심지어')의 센 카드는 "
              "사진의 예쁜 풍경보다 **아래 사실 중 사람들이 놀랄 것**(계절·시간·아이·서비스처럼 이야기의 불편을 직접 없애는 것)으로 채운다. "
              "실제 후기에 나온 불편·감탄은 인물의 이야기로 옮겨도 된다. 아래에도 사진에도 없는 사실은 지어내지 마라. "
              "숙소 이름·지역명·가격 숫자는 여전히 쓰지 않는다(재료에 있어도).\n" + facts)
    got = claude_call([q["path"] for q in picks], p + want, model=model)
    versions = [v for v in got.get("versions") or [] if isinstance(v, dict) and v.get("lines")]
    for v in versions:
        o = v.get("order")
        v["order"] = o if isinstance(o, list) and sorted(int(x) for x in o) == list(range(1, len(picks) + 1)) else list(range(1, len(picks) + 1))
    issues = {v.get("type", "?"): script_issues(v["lines"], detail, len(picks), style=style) for v in versions}
    scores = {}
    for v in versions:        # 안마다 사진 순서가 달라서 채점도 안마다 그 순서로
        scores.update(judge_scripts([v], ordered_picks(picks, v), style=style, facts=facts))
    for t, sc in scores.items():
        issues.setdefault(t, []).extend("사진 대조: " + b for b in sc.get("bad_lines") or [])
    hard_ok = [v for v in versions if not [x for x in script_issues(v["lines"], detail, len(picks), style=style)
                                            if not x.startswith(("길이", "말투"))]]
    chosen = max(hard_ok or versions, key=lambda v: (scores.get(v.get("type", "?")) or {}).get("total", 0)) if versions else None
    revised = None
    if revise and chosen and issues.get(chosen.get("type", "?")):
        # 1등 안만 지적을 주고 한 번 고쳐 쓴다 → 같은 관문·같은 채점을 다시 돌려 나아졌을 때만 바꾼다(나빠지면 원래 안 유지)
        new_lines = revise_claude(chosen, issues[chosen["type"]], ordered_picks(picks, chosen), detail, style=style, model=model)
        if new_lines:
            nv = {"type": chosen["type"] + " (고쳐 씀)", "lines": new_lines, "order": chosen.get("order")}
            n_iss = script_issues(new_lines, detail, len(picks), style=style)
            n_sc = judge_scripts([nv], ordered_picks(picks, nv), style=style, facts=facts).get(nv["type"]) or {}
            n_iss += ["사진 대조: " + b for b in n_sc.get("bad_lines") or []]
            revised = {"version": nv, "issues": n_iss, "score": n_sc}
            if len(n_iss) < len(issues[chosen["type"]]) and n_sc.get("total", 0) >= (scores.get(chosen["type"]) or {}).get("total", 0) - 2:
                versions.append(nv)
                issues[nv["type"]], scores[nv["type"]] = n_iss, n_sc
                chosen = nv
    return {"chosen": chosen, "versions": versions, "issues": issues, "scores": scores, "writer": "claude-" + model,
            "clean": bool(chosen) and not issues.get(chosen.get("type", "?")), "attempts": 1, "revised": revised}


def write_script(picks, detail, call=None, verify=None, tries=2):
    """→ {"chosen", "versions", "issues": {유형: [문제]}, "attempts"}. 문제 없는 첫 유형을 고른다.
    관문 두 겹: ① script_issues(이름·가격·지역·가 본 척·길이) ② verify_lines(사진에 없는 말). 모두 탈락이면 한 번 더 쓴다."""
    if call is None:
        from shopping_shorts.edit_plan import _vault_call as call
    best, feedback = None, None
    for attempt in range(1, tries + 1):
        got = call(script_prompt(picks, detail, feedback), _SCRIPT_SCHEMA) or {}
        versions = [v for v in got.get("versions") or [] if isinstance(v, dict) and v.get("lines")]
        issues = {v.get("type", "?"): script_issues(v["lines"], detail, len(picks)) for v in versions}
        seen = verify_lines(versions, picks, call=verify) if versions else {}
        for k, v in seen.items():
            issues.setdefault(k, []).extend(v)
        chosen = next((v for v in versions if not issues.get(v.get("type", "?"))), None)
        best = {"chosen": chosen, "versions": versions, "issues": issues, "attempts": attempt, "clean": bool(chosen)}
        if chosen:
            break
        feedback = ["[%s] %s" % (k, x) for k, v in issues.items() for x in v][:14]
    if best and not best["chosen"] and best["versions"]:
        # 다 걸리면 지적이 가장 적은 안을 '추천'으로 — 사람(사장님 검토 화면)이 지적을 보고 최종 결정한다.
        #   clean=False 인 안은 render 단계가 그대로 쓰지 않는다(사람이 --script 로 고른 경우만).
        best["chosen"] = min(best["versions"], key=lambda v: len(best["issues"].get(v.get("type", "?")) or []))
    return best


# ── 계획 ─────────────────────────────────────────────────────────────────────
def build_plan(lines, tts_paths, clip_paths, probe):
    """줄 i = 클립 s{i}. 클립(4초)을 줄 길이에 맞춰 배속해 카메라 움직임 전체가 보이게 한다(1.0~2.0배).
    반환: (edit_plan, source_video_paths)."""
    beats, srcs = [], {}
    for i, (line, tts, clip) in enumerate(zip(lines, tts_paths, clip_paths)):
        dur = float(probe(tts) or 0.0)
        cdur = float(probe(clip) or 0.0)
        speed = max(1.0, min(2.0, cdur / dur)) if dur > 0 and cdur > 0 else 1.0
        vid = "s%d" % i
        srcs[vid] = str(clip)
        beats.append({"beat_idx": i, "narration": line, "caption_lines": [line], "tts_path": str(tts),
                      "target_seconds": dur, "role": "hook" if i == 0 else ("cta" if i == len(lines) - 1 else "body"),
                      "sync_speed": round(speed, 3),
                      "primary": {"video_id": vid, "start": 0.0, "end": round(min(cdur, dur * speed), 3)}})
    return {"beats": beats}, srcs


def deco_for(detail, ad=True, ai=True):
    """여행형 꾸미기 — 표기만 정한다(광고·AI 콘텐츠·출처). 문구의 주인은 travel_source.source_label."""
    return {"disclosure": {"ad": bool(ad), "ai": bool(ai), "source": (detail or {}).get("source_label") or ""}}


def download(url, out_path):
    from curl_cffi import requests as cr
    r = cr.get(url, impersonate="chrome", timeout=30)
    if r.status_code != 200 or len(r.content) < 5000:
        raise RuntimeError("사진 받기 실패 %s %s" % (r.status_code, url))
    Path(out_path).write_bytes(r.content)
    return str(out_path)
