# -*- coding: utf-8 -*-
"""yummyknow 3편 외관 교체 — 원본 채널 틀 흔적 제거(채널명 맛템썰템·미식 삭제·팔레트·글꼴·카드 모양·상단·자막 칸·조회수 줄 전부 새 설계).
대본·나레·컷·자막 글은 그대로, 영상 창(video) 자리도 그대로 — frame 만 새 파일로 (관제 097, 10-17)."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent
DEEP = [22, 52, 50]        # 깊은 청록 먹색(채도 낮춤)
PAPER = [243, 241, 237]    # 중성 웜 그레이 카드
SHADE = [231, 229, 224]    # 아주 옅은 그림자
WHITE = [255, 255, 255]
ACC = [201, 138, 62]       # 포인트 1색: 낮춘 앰버
ACC_L = [228, 190, 130]    # 훅 제목 2줄(앰버 밝은 톤)
MUTE = [112, 122, 118]
SOFT = [178, 192, 188]
RAD = 44
JOBS = {   # 폴더: (hook, body, 새 hook, 새 body, 조회수 줄)
    "칼카피_rGFX": ("frame_rGFX_hook.json", "frame_rGFX_body.json", "frame_rGFX_hook_맛템썰템.json", "frame_rGFX_body_맛템썰템.json", "8.7만 읽음 · 412 공감"),
    "새소재_shinramyun_gumi": ("frame_hook.json", "frame_body.json", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "15.2만 읽음 · 538 공감"),
    "새소재_rescene_bread": ("frame_hook.json", "frame_body.json", "frame_hook_맛템썰템.json", "frame_body_맛템썰템.json", "11.6만 읽음 · 297 공감"),
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
    cap.update(font="SUITBold", size=62, line_h=93, rgb=WHITE, align="center",
               box={"rgb": DEEP, "pad": 14, "radius": 22})
    d["layers"] = [
        {"kind": "bg", "rgb": WHITE[:]}, vid,
        B(30, 44, 1020, 470, SHADE, RAD),                       # 아주 옅은 그림자
        B(30, 36, 1020, 470, PAPER, RAD),                       # 카드
        B(66, 72, 84, 84, DEEP, 42),                            # 로고 원
        T("brand", "맛", 108, 83, 84, 46, "PretendardXBold", WHITE, align="center"),
        T("brand", "맛템썰템 🥢", 172, 88, 520, 44, "PretendardXBold", DEEP),
        T("label", stats, 1014, 96, 520, 30, "CcPretendard-SemiBold", MUTE, align="right"),
        B(66, 184, 948, 2, [214, 211, 205]),
        T("title", split2(title), 66, 224, 948, 66, "SUITBold", DEEP, lines=2, line_h=88),
        B(66, 428, 72, 6, ACC, 3),
        cap,
    ]
    d["_note"] = "맛템썰템 외관(10-17): 원본 채널 틀(상단 띠·프로필 칸·구분선) 폐기 — 둥근 카드·로고 원·조회 줄·진녹 자막 칸. 영상 창 자리는 그대로"
    d.pop("made_from", None)
    return d


def hook(d):
    L = d["layers"]
    title = next(l for l in L if l.get("role") == "title")
    label = next(l["text"] for l in L if l.get("role") == "label" and l["y"] == 581)
    vid = dict(next(l for l in L if l["kind"] == "video")); vid["radius"] = RAD
    tl = dict(title)
    tl.update(x=66, y=196, w=948, align="left", size=112, line_h=130, font="GmarketSansBold", rgb=WHITE,
              line_rgb=[WHITE[:], ACC_L[:]], shadow=None, outline=None, lines=2)
    d["layers"] = [
        {"kind": "bg", "rgb": DEEP[:]}, vid,
        B(66, 84, 262, 70, PAPER, 35),
        T("brand", "🥢 맛템썰템", 197, 97, 250, 36, "PretendardXBold", DEEP, align="center"),
        tl,
        B(66, 508, 72, 6, ACC, 3),
        T("label", label, 66, 548, 948, 44, "CcPretendard-SemiBold", SOFT),
    ]
    d["_note"] = "맛템썰템 외관(10-17): 훅 카드 — 좌측 정렬 제목·채널 알약·둥근 영상 창. 영상 창 크기·자리 그대로"
    d.pop("made_from", None)
    return d


for folder, (h, b, nh, nb, stats) in JOBS.items():
    p = R / folder
    j = json.loads((p / h).read_text(encoding="utf-8")); (p / nh).write_text(json.dumps(hook(j), ensure_ascii=False, indent=1), encoding="utf-8")
    j = json.loads((p / b).read_text(encoding="utf-8")); (p / nb).write_text(json.dumps(body(j, stats), ensure_ascii=False, indent=1), encoding="utf-8")
    print(folder, "ok")
