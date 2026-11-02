# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/맛템썰템판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 옛 영상 재현용 읽기 전용 참고물 — 규칙은 판 칸·_pending.upgrade_from_hand_scripts 로 옮김)
"""yummyknow 3편 외관 교체 — 원본 채널 틀 흔적 제거(채널명 맛템썰템·미식 삭제·팔레트·글꼴·카드 모양·상단·자막 칸·조회수 줄 전부 새 설계).
대본·나레·컷·자막 글은 그대로, 영상 창(video) 자리도 그대로 — frame 만 새 파일로 (관제 097, 10-17)."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent
ESP = [44, 30, 24]         # 샘플 E 에스프레소
PAGE = [247, 243, 238]
CREAM = [255, 246, 224]
GOLD = [240, 200, 120]     # 크림골드(네온 글로우·둘째 줄·선)
BRONZE = [170, 120, 60]    # 메타 글자
WHITE = [255, 255, 255]
SOFT = [222, 205, 180]
RAD = 28
JOBS = {   # 폴더: (hook, body, 새 hook, 새 body, 조회수 줄)
    "칼카피_rGFX": ("frame_rGFX_hook.json", "frame_rGFX_body.json", "frame_rGFX_hook_맛템썰템.json", "frame_rGFX_body_맛템썰템.json", "맛템썰템 · 8.7만 읽음"),
    "새소재_shinramyun_gumi": ("frame_hook.json", "frame_body.json", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "맛템썰템 · 15.2만 읽음"),
    "새소재_rescene_bread": ("frame_hook.json", "frame_body.json", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "맛템썰템 · 11.6만 읽음"),
}


def T(role, text, x, y, w, size, font, rgb, align="left", lines=1, line_h=None, **kw):
    d = {"kind": "text", "role": role, "x": x, "y": y, "w": w, "align": align, "lines": lines, "font": font, "size": size,
         "line_h": line_h or round(size * 1.18), "rgb": rgb, "line_rgb": None, "outline": None, "shadow": None, "box": None,
         "italic": False, "letter_spacing": 0, "word_spacing": 0, "enter": None, "text": text}
    d.update(kw)
    return d


def B(x, y, w, h, rgb, radius=0):
    return {"kind": "band", "x": x, "y": y, "w": w, "h": h, "rgb": rgb, "radius": radius}


def split2(s, n=None):
    """제목을 두 줄로 — 가운데에 가까운 공백에서."""
    if "\n" in s or " " not in s:
        return s
    mid = len(s) / 2
    i = min((k for k, c in enumerate(s) if c == " "), key=lambda k: abs(k - mid))
    return s[:i] + "\n" + s[i + 1:]


def body(d, stats):
    L = d["layers"]
    title = next(l["text"] for l in L if l.get("role") == "label" and l["y"] == 412)
    cap = dict(next(l for l in L if l.get("role") == "caption"))
    vid = dict(next(l for l in L if l["kind"] == "video"))
    vid.update(x=0, y=510, w=1080, h=1300, radius=0)   # 엔진 shot_clip 은 창 x=0·폭 1080 만 받는다 — 좌우 48px 은 바탕색 띠로 덮어 카드처럼 보이게
    cap.update(font="CcPretendard-Bold", size=60, line_h=82, rgb=WHITE, align="center", x=540, y=1620, w=900, lines=2, valign="top",
               box={"rgb": ESP, "pad": 22, "radius": 22})
    d["layers"] = [
        {"kind": "bg", "rgb": PAGE[:]}, vid,
        B(0, 510, 48, 1300, PAGE), B(1032, 510, 48, 1300, PAGE),
        B(0, 0, 1080, 210, ESP),
        T("brand", "맛템썰템", 540, 52, 900, 72, "GmarketSansBold", CREAM, align="center", glow={"px": 28, "rgb": GOLD[:]}),
        B(480, 170, 120, 3, GOLD),
        B(48, 250, 984, 220, WHITE, RAD),
        T("label", stats, 540, 278, 900, 30, "CcPretendard-SemiBold", BRONZE, align="center"),
        T("title", split2(title), 540, 326, 920, 58, "SUITBold", ESP, align="center", lines=2, line_h=70),
        cap,
    ]
    d["_note"] = "맛템썰템 E 에스프레소·크림골드(사장님 선택 10-17): 에스프레소 헤더·네온 채널명·흰 제목 카드·큰 둥근 그림 칸·그림 아래 자막 박스"
    d.pop("made_from", None)
    return d


def hook(d):
    L = d["layers"]
    title = next(l for l in L if l.get("role") == "title")
    label = next(l["text"] for l in L if l.get("role") == "label" and l["y"] == 581)
    vid = dict(next(l for l in L if l["kind"] == "video")); vid.update(x=0, y=690, w=1080, h=1130, radius=0)
    tl = dict(title)
    tl.update(x=540, y=250, w=960, align="center", size=118, line_h=140, font="SUITBold", rgb=WHITE,
              line_rgb=[WHITE[:], GOLD[:]], shadow=None, outline=None, lines=2)
    d["layers"] = [
        {"kind": "bg", "rgb": ESP[:]}, vid,
        B(0, 690, 48, 1130, ESP), B(1032, 690, 48, 1130, ESP),
        T("brand", "맛템썰템", 540, 70, 900, 64, "GmarketSansBold", CREAM, align="center", glow={"px": 28, "rgb": GOLD[:]}),
        B(480, 170, 120, 3, GOLD),
        tl,
        T("label", label, 540, 580, 960, 40, "CcPretendard-SemiBold", SOFT, align="center"),
    ]
    d["_note"] = "맛템썰템 E 훅 카드: 에스프레소 바탕·네온 채널명·흰 큰 제목(둘째 줄 크림골드)·둥근 그림 창"
    d.pop("made_from", None)
    return d


for folder, (h, b, nh, nb, stats) in JOBS.items():
    p = R / folder
    j = json.loads((p / h).read_text(encoding="utf-8")); (p / nh).write_text(json.dumps(hook(j), ensure_ascii=False, indent=1), encoding="utf-8")
    j = json.loads((p / b).read_text(encoding="utf-8")); (p / nb).write_text(json.dumps(body(j, stats), ensure_ascii=False, indent=1), encoding="utf-8")
    print(folder, "ok")
