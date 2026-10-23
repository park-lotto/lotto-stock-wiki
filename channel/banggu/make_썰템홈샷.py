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
# 샘플 B 차콜·민트네온(사장님 10-17): 차콜 머리·페이지 (238,240,242)·흰 카드·민트 네온 채널명
CHAR, PAGE, WHITE, MINT, MINT_CORE, MINT_DK, INK = [28, 30, 34], [238, 240, 242], [255, 255, 255], [40, 230, 180], [220, 255, 244], [30, 170, 140], [26, 28, 32]
R = 28
# 그림 창 모서리 마스크: 페이지색 바깥 사각 − 둥근 안쪽(evenodd) 한 장. 엔진 창이 가로 1080 고정이라 안쪽 가로 984 둥근 카드는 이 마스크+양옆 띠로 만든다
CORNER = ("data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20viewBox=%270%200%20246%20325%27%3E%3Cpath%20fill-rule=%27evenodd%27%20fill=%27%23EEF0F2%27%20d=%27"
          "M0,0h246v325H0z%20M7,0h232a7,7,0,0,1,7,7v311a7,7,0,0,1-7,7H7a7,7,0,0,1-7-7V7a7,7,0,0,1,7-7z%27/%3E%3C/svg%3E")
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


def header():
    """차콜 머리(높이 210) · 채널명 가운데 GmarketSansBold 72 + 민트 네온 글로우 · 아래 민트 선 120x3(y170)."""
    return [band(0, 0, 1080, 210, CHAR, 0),
            text("brand", "GmarketSansBold", BRAND, 70, 62, 540, 900, "center", MINT_CORE, text=BRAND, glow={"px": 28, "rgb": MINT}),
            band(480, 170, 120, 3, MINT, 0)]


def split2(t):
    w = t.split(" "); best = min(range(1, len(w)), key=lambda i: abs(len(" ".join(w[:i])) - len(" ".join(w[i:]))))
    return " ".join(w[:best]) + chr(10) + " ".join(w[best:])


def frames(key):
    P = PIECES[key]
    d = H / P["dir"]
    ob = json.loads((d / "frame_body.json").read_text(encoding="utf-8"))
    oh = json.loads((d / "frame_hook.json").read_text(encoding="utf-8"))
    post = [l for l in ob["layers"] if l["kind"] == "text" and l["role"] == "label"][0]["text"]
    hook = [l for l in oh["layers"] if l["kind"] == "text" and l["role"] == "title"][0]["text"].split(chr(10))
    meta = BRAND   # 가짜 시각 뺌(사장님 10-24)
    post2 = split2(post)
    body = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": ob.get("source"),
            "made_from": {"tool": "channel/banggu/make_썰템홈샷.py", "note": "샘플 B 차콜·민트네온 — 그림 칸 가로 전체·자막 그림 아래 박스(v2 배치 유지)"},
            "layers": [
                {"kind": "bg", "rgb": PAGE},
                {"kind": "video", "x": 0, "y": 510, "w": 1080, "h": 1300, "radius": 0},
                band(0, 510, 48, 1300, PAGE, 0), band(1032, 510, 48, 1300, PAGE, 0),
                {"kind": "image", "src": CORNER, "x": 48, "y": 510, "w": 984, "h": 1300},
                *header(),
                band(48, 250, 984, 220, WHITE, R),
                text("label", "CcPretendard-SemiBold", meta, 284, 24, 540, 900, "center", MINT_DK, text=meta),
                text("label", "SUITBold", post2, 336, 50, 540, 920, "center", INK, lines=2, line_h=70, text=post2),
                text("caption", "CcPretendard-Bold", "아웃백에서 사람들이", 1604, 50, 540, 900, "center", WHITE, lines=2, line_h=82, valign="top",
                     box={"rgb": CHAR, "pad": 22, "radius": 22}),
            ]}
    hookf = {"canvas": [1080, 1920], "made_by": schema.MADE_BY, "source": ob.get("source"),
             "made_from": {"tool": "channel/banggu/make_썰템홈샷.py", "note": "훅 카드: 샘플 B 팔레트 — 차콜 바탕·민트 네온 채널명·흰 큰 제목(둘째 줄 민트) 가운데 정렬"},
             "layers": [
                 {"kind": "bg", "rgb": CHAR},
                 {"kind": "video", "x": 0, "y": 780, "w": 1080, "h": 1140, "radius": R},
                 *header(),
                 text("title", "SUITBold", hook[0], 290, 92, 540, 1000, "center", WHITE, lines=2, line_h=150,
                      text=chr(10).join(hook), line_rgb=[WHITE, [90, 240, 200]]),
                 text("label", "CcPretendard-SemiBold", post, 650, 36, 540, 960, "center", [168, 180, 184], text=post),
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
            g["box"] = [48, 0, 984, g["win"]["h"]]; g["min_y"] = 0; g["anchor"] = True; g["fit"] = "cover"
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
