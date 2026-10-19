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
TARGET_SEC = (17.5, 21.0)
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


def script_issues(lines, detail, n_expected=None):
    """대본 금지 검사(렌더 전 관문). 문제 목록(빈 목록 = 통과)."""
    issues = []
    text = " ".join(lines or [])
    if n_expected and len(lines or []) != n_expected:
        issues.append("줄 수 %d (기대 %d)" % (len(lines or []), n_expected))
    for w in ("다녀왔", "좋았고요", "먹어봤", "묵어봤", "가봤는데"):
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
