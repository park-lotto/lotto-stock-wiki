# -*- coding: utf-8 -*-
"""폰트가 **이 글자를 실제로 그릴 수 있는가** — 판정의 단일 출구(0순위-B).

★왜 이 모듈이 따로 있나 (실사고 2026-08-26)
   '옥 말랑'(OkMallangW.ttf)은 OKFont가 낸 **영문 전용** 폰트인데 한글 폰트 목록에
   들어 있었다(글리프 81개 = 영문·숫자·기호, 한글 0자, 괄호도 없다). 파일 자체는
   정상 TTF라 브라우저도 ffmpeg도 PIL도 **아무 오류 없이 로드**했고, 목록·렌더가 모두
   "파일이 있는가"만 보고 있어서 세 층을 전부 통과한 뒤 고객 영상에서 처음 드러났다.

   고치고 보니 폰트를 쓰는 곳이 **세 군데**였다(사장님 "렌더에서 안되는거 없겠어?"로 발견):
     ① video_assemble  — 자막·헤드카피·워터마크 (ffmpeg drawtext)
     ② deco_frame      — 꾸미기 틀의 채널명·제목 (PIL)
     ③ tools/sync_fonts.py — 목록에 넣는 단계의 가드
   같은 판단을 세 벌 적으면 언젠가 반드시 어긋난다 → 여기 한 곳에서만 정한다.

★판정 원리 — 이름·파일크기로 판정하지 마라(그런 목록은 반드시 썩는다)
   폰트에 없는 글자는 전부 같은 `.notdef` 글리프로 그려진다. 사적사용영역 문자
   두 개(어떤 한글 폰트에도 없다)의 마스크가 서로 같으면 그게 이 폰트의 `.notdef`이고,
   어떤 글자의 마스크가 그것과 같으면 그 글자는 **없는 것**이다.

★Pillow만 쓴다 — fontTools는 requirements.txt에 없다(서버 의존성을 늘리지 않기로).
"""
import sys

from PIL import ImageFont

# 어떤 한글 폰트에도 글리프가 없는 사적사용영역(PUA) 문자 — .notdef 표본을 얻는 자리.
_PUA = ("", "")

# 고른 폰트를 버리고 기본폰트로 되돌리는 문턱(못 그리는 글자 비율).
#
# ★왜 '한 글자라도'가 아닌가 (실측 2026-08-26)
#   완성형 2350자 폰트 10종이 '뷁·똠·뎊'을 못 그린다. 한 글자만 없어도 폴백시키면
#   자막에 '똠양꿍'이 들어간 순간 배민 주아를 골라도 통째로 다른 글꼴이 된다 —
#   두부 한 글자보다 글꼴이 통째로 바뀌는 쪽이 더 큰 사고다.
#   막으려는 건 '옥 말랑'처럼 한글이 아예 없는 폰트다(그 경우 100% 누락).
#   실사용 글자 121자 점검에서 정상 폰트의 최대 누락은 3자(2.5%)였다.
FALLBACK_RATIO = 0.5


def missing_glyphs(font_path, text):
    """font_path 폰트가 text에서 못 그리는 글자들(중복·공백 제외한 문자열).

    공백(U+0020)은 검사하지 않는다 — 빙그레·리디바탕은 공백 글리프가 없지만
    video_assemble._lacks_space_glyph 우회가 이미 처리한다. 여기서 없는 글자로 세면
    사장님이 고른 글꼴이 통째로 바뀌는 회귀가 난다.
    """
    text = _body(text)
    if not text:
        return ""
    try:
        f = ImageFont.truetype(str(font_path), 70)

        def mask(c):
            m = f.getmask(c)
            return (m.size, bytes(m))

        ref, ref2 = mask(_PUA[0]), mask(_PUA[1])
        if ref != ref2:
            return ""  # PUA에 글리프가 있는 폰트 — 이 방법으로는 판정 못 한다
        return "".join(c for c in text if mask(c) == ref)
    except Exception as e:  # noqa: BLE001 — 판정 실패가 렌더를 막으면 안 된다
        print(f"[폰트] 글리프 판정 실패(정상으로 간주) {font_path}: {e!r}", file=sys.stderr)
        return ""


def too_broken(font_path, text, label=""):
    """이 폰트로 이 문구를 그리면 **거의 다 두부인가** — True면 기본폰트로 되돌려라.

    몇 글자만 빠진 경우는 False를 주되(글꼴을 지킨다) stderr에 흔적을 남긴다.
    """
    body = _body(text)
    miss = missing_glyphs(font_path, text)
    if not miss or not body:
        return False
    name = label or str(font_path)
    if len(miss) / len(body) >= FALLBACK_RATIO:
        print(f"[폰트] {name} 이 문구의 {len(miss)}/{len(body)}자를 못 그린다"
              f"({miss[:12]}) — 기본폰트로 대체한다(두부 방지)", file=sys.stderr)
        return True
    print(f"[폰트] {name} 에 없는 글자 {len(miss)}자({miss[:12]}) — 글꼴은 그대로 쓴다",
          file=sys.stderr)
    return False


def _body(text):
    """검사 대상 글자 — 공백을 빼고 중복을 없앤다(비율 계산도 이 기준)."""
    return "".join(dict.fromkeys((text or "").replace(" ", "")))


# ─────────────────────────────────────────────────────────────────────────────
# 띄어쓰기 글리프가 없는 폰트 (빙그레·리디바탕)
#
# ★왜 여기 있나: 종전엔 video_assemble(자막)에만 우회가 있고 deco_frame(꾸미기 틀)에는
#   없었다 → 꾸미기 틀 채널명·제목에서 띄어쓰기가 ⊠로 나갔다(2026-08-26 실측, 36종
#   전수 렌더로 발견). 같은 판단을 두 번 적으면 이렇게 한쪽만 고쳐진다(0순위-B).
# ─────────────────────────────────────────────────────────────────────────────

def lacks_space_glyph(pil_font):
    """이 폰트가 띄어쓰기를 '없는 글자 네모(⊠)'로 그리는가 — 2026-08-24 고객 제보 실측.

    빙그레(Binggrae-Bold)·리디바탕(RIDIBatang)은 U+0020 글리프가 아예 없어서,
    그대로 그리면 **모든 띄어쓰기가 ⊠**가 된다. 나머지는 멀쩡하다.
    판정: 정상 폰트는 공백 마스크 높이가 0이고, 없는 폰트는 글자 높이만큼 나온다.
    """
    try:
        return pil_font.getmask(" ").size[1] > 0
    except Exception as e:  # noqa: BLE001 — 판정 실패가 렌더를 막으면 안 된다
        print(f"[폰트] 공백 글리프 판정 실패(정상으로 간주): {e!r}", file=sys.stderr)
        return False


def space_px(pil_font, size):
    """띄어쓰기 한 칸의 폭. 공백 글리프가 없는 폰트는 advance가 ⊠ 네모 폭(≈1em)이라
    그대로 쓰면 어절이 과하게 벌어진다 → 흔한 비율 0.28em으로 대체한다."""
    return size * 0.28 if lacks_space_glyph(pil_font) else pil_font.getlength(" ")


def text_px(pil_font, text, size):
    """**실제로 그려질** 폭. 공백 없는 폰트에서도 맞다.
    중앙정렬·자동축소가 이 값을 쓰므로 getlength를 직접 부르지 마라(0순위-B)."""
    if not lacks_space_glyph(pil_font):
        return pil_font.getlength(text)
    words = (text or "").split(" ")
    return (sum(pil_font.getlength(w) for w in words)
            + space_px(pil_font, size) * max(0, len(words) - 1))


def draw_text(d, xy, text, font, fill, anchor="la", size=None,
              stroke_width=0, stroke_fill=None):
    """PIL 그리기 — 공백 글리프가 없는 폰트면 어절을 따로 그리고 사이를 좌표로 벌린다.

    anchor는 두 글자(가로,세로). 가로 'l'(왼쪽)·'m'(중앙)만 쓰며, 세로는 그대로 넘긴다.
    정상 폰트는 **종전 그대로 한 번에** 그린다(회귀 0).
    stroke_*는 외곽선(2026-08-28) — 둘 다 있어야만 넘긴다(안 주면 기존과 동일).
    """
    text = text or ""
    sk = ({"stroke_width": stroke_width, "stroke_fill": stroke_fill}
          if (stroke_width and stroke_fill) else {})
    if not lacks_space_glyph(font) or " " not in text:
        d.text(xy, text, font=font, fill=fill, anchor=anchor, **sk)
        return
    size = size or getattr(font, "size", 40)
    x, y = xy
    total = text_px(font, text, size)
    ha, va = (anchor + "a")[:2]
    start = x - total / 2 if ha == "m" else x
    gap = space_px(font, size)
    for w in text.split(" "):
        if w:
            d.text((start, y), w, font=font, fill=fill, anchor="l" + va, **sk)
            start += font.getlength(w)
        start += gap
