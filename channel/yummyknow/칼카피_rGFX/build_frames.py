"""rGFXQlS9Cp4 틀 2장(훅 카드 / 본문 게시글) — 원본 프레임 픽셀 실측값으로 손 작성(to_frame 은 이 편에서 제목 lines=5 로 실패).
크기·y 는 to_frame.size_and_top(잉크 위 끝·잉크 높이 → 글자 크기·줄 칸 y) 로 푼다(틀 담당 함수 재사용)."""
import json, sys
sys.path.insert(0, r"C:/Users/CH/Desktop/로또의 주식/.tracks/칼카피숏템엔진")
from tools.calcopy.engine import to_frame as T
from shopping_shorts.calcopy_frame import schema

OUT = sys.argv[1]
BRAND = "맛잘알 친구들"      # 원본 채널 이름(맛있는 친구들) 대신 — 남의 채널 이름을 그대로 쓰지 않는다
TITLE = "한국에서 유독 맛 논란 난 코스트코 두바이 스프레드"   # 10-16 4판: 썰형 제목(원본 역할만 — 베끼지 않음)


def text(role, fam, sample, ink_top, ink_h, x, w, align, rgb, lines=1, line_h=None, **kw):
    f = T.size_and_top(fam, sample, ink_top, ink_h, line_h)
    d = {"kind": "text", "role": role, "x": x, "y": f["y"], "w": w, "align": align, "lines": lines, "font": fam,
         "size": f["size"], "line_h": f["line_h"], "rgb": rgb, "line_rgb": None, "outline": None, "shadow": None, "box": None,
         "italic": False, "letter_spacing": 0, "word_spacing": 0, "enter": None}
    d.update(kw)
    return d


body = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": "rGFXQlS9Cp4",
        "made_from": {"tool": "scratch build_frames_rgfx.py", "note": "원본 2.8초 프레임 픽셀 실측(헤더 연두 227,239,211 y0~236 · 프로필 칸 · 글 제목 · 구분선 y515 · 누적 자막 2줄 570/663)"},
        "layers": [
            {"kind": "bg", "rgb": [255, 255, 255]},
            {"kind": "video", "x": 0, "y": 660, "w": 1080, "h": 1260, "radius": 0},   # 원본 컷별 그림 칸 y 666~1185 를 다 담게
            {"kind": "band", "x": 0, "y": 0, "w": 1080, "h": 236, "rgb": [227, 239, 211], "radius": 0},
            text("label", "BMDOHYEON", BRAND, 75, 100, 77, 960, "left", [0, 0, 0], text="» " + BRAND + " 🍽"),
            {"kind": "band", "x": 85, "y": 265, "w": 140, "h": 128, "rgb": [227, 239, 213], "radius": 0},
            text("label", "NotoSansKRBold", "味", 291, 77, 155, 140, "center", [0, 0, 0], text="味"),
            text("brand", "BMDOHYEON", "미 식", 286, 51, 254, 300, "left", [0, 0, 0], text="미 식"),
            text("label", "CcPretendard-Regular", "11:11 | 댓글 9999", 365, 22, 256, 400, "left", [140, 140, 140], text="오늘 | 11:11 | 댓글 9999"),
            text("label", "BMDOHYEON", TITLE, 422, 63, 80, 960, "left", [0, 0, 0], text=TITLE),   # 글 제목 = 고정 문구(title 1줄은 hook1 첫 낱말만 그렸다)
            {"kind": "band", "x": 0, "y": 515, "w": 1080, "h": 2, "rgb": [0, 0, 0], "radius": 0},
            text("caption", "BMDOHYEON", "최근 코스트코는", 570, 54, 540, 1000, "center", [0, 0, 0], lines=2, line_h=93),
        ]}
hook = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": "rGFXQlS9Cp4",
        "made_from": {"tool": "scratch build_frames_rgfx.py", "note": "원본 0.7초 훅 카드 실측(바탕 64,64,64 · 제목 흰/연두 2줄 · 회색 띠 568~683 · 그림 690~1697 전폭)"},
        "layers": [
            {"kind": "bg", "rgb": [64, 64, 64]},
            {"kind": "video", "x": 0, "y": 690, "w": 1080, "h": 1008, "radius": 0},
            text("title", "PretendardXBold", "한국인이 비벼버린", 228, 132, 540, 1000, "center", [255, 255, 255], lines=2, line_h=150,
                 text="한국인이 비벼버린\n두바이 스프레드", line_rgb=[[255, 255, 255], [142, 248, 133]], shadow={"dx": 4, "dy": 4, "blur": 6, "rgb": [0, 0, 0]}),
            {"kind": "band", "x": 0, "y": 568, "w": 1080, "h": 116, "rgb": [235, 235, 235], "radius": 0},
            text("label", "CcPretendard-Bold", TITLE, 590, 66, 540, 960, "center", [0, 0, 0], text=TITLE),
            text("label", "BMDOHYEON", "»", 75, 100, 77, 200, "left", [0, 0, 0], text="»"),
            text("label", "NotoSansKRBold", "🍽", 65, 107, 990, 200, "right", [0, 0, 0], text="🍽"),
        ]}
for name, f in (("frame_rGFX_body.json", body), ("frame_rGFX_hook.json", hook)):
    schema.validate(f)
    open(f"{OUT}/{name}", "w", encoding="utf-8").write(json.dumps(f, ensure_ascii=False, indent=1))
    print("ok", name)
