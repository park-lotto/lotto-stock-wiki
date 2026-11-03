# 줄판독 json 만들기 — 픽셀 측정(m.json·capm.json·hook_measure·tone/sfx) + 클로드 눈 판독(readings.py)
import json, sys, os, statistics
sys.path.insert(0, os.path.dirname(__file__))
from readings import R

W = "C:/숏템_칼카피/evenshopping/work"
OUT = "C:/Users/CH/Desktop/로또의 주식/.tracks/칼카피숏템엔진/channel/evenshopping/줄판독"
HOOK = json.load(open(f"{W}/hook_measure.json", encoding="utf-8"))
TONE = json.load(open(f"{W}/tone_detect.json", encoding="utf-8"))
SFXD = json.load(open(f"{W}/sfx_detect.json", encoding="utf-8"))

# 스티커(눈+빨강 픽셀 추적 red.py, 좌표는 1080x1920 원본 픽셀 · ±40px)
CARD = "증거카드"
STK = {
 "tcaIPaGWLrE": {
  30: [{"what": f"{CARD}(황색포도상구균 배양 접시 사진)", "x": 20, "y": 590, "w": 1016, "t_in": 26.43, "t_out": 27.22, "anim": "컷(한 번에 · 손 영상 위에 덮음)"}],
  31: [{"what": f"{CARD}(대장균 배양 접시 사진)", "x": 20, "y": 590, "w": 1016, "t_in": 27.22, "t_out": 27.85, "anim": "컷"},
       {"what": f"{CARD}(전후 배양 접시 4칸 · 99.9% 감소)", "x": 20, "y": 590, "w": 1016, "t_in": 27.9, "t_out": 29.95, "anim": "흰 번쩍 전환 뒤 등장"}],
  32: [{"what": "빨간원(손그림 · '99.9% 감소' 위)", "x": 600, "y": 1010, "w": 340, "t_in": 28.47, "t_out": 29.95, "anim": "그려짐(획이 0.5초에 걸쳐 늘어남)"},
       {"what": "빨간원(손그림 · 아래 '99.9% 감소' 위)", "x": 610, "y": 1610, "w": 370, "t_in": 29.2, "t_out": 29.95, "anim": "그려짐(0.5초)"}],
  36: [{"what": f"{CARD}(피부 일차자극 평가 0.00 인증 표)", "x": 336, "y": 620, "w": 408, "t_in": 32.68, "t_out": 33.47, "anim": "컷"},
       {"what": "빨간원(손그림 · '0.00' 위)", "x": 350, "y": 1310, "w": 390, "t_in": 32.73, "t_out": 33.47, "anim": "그려짐(0.5초)"}],
 },
 "Y2YXuAE4J00": {
  24: [{"what": f"{CARD}(시험성적서 문서)", "x": 120, "y": 590, "w": 860, "t_in": 23.12, "t_out": 24.07, "anim": "컷"},
       {"what": "도장(원형 '믿을 수 있는 100% 국내생산')", "x": 600, "y": 990, "w": 400, "t_in": 23.12, "t_out": 24.07, "anim": "카드와 함께 컷"},
       {"what": "빨간 화살표(손그림 · 도장을 가리킴)", "x": 200, "y": 1070, "w": 360, "t_in": 23.6, "t_out": 24.07, "anim": "한 번에 등장(30fps 한 프레임)"}],
 },
}
FLASH = {("tcaIPaGWLrE", 27.85): "흰 번쩍(회색 가로 번짐 1프레임+흰 1프레임, 30fps 띠 확인)"}


def hx(v):
    return v


def build(vid):
    rd = R[vid]
    m = json.load(open(f"{W}/{vid}/m.json", encoding="utf-8"))
    cm = json.load(open(f"{W}/{vid}/capm.json", encoding="utf-8"))
    hk = HOOK[vid]
    segs = m["segs"]
    assert len(segs) == len(rd["lines"]), (vid, len(segs), len(rd["lines"]))
    dur = round(m["dur"], 3)
    cuts = m["cuts"]
    shots = m["shots"]
    tones = [t for t in TONE[vid] if t["dur"] >= 0.25]
    broads = [e for e in SFXD[vid] if e["kind"] == "broad" and e.get("isolated", 0) >= 0.8 and e["db"] >= 25]
    sfx_ev = [{"kind": "띵(4.3kHz 순음)", "t": t["t"], "basis": "파형 솟음", "dur": t["dur"], "hz": t["hz"]} for t in tones] + \
             [{"kind": "휙(고역 광대역)", "t": e["t"], "basis": "파형 솟음", "dur": e["dur"], "hz": e["cen_hz"]} for e in broads]
    # 같은 0.3초 안은 하나로
    sfx_ev.sort(key=lambda e: e["t"])
    ded = []
    for e in sfx_ev:
        if ded and e["t"] - ded[-1]["t"] < 0.3:
            continue
        ded.append(e)
    lines = []
    for i, (s, (text, role, fit, scene, sdesc)) in enumerate(zip(segs, rd["lines"])):
        t0, t1 = s["t0"], s["t1"]
        if i == len(segs) - 1:
            t1 = dur
        c = cm[i]
        hook = i == 0
        inl = [k for k in cuts if t0 - 0.05 <= k["t"] < t1 - 0.02]
        cut_at = [round(k["t"], 3) for k in inl]
        trs = []
        for k in inl:
            fl = FLASH.get((vid, round(k["t"], 2)))
            trs.append("flash" if fl else "cut")
        transition = ("flash" if "flash" in trs else "cut") if trs else "없음"
        mid = (t0 + t1) / 2
        sh = next((x for x in shots if x["t0"] <= mid < x["t1"]), shots[-1])
        motion = "still" if sh["jit"] < 0.25 else "cam"
        sfx = next(({"kind": e["kind"], "t": e["t"], "basis": e["basis"]} for e in ded if t0 <= e["t"] < t1), None)
        stk = STK.get(vid, {}).get(i, [])
        if hook:
            y = [hk["hook_cap_y"][0], min(hk["hook_cap_y"][1], 700)] if hk.get("hook_cap_y") else [600, 700]
            line = {"t0": round(t0, 3), "t1": round(t1, 3), "speaker": "나레", "text": text, "layer": "채널", "role": role,
                    "enter": "instant", "enter_ms": 0, "enter_curve": [], "type_cps": None, "cursor": False, "exit": "cut",
                    "variant": "훅 썸네일 틀 — 큰 제목 2줄(흰+하늘) 아래 흰 둥근 상자 자막(작은 글자 · 제목을 물음표로 다시 읽음)",
                    "font": {"name": "BMJUA(추정 — 본문 자막과 같은 모양, 크기만 작음)", "basis": "눈"},
                    "size_px": None, "x": 540, "align": "center", "max_w": 1000, "letter_gap_px": None, "line_gap_px": None,
                    "outline": None, "ring": None, "shadow": {"hex": "#000000", "note": "상자 아래 흐린 그림자(눈)"}, "glow": None,
                    "box": {"hex": "#FFFFFF", "alpha": 1.0, "pad": None, "radius": "둥근(눈)"},
                    "emph": [], "sticker": [], "sfx": sfx, "cut_at": cut_at, "y": y, "fill_hex": "#000000",
                    "scene": scene, "scene_desc": sdesc, "fit": fit, "motion": motion, "transition": transition,
                    "confidence": {"t": "픽셀", "text": "눈", "enter": "픽셀", "fill_hex": "눈", "speaker": "신호(받아쓰기=자막)", "role": "눈", "fit": "눈",
                                   "motion": "신호", "transition": "픽셀+눈", "sfx": "신호", "font": "눈"},
                    "notes": "0~%.2f초 훅 틀(머리띠에 '이븐쇼핑' 글자 없음 · 조회수 줄 없음). 그 뒤 본문 틀로 1프레임 컷 전환" % t1}
        else:
            ink_h = c.get("ink_h")
            line = {"t0": round(t0, 3), "t1": round(t1, 3), "speaker": "나레", "text": text, "layer": "채널", "role": role,
                    "enter": "instant", "enter_ms": 0, "enter_curve": [], "type_cps": None, "cursor": False, "exit": "cut",
                    "variant": "기본",
                    "font": {"name": "BMJUA", "basis": "fontmatch.pooled_rank 6줄(3편) 6/6 1위 raw 0.824 · 2위 BMDOHYEON 0.54"},
                    "size_px": round(ink_h / 0.92) if ink_h else None, "x": round((c["x"][0] + c["x"][1]) / 2) if c.get("x") else 540,
                    "align": "center", "max_w": 1040, "letter_gap_px": 0, "line_gap_px": None,
                    "outline": None, "ring": None, "shadow": None, "glow": None,
                    "box": {"hex": "#FFFFFF", "alpha": 1.0, "pad": None, "radius": 0, "band_y": [405, 590], "note": "화면 폭 전체 흰 띠(고정 틀)"},
                    "emph": [], "sticker": stk, "sfx": sfx, "cut_at": cut_at, "y": c.get("y") or [458, 514], "fill_hex": c.get("fill_hex") or "#000000",
                    "scene": scene, "scene_desc": sdesc, "fit": fit, "motion": motion, "transition": transition,
                    "confidence": {"t": "픽셀", "text": "눈", "enter": "픽셀", "fill_hex": "픽셀", "size_px": "픽셀(잉크 높이 근사)", "speaker": "신호(받아쓰기=자막)" if vid != "1kfqEB2b1xM" else "눈(받아쓰기 실패 편 — 같은 틀·같은 나레 결)",
                                   "role": "눈", "fit": "눈", "motion": "신호", "transition": "픽셀+눈", "sfx": "신호", "sticker": "눈+픽셀" if stk else "눈", "font": "픽셀"},
                    "ink_w_px": c.get("w"), "notes": None}
        lines.append(line)
    narr_sec = sum(l["t1"] - l["t0"] for l in lines)
    cps = sum(len(l["text"].replace(" ", "")) for l in lines) / max(1e-6, narr_sec)
    roles = [l["role"] for l in lines]
    first = {r: next(l["t0"] for l in lines if l["role"] == r) for r in dict.fromkeys(roles)}
    beats = " → ".join(f"{r}({first[r]:.1f}~)" for r in dict.fromkeys(roles))
    sfx_list = [l["sfx"] for l in lines if l["sfx"]]
    doc = {
        "id": vid, "dur": dur, "fps": m["fps"], "size": [1080, 1920],
        "title_lines": [
            {"text": rd["hook_title"][0], "colors": [{"word": rd["hook_title"][0], "hex": hk["hook_white_hex"]}], "y": hk["hook_white_y"], "where": "훅 틀(0~%.2f초)" % lines[0]["t1"],
             "font": {"name": "JalnanGothic(추정)", "basis": "fontmatch 하늘 줄 3편 raw 0.66, 2/3 — 외곽·그림자 탓에 낮음"}},
            {"text": rd["hook_title"][1], "colors": [{"word": rd["hook_title"][1], "hex": hk["hook_cyan_hex"]}], "y": hk["hook_cyan_y"], "where": "훅 틀",
             "outline": {"px": None, "hex": "#000000", "note": "어두운 외곽+그림자(눈)"}},
            {"text": rd["body_title"], "colors": [{"word": rd["body_title"], "hex": "#FFFFFF"}], "y": [231, 300], "where": "본문 틀 제목 띠(배경 %s)" % hk["head_bg_hex"],
             "font": {"name": "BMDOHYEON", "basis": "fontmatch 3편 3/3 1위 raw 0.869"}},
        ],
        "source_label": None,
        "layout": {"window": [0, 591, 1080, 1219], "caption_band": [405, 590], "title_y": [179, 402], "source_y": None, "source_hex": None,
                   "logo_y": [0, 173], "logo": "머리띠 #424242 가운데 '이븐쇼핑' 흰 글자 + 왼쪽 햄버거 · 오른쪽 돋보기(빨간 손잡이) — 앱 화면 흉내",
                   "counter": {"text": "조회수 235만 | 댓글 697개", "y": [336, 373], "note": "6편 모두 같은 숫자(틀에 박힌 가짜 지표 — 편마다 안 바뀜)"},
                   "bottom_bar": {"y": [1810, 1920], "hex": hk["bottom_bg_hex"]}, "watermark": {"present": False, "alpha": None},
                   "bg_hex": hk["header_bg_hex"], "band_hex": hk["band_hex"],
                   "hook_frame": {"t": [0, lines[0]["t1"]], "title_white_y": hk["hook_white_y"], "title_cyan_y": hk["hook_cyan_y"], "caption_y": lines[0]["y"]}},
        "lines": lines,
        "no_caption": [],
        "beats": beats,
        "narr_share": f"나레 {len(lines)}/{len(lines)}줄 · 나레 자막 {round(narr_sec,2)}/{dur}초(원음 줄 0 — 받아쓰기가 자막과 같고 원본 소리 안 들림)",
        "narr_cps": round(cps, 2),
        "frame0": {"what": "훅 썸네일 틀: 머리띠(햄버거·돋보기, 로고 글자 없음)+큰 제목 2줄(흰 %s / 하늘 %s)+흰 상자 부제+제품 시연 영상" % (hk["hook_white_hex"], hk["hook_cyan_hex"]),
                   "face_frac": 0.0, "text": " ".join(rd["hook_title"])},
        "sfx_events": ded,
        "bgm": {"present": False, "basis": "쉼 구간(말 p95 −25dB 아래 ≥40ms) 바닥이 말보다 30~39dB 낮고 스펙트로그램 쉼이 전 대역 어둡다(조성 줄 없음) — work/bgm_check.json·spec_*.png"},
        "name_evidence": [],
        "notes": [
            "자막 등장은 전부 instant: 60fps 띠 마스크 차이가 1프레임에 끝남(chg_frames=1, 첫 6프레임 잉크량 변화 ≤5px) — 퇴장도 다음 덩어리로 1프레임 교체(exit cut)",
            "강조 낱말 색 0줄: 자막 띠 안 유채색 잉크 0px(1kf 6번 94px 는 띠 아래 회색 선 — 글자 아님)",
            "transition: 컷 감지(창 히스토그램+밝기차 지역 최대) 뒤 컷 시트(cuts.jpg, 컷마다 -2·-1·0·+1·+3 프레임)로 눈 확인. 흐림 의심(blur_check)은 원본 움직임 번짐이었고 전부 하드 컷. 줄 안에 컷이 없으면 '없음'",
            "motion: 샷마다 LK 추적 전역 닮음변환 — 손떨림 0.25px 미만이면 still, 그 외 cam(원본 촬영 움직임). 편집 확대·이동 효과는 시트에서 안 보임(원본 그대로)",
            "효과음: 4.3kHz(+5.8kHz 배음) 순음 '띵' 0.28~1.08초 — tone.py(2.5~6kHz 칸이 주변보다 ≥14dB 0.12초+) · 스펙트로그램 가로 줄로 확인. sfx_events.py broad 는 이 편에서 db≥25 고립 후보만 채택",
            "BGM 없음(0/6 편 공통 측정) · 원음 0 · 나레 한 목소리(받아쓰기 엔진 gemini-free, 기존 asr/ 파일 재사용 — 이번 호출 0)",
            "size_px = 잉크 높이/0.92 근사(BMJUA 한글 잉크≈0.92em 가정, 렌더 대조 안 함) · letter_gap_px 0 = 글꼴 폭 맞춤 점수(종횡비 벌점 포함) 1위 기준 근사",
        ] + (["받아쓰기 파일이 빈 결과(asr/1kfqEB2b1xM.json 0자) — 화자는 같은 틀·같은 목소리 결로 '나레' 판정(confidence 눈)"] if vid == "1kfqEB2b1xM" else []),
        "_made_by": "evenshopping 줄판독 워커(클로드 눈 + 픽셀 측정 measure/capsheet/cutsheet/tone/red, 2026-10-25, 관제 263 지시서 06)",
    }
    os.makedirs(OUT, exist_ok=True)
    json.dump(doc, open(f"{OUT}/{vid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(vid, len(lines), "cps", round(cps, 2), "sfx", [(e["t"], e["kind"][:2]) for e in ded], "trans", {k: sum(1 for l in lines if l["transition"] == k) for k in ("cut", "flash", "없음")})


for v in R:
    build(v)
