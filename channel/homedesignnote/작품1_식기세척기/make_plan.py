# -*- coding: utf-8 -*-
"""두유노홈디노 작품1 싱크대 매립형 식기세척기 — 선검수 산출(대본.json·재료.json·plan/계획.md·plan/계획_시트.jpg). TTS·렌더 없음.

    PYTHONUTF8=1 py channel/homedesignnote/작품1_식기세척기/make_plan.py

규칙(프리셋 전체화면_가운데자막 manifest.channel_rules): 자막 1토막 = 컷 1개 · 짤 0 · 효과음 0 · 자막만 · 차분 BGM · 원음 안 씀.
토막 = narr_video.steps_of(replace, n=9) — 원본 자막 한 줄 OCR 중앙 10자(공백 포함, 8편 210개)·p90 14자.
토막 길이 = 공백 뺀 글자 ÷ 8.32자/초(asr 49편 중앙). 가로 소스(1920×1080)는 9:16 세로로 오린다(src_crop, 확대 1.78배 ≤2.3).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as N  # noqa: E402

HERE = Path(__file__).parent
SRC = Path("C:/숏템_칼카피/homedesignnote/작품1_식기세척기")
CPS = 8.32
BEFORE = {"xxGmmE_KLkI", "HxOwUlonEW8", "NzSGmn7g4kM"}   # 페이블 10-17: 비포 장면은 다른 제품 OK(원본 fQPX 도 비포는 제품 밖)
CHUNK_FIX = {2: ["근데 이건 중국에서만", "누적 판매 수백만 대를", "찍었다는데"]}
CHUNK = 9   # 공백 뺀 9자 — 토막 길이 중앙 0.96초(8자면 0.84초로 원본 자막 0.9·컷 1.15초보다 짧다)
LINES = [
    "좁은 주방에서 설거지하다 허리 굽히는 게 귀찮았던 중국 주방가전 회사가 아예 싱크대 안에 식기세척기를 쏙 숨겨버렸대요.",
    "보통 식기세척기는 허리 숙여서 넣고 빼야 되는데 그거 진짜 허리 나가잖아요.",
    "근데 이건 중국에서만 누적 판매 수백만 대를 찍었다는데,",
    "진짜 핵심은 이건데, 싱크볼에 그릇 툭툭 넣고 뚜껑만 닫으면 그 싱크볼이 그대로 식기세척기가 돼요.",
    "심지어 과일이랑 채소 농약까지 초음파로 털어내는 모드가 있어서",
    "요즘 신혼부부들 사이에서 이거 없으면 주방 공사 다시 한다고 난리래요.",
]
CLIMAX = {0: "①센 시작", 2: "②숫자", 3: "③진짜 핵심 반전", 4: "④심지어", 5: "⑤난리"}
ROLE = {0: "훅", 1: "도입", 2: "도입(증거)", 3: "설명", 4: "효과", 5: "효과·행동유도"}   # script_frame F1 칸
URL = {"xxGmmE_KLkI": "https://www.youtube.com/watch?v=xxGmmE_KLkI", "HxOwUlonEW8": "https://www.youtube.com/watch?v=HxOwUlonEW8", "NzSGmn7g4kM": "https://www.youtube.com/watch?v=NzSGmn7g4kM", "wqJZ_00Sogc": "https://www.youtube.com/watch?v=wqJZ_00Sogc", "-JU-gKEN1gQ": "https://www.youtube.com/watch?v=-JU-gKEN1gQ",
       "UNB6H9nmbP4": "https://www.youtube.com/watch?v=UNB6H9nmbP4", "TJDOFm5BQkE": "https://www.youtube.com/watch?v=TJDOFm5BQkE"}
# 토막 → (소스 id, 시작 초, 가로 중심 비율(가로 소스만), 화면에 보이는 것)
SHOTS = [
    ("UNB6H9nmbP4", 1.0, 0.42, "좁은 타이니하우스 주방, 싱크대 앞에 선 사람"),
    ("wqJZ_00Sogc", 16.8, 0.62, "싱크볼에 물 틀어 씻기(설거지)"),
    ("UNB6H9nmbP4", 58.4, 0.45, "싱크대 앞에서 허리 굽히는 사람"),
    ("TJDOFm5BQkE", 26.0, None, "주방가전 매장 — 후드·오븐 줄지어 진열"),
    ("wqJZ_00Sogc", 30.3, 0.42, "싱크대가 있는 밝은 주방 전경"),
    ("wqJZ_00Sogc", 20.4, 0.42, "싱크대 한 칸 덮개를 열자 식기세척기 칸"),
    ("wqJZ_00Sogc", 32.8, 0.32, "검은 유리 덮개 닫기(쏙 숨김)"),
    ("xxGmmE_KLkI", 0.5, 0.45, "보통(빌트인) 식기세척기 문 열린 칸 — 비포, 다른 제품"),
    ("HxOwUlonEW8", 6.2, 0.4, "낮은 식기세척기에 허리 굽혀 그릇 넣는 남자 — 비포, 다른 제품"),
    ("NzSGmn7g4kM", 8.5, 0.5, "낮은 식기세척기 선반에서 그릇 빼는 손 — 비포, 다른 제품"),
    ("HxOwUlonEW8", 9.0, 0.37, "허리 짚고 일어나는 남자 — 비포, 다른 제품"),
    ("TJDOFm5BQkE", 46.0, None, "매장 진열 싱크 매립형 제품(과일 담긴 싱크)"),
    ("TJDOFm5BQkE", 30.0, None, "매장 전시 주방 줄"),
    ("TJDOFm5BQkE", 34.0, None, "매장 전시 줄 끝까지"),
    ("UNB6H9nmbP4", 37.0, 0.55, "싱크대 한 칸 뚜껑이 올라가며 열리는 순간"),
    ("wqJZ_00Sogc", 34.3, 0.4, "손으로 접시를 선반에 툭 넣기"),
    ("wqJZ_00Sogc", 50.3, 0.7, "손으로 덮개 닫기"),
    ("wqJZ_00Sogc", 36.3, 0.42, "싱크볼 속 식기 선반 위에서 본 모습"),
    ("TJDOFm5BQkE", 58.0, None, "덮개 열린 칸 안 세척 선반(그대로 식기세척기)"),
    ("-JU-gKEN1gQ", 48.3, 0.5, "과일·채소 바구니(포도·토마토·피망)"),
    ("wqJZ_00Sogc", 18.3, 0.6, "싱크에서 채소(감자) 씻는 손"),
    ("-JU-gKEN1gQ", 45.4, 0.78, "덮개 터치판 모드 누르기"),
    ("wqJZ_00Sogc", 40.3, 0.5, "그릇 들고 웃는 사람(밝은 주방)"),
    ("wqJZ_00Sogc", 44.3, 0.45, "싱크 위에 그릇 올려놓기"),
    ("wqJZ_00Sogc", 28.8, 0.6, "새 주방 전경(싱크·가스레인지)"),
    ("TJDOFm5BQkE", 88.5, None, "과일 얹은 매립형 싱크 완성 모습"),
]


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def crop_of(w, h, cx):
    if w <= h:   # 세로 소스 — 그대로
        return [0, 0, w, h]
    cw = round(h * 9 / 16)
    x = int(min(max(cx * w - cw / 2, 0), w - cw))
    return [x, 0, cw, h]


def grab(p, t, crop):
    x, y, w, h = crop
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(p), "-frames:v", "1",
                          "-vf", f"crop={w}:{h}:{x}:{y},scale=270:480", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return Image.fromarray(np.frombuffer(raw, np.uint8).reshape(480, 270, 3))


def main():
    steps = N.steps_of(LINES, CHUNK, "replace")
    # 낱말 묶음 끊김 금지(페이블 10-17: '수백만 / 대를' 금지) — 그 줄만 손 토막
    for li, parts in CHUNK_FIX.items():
        idx = [k for k, x in enumerate(steps) if x["line"] == li]
        sent = steps[idx[0]]["sent"]
        new = [{"text": c, "chars": len(c.replace(" ", "")), "new_cut": j == 0, "sent": sent, "line": li} for j, c in enumerate(parts)]
        steps = steps[:idx[0]] + new + steps[idx[-1] + 1:]
    assert len(steps) == len(SHOTS), (len(steps), len(SHOTS))
    t = 0.0
    toks, shots = [], []
    for i, (s, sh) in enumerate(zip(steps, SHOTS)):
        dur = round(max(0.5, s["chars"] / CPS), 2)
        vid, ss, cx, see = sh
        p = SRC / f"src_{vid}.mp4"
        w, h = probe(p)
        crop = crop_of(w, h, cx or 0.5)
        toks.append({"i": i, "line": s["line"], "text": s["text"], "chars": s["chars"], "t0": round(t, 2), "dur": dur})
        shots.append({"i": i, "src": p.name, "url": URL[vid], "ss": ss, "dur": dur, "kind": ("비포(다른 제품 일반 식기세척기)" if vid in BEFORE else "같은 제품 실영상(FOTILE 매립형)"),
                      "full": True, "fit": "cover", "src_crop": crop, "res": f"{w}x{h}", "zoom": round(1920 / crop[3], 2),
                      "audio": "끔(원음 안 씀 — 나레+BGM만)", "ours": see, "caption": s["text"]})
        t += dur
    total = round(t, 2)
    script = {"channel": "homedesignnote", "brand": "잇썸홈", "preset": "channel/homedesignnote/preset/전체화면_가운데자막",
              "topic": "싱크대 매립형 식기세척기(FOTILE 2-in-1/3-in-1 in-sink dishwasher)",
              "voice": {"name": "박창수", "voice_id": "tc_6059dad0b83880769a50502f"}, "cps_target": CPS,
              "bgm": {"id": "honwaka_puppu", "db_below_voice": 14.4, "why": "보컬 없음·차분 7/10(제미나이 청취)"}, "sfx": 0, "meme": 0,
              "lines": [{"i": i, "text": l, "tts": l, "role": ROLE[i], "climax": CLIMAX.get(i)} for i, l in enumerate(LINES)],
              "tokens": toks, "est_sec": total, "source": "channel/homedesignnote/대본초안_5편.md 1번(2판 고조 5)"}
    (HERE / "대본.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    mats = {"_note": "토막 1개 = 컷 1개. 같은 제품(FOTILE 싱크 매립형) 실영상만 — OBRO(7YL, 타 브랜드)·5H2(3D CG) 안 씀. 쇼룸=TJDO(세로 손촬영) 대체 확정. "
                     "남의 글자(영상 자막·FOTILE 로고·끝카드) 구간 피함 — wqJZ 8~14·22~24·48~49·54~55·60~70, -JU 하단 설명 자막 구간 피함.",
            "cand_dir": str(SRC).replace("\\", "/"), "shots": shots}
    (HERE / "재료.json").write_text(json.dumps(mats, ensure_ascii=False, indent=1), encoding="utf-8")

    # 시트: 토막마다 [번호·자막·시각] + 컷 프레임 2장(시작+0.1·끝−0.1)
    font = ImageFont.truetype(str(ROOT / "shopping_shorts/static/fonts/PoorStory.ttf"), 30)
    small = ImageFont.truetype(str(ROOT / "shopping_shorts/static/fonts/Pretendard-Regular.otf"), 18)
    cols, cell_w, cell_h = 5, 560, 520
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for k, sh in enumerate(shots):
        x0, y0 = (k % cols) * cell_w, (k // cols) * cell_h
        p = SRC / sh["src"]
        a = grab(p, sh["ss"] + 0.1, sh["src_crop"]); b = grab(p, sh["ss"] + sh["dur"] - 0.1, sh["src_crop"])
        sheet.paste(a, (x0 + 5, y0 + 36)); sheet.paste(b, (x0 + 285, y0 + 36))
        tk = toks[k]
        d.text((x0 + 6, y0 + 4), f"#{k} {tk['t0']:.2f}s +{tk['dur']:.2f}  {sh['src'][4:-4]} {sh['ss']}s", font=small, fill=(255, 220, 90))
        # 자막(프레임 위 가운데) — 프리셋처럼 흰 글자+검정 외곽
        for img_x in (x0 + 5,):
            tw = d.textlength(tk["text"], font=font)
            d.text((img_x + 275 - tw / 2, y0 + 36 + 200), tk["text"], font=font, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    out = HERE / "plan"; out.mkdir(exist_ok=True)
    sheet.save(out / "계획_시트.jpg", quality=85)
    md = ["# 작품1 싱크대 매립형 식기세척기 — 계획(선검수, TTS·렌더 전)", "",
          f"- 토막 {len(toks)}개 = 컷 {len(shots)}개 · 공백 뺀 글자 {sum(t['chars'] for t in toks)} · 예상 길이 {total}초(8.32자/초)",
          "- 틀: 프리셋 `전체화면_가운데자막`(자막 y 927 기본·PoorStory 64·번짐 외곽선16+blur30+glow60) · 브랜드 잇썸홈 · 짤 0 · 효과음 0 · 원음 끔",
          "- 목소리: 박창수 tc_6059dad0b83880769a50502f · BGM: 아래", "",
          "| # | 줄 | 자막 토막 | 시작~길이(초) | 소스 | 구간 | 화면에 보이는 것 |", "|---|---|---|---|---|---|---|"]
    for tk, sh in zip(toks, shots):
        md.append(f"| {tk['i']} | {tk['line'] + 1} | {tk['text']} | {tk['t0']}+{tk['dur']} | {sh['src'][4:-4]} {sh['res']} ×{sh['zoom']} | {sh['ss']}~{round(sh['ss'] + sh['dur'], 2)} | {sh['ours']} |")
    md += ["", "## BGM — honwaka_puppu 선택", "제미나이 청취(gemini-3-flash-preview, 각 곡 앞 30초, 10-17):", "",
           "| 곡 | 보컬 | 분위기 | 차분(0~10) | 나레 밑 |", "|---|---|---|---|---|",
           "| honwaka_puppu | 없음 | 밝고 아기자기, 단순 반복 멜로디 | 7 | 적합 |",
           "| before_spring_ends | 있음(0~30초) | 감성·드라마틱 | 4 | 부적합 |",
           "| mori_no_restaurant(보조) | 있음 | 따뜻·어쿠스틱 | 7 | 적합 판정이나 보컬 |", "",
           "음량: 원본 bench 말 p90 − 바닥 14.4dB(50편 중앙) → BGM 을 나레보다 약 14dB 아래. 원본 통합 −7.5 LUFS(50편 중앙).",
           "", "## 남의 글자 점검(시트 눈 대조)",
           "- #6 덮개·#11·#25 매장 진열 터치판에 작은 FOTILE 로고(제품 각인, 높이 ~10px) — 같은 제품 실물 각인이라 둠. 페이블 판단 필요하면 크롭/교체.",
           "- 영상 자막 구간(wqJZ 8~14·22~24·48~49·54~55·60~70, -JU 설명 자막) 피함 — #7·#14·#21 은 1판 시트에서 글자 보여 시작·크롭 옮김."]
    (out / "계획.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("토막", len(toks), "예상", total, "초 · 소스 컷 중앙", sorted(t["dur"] for t in toks)[len(toks) // 2])


if __name__ == "__main__":
    main()
