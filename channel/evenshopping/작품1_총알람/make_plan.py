# -*- coding: utf-8 -*-
"""재미썸홈 작품1 총 쏘는 알람시계 — 선검수 계획(TTS·렌더 금지 단계). 대본.json · 재료.json · plan/계획_시트.jpg 를 만든다.

대본 = channel/homedesignnote/대본초안_5편_이븐쇼핑형.md 3번(대사 교체본) 그대로. 재료 = 재료후보.md(+페이블 판정) 에서 토막마다 고름.
토막 시간 = 글자 수(한글·영숫자) ÷ 8.8자/초(이븐쇼핑 47편 중앙, 프리셋 manifest) — TTS 전 추정치.
화면 = 숏템 t11 영상 칸 비율(1080×1407) 크롭. crop_x = 원본 픽셀 기준 크롭 왼쪽 끝(없으면 가운데).
    PYTHONUTF8=1 py channel/evenshopping/작품1_총알람/make_plan.py
"""
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = Path("C:/숏템_칼카피/evenshopping/작품1_총알람")
MEME = Path("C:/숏템_칼카피/packs/meme/meme_pack")
PRESET = json.loads((HERE.parent / "preset/숏템템플릿/manifest.json").read_text(encoding="utf-8"))
CPS = PRESET["measured"]["speech_rate"]["chars_per_s_total"]
WIN = (1080, 1407)

SENTENCES = [
    ("title", "애들 깨우다 현타 온 일본 천재가 만들어 떼돈 번 알람의 정체."),
    ("bait", "최근 등교 전쟁 겪는 엄마들 사이에서 바이럴이 터지며 논란인 알람이 있는데,"),
    ("reveal", "이건 바로 총 쏘는 알람시계."),
    ("solve", "이게 말도 안 되는 게 알람이 울리면 버튼이 아니라 과녁을 맞혀야만 꺼진다는 거."),
    ("more", "심지어 이게 건담 만든 반다이 작품인데,"),
    ("more2", "명중하는 순간 과녁이 툭 쓰러지면서 빨간 불이 번쩍 들어와서 진짜 사격장에 온 것 같다는데,"),
    ("twist", "근데 진짜 충격적인 포인트는 침대에 누운 채로는 절대 못 맞혀서 결국 일어나 조준하다 보면 잠이 저절로 다 깨버린다고."),
    ("land", "그래서 요즘엔 아침마다 애들이 먼저 일어나서 서로 쏘겠다고 싸우는 바람에 엄마들 사이에서 등교 전쟁 끝낸 효자템으로 난리라고."),
]
# 대사 = 페이블 10-17 확장본(길이 부족·고조⑤ 해결). 자막 조각마다 컷 1개.
# (자막 조각, 칸, 소스, 시작초, crop_x, 효과음, 화면에 보이는 것)
KID = "_GF8R1NUsQI"
CUTS = [   # 수정2(사장님 10-17): "+" = 앞 컷을 끊지 않고 이어감(자막만 바뀜). 이야기 한 묶음 = 한 인물·한 영상 줄기.
    ("애들 깨우다 현타 온", "유사", "6XBK3BmPHNE", 14.0, 400, "", "이불 덮어쓴 딸 앞에 서서 깨우는 엄마(방)"),
    ("일본 천재가 만들어", "제품", "ProcmLGVjUs", 12.5, None, "", "검정 과녁 알람·권총·설명서 첫 공개"),
    ("떼돈 번 알람의 정체", "제품", "AP-6U2s1j9A", 8.0, None, "", "침대 위 흰 알람, 과녁 세워짐"),
    ("최근 등교 전쟁 겪는", "유사", "GjAHiMZtd7c", 0.0, None, "", "아침 7:00 침대 옆 알람(사람 없음)"),
    ("엄마들 사이에서", "유사", "6XBK3BmPHNE", 16.0, 420, "", "침대 옆에 선 엄마"),
    ("바이럴이 터지며", "짤", "meme:fm_mindblown", 0.3, None, "", "얼굴 앞에서 터지는 불꽃(머리 터짐 짤)"),
    ("논란인 알람이 있는데", "제품", "ProcmLGVjUs", 47.0, None, "", "책상 위 검정 과녁 알람, 손가락"),
    ("이건 바로", "제품", "Z8Jqs2UFUtM", 26.9, None, "", "흰 알람 정면, 세워진 과녁 → 흰 권총 등장"),
    ("총 쏘는 알람시계", "+", "+", 0, None, "", "(이어감)"),
    ("이게 말도 안 되는 게", "짤", "meme:fm_frysquint", 0.2, None, "", "의심 눈 프라이(초록 배경)"),
    ("알람이 울리면", "제품", "ProcmLGVjUs", 80.4, None, "", "알람 화면 9:24 + 버튼 누르는 손가락"),
    ("버튼이 아니라", "+", "+", 0, None, "", "(이어감)"),
    ("과녁을 맞혀야만", "제품", "ProcmLGVjUs", 60.6, None, "", "알람에서 과녁이 일어섬"),
    ("꺼진다는 거", "제품", "Z8Jqs2UFUtM", 29.5, None, "", "맞은 과녁이 누워 꺼진 흰 알람"),
    ("심지어 이게", "제품", "ProcmLGVjUs", 36.5, None, "", "손에 든 검정 권총"),
    ("건담 만든", "유사", "YLHqd3_YO-U", 58.05, None, "", "건담 방패 → 완성 얼굴 클로즈업(59.5초 글자 전까지)"),
    ("반다이 작품인데", "+", "+", 0, None, "", "(이어감)"),
    ("명중하는 순간", "제품", "Z8Jqs2UFUtM", 27.9, 640, "", "흰 권총 → 과녁 정중앙 빨간 불"),
    ("과녁이 툭 쓰러지면서", "제품", "AP-6U2s1j9A", 30.4, None, "", "명중 불빛 뒤 과녁이 접혀 사라짐"),
    ("빨간 불이 번쩍 들어와서", "제품", "ProcmLGVjUs", 62.3, None, "", "과녁에 빨간 명중 불빛 → 쓰러짐"),
    ("진짜 사격장에", "제품", "Z8Jqs2UFUtM", 20.0, None, "", "두 손으로 권총 든 남자"),
    ("온 것 같다는데", "제품", "Z8Jqs2UFUtM", 24.0, None, "", "코앞 과녁에 권총 겨눈 남자"),
    ("근데 진짜", "짤", "meme:fm_joeyshock", 0.0, None, "", "놀라는 조이(초록 배경)"),
    ("충격적인 포인트는", "+", "+", 0, None, "", "(이어감)"),
    ("침대에 누운 채로는", "유사", "GjAHiMZtd7c", 8.5, None, "", "[묶음A 여성] 베개에 누워 자는 여성"),
    ("절대 못 맞혀서", "제품", "AP-6U2s1j9A", 19.6, 900, "", "[묶음A 제품 끼움] 침대 위 과녁 겨눈 주황 권총"),
    ("결국 일어나", "유사", "GjAHiMZtd7c", 12.3, None, "", "[묶음A 여성] 팔 뻗으며 깨는 여성"),
    ("조준하다 보면", "+", "+", 0, None, "", "(이어감)"),
    ("잠이 저절로", "+", "+", 0, None, "", "(이어감)"),
    ("다 깨버린다고", "+", "+", 0, None, "", "(이어감)"),
    ("그래서 요즘엔", "제품", KID, 39.0, 1090, "", "[묶음B 남자아이] 탁자 위 과녁 알람 앞에서 총 들고 겨누는 아이"),
    ("아침마다 애들이", "+", "+", 0, None, "", "(이어감)"),
    ("먼저 일어나서", "+", "+", 0, None, "", "(이어감)"),
    ("서로 쏘겠다고", "+", "+", 0, None, "", "(이어감)"),
    ("싸우는 바람에", "+", "+", 0, None, "", "(이어감)"),
    ("엄마들 사이에서", "유사", "6XBK3BmPHNE", 24.6, 700, "", "[묶음C 엄마] 웃는 엄마"),
    ("등교 전쟁 끝낸", "+", "+", 0, None, "", "(이어감)"),
    ("효자템으로", "+", "+", 0, None, "", "(이어감)"),
    ("난리라고", "제품", "ProcmLGVjUs", 62.25, None, "", "과녁 빨간 명중 불빛(끝 컷 ≥1.5초)"),
]


def nchar(s):
    return len(re.findall(r"[가-힣A-Za-z0-9]", s))


def path_of(src):
    return MEME / f"{src[5:]}.mp4" if src.startswith("meme:") else SRC / f"src_{src}.mp4"


def probe(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    j = json.loads(o)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def frame(p, t, w, h, crop_x):
    s = WIN[1] / h                                   # 영상 칸 높이에 맞춰 키움(compose 와 같은 cover)
    cw = WIN[0] / s                                  # 원본 픽셀로 본 크롭 폭
    x = (w - cw) / 2 if crop_x is None else crop_x
    vf = f"crop={int(cw)}:{h}:{int(x)}:0,scale=200:261"
    png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1", "-vf", vf, "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    import io
    return Image.open(io.BytesIO(png)).convert("RGB"), round(s, 2), int(x)


def main():
    # 자막 조각이 대사를 빠짐없이 순서대로 덮는지(공백·문장부호 무시)
    whole = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(s for _, s in SENTENCES)))
    pieces = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(c[0] for c in CUTS)))
    assert whole == pieces, "자막 조각이 대사와 다르다"
    t, rows = 0.0, []
    prev = None
    for i, (cap, kind, src, st, cx, sfx, seen) in enumerate(CUTS):
        d = round(nchar(cap) / CPS, 2)
        if src == "+":   # 앞 컷 이어감 — 같은 소스, 시간은 연속
            kind, src, cx = prev["kind"], prev["source"], prev["crop_x"]
            st = prev["src_t1"]; seen = "(이어감)"
        p = path_of(src); w, h, dur = probe(p)
        assert st + d <= dur, (cap, src, st, d, dur)
        rows.append({"i": i + 1, "t0": round(t, 2), "dur": d, "caption": cap, "caption_chars": len(cap), "kind": kind,
                     "source": src, "src_t0": st, "src_t1": round(st + d, 2), "src_res": f"{w}x{h}", "crop_x": cx,
                     "sfx_at_t0": "sfx_pack(렌더에서 자막 줄 기준)", "seen": seen, "hook": i < 3, "_p": p, "_w": w, "_h": h, "cont": CUTS[i][2] == "+"})
        prev = rows[-1]
        t += d
    total = round(t, 2)
    # 대본.json
    (HERE / "대본.json").write_text(json.dumps({
        "channel": "재미썸홈", "preset": "channel/evenshopping/preset/숏템템플릿/manifest.json",
        "from": "channel/homedesignnote/대본초안_5편_이븐쇼핑형.md 3번 → 페이블 10-17 확장본(more2·land 추가)",
        "title_slots": {k: PRESET["sample_title"][k] for k in ("hook1", "hook2", "bodyTitle")},
        "spine55": [{"slot": k, "line": s, "tts": s} for k, s in SENTENCES],
        "chars": nchar(whole), "est_sec": total, "cps_used": CPS,
        "hype": {"①센 시작": "현타 온 … 떼돈 번", "②권위": "건담 만든 반다이", "③진짜 핵심 반전": "근데 진짜 충격적인 포인트는", "④심지어": "심지어 이게", "⑤~까지 난리": "효자템으로 난리라고"},
        "pieces": [{k: r[k] for k in ("i", "t0", "dur", "caption", "caption_chars", "hook")} for r in rows],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    # 재료.json
    cnt = {k: sum(r["kind"] == k for r in rows) for k in ("제품", "유사", "짤")}
    (HERE / "재료.json").write_text(json.dumps({
        "material_mix": {k: f"{v}/{len(rows)} ({v / len(rows):.0%})" for k, v in cnt.items()},
        "cuts": [{k: v for k, v in r.items() if not k.startswith("_")} | {"zoom": round(WIN[1] / r["_h"], 2)} for r in rows],
        "sfx_rule": "shopping_shorts/sfx_pack.events (페이블 10-17 정정: 컷 경계 규칙 폐기)",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    # 계획 시트
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER = 2 * 200 + 230, 261 + 8, 3
    nrow = (len(rows) + PER - 1) // PER
    head = 70
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * nrow), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), f"재미썸홈 작품1 총 쏘는 알람시계 — 계획 시트(TTS 전) · 컷 {len(rows)} · 예상 {total}초(글자 {nchar(whole)}÷{CPS}) · "
                    f"제품 {cnt['제품']} 유사 {cnt['유사']} 짤 {cnt['짤']} · 효과음 = 숏템 sfx_pack(렌더 때 자막 줄 기준, render/sfx_events.json)", fill="black", font=font)
    d.text((10, 38), "프레임 2장 = 컷 시작+0.1초 · 끝−0.1초, t11 영상 칸(1080×1407) 크롭 그대로. 1~3 = 훅(화면 자막 없음, 제목 2줄)", fill="#444", font=small)
    colors = {"제품": "#1a7f37", "유사": "#9a6700", "짤": "#cf222e"}
    for k, r in enumerate(rows):
        x0, y0 = (k % PER) * COLW, head + (k // PER) * ROWH
        for j, tt in enumerate((r["src_t0"] + 0.1, r["src_t1"] - 0.1)):
            im, _, _ = frame(r["_p"], tt, r["_w"], r["_h"], r["crop_x"])
            sheet.paste(im, (x0 + j * 200, y0))
        tx = x0 + 405
        d.text((tx, y0 + 2), f"#{r['i']} {r['t0']:.2f}s +{r['dur']:.2f}", fill="black", font=font)
        d.text((tx, y0 + 26), f"[{r['kind']}]", fill=colors[r["kind"]], font=font)
        # 자막은 줄바꿈해서
        cap = r["caption"]
        d.text((tx, y0 + 52), cap[:9], fill="black", font=font)
        if len(cap) > 9:
            d.text((tx, y0 + 74), cap[9:], fill="black", font=font)
        d.text((tx, y0 + 104), f"{r['source'][:16]}", fill="#333", font=small)
        d.text((tx, y0 + 122), f"{r['src_t0']}~{r['src_t1']}s {r['src_res']}", fill="#333", font=small)
        d.text((tx, y0 + 140), f"확대 {WIN[1] / r['_h']:.2f}배", fill="#333", font=small)
        seen = r["seen"]
        for li in range(0, min(len(seen), 39), 13):
            d.text((tx, y0 + 162 + li // 13 * 18), seen[li:li + 13], fill="#555", font=small)
    (HERE / "plan").mkdir(exist_ok=True)
    sheet.save(HERE / "plan/계획_시트.jpg", quality=85)
    print("cuts", len(rows), "est", total, cnt, "max caption", max(r["caption_chars"] for r in rows),
          "max zoom", max(round(WIN[1] / r["_h"], 2) for r in rows))


if __name__ == "__main__":
    main()
