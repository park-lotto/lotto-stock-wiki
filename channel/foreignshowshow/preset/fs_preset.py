# -*- coding: utf-8 -*-
"""샥탬스토리(벤치 해외쇼츠 @foreignshowshow 샤크탱크 쇼핑 편) 프리셋 「샤크탱크_검정띠2줄」 — 자동 설명서 8편 → 손질 → preset_save
→ 채널 규칙 → 하나 빼고 실제 렌더 대조(loo) (관제 097, 2026-10-18 오푸스).

    PYTHONUTF8=1 py channel/foreignshowshow/preset/fs_preset.py build     # _hand/frame_<id>.json 8편 → 프리셋 + 채널 규칙
    PYTHONUTF8=1 py channel/foreignshowshow/preset/fs_preset.py loo       # 편 하나씩 빼고 만든 프리셋 → 실제 렌더(frame_video) → 원본 대조

자동 설명서(to_frame, C:/숏템_칼카피/foreignshowshow/frames_auto/<id>_auto.json)는 8편 모두 바탕·창만 냈다 — 뜯기 글꼴 판별이
제미나이 한도(quota)로 비어 '글꼴 못 정함 → 글자 층 생략'. 그래서 제목·자막 층은 실측(fs_measure.py, _hand/measure_title.json ·
C:/숏템_칼카피/foreignshowshow/preset_work/caps.json·cap_kinds.json)으로 손질해 넣었다. 근거는 층마다 made_from.notes.

손질 근거(실측 10-18, 클로드 눈 판독 + 픽셀):
  창 = to_frame 그대로 [0,434~437,1080,1046~1052](8/8). 창 밖 화면(위 0~140·아래 1495~1920)은 48프레임 전부 검정(최대 밝기 ≤6) —
       로고·채널명 자리 없음 → 샥탬스토리 글자를 넣지 않는다(벤치 그대로, §0-1 9번).
  제목 = GmarketSansBold(fontmatch 묶음 1위 0.996~1.0, 16줄 중 11줄 1위), 1줄 노랑 [255,250,121](8편 중앙) · 2줄 흰 [255,255,255],
       외곽선·그림자 없음(검정 띠 위). 줄마다 크기가 다르다(잉크 높이 82~118) → line_scale. 2줄 잉크 아래 끝 404~416(7/8, HI 376).
  자막 = GmarketSansBold(5줄 묶음 1위 4/5) · 줄 칸 68 · 가운데 정렬. 1줄 잉크 929~988(8/8 가운데 958.5),
       2줄 895~953·963~1022(줄 간격 68, 칸 가운데 958.5 그대로) → valign center·lines 2·y 894.
       채움 흰 + 낱말별 형광색(같은 색 번짐 빛) · 흰 글자는 오른쪽 아래 옅은 검정 그림자(아래오른쪽 고리가 위왼쪽보다 어두움 18/10/2).
       나레 자막과 원음(번역) 자막은 글꼴·색 규칙·자리가 같다(8편 296칸 판독). 다른 점 하나: 원음 짧은 반응(뭐라고?!·대박·와우·미친짓 그만해!)
       은 크게 — 잉크 72~76(보통 58~60, ×1.25), 6/8편 18칸 → caption_styles '원음반응_크게'.
"""
from __future__ import annotations

import copy
import json
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.calcopy.engine import loo_preset as L, preset_save as P  # noqa: E402
from tools.calcopy.engine.to_frame import size_and_top, spacing_for  # noqa: E402
import fs_measure as FM  # noqa: E402

SLUG, STYLE = "foreignshowshow", "샤크탱크_검정띠2줄"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
HAND = Path(__file__).parent / "_hand"
AUTO = Path("C:/숏템_칼카피/foreignshowshow/frames_auto")
WORK = Path("C:/숏템_칼카피/foreignshowshow/preset_work")
MP4 = FM.MP4
IDS = FM.IDS
FONT = "GmarketSansBold"
TITLE_TEXT = "layers[text:title].text"

ROLES = ["0~2초 결말 반응(투자자 원음 리액션 + 빨간 원, 나레 없음)",
         "나레 정체 한 줄(‘~하는 봉투가 있는데’ 숫자로 능력)",
         "원음 시연·증거(번역 자막) ↔ 나레 한 줄 교대",
         "기존 불편(나레 ‘~와 달리’ + 원음 공감)",
         "숫자 박자(매출·원가·판매량 — 출처 있는 것만)",
         "지분 경쟁(제안 금액·지분, 원음 ‘우리도 똑같이!’)",
         "방송 후 결과(나레 후일담 ‘~다고’ 전언)"]

CAP = dict(kind="text", role="caption", x=540, w=1000, align="center", y=897, lines=2, font=FONT, size=68.0, line_h=68,
           rgb=[253, 250, 250], line_rgb=None, line_scale=None, outline=None, line_outline=None,
           shadow={"dx": 3, "dy": 3, "blur": 6, "rgb": [0, 0, 0]}, glow=None, box=None, italic=False,
           letter_spacing=0, word_spacing=0, valign="center", enter={"kind": "none", "ms": 300}, emphasis=None)
BIG_SCALE = 1.25        # 원음 짧은 반응 잉크 72~76 / 보통 58~60

HL = {"노랑": [252, 226, 61], "주황": [245, 155, 72], "빨강": [235, 78, 79], "초록": [66, 252, 81],
      "민트·청록": [64, 248, 240], "파랑": [67, 165, 246], "분홍": [242, 98, 146]}
HL_N = {"노랑": "71칸·8편", "주황": "83칸·8편", "빨강": "78칸·8편", "초록": "45칸·7편", "민트·청록": "46칸·7편", "파랑": "29칸·7편", "분홍": "9칸·4편"}

EFFECTS = {
    "빨간 원(0~2초 첫 컷, 얼굴·반응 둘레)": {"편": "6/8 눈 확인(QMJ·kmQ·2jJ·hZg·mVz·HI)", "자리": "반지름 178~217·선 12~15px·[249,41,43] 실선",
                                     "박자": "0초 결말 반응", "근거": "fs_measure fx 10fps 순빨강 픽셀 + 프레임 눈 확인(fx_a/fx_b 시트)"},
    "빨간 점선 원": {"편": "4/8(QMJ 9.1~11.8·kmQ 29.9~30.9·2jJ 29.6~31.5·hZg 3.2~4.4)", "박자": "기존 불편·상처·증거 가리킴"},
    "화살표": {"편": "분홍 굵은 화살표 2편(QMJ 12.0~13.7·hZg 8.3~10.1) · 빨간 곡선 1편(QMJ 20.4~22.9) · 초록 화살표 3편(QMJ 0.7·kmQ 0.0·2jJ 29.6)",
             "박자": "시연 대상 가리킴"},
    "날개 돈다발 이모지": {"편": "3/8(QMJ 38.7·kmQ 32.6·aFq 34.1)", "박자": "투자 제안 금액 줄"},
    "색 필터 번쩍(초록·빨강/분홍·노랑, 0.1~0.3초)": {"편": "8/8", "횟수": "편당 초록 2~6·빨강/분홍 0~4·노랑 0~1(10fps 창 평균 치우침 + 눈 확인)",
                                          "박자": "컷 넘김(가로 흐림과 같이)"},
    "자막 넘김 가로 흐림(약 2프레임)": {"편": "8/8 판독 시트", "박자": "자막 바뀔 때 앞 자막이 가로로 번지며 빠지고 새 자막이 번지며 들어옴"},
    "상황 자막 *…*": {"편": "3/8(QMJ ‘*거래 성공*’·hZg ‘*직접 시범을 보여주는데*’ 등·vbx ‘* 하루에서 이틀 건조 *’)", "꼴": "같은 자막 칸·노랑/빨강"},
}

CHANNEL_RULES = {
    "_why": "벤치 해외쇼츠 8편 실측(10-18, fs_measure.py) + 사장님 10-18 확정(샥탬스토리 시작 문서 §1) — 값마다 출처",
    "brand": "샥탬스토리 — 화면에 넣지 않음(벤치 8편 화면 어디에도 로고·채널명 없음, 창 밖 48프레임 최대 밝기 ≤6)",
    "style": "현장썰(한국어 나레 + 영어 원음 번역 자막 + 제품)",
    "formula": "6박자: 0~3초 결말 반응(투자자+빨간 원) → 시연 → 기존 불편 → 숫자 → 지분 경쟁 → 방송 후 결과",
    "narration_tone": "반말 전언체(~는데/~다고/~되자), 벤치 나레 연속 3어절 베끼기 금지, 숫자는 출처 있는 것만",
    "captions": {
        "narration_and_quote_same_style": True,
        "why": "8편 296칸 판독 — 나레 자막·원음 번역 자막 모두 GmarketSansBold·같은 자리(가운데 958.5)·흰+낱말 형광. 원음 짧은 반응만 ×1.25",
        "highlight_palette": HL, "highlight_counts": HL_N,
        "highlight_how": "낱말(구) 단위 1~2곳, 줄 전체를 한 색으로 칠하는 칸도 있음(원음 반응·상황 자막). 색 고르는 규칙은 없음(같은 편 안에서도 다 다름)",
        "max_lines": 2, "first_cut_sec": "0.57~1.87(7/8, 뜯기 요약)", "cut_sec_median_ref": 1.27,
    },
    "effects": EFFECTS,
    "sound": {
        "target_lufs": -9.0, "target_peak_dbfs_max": -0.5, "clipping": 0,
        "target_why": "페이블 10-18(사장님 확정): 검수 매뉴얼 B2 우리 기준 = 벤치 ±1.5 LUFS + 최고점 ≤ −0.5 dBFS",
        "bench_measured": {"I_lufs": [-8.2, -7.1], "true_peak_dbtp": [1.0, 1.6], "LRA": [1.2, 2.9],
                           "per_video": {"QMJtjJz4M6w": [-7.8, 1.0], "kmQGQNJgSVo": [-7.3, 1.6], "2jJoIbdciDY": [-7.7, 1.1],
                                         "vbxJ_v132ao": [-8.2, 1.5], "hZgCO9PEnO8": [-7.2, 1.6], "mVzrvBpMu3E": [-7.1, 1.2],
                                         "aFqKN8s2cA8": [-7.9, 1.2], "HI--3fL7nt4": [-8.0, 1.0]},
                           "from": "뜯기.json audio.bench(I·TP·LRA) — 8/8 트루피크 +1.0~+1.6 = 클리핑, 그대로 따라가지 않는다"},
        "bgm_sfx_voice": "미측정 — 뜯기 받아쓰기·효과음·BGM 판독이 제미나이 quota 로 실패(엔진 요청: hybrid/server_ai.py asr 로 다시)",
    },
    "source_credit": False,
    "excluded": "원본 방송 화면에 박힌 자막·로고($200k for a 10% stake 등 방송 그래픽)는 재료 크롭 단계에서 뺀다(공통 규칙)",
}


def title_layer(i: str, M: dict) -> tuple[dict, list]:
    """measure_title.json(잉크 y·높이·폭·채움색) → 제목 층. 크기·자리 역산은 to_frame 과 같은 함수(size_and_top·spacing_for)."""
    d = M[i]
    lines = d["lines"]
    tl = [l["text"] for l in lines]
    line_h = lines[1]["ink_y"][0] - lines[0]["ink_y"][0]
    fits = [size_and_top(FONT, l["text"], l["ink_y"][0], l["ink_h"], line_h) for l in lines]
    size = round(st.mean(f["size"] for f in fits), 1)
    scale = [round(f["size"] / size, 3) for f in fits]
    scale = scale if max(abs(s - 1) for s in scale) > 0.03 else None
    ys = [f["y"] - k * fits[0]["line_h"] for k, f in enumerate(fits)]
    sp = [spacing_for(FONT, fits[k]["size"] if scale else size, tl[k], lines[k]["ink_w"]) for k in range(len(lines))]
    sp = [v for v in sp if v is not None]
    maxw = max(l["ink_w"] for l in lines)
    layer = dict(kind="text", role="title", x=540, w=min(1080, max(1000, maxw + 40)), align="center", y=round(st.mean(ys)), lines=2,
                 font=FONT, size=size, line_h=fits[0]["line_h"], rgb=lines[0]["fill_rgb"],
                 line_rgb=[lines[0]["fill_rgb"], lines[1]["fill_rgb"]], line_scale=scale, outline=None, line_outline=None,
                 shadow=None, box=None, italic=False, letter_spacing=min(sp) if sp else 0, word_spacing=0, enter=None,
                 text="\n".join(tl))
    notes = [f"제목 = 실측 잉크 {[(l['ink_y'], l['ink_w']) for l in lines]} → 줄 크기 {[f['size'] for f in fits]} (to_frame.size_and_top)",
             f"제목 글꼴 {FONT} — fontmatch 묶음 {d['font_rank']['top'][0]}",
             f"제목 채움 {[l['fill_rgb'] for l in lines]}"]
    return layer, notes


def hand(i: str, M: dict) -> dict:
    F = json.loads((AUTO / f"{i}_auto.json").read_text(encoding="utf-8"))
    t, tn = title_layer(i, M)
    F["layers"] = [l for l in F["layers"] if l["kind"] in ("bg", "video")] + [t, copy.deepcopy(CAP)]
    F["made_from"] = {"tool": "fs_preset.hand", "from": f"{i}_auto.json(바탕·창) + fs_measure 실측(제목·자막)",
                      "notes": (F.get("made_from") or {}).get("notes", []) + tn + [
                          "자막 = 8편 공통 실측(1줄 잉크 929~988·2줄 895~953/963~1022, GmarketSansBold·줄 칸 68·valign center)",
                          "자막 크기 68·y 897 = 렌더 대조로 맞춤(PIL 역산 65.6·y 894 로 그리니 1줄 잉크 927~983 폭 615 vs 원본 929~987 폭 645 — loo QMJ 10-18)",
                          "자막 그림자 = 흰 글자 아래오른쪽 고리가 위왼쪽보다 어두움(밝기 차 18/10/2, 3표본) + 뜯기 glyph 그림자 [2,2] → dx3 dy3 blur6 (근사)",
                          "낱말 형광색·같은 색 번짐 빛은 층 하나로 못 그림(emphasis 는 한 색) — manifest channel_rules.captions.highlight_palette"]}
    return F


def frames() -> dict:
    return {v: json.loads((HAND / f"frame_{v}.json").read_text(encoding="utf-8")) for v in IDS}


def post_edit(pdir: Path) -> dict:
    """엔진 build 가 manifest 를 새로 쓰므로 build 뒤 매번 이 틀의 판단을 얹는다."""
    M = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    M["roles"] = ROLES
    K = (M.get("rules") or {}).get("keys") or {}
    if "fill_w" in K:
        # 벤치는 긴 줄을 '크기'로 줄인다(mVz·HI 1줄 잉크 84·82 vs 2줄 117, 낱말 사이 띄어쓰기 그대로). 엔진 규칙(자간부터 −15%)으로 두면
        #   loo 1판에서 '여성만쓸수있는수건?!'·'산다vs안산다' 처럼 띄어쓰기가 붙었다(10-18 loo_대조) → 규칙은 자간을 건드리지 않게 두고,
        #   렌더러가 줄마다 칸 폭(w)에 맞춰 크기를 줄이게 한다(precision20-ui renderSpec: 줄마다 칸을 넘으면 0.97배씩).
        K["fill_w"]["default"] = 4000
        K["fill_w"]["how"] = "자간 줄이기 끔(4000) — 긴 줄은 렌더러가 칸 폭 w 에 맞춰 줄마다 크기를 줄인다(벤치와 같은 방식)"
    if "video_anchor" in K:
        K["video_anchor"] = {"values": None, "default": "constant", "range": None,
                             "how": "창 y 고정(video_top) — 벤치 창 위 끝 434~437(폭 3px) vs 제목 잉크 끝–창 간격 17~70(폭 53px): 창은 제목 크기와 무관하게 그 자리"}
    M["source_kind"] = "해외영상"
    base = next(l for l in json.loads((pdir / "frame.json").read_text(encoding="utf-8"))["layers"] if l.get("role") == "caption")
    for s in M.get("caption_styles") or []:
        s["notes"] = ["나레 자막·원음 번역 자막 공통(8편 판독에서 꼴 차이 없음)"]
    big = copy.deepcopy(base)
    big["size"] = round(base["size"] * BIG_SCALE, 1)
    big["line_h"] = round(base["line_h"] * BIG_SCALE)
    big["y"] = round(base["y"] + base["line_h"] - big["line_h"])   # 2줄 칸 가운데를 보통 자막과 같게
    M["caption_styles"] = [s for s in M.get("caption_styles") or [] if s.get("name") != "원음반응_크게"] + [
        {"name": "원음반응_크게", "layer": big, "sources": IDS,
         "status": "손질(6/8편 18칸 실측 — 원음 짧은 반응 잉크 72~76 vs 보통 58~60)",
         "notes": ["뭐라고?!·대박·대단해!·그거 정말 좋네!·와우·아니·미친짓 그만해! 같은 한 마디 반응. 줄 전체 한 색인 칸이 많다",
                   "자리는 보통 자막과 같은 가운데(958.5)"]}]
    M["title_rule"] = {"font": FONT, "line_rgb": "1줄 노랑 [255,250,121](8편 중앙) · 2줄 흰",
                       "size": "편집자가 줄마다 고름(잉크 높이 82~118) — 2줄 잉크 아래 끝이 창 위 18~30px 위에 오도록(7/8)",
                       "ends": "2줄 끝 '?!' 6/8(vbx·mVz/HI 2줄 '산다 vs 안산다' 는 1줄 끝 ?!)"}
    M["channel_name"] = {"slot": None, "note": "벤치 화면에 로고·채널명 없음(8편 창 밖 48프레임 최대 밝기 ≤6) — 샥탬스토리 글자 넣지 않음"}
    M["render_gaps"] = RENDER_GAPS
    M["channel_rules"] = CHANNEL_RULES
    (pdir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


RENDER_GAPS = [
    {"what": "자막 낱말별 형광색 + 같은 색 번짐 빛(한 줄에 여러 색)", "now": "emphasis 는 한 색·glow 는 층 전체 한 색", "pack": "없음"},
    {"what": "원음 짧은 반응 크게(×1.25)", "now": "caption_styles 로 층 바꾸기는 되나 장면마다 고르는 칸은 대본·제작 단계 몫", "pack": "해당 없음"},
    {"what": "자막 넘김 가로 흐림(2프레임)", "now": "enter kind 에 없음(pop|fade|rise|typewriter|none) → none", "pack": "없음"},
    {"what": "빨간 원(실선, 반지름 178~217·선 12~15)", "now": "frame.json 층 없음", "pack": "circle_ring(강조, legacy·지어낸 모양 — 실측 아님)"},
    {"what": "빨간 점선 원", "now": "없음", "pack": "없음"},
    {"what": "분홍 굵은 화살표·빨간 곡선 화살표·초록 화살표", "now": "없음", "pack": "arrow_bold·arrow_curve(legacy, 기본색 #FF3B30)"},
    {"what": "날개 돈다발 이모지", "now": "없음", "pack": "없음"},
    {"what": "색 필터 번쩍(초록·빨강·노랑 0.1~0.3초)", "now": "없음", "pack": "없음(burst 는 도형)"},
    {"what": "상황 자막 *…*", "now": "자막 글로 넣으면 됨(같은 칸)", "pack": "해당 없음"},
]


def build():
    MT = json.loads((HAND / "measure_title.json").read_text(encoding="utf-8"))
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i, MT), ensure_ascii=False, indent=1), encoding="utf-8")
    old = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8")).get("verification") if (PRESET / "manifest.json").exists() else None
    L.build(PRESET, SLUG, IDS, frames(), "샥탬 손질본(실측 자막 — 나레·원음 공통)")
    M = post_edit(PRESET)
    if old:
        M["verification"] = {**old, "note": "build 전 loo 결과 — 이 build 뒤 다시 안 돌렸으면 옛 값"}
        (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("프리셋", PRESET, "변수", M["variables"])


# ── loo: 편 하나씩 빼고 → 뺀 편 제목 글만 넣어 기본값+관계 규칙으로 설명서 → 실제 렌더 → 원본과 대조 ──
# 자막 표본(클로드 눈 판독 시트 strips — 시각·글·줄): 1줄 보통 하나 + 2줄 하나(HI 는 2줄 자막 없음 → 1줄 둘)
CAP_SAMPLES = {
    "QMJtjJz4M6w": [(36.45, ["돈 벌 자신이 있다는데"]), (12.15, ["수십키로에 달하는", "무게를 무시할 수 없어요"])],
    "kmQGQNJgSVo": [(33.65, ["매출과 마진이"]), (19.05, ["이건 여성이", "주요 타겟입니다"])],
    "2jJoIbdciDY": [(51.05, ["그렇게 빈손으로 돌아갔고"]), (10.65, ["마지막 땅콩 버터까지", "짜낼 수 있도록 설계했습니다"])],
    "vbxJ_v132ao": [(13.75, ["디스크 위에 특수 점토를 대고"]), (3.15, ["내가 이제 이 벽을", "다시 고쳐볼게 !"])],
    "hZgCO9PEnO8": [(34.35, ["오로지 줄만 끊을 수 있게"]), (13.75, ["그리고 저의", "첫번째 모델이 발명됐죠"])],
    "mVzrvBpMu3E": [(6.85, ["이건 목에 걸어쓰는 타월로"]), (12.75, ["나는 샤워 후에만", "입으려고 만들었어"])],
    "aFqKN8s2cA8": [(23.45, ["도매가는 약 8000원이고"]), (7.25, ["네 물기를 제거해", "말린거예요"])],
    "HI--3fL7nt4": [(13.65, ["올라와서 확인해보세요"]), (18.35, ["분명 괜찮을거예요"])],
}
SEG = 1.5
CAP_Z = (860, 1060)      # 원본 자막을 가리는 띠(재료에서) — 우리 자막만 보이게


def cap_ink(img, y0=860, y1=1060) -> list:
    """자막 띠 잉크 줄(흰·형광 채움) — 줄마다 [y0,y1,x0,x1]."""
    import numpy as np
    a = img[y0:y1, 20:1060].astype(int)
    mn, mx = a.min(axis=2), a.max(axis=2)
    m = (mn > 225) | ((mx > 215) & (mx - mn > 110))
    out = []
    for s, e in FM.segs(m.sum(axis=1) > 12, min_len=40, gap=2):
        cols = np.where(m[s:e].sum(axis=0) > 2)[0]
        out.append([int(s + y0), int(e + y0), int(cols.min() + 20), int(cols.max() + 21)])
    return out


def grab_file(p: Path, t: float):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(p), "-frames:v", "1", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(1920, 1080, 3)


def clip(held: str, d: Path) -> Path:
    """표본 두 자막 구간(각 1.5초)을 이어 붙이고 원본 자막 띠를 회색으로 가린 재료."""
    out = d / "clip.mp4"
    if out.exists():
        return out
    (a, _), (b, _) = CAP_SAMPLES[held]
    src = str(MP4 / f"{held}.mp4")
    box = f"drawbox=x=0:y={CAP_Z[0]}:w=1080:h={CAP_Z[1] - CAP_Z[0]}:color=0x808080:t=fill"
    fc = (f"[0:v]trim={a - SEG / 2}:{a + SEG / 2},setpts=PTS-STARTPTS[a];[0:v]trim={b - SEG / 2}:{b + SEG / 2},setpts=PTS-STARTPTS[b];"
          f"[a][b]concat=n=2:v=1:a=0,{box},fps=30[v]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def loo(ids=None):
    ids = ids or IDS
    F_all = frames()
    res = {}
    for held in ids:
        d = WORK / "loo" / held
        d.mkdir(parents=True, exist_ok=True)
        rest = [x for x in IDS if x != held]
        pdir = d / "preset" / STYLE
        L.build(pdir, SLUG, rest, {k: F_all[k] for k in rest}, "loo")
        post_edit(pdir)
        pre, Mh = P.load(pdir)
        title = next(l for l in F_all[held]["layers"] if l.get("role") == "title")
        F = P.apply(pre, None, {TITLE_TEXT: title["text"]}, Mh["variable_stats"], None, Mh["rules"])
        fp = d / "frame.json"; fp.write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
        src = clip(held, d)
        J = json.loads((ROOT / "channel" / SLUG / "뜯기" / held / "뜯기.json").read_text(encoding="utf-8"))
        J["source"] = str(src).replace("\\", "/"); J["probe"]["duration"] = 2 * SEG
        J["captions"] = {"spans": [[0.05, SEG - 0.05], [SEG + 0.05, 2 * SEG - 0.05]],
                         "items": [{"i": k, "text": ["\n".join(lines)]} for k, (_, lines) in enumerate(CAP_SAMPLES[held])]}
        jp = d / "J.json"; jp.write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")
        ours = d / "vid" / "ours.mp4"
        if not ours.exists():
            r = subprocess.run([sys.executable, "tools/calcopy/frame_video.py", str(fp), str(jp), str(d / "vid"), "--src-window"],
                               cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                res[held] = {"failed": r.stderr[-600:]}; print(held, "렌더 실패", r.stderr[-300:]); continue
        r2 = subprocess.run([sys.executable, "tools/calcopy/engine/compare.py", str(src), str(ours), "--out", str(d / "cmp"), "--layout", "single"],
                            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        rows = L.frame_rows(d / "cmp" / "차이표.json") if (d / "cmp" / "차이표.json").exists() else []
        caps = []
        for k, (t, lines) in enumerate(CAP_SAMPLES[held]):
            o = cap_ink(grab_file(MP4 / f"{held}.mp4", t))
            u = cap_ink(grab_file(ours, SEG * k + SEG / 2), *CAP_Z)
            caps.append({"t": t, "text": lines, "orig": o, "ours": u})
        res[held] = {"rows": [{k: r.get(k) for k in ("key", "name", "orig", "ours", "diff", "status")} for r in rows],
                     "in": sum(r["status"] == "in" for r in rows), "n": len(rows), "frame": str(fp), "caps": caps,
                     "compare_rc": r2.returncode, "side_by_side": str(d / "cmp" / "side_by_side.jpg")}
        print(held, "틀", res[held]["in"], "/", res[held]["n"], "자막", json.dumps(caps, ensure_ascii=False))
    (WORK / "loo" / "loo_fs.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    two = L.judge(res, {FONT})
    (WORK / "loo" / "loo_fs_judge.json").write_text(json.dumps(two, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for k, v in two.items():
        print(k, "두 층 판정", v["in"], "/", v["n"], "밖:", v["defects"])


def verify():
    """loo 결과(loo_fs.json·loo_fs_judge.json) → 항목별 일치 수를 manifest.verification 에."""
    import collections
    R = json.loads((WORK / "loo" / "loo_fs.json").read_text(encoding="utf-8"))
    Jd = json.loads((WORK / "loo" / "loo_fs_judge.json").read_text(encoding="utf-8"))
    c = collections.defaultdict(lambda: [0, 0])
    for v in Jd.values():
        for r in v["rows"]:
            c[r["name"].split(" [")[0] + ("" if "띠" not in r["name"] else " " + r["name"].split(") ")[-1])][0] += r["in"]
            c[r["name"].split(" [")[0] + ("" if "띠" not in r["name"] else " " + r["name"].split(") ")[-1])][1] += 1
    one, two = [], []
    for k, v in R.items():
        for cap in v.get("caps", []):
            n = len(cap["text"])
            o = [l for l in cap["orig"] if 50 <= l[1] - l[0] <= 66]
            if len(o) < n or len(cap["ours"]) != n:
                continue
            o = sorted(o, key=lambda l: abs(l[0] - (929 if n == 1 else 895)))[:n]
            o.sort()
            for a, b in zip(o, cap["ours"]):
                (one if n == 1 else two).append({"id": k, "t": cap["t"], "y0": [a[0], b[0]], "h": [a[1] - a[0], b[1] - b[0]],
                                                 "w": [a[3] - a[2], b[3] - b[2]]})
    def cnt(rows):
        return {"잉크 위 y ±4": f"{sum(abs(r['y0'][0] - r['y0'][1]) <= 4 for r in rows)}/{len(rows)}",
                "잉크 높이 ±12%": f"{sum(abs(r['h'][1] - r['h'][0]) / r['h'][0] <= .12 for r in rows)}/{len(rows)}",
                "잉크 폭 ±10%": f"{sum(abs(r['w'][1] - r['w'][0]) / r['w'][0] <= .10 for r in rows)}/{len(rows)}"}
    summ = {"at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "tool": "channel/foreignshowshow/preset/fs_preset.py loo",
            "frame_items(engine compare+judge)": {k: f"{a}/{b}" for k, (a, b) in c.items()},
            "caption_1line": cnt(one), "caption_2line_per_line": cnt(two), "caption_rows": one + two,
            "notes": ["원본 자막 잉크는 배경 흰·형광 물체가 섞인 칸을 뺐다(원본 못 잼)",
                      "kmQ·aFq 창 y 어긋남 = 재료 회색 가림 띠(자막 가리기)를 compare 가 창 경계로 읽은 것(창 규칙 값은 434~437 고정)",
                      "엔진 judge 는 창 위 띠 #0 을 [광고] 고정 띠로 보고 '고정' 판정 — 이 채널 띠 #0 = 제목 1줄(편집자가 고르는 크기)이라 띠1 글자 높이 불일치는 변수 차이"],
            "sheet": "channel/foreignshowshow/preset/_hand/loo_대조.jpg", "detail": str(WORK / "loo" / "loo_fs.json")}
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["verification"] = summ
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summ.items() if k != "caption_rows"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "loo": lambda: loo(sys.argv[2:] or None), "verify": verify}[cmd]()
