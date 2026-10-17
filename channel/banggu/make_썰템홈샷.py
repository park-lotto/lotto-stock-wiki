# -*- coding: utf-8 -*-
"""방구석 3편 외관만 바꿔 재렌더(10-17): 채널명 썰템홈샷 · 코랄 머리띠 + 아이보리 바탕 · 둥근 제목 카드 · 둥근 자막 박스(SBAggroB) · 둥근 그림 칸(엔진 shot_clip 이 창 x=0·폭 1080 만 받아 위 모서리만 둥글다).
내용·컷·나레·자막 글은 그대로 — 나레(TTS) 파일은 기존 것 그대로 쓰고(재호출 없음), 컷·자막 시각은 통과본 timeline.json 에 고정한다.
usage: py make_썰템홈샷.py frames|render  ilii|banana|costco   (frames=틀 json 만 / render=틀+재렌더)"""
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
ROOT = H.parents[1]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import to_frame as T
from shopping_shorts.calcopy_frame import schema

BRAND = "썰템홈샷"
# 팔레트 3색: 깊은 잉크(저채도 갈색 검정) · 중성 바탕(웜 그레이지) · 포인트 1색(저채도 테라코타 코랄)
INK, BG, ACC, WHITE, TINT, SOFT = [38, 34, 31], [246, 242, 236], [214, 106, 80], [255, 255, 255], [236, 228, 218], [200, 194, 186]
R = 36   # 모서리 반경 통일
L = 70   # 왼쪽 기준선 통일
def heart(hexcol):
    return ("data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20viewBox=%270%200%2024%2024%27%20fill=%27none%27%20stroke=%27%23" + hexcol +
            "%27%3E%3Cpath%20d=%27M12%2020s-7-4.500-7-10a4%204%200%200%201%207-2.500A4%204%200%200%201%2019%2010c0%205.500-7%2010-7%2010z%27/%3E%3C/svg%3E")


PIECES = {
    "ilii":   dict(dir="칼카피_ILIi",   win="칼카피_ILIi/render2", name="아웃백영업기밀", bgm_ratio=0.22),
    "banana": dict(dir="칼카피_banana", win="칼카피_banana/render2", name="바나나맛우유단지", bgm_ratio=0.22),
    "costco": dict(dir="칼카피_3편",    win="칼카피_3편/render", name="코스트코가격표암호", bgm_ratio=0.22),
}


def text(role, fam, sample, ink_top, ink_h, x, w, align, rgb, lines=1, line_h=None, **kw):
    f = T.size_and_top(fam, sample, ink_top, ink_h, line_h)
    d = {"kind": "text", "role": role, "x": x, "y": f["y"], "w": w, "align": align, "lines": lines, "font": fam,
         "size": f["size"], "line_h": f["line_h"], "rgb": rgb, "line_rgb": None, "outline": None, "shadow": None, "box": None,
         "italic": False, "letter_spacing": 0, "word_spacing": 0, "enter": None}
    d.update(kw)
    return d


def band(x, y, w, h, rgb, radius=0, **kw):
    return dict({"kind": "band", "x": x, "y": y, "w": w, "h": h, "rgb": rgb, "radius": radius}, **kw)


def header(dark):
    """슬림 머리줄(띠 없음) — 채널명 작게 왼쪽 기준선 · 오른쪽 단색 라인 하트 · 가는 구분선. ≡·돋보기 없음."""
    col = SOFT if dark else INK
    return [text("brand", "GmarketSansBold", BRAND, 52, 40, L, 600, "left", col, text=BRAND, letter_spacing=1),
            {"kind": "image", "src": heart("C8C2BA" if dark else "D66A50"), "x": 920, "y": 40, "w": 80, "h": 80},
            band(L, 132, 1080 - 2 * L, 2, [78, 70, 64] if dark else [222, 216, 208], 0)]


def frames(key):
    P = PIECES[key]
    d = H / P["dir"]
    ob = json.loads((d / "frame_body.json").read_text(encoding="utf-8"))
    oh = json.loads((d / "frame_hook.json").read_text(encoding="utf-8"))
    post = [l for l in ob["layers"] if l["kind"] == "text" and l["role"] == "label"][0]["text"]
    hook = [l for l in oh["layers"] if l["kind"] == "text" and l["role"] == "title"][0]["text"].split("\n")
    meta = BRAND + " · 14:25"
    body = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": ob.get("source"),
            "made_from": {"tool": "channel/banggu/make_썰템홈샷.py", "note": "방구석 틀 외관 변형(10-17): 슬림 머리줄·저채도 팔레트·왼쪽 정렬 카드·SUIT 자막 박스. 내용은 그대로"},
            "layers": [
                {"kind": "bg", "rgb": BG},
                {"kind": "video", "x": 0, "y": 410, "w": 1080, "h": 1400, "radius": R},
                *header(False),
                band(L - 6, 176, 1080 - 2 * L + 12, 196, [228, 221, 211], R),      # 아주 옅은 그림자(밑으로 6px 비껴 깐 한 장)
                band(L - 10, 164, 1080 - 2 * L + 20, 198, WHITE, R),
                text("label", "CcPretendard-Regular", meta, 198, 26, L + 30, 700, "left", ACC, text=meta),
                text("label", "PretendardXBold", post, 262, 54, L + 30, 1080 - 2 * L - 20, "left", INK, text=post),
                text("caption", "SUITBold", "아웃백에서 사람들이", 1560, 48, 540, 900, "center", WHITE, lines=2, line_h=82, valign="top",
                     box={"rgb": [52, 46, 42], "pad": 22, "radius": R}),
            ]}
    hookf = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": ob.get("source"),
             "made_from": {"tool": "channel/banggu/make_썰템홈샷.py", "note": "훅 카드: 깊은 잉크 바탕 · 왼쪽 정렬 큰 제목(포인트색 둘째 줄) · 포인트 막대 + 문장 · 둥근 그림 창"},
             "layers": [
                 {"kind": "bg", "rgb": INK},
                 {"kind": "video", "x": 0, "y": 740, "w": 1080, "h": 1180, "radius": R},
                 *header(True),
                 text("title", "PretendardXBold", hook[0], 214, 92, L, 1080 - 2 * L, "left", WHITE, lines=2, line_h=150,
                      text="\n".join(hook), line_rgb=[WHITE, [232, 128, 102]], shadow={"dx": 0, "dy": 4, "blur": 10, "rgb": [20, 17, 15]}),
                 band(L, 548, 96, 8, ACC, 4),
                 text("label", "CcPretendard-Regular", post, 590, 40, L, 1080 - 2 * L, "left", SOFT, text=post),
             ]}
    for name, f in (("frame_hook_썰템홈샷.json", hookf), ("frame_body_썰템홈샷.json", body)):
        schema.validate(f)
        (d / name).write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
        print("ok", d.name, name, len(f["layers"]), "층")


def render(key):
    from tools.calcopy import narr_video as nv
    P = PIECES[key]
    d = H / P["dir"]
    WIN = Path("C:/숏템_칼카피/banggu") / P["win"]
    OUT = Path("C:/숏템_칼카피/banggu/썰템홈샷") / key
    OUT.mkdir(parents=True, exist_ok=True)
    au = json.loads((WIN / "audio.json").read_text(encoding="utf-8"))
    plan = {"tteutgi": str(H / "칼카피_ILIi/뜯기2/뜯기.json"),
            "frames": [{"frame": str(d / "frame_hook_썰템홈샷.json"), "t_end": None}, {"frame": str(d / "frame_body_썰템홈샷.json"), "t_end": None}],
            "script": str(d / "대본.json"), "tts": au["tts"], "materials": str(d / "재료.json"), "out": str(OUT),
            "bgm": au["bgm"], "bgm_ratio": au["bgm_ratio"], "lufs": au["target_lufs"], "chunk": 13}
    import inspect
    _orig = nv.shot_clip
    def _wide(*a, **k):   # v2: 그림 칸 = 창 전체(가로 1080·세로 창 높이, cover) — 오른쪽 치우침·흰 빈칸 없음, 자막은 그림 위 아래쪽(min_y 해제)
        b = inspect.signature(_orig).bind(*a, **k); b.apply_defaults(); g = b.arguments
        if not g["full"]:
            g["box"] = [0, 0, 1080, g["win"]["h"]]; g["min_y"] = 0; g["anchor"] = True; g["fit"] = "cover"
        return _orig(*b.args, **b.kwargs)
    nv.shot_clip = _wide
    old = json.loads((WIN / "timeline.json").read_text(encoding="utf-8"))["steps"]
    nv.time_steps = lambda st, audio, snap=0.4, **kw: ([dict(s) for s in old], nv.speech_segments(audio)[1])
    print("final", nv.build(plan))


if __name__ == "__main__":
    mode, key = sys.argv[1], sys.argv[2]
    frames(key)
    if mode == "render":
        render(key)
