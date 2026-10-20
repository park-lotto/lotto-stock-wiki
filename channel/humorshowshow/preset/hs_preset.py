# -*- coding: utf-8 -*-
"""썰템쇼(벤치 재밌쇼 @humorshowshow) 프리셋 「썰템쇼_화자썰」 — 틀 2장(훅 카드 + 본문 게시글) 손질 → preset_save → 채널 규칙 → loo 렌더 대조 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/humorshowshow/preset/hs_preset.py hand     # 실측(hs_measure) → _hand/frame_<id>.json 8장
    PYTHONUTF8=1 py channel/humorshowshow/preset/hs_preset.py build    # _hand 8장 → 프리셋 + CHANNEL_RULES
    PYTHONUTF8=1 py channel/humorshowshow/preset/hs_preset.py loo      # 편 하나 빼고 만든 프리셋 → 실제 렌더(compose_still) → 원본과 층별 잉크 대조

방향(사장님 10-18): 벤치 재밌쇼를 **그대로** 카피. 바꾸는 것은 로고 「재밌쇼」→「썰템쇼」 하나(같은 꼴·자리·크기). 조회수 줄도 벤치처럼 켠다(숫자는 변수, 기본값 = 벤치 꼴).
렌더러가 못 그리는 것(글자 회전·세로 그라데이션·기울어진 선)은 가장 가까운 꼴로 두고 manifest.differences 에 적는다.
실측 근거: hs_measure.py → C:/숏템_칼카피/humorshowshow/preset_work/measure/{all,fonts}.json (8편, 본문·훅 프레임 한 장씩).
"""
from __future__ import annotations

import copy
import json
import statistics as st
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402
from tools.calcopy.engine import preset_save as P, to_frame as TF  # noqa: E402
from channel.humorshowshow.preset import hs_measure as HM  # noqa: E402

SLUG, STYLE = "humorshowshow", "썰템쇼_화자썰"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
HAND = Path(__file__).parent / "_hand"
WORK = HM.WORK
TG = Path("C:/숏템_칼카피/humorshowshow/뜯기")
IDS = HM.IDS
BRAND = "썰템쇼"

# 훅 라벨 줄 = 화면 글(눈으로 읽음, 훅 프레임 0.9초). 줄판독 title_card 를 이어 붙인 글과 다른 3편만(나머지 5편은 같음 — fontmatch 0.71~0.76 로 확인)
LABEL_FIX = {"cHynO-CRdYE": "한국인들을 완전히 낚아버린 와사비의 정체",
             "BlA9f8rBPuc": "오뚜기가 일반인한테는 절대 안 파는 것",
             "0Q-CAw_iaNw": "한국인들이 유독 못 지킨다는 디저트 레시피"}
# 조회수 줄 날짜(편마다, 본문 프레임 메타 줄 눈으로 읽음 — preset_work/meta_rows.png · meta_cH.png). 나머지 글자는 8편 같음
META_DATE = {"NBdmq90aJus": "26.01.31", "jECuoRljWj0": "26.03.31", "GPeF16iUHNo": "25.10.31", "cHynO-CRdYE": "25.10.31",
             "BlA9f8rBPuc": "25.10.31", "cj3-wcltAao": "26.03.31", "xJvwMApZwnE": "26.02.28", "0Q-CAw_iaNw": "25.11.30"}
META_TMPL = "추천891 조회 1,954,556 {d} 09:18 댓글"

ROLES = ["훅 카드(0~2초): [주체] + [센 동사] + [정체 숨긴 대상]? — 2줄째 연두, 아래 띠에 같은 문장",
         "대상 소개·배경(회사·시장·문제, ~는데로 넘김)",
         "충격 사실·장애물(숫자·ㄷㄷ)",
         "화자 대사 1~3줄(「화자 : 대사」 + 반응 짤)",
         "정체 공개·해결(바로 ○○ / 대체품·먹는 법)",
         "근거(성분표·문의답변·댓글·인터뷰 캡처 + 빨간 화살표·밑줄)",
         "맛·이득 묘사 2~4줄(꾸덕·도른 조합·쟁여두기)",
         "끝줄 = 1인칭 혼잣말 드립 + ㅋㅋ(아/하 ~ 로 시작)"]


def _M() -> dict:
    return json.loads((WORK / "measure" / "all.json").read_text(encoding="utf-8"))


def _med(xs):
    xs = [x for x in xs if x is not None]
    return int(round(st.median(xs))) if xs else None


def _medf(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def _rgb_med(xs):
    xs = [x for x in xs if x]
    return [int(round(st.median(c[i] for c in xs))) for i in range(3)]


def measured() -> dict:
    """8편 실측 중앙값(층마다) — 손질 숫자의 출처. 편마다 본문 = body2(없으면 body1)."""
    A = _M()
    B = [r.get("body2") or r["body1"] for r in A.values()]
    Ball = [r[k] for r in A.values() for k in ("body1", "body2") if r.get(k)]
    H = [r["hook"] for r in A.values()]
    two = [b["cap_lines"] for b in Ball if len(b["cap_lines"]) == 2]
    one = [b["cap_lines"][0] for b in Ball if b["cap_lines"]]
    capx = [(x[0] + x[1]) / 2 for b in Ball for x in b["cap_x"] if x[1] - x[0] > 250]
    return {
        "hdr_rgb": _rgb_med(b["hdr_rgb"] for b in B), "hdr_end": _med(b["hdr_end"] for b in B),
        "arrow": [_med(b["arrow"][i] for b in B) for i in range(4)], "arrow_rgb": _rgb_med(b["arrow_rgb"] for b in B),
        "bookmark": [_med(b["bookmark"][i] for b in B) for i in range(4)], "bookmark_rgb": _rgb_med(b["bookmark_rgb"] for b in B),
        "logo": [_med(b["logo"][i] for b in B) for i in range(4)], "logo_green": _rgb_med(b["logo_green"] for b in B),
        "title_top": _med(b["title_rows"][0] for b in B), "title_bot": _med(b["title_rows"][1] for b in B),
        "title_cx": _med((b["title_x"][0] + b["title_x"][1]) / 2 for b in B),
        "meta_rows": [_med(b["meta_rows"][i] for b in B) for i in (0, 1)],
        "meta_gray": _rgb_med(b["meta_gray_rgb"] for b in B), "meta_red": _rgb_med(b["meta_red_rgb"] for b in B),
        "meta_dark": _rgb_med(b["meta_dark_rgb"] for b in B), "meta_red_x": [_med(b["meta_red_x"][i] for b in B) for i in (0, 1)],
        "divider": [_med(b["divider_rows"][i] for b in B) for i in (0, 1)], "divider_rgb": _rgb_med(b["divider_rgb"] for b in B),
        "cap1_top": _med(x[0] for x in one), "cap1_bot": _med(x[1] for x in one),
        "cap2_top": _med(x[1][0] for x in two), "cap_cx": _med(capx),
        "window": [_med(b["window_rows"][0] for b in B), _med(b["window_rows"][1] for b in B)],
        "hook_bg": _rgb_med(h["bg_rgb"] for h in H),
        "hook_white": [_med(h["white_rows"][i] for h in H) for i in (0, 1)],
        "hook_green": [_med(h["green_rows"][i] for h in H) for i in (0, 1)], "hook_green_rgb": _rgb_med(h["green_rgb"] for h in H),
        "hook_label": [_med(h["label_rows"][i] for h in H) for i in (0, 1)],
        "n": len(A),
    }


def svg_uri(svg: str) -> str:
    return "data:image/svg+xml," + quote(svg, safe=":/=,.-")


def _hex(rgb):
    return "%23" + "".join(f"{c:02x}" for c in rgb)


def icons(m: dict) -> dict:
    """머리띠 아이콘 — 원본 프레임 확대(preset_work/arrow_z.png·book_z.png)를 보고 잰 꼴을 SVG 로. 색·상자 = 8편 실측 중앙.
    schema 의 image.src 는 300자 상한 — 경로 하나·짧은 색 표기로 줄인다."""
    ax0, ay0, ax1, ay1 = (int(v) for v in m["arrow"])
    aw, ah = ax1 - ax0 + 1, ay1 - ay0 + 1
    arrow = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {aw} {ah}'><path d='M{aw - 4} 4L4 {ah // 2}L{aw - 4} {ah - 4}' "
             f"fill='none' stroke='#{''.join(f'{c:02x}' for c in m['arrow_rgb'])}' stroke-width='7' stroke-linecap='round'/></svg>")
    bx0, by0, bx1, by1 = (int(v) for v in m["bookmark"])
    bw, bh = bx1 - bx0 + 1, by1 - by0 + 1
    book = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {bw} {bh}'><path d='M0 5Q0 0 5 0H{bw - 5}Q{bw} 0 {bw} 5V{bh - 2}"
            f"L{bw // 2} {round(bh * 0.765)}L0 {bh - 2}Z' fill='#{''.join(f'{c:02x}' for c in m['bookmark_rgb'])}'/></svg>")
    # 로고 따옴표 〃 〃 — 왼쪽 [420,138,430,146] · 오른쪽 [653,139,664,146](3편 같은 값), 짧은 검정 빗금 두 개씩
    qx0, qy0, qw, qh = 419, 137, 247, 11
    quotes = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {qw} {qh}'><path d='M2 2l2 7M7 2l2 7M236 3l2 7M241 3l2 7' "
              f"stroke='#000' stroke-width='2.4' stroke-linecap='round'/></svg>")
    out = {"arrow": {"kind": "image", "src": svg_uri(arrow), "x": ax0, "y": ay0, "w": aw, "h": ah},
           "bookmark": {"kind": "image", "src": svg_uri(book), "x": bx0, "y": by0, "w": bw, "h": bh},
           "quotes": {"kind": "image", "src": svg_uri(quotes), "x": qx0, "y": qy0, "w": qw, "h": qh}}
    for k, v in out.items():
        assert len(v["src"]) <= 300, (k, len(v["src"]))
    return out


def text(role, fam, sample, ink_top, ink_h, x, w, align, rgb, lines=1, line_h=None, **kw):
    f = TF.size_and_top(fam, sample, ink_top, ink_h, line_h)
    d = {"kind": "text", "role": role, "x": x, "y": f["y"], "w": w, "align": align, "lines": lines, "font": fam,
         "size": f["size"], "line_h": f["line_h"], "rgb": rgb, "line_rgb": None, "outline": None, "shadow": None, "box": None,
         "italic": False, "letter_spacing": 0, "word_spacing": 0, "enter": None}
    d.update(kw)
    return d


LOGO_FONT = "BMJUA"           # fontmatch.pooled_rank 1위(재·밌·쇼 글자별 + 낱말, 4표 정규화 0.902) — preset_work/logo_fontmatch.json
LOGO_CX = [460, 541, 622]     # 글자 가운데 x — 원본 로고 상자 419~665(외곽 포함, 8편 중앙)를 BMJUA 글자 셋(글자폭 77+외곽 8)이 4px 씩만 겹쳐 채우게 고르게 나눔.
                              # 3차 렌더(jECu)에서 원본 글자별 가운데(471·552·620)를 그대로 쓰면 BMJUA '쇼'(81px)가 원본 '쇼'(51px)보다 넓어 템·쇼가 20px 겹쳤다
LOGO_FILL = [145, 76]         # 채움 잉크 위·높이 → BMJUA 92.7px(위 145 = 4차 loo 로고 상자 위 −0/아래 −8~9 를 가운데로: 4px 내림). 원본 채움 상자 138~227(기울어진 글자 포함)보다 낮다 — 폭을 맞추면 높이가 모자람(글자 회전 없음, differences)
LABEL_LS = -2.6                  # 렌더 보정: 2차 loo NBdm 라벨 폭 876(원본 821, +6.7%) → 글자 21개에 −2.6px
LABEL_FONT = "CcPretendard-SemiBold"   # 훅 라벨 — 1차 렌더(Bold)가 원본보다 굵고 5% 넓음(preset_work/label_cmp.png) → 한 단계 가는 SemiBold
CAP_FONT = "CcPretendard-Bold"   # 자막·훅 라벨 — 글자 맞는 줄(점수 0.6↑) 1위 Pretendard-Bold 4·NotoSansKR-Bold 3 (근소, fonts.json)
HOOK_DY, HOOK_K = 8.5, 98 / 95   # 렌더 보정: 1차 렌더 흰 잉크 138~233(원본 146~244) — PIL 역산과 브라우저 자리 차이
CAP_LINES = 3                    # ★우회(엔진 요청): 벤치 자막은 최대 2줄인데 렌더러 맞춤(precision20-ui.js specTexts, rows>1 이면 scrollHeight>clientHeight+1 로 넘침 판정)이
                                 # 2줄 칸(line_h×2)에서 늘 넘침으로 봐 글자를 88%로 줄였다(loo GPeF 2줄 자막 잉크 46px·폭 −12%). 칸을 3줄로 두면(valign top 이라 1·2줄 자리 같음) 원본과 ±2px — preset_work/exp_lines3
CAP_K, CAP_LS = 1.04, -1.0       # 렌더 보정: 1차 자막 잉크 500~550·폭 473(원본 498~552·483) — 높이 키우고 자간 −1
META_FONT = "SUITBold"        # 메타 줄 — 낱말별 대조 조회 0.76·댓글 0.90·익명 0.78 1위


def meta_ws(size: float, txt: str, target_w: float) -> float:
    f = TF._pil_font(META_FONT, size)
    w = f.getlength(txt)
    return round((target_w - w) / txt.count(" "), 1)


TEXT_FIX = {"jECuoRljWj0": ("깨부셨다는", "깨부쉈다는")}   # 줄판독 오타 — 화면 글은 '깨부쉈다는'(loo 대조시트_훅·본문에서 눈으로 확인)


def hand(vid: str, m: dict, A: dict) -> dict:
    T = dict(A[vid]["times"])
    if vid in TEXT_FIX:
        a_, b_ = TEXT_FIX[vid]
        T["title_card"], T["post_title"] = T["title_card"].replace(a_, b_), T["post_title"].replace(a_, b_)
    tc = [s.strip() for s in T["title_card"].split("/")]
    label = LABEL_FIX.get(vid, " ".join(tc))
    he = HM.hook_end(vid)
    ic = icons(m)
    # ── 본문 ──
    W0, W1 = m["window"]
    hdr = m["hdr_rgb"]
    logo = []
    for ch, cx, fill in zip(BRAND, LOGO_CX, ([175, 218, 129], [255, 255, 255], [175, 218, 129])):
        logo.append(text("brand", LOGO_FONT, BRAND, LOGO_FILL[0], LOGO_FILL[1], cx, 120, "center", fill, text=ch,
                         outline={"px": 4, "rgb": [0, 0, 0]}, shadow={"dx": 5, "dy": 5, "blur": 0, "rgb": [172, 196, 138]}))
    mt, mb = m["meta_rows"]
    dark_l = text("label", META_FONT, "익명", mt + 1, mb - mt - 2, 80, 60, "left", m["meta_dark"], text="익명")
    gray_txt = META_TMPL.format(d=META_DATE[vid])
    gl = text("label", META_FONT, "추천891 조회", mt + 1, mb - mt - 2, 137, 470, "left", m["meta_gray"], text=gray_txt)
    gl["word_spacing"] = meta_ws(gl["size"], gray_txt, 596 - 137)
    red_l = text("label", META_FONT, "7544", mt + 4, 15, m["meta_red_x"][0] - 1, 80, "left", m["meta_red"], text="7544")
    title = text("label", "PretendardXBold", T["post_title"], m["title_top"], m["title_bot"] - m["title_top"], round(m["title_cx"]), 980,
                 "center", [0, 0, 0], text=T["post_title"])
    cap = text("caption", CAP_FONT, "가나다라마바사", m["cap1_top"], (m["cap1_bot"] - m["cap1_top"]) * CAP_K, round(m["cap_cx"]), 1000, "center",
               [0, 0, 0], lines=CAP_LINES, line_h=m["cap2_top"] - m["cap1_top"], valign="top", letter_spacing=CAP_LS)
    body = [{"kind": "bg", "rgb": [255, 255, 255]},
            {"kind": "video", "x": 0, "y": W0, "w": 1080, "h": W1 - W0 + 1, "radius": 0},
            {"kind": "band", "x": 0, "y": 0, "w": 1080, "h": m["hdr_end"], "rgb": hdr, "radius": 0},
            ic["arrow"], ic["bookmark"], ic["quotes"], *logo, title, dark_l, gl, red_l,
            {"kind": "band", "x": 0, "y": m["divider"][0], "w": 1080, "h": m["divider"][1] - m["divider"][0] + 1, "rgb": m["divider_rgb"], "radius": 0},
            cap]
    # ── 훅 카드 ── 띠 줄 밝기는 8편 중앙 프레임(hs_measure 훅 행 표, 10-18 출력)
    wt, wb = m["hook_white"]
    gt, gb = m["hook_green"]
    htitle = text("title", "GmarketSansBold", tc[0], wt + HOOK_DY, (wb - wt) * HOOK_K, 540, 1060, "center", [255, 255, 255], lines=2, line_h=gt - wt,
                  text="\n".join(tc), line_rgb=[[255, 255, 255], m["hook_green_rgb"]],
                  outline={"px": 3, "rgb": [0, 0, 0]}, shadow={"dx": 6, "dy": 6, "blur": 0, "rgb": [20, 20, 20]})
    lt, lb = m["hook_label"]
    hlabel = text("label", LABEL_FONT, label, lt, lb - lt, 540, 1040, "center", [0, 0, 0], text=label, letter_spacing=LABEL_LS)
    hook = [{"kind": "bg", "rgb": [97, 97, 97]},
            {"kind": "video", "x": 0, "y": 748, "w": 1080, "h": 1172, "radius": 0},
            {"kind": "band", "x": 0, "y": 0, "w": 1080, "h": m["hdr_end"], "rgb": m["hook_bg"], "radius": 0},
            {"kind": "band", "x": 0, "y": 490, "w": 1080, "h": 38, "rgb": [227, 227, 227], "radius": 0, "fade": [38, 0]},
            {"kind": "band", "x": 0, "y": 530, "w": 1080, "h": 3, "rgb": [55, 55, 55], "radius": 0},
            {"kind": "band", "x": 0, "y": 533, "w": 1080, "h": 107, "rgb": [253, 253, 253], "radius": 0},
            {"kind": "band", "x": 0, "y": 640, "w": 1080, "h": 64, "rgb": [237, 237, 237], "radius": 0},
            {"kind": "band", "x": 0, "y": 704, "w": 1080, "h": 3, "rgb": [50, 50, 50], "radius": 0},
            {"kind": "band", "x": 0, "y": 707, "w": 1080, "h": 26, "rgb": [205, 205, 205], "radius": 0, "fade": [0, 26]},
            {"kind": "band", "x": 0, "y": 733, "w": 1080, "h": 15, "rgb": [52, 52, 52], "radius": 0},
            htitle, hlabel]
    F = {"canvas": [1080, 1920],
         "frames": [{"id": "hook", "span": [0, he], "layers": hook}, {"id": "body", "span": [he, None], "layers": body}],
         "template_off": None, "made_by": schema.MADE_BY, "source": vid,
         "made_from": {"tool": "channel/humorshowshow/preset/hs_preset.py hand (hs_measure 8편 실측 중앙값)", "font": CAP_FONT,
                       "notes": [
                           f"훅 길이 {he}초 = 머리띠 연두가 처음 뜨는 프레임(hs_measure.hook_end, 30fps)",
                           f"본문 머리띠 0~{m['hdr_end'] - 1} {hdr} · 구분선 {m['divider']} {m['divider_rgb']} · 그림 창 {W0}~{W1} (8편 중앙, measure/all.json)",
                           f"로고 '{BRAND}' = 벤치 '재밌쇼' 자리(글자 채움 가운데 x {LOGO_CX}, 채움 위 {LOGO_FILL[0]} 높이 {LOGO_FILL[1]}) · 색 초록 [175,218,129]/흰/초록 · 검정 외곽 4px(행 판독 KKK+번짐) · 연초록 그림자 [172,196,138] 5px(오른쪽 아래) · 글꼴 {LOGO_FONT}(fontmatch 묶음 1위, 낮은 확신 raw 0.44)",
                           f"게시글 제목 = 줄판독 post_title, PretendardXBold(fontmatch 8/8 1위 raw 0.78), 잉크 {m['title_top']}~{m['title_bot']} 가운데 {m['title_cx']}",
                           f"조회수 줄 = 벤치처럼 켬(사장님 10-18): 익명 검정 x80 · 회색 {m['meta_gray']} x137~596 · 댓글 수 빨강 {m['meta_red']} x{m['meta_red_x']} · 잉크 {m['meta_rows']} · 날짜 {META_DATE[vid]}",
                           f"자막 = 누적형 2줄(valign top) 1줄 잉크 {m['cap1_top']}~{m['cap1_bot']} · 2줄 위 {m['cap2_top']} · 가운데 x {m['cap_cx']} · 검정 외곽 없음 · {CAP_FONT}",
                           f"훅 제목 GmarketSansBold(fontmatch 16줄 1위 raw 0.81, 15/16 일치) 흰 잉크 {m['hook_white']} · 연두 {m['hook_green_rgb']} 잉크 {m['hook_green']} · 검정 외곽 3px + 그림자 (5,4) [20,20,20]",
                           f"훅 띠: 490~527 밝아지는 회색(fade) · 530 검정 선 · 533~703 흰 칸 · 704 검정 선 · 707~732 어두워지는 회색 · 733~747 짙은 띠 · 그림 748~1919 (8편 같은 줄 밝기 std ≤7)",
                           f"훅 라벨 = {'눈으로 읽은 화면 글' if vid in LABEL_FIX else '줄판독 title_card 이어 붙임(화면과 같음)'} · 잉크 {m['hook_label']}"]}}
    schema.validate(F)
    return F


def write_hand():
    m = measured()
    A = _M()
    HAND.mkdir(exist_ok=True)
    (WORK / "measure" / "medians.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in IDS:
        (HAND / f"frame_{v}.json").write_text(json.dumps(hand(v, m, A), ensure_ascii=False, indent=1), encoding="utf-8")
    print("손질", len(IDS), "장 →", HAND)


# ── 채널 규칙(대본·소리·컷) ──
def sound_cut_stats() -> dict:
    rows = []
    for v in IDS:
        p = TG / v / "뜯기.json"
        if not p.exists():
            continue
        J = json.loads(p.read_text(encoding="utf-8"))
        a, c, vr = J.get("audio") or {}, J.get("cuts") or {}, J.get("voice_rules") or {}
        rows.append({"id": v, "dur": J["probe"]["duration"], "lufs": (a.get("bench") or {}).get("I"), "tp": (a.get("bench") or {}).get("TP"),
                     "cps": vr.get("cps"), "kind": (a.get("composition") or {}).get("kind"),
                     "shot_med": (c.get("shot_len") or {}).get("median"), "first_cut": c.get("first_cut"),
                     "cut_eq_sub": c.get("cut_eq_sub_rate"), "cut_per_min": c.get("cut_per_min"),
                     "zoomin": (c.get("zoom") or {}).get("zoomin_frac"),
                     "sub_med": _medf([b - a_ for a_, b in (J.get("captions") or {}).get("spans") or []])})
    f = lambda k: _medf([r[k] for r in rows])
    return {"n": len(rows), "ids": [r["id"] for r in rows], "rows": rows,
            "median": {k: (round(f(k), 3) if f(k) is not None else None) for k in
                       ("dur", "lufs", "tp", "cps", "shot_med", "first_cut", "cut_eq_sub", "cut_per_min", "zoomin", "sub_med")},
            "kinds": {k: sum(1 for r in rows if r["kind"] == k) for k in {r["kind"] for r in rows}}}


def channel_rules(S: dict) -> dict:
    md = S["median"]
    return {
        "_why": "사장님 10-18(벤치 재밌쇼 그대로 칼카피, 로고만 썰템쇼, 조회수 줄 켬) + 21편 줄판독 + 뜯기 실측(값마다 출처)",
        "style": "화자썰", "style_ref": "channel/스타일.json 화자썰", "script_ref": "channel/humorshowshow/대본스타일_줄판독_2026-10-17.md",
        "brand": BRAND, "bench": "재밌쇼(@humorshowshow)",
        "speaker_lines": {"rule": "「화자 : 대사」 자막 줄 0~3개/편 — 화자 = 의인화한 집단·회사·나라(한국인들·제조사·벨·코스트코·프랑스…)",
                          "narration_reads": "나레는 화자 이름을 빼고 대사만 읽는다(78p9·jECu 받아쓰기 대조)",
                          "count_from": "21편 356줄: 화자대사 48 · 2인대화 8 (15/21편에 있음)", "max_per_video": 3},
        "speaker_line_picture": "반응 짤(해외 드라마·영화 표정·예능 장면) — 짤 속 원래 자막과 대사 말장난(21편 중 밈짤 있는 편 17/21)",
        "last_line": {"rule": "1인칭 혼잣말 드립 + ㅋㅋ 로 끝", "from": "훅 카드 꼴 16/16편 ㅋㅋ 끝, 그중 12편 '아/하 ~' 시작"},
        "caption_endings": {"from": "21편 자막 끝 판독", "ㄷㄷ": 27, "~는데": 17, "ㅋㅋ": 16, "명사 끝": 10, "~인데": 7, "~다고": 6, "~함/~임/~보임": 11},
        "tone": "반말 전언체(존댓말 0 — 뜯기 script_tone polite_ratio 0.0 NBdm)",
        "hook_formula": "[주체(한국인들/코스트코/오뚜기)] + [센 동사(대놓고 차별한·낚아버린·깨부셨다는)] + [정체 숨긴 대상(디저트·소스)]?",
        "sound": {"narration": f"나레 1명 — 뜯기 audio.composition kind 판정된 {sum(v for k, v in S['kinds'].items() if k)}편 {{{', '.join(f'{k}: {v}' for k, v in S['kinds'].items() if k)}}}, 나머지 {S['kinds'].get(None, 0)}편은 무료 키 quota 로 받아쓰기 실패(미판정)",
                  "speech_rate_cps": md["cps"], "speech_rate_from": f"뜯기 voice_rules.cps 중앙(받아쓰기 된 편만 {sum(1 for r in S['rows'] if r['cps'])}편)",
                  "master_lufs": md["lufs"], "true_peak": md["tp"], "lufs_from": f"뜯기 audio.bench.I 중앙({S['n']}편)",
                  "bgm": "있음·경쾌(NBdm 판독 '경쾌한·신나는·정보전달')", "sfx": "휙·띵(NBdm 받아쓰기 sfx 6개/28초)",
                  "voice_tone": "빠르고 위트 있는 20대 남성 TTS 해설 톤(NBdm 제미나이 판독) — 목소리는 따라가지 않는다(사장님 10-17)"},
        "shot_contract": {"cut_sec_median": md["shot_med"], "first_cut_sec": md["first_cut"], "cut_eq_sub_rate": md["cut_eq_sub"],
                          "cut_per_min": md["cut_per_min"], "sub_sec_median": md["sub_med"], "zoomin_frac": md["zoomin"],
                          "duration_sec_median": md["dur"], "from": f"뜯기 cuts·captions 중앙({S['n']}편: {', '.join(S['ids'])})",
                          "rows": S["rows"]},
        "meta_line": {"status": "켬(사장님 10-18 '벤치처럼 켜 둔다') — 숫자는 변수, 기본값 = 벤치 실측 꼴",
                      "bench_value": "익명 추천891 조회 1,954,556 <날짜> 09:18 댓글 7544 (8편 같은 값, 날짜만 다름)",
                      "caution": "21편 전부 같은 꾸민 값 — 우리 금지선(가짜지표)과 부딪칠 수 있어 사장님 확인 기록용"},
        "materials": "남의 영상 재편집 0.85 · 짤·밈 0.15 (NBdm 뜯기 materials)",
    }


DIFFERENCES = [
    "로고: 벤치는 글자마다 기울인 손글씨 레터링 — 렌더러에 글자 회전 칸이 없어 BMJUA 바로 선 글자 3개(같은 자리·크기·색·외곽·그림자)로 둠(엔진 요청)",
    "로고 글꼴: 창고에 같은 레터링 없음 — fontmatch 묶음 1위 BMJUA(정규화 0.90, 원점수 0.44 = 낮은 확신)",
    "훅 카드 위 칸: 벤치는 본문 틀을 어둡게 깐 것이라 로고·아이콘이 희미하게 비침 — 우리는 단색(머리띠 자리 [87,93,80]·아래 [97,97,97])만, 희미한 비침은 안 그림",
    "훅 띠 검정 선 2줄(529~533·703~708): 벤치는 4px 기울어짐 — 렌더러에 기운 선이 없어 가로 3px 선(가운데 y)으로",
    "훅 흰 칸 세로 그라데이션(254→226): 2단(253·237)으로, 위·아래 회색 그라데이션은 band fade(바탕 97 쪽으로 흐려짐)로 근사",
    "그림 창: 벤치는 컷마다 그림 높이가 489~933 로 바뀜(뜯기 picture_boxes) — 프리셋은 고정 창 본문 [0,673,1080,877]·훅 [0,748,1080,1172]",
    "자막 2줄째 '덧붙음'(누적형) 시각은 대본 장면 나누기 몫 — 틀은 valign top 2줄 칸만 정한다",
    "벤치 틀이 2025→2026 사이 바뀜(loo 로 드러남): 2025편(GPeF·cHyn·BlA9·0Q-C, 메타 날짜 25.10~25.11) 훅 라벨이 굵고 넓다(원본 폭이 우리보다 7% 넓음, 글자 모양 Bold·자간 0) · "
    "2026편(NBdm·jECu·cj3·xJvw, 26.01~26.03) 라벨은 가늘고 좁다 → 프리셋 = 최신 2026 꼴(CcPretendard-SemiBold 자간 −2.6). 2025 꼴로 바꾸려면 훅 라벨 font=CcPretendard-Bold·letter_spacing=0",
    "자막 층 lines=3(우회): 렌더러 2줄 칸 넘침 판정이 2줄 자막을 88%로 줄여서 — 그림은 2줄 그대로(valign top), 엔진 수리 뒤 2로 되돌릴 것",
    "BlA9·0Q-C 원본 훅 제목 1줄째가 가운데에서 16px 왼쪽(편집 차이) — 프리셋은 가운데 정렬",
]


def post_edit(preset_dir: Path, S: dict | None = None) -> dict:
    M = json.loads((preset_dir / "manifest.json").read_text(encoding="utf-8"))
    F = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    flat = P.flat(F)
    # 조회수 줄 숫자 = 변수(편마다), 기본값 = 벤치 실측 꼴(날짜는 8편 최빈 25.10.31)
    meta_paths = {}
    for path, v in flat.items():
        if path.startswith("frames[body].layers[text:label") and path.endswith(".text"):
            src_vals = {sid: P.flat(json.loads((preset_dir / "sources" / f"{sid}.json").read_text(encoding="utf-8"))).get(path) for sid in
                        [s["id"] for s in M["sources"]]}
            any_v = next(iter(src_vals.values()))
            if any_v == "7544" or (isinstance(any_v, str) and any_v.startswith("추천")):
                meta_paths[path] = src_vals
    for path, vals in meta_paths.items():
        flat[path] = P.VAR
        dflt = "7544" if "7544" in vals.values() else META_TMPL.format(d="25.10.31")
        M["variable_stats"][path] = {"values": vals, "default": dflt, "range": None,
                                     "how": "조회수 줄 숫자 — 편마다 바꿀 수 있는 변수, 기본값 = 벤치 실측 꼴(사장님 10-18 '벤치처럼 켜 둔다')"}
        if path not in M["variables"]:
            M["variables"].append(path)
    F = P.unflat(flat, P.layer_order(F))
    (preset_dir / "frame.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    M["roles"] = ROLES
    M["source_kind"] = "제품비하인드"
    M["brand"] = {"name": BRAND, "bench_logo": "재밌쇼", "layers": "frames[body] text:brand ×3(글자마다 — 가운데 글자만 흰 채움)"}
    M["channel_rules"] = channel_rules(S or sound_cut_stats())
    M["meta_line"] = M["channel_rules"]["meta_line"]
    M["differences"] = DIFFERENCES
    M["measure_tool"] = "channel/humorshowshow/preset/hs_measure.py (8편 실측 → preset_work/measure/all.json·fonts.json·medians.json)"
    (preset_dir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def _build(preset_dir: Path, ids: list[str]) -> dict:
    import shutil
    shutil.rmtree(preset_dir, ignore_errors=True)
    M = None
    for v in ids:
        J = json.loads((TG / v / "뜯기.json").read_text(encoding="utf-8")) if (TG / v / "뜯기.json").exists() else \
            {"engine": "뜯기 없음(분석 실패·진행 중)", "measured_at": None, "unknown": ["뜯기 없음 — 틀 값은 hs_measure 프레임 실측"]}
        F = json.loads((HAND / f"frame_{v}.json").read_text(encoding="utf-8"))
        M = P.save(J, F, preset_dir, v, str(TG / v / "뜯기.json").replace("\\", "/"), caption_style=STYLE,
                   caption_note="손질본(틀 2장, hs_measure 실측)")
    return post_edit(preset_dir)


def build():
    old = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8")).get("verification") if (PRESET / "manifest.json").exists() else None
    M = _build(PRESET, IDS)
    if old:
        M["verification"] = {**old, "note": "build 전 loo 결과 — 이 build 뒤 다시 안 돌렸으면 옛 값"}
        (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("프리셋", PRESET, "변수", M["variables"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "hand":
        write_hand()
    elif cmd == "build":
        build()
    elif cmd == "loo":
        from channel.humorshowshow.preset import hs_loo
        hs_loo.loo(sys.argv[2:] or None)
