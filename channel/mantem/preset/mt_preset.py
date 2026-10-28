# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/만템판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 읽기 전용 참고물 — 설명서 프리셋 생성기는 회원 옛 길이 결과를 읽으므로 지우지 않는다)
"""얜샷템 프리셋 「얜샷템」 — 벤치 만템 연예인템 8편 자동 설명서 → 손질(실측 색·글꼴 고정) → preset_save (관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/mantem/preset/mt_preset.py
손질 근거(실측, channel/mantem/뜯기/색톤_실측.md):
  제목 = Cafe24Ohsquare 기울임(fontmatch 8/8 1위·기울기 10도) 118px, 1줄 흰 [253,253,253] / 2줄 민트 [166,254,246](8편 군집 중앙),
         외곽선·그림자 없음(글자 둘레 밝기 대칭 = 번짐뿐). 2줄 끝 낱말 노랑 [249,245,157] 은 제목 낱말 강조 칸이 없어 못 넣음(엔진 요청).
  나레 자막 = 노랑 [245,255,22] Cafe24Ohsquare 기울임 64px·검정 외곽 5 (8편 18칸 중앙, 잉크 위 1226).
  원음 자막 = 흰 [255,255,255] GmarketSansBold 바로 선 58px·검정 외곽 5, 잉크 위 1322~1329(나레보다 약 100px 아래). 강조 낱말 민트 [187,255,230]·노랑 [249,245,183].
  출처 = 창 아래 '출처 : <원본 채널>' 흰 GmarketSansBold 32px(잉크 높이 31, 위 1518~1525). 채널명 자리는 화면에 없다(만템 8편 모두) — 얜샷템 글자 넣지 않음.
자동 to_frame 이 2편(S_CXTCRKFVg·Pfvwjggi7UA)에서 죽어(엔진 결함, 보고함) 그 2편은 6편과 같은 손질 틀에 뜯기 OCR 제목만 넣었다."""
import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P  # noqa: E402

SLUG, STYLE = "mantem", "얜샷템"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/mantem/frames_auto")
HAND = Path(__file__).parent / "_hand"
IDS = ["BDAjUIBTjfY", "S_CXTCRKFVg", "qBPnRzR-VaQ", "3Xb8hDoRiU4", "9FcPMZtJVB0", "Sq-kzCh0Xds", "Pfvwjggi7UA", "0LOyszI-Z0U"]
CREDIT = {"BDAjUIBTjfY": "장공장장윤정", "S_CXTCRKFVg": "이미숙_숙스러운미숙씨", "qBPnRzR-VaQ": "최은경의 관리사무소",
          "3Xb8hDoRiU4": "Allure Korea", "9FcPMZtJVB0": "VOGUE KOREA", "Sq-kzCh0Xds": "깡주은",
          "Pfvwjggi7UA": "비보티비", "0LOyszI-Z0U": "부글부글"}   # 화면 '출처 :' 글자를 눈으로 읽음(프레임 2.5초)
ROLES = ["원음 훅(본인 말 중 가장 센 한 마디, 0~2초)",
         "나레 다리 1(‘[인물]이 [수식] [제품 정체]이라는데’ 2초 안팎)",
         "원음 증언 1(쓰는 이유·느낌, 길게)",
         "나레 다리 2(질문·숫자 ‘~라는데’, 선택)",
         "원음 증언 2(개수·가격·반응)",
         "나레 마무리(‘~라네요’ 전언 한 줄)"]
BG = {"kind": "bg", "rgb": [0, 0, 0]}
VIDEO = {"kind": "video", "x": 0, "y": 420, "w": 1080, "h": 1080, "radius": 0}
TITLE = dict(kind="text", role="title", x=540, w=1040, align="center", y=146, lines=2, font="Cafe24Ohsquare", size=118.0, line_h=127,
             rgb=[253, 253, 253], line_rgb=[[253, 253, 253], [166, 254, 246]], line_scale=None, outline=None, line_outline=None,
             shadow=None, box=None, italic=True, letter_spacing=-5.5, word_spacing=14, enter=None)
NARR = dict(kind="text", role="caption", x=540, w=1000, align="center", y=1206, lines=1, font="Cafe24Ohsquare", size=64.0, line_h=74,
            rgb=[245, 255, 22], line_rgb=None, outline={"px": 5, "rgb": [0, 0, 0]}, shadow=None, box=None, italic=True,
            letter_spacing=0, word_spacing=0, enter={"kind": "none", "ms": 300}, emphasis=None)
QUOTE = dict(font="GmarketSansBold", size=58.0, line_h=67, y=1320, rgb=[255, 255, 255], outline={"px": 5, "rgb": [0, 0, 0]}, italic=False)
LABEL = dict(kind="text", role="label", x=540, w=900, align="center", y=1524, lines=1, font="GmarketSansBold", size=32.0, line_h=40,
             rgb=[255, 255, 255], outline=None, shadow=None, box=None, italic=False, letter_spacing=0)


def title_text(i):
    a = AUTO / f"{i}_auto.json"
    if a.exists():
        F = json.loads(a.read_text(encoding="utf-8"))
        return next(l for l in F["layers"] if l.get("role") == "title")["text"], "to_frame"
    J = json.loads((ROOT / f"channel/mantem/뜯기/{i}/뜯기.json").read_text(encoding="utf-8"))
    return "\n".join(" ".join(b["text"]) for b in J["fonts"]["title_bands"]["bands"]), "뜯기 OCR(to_frame 실패)"


def hand(i):
    text, how = title_text(i)
    t = copy.deepcopy(TITLE); t["text"] = text
    lab = copy.deepcopy(LABEL); lab["text"] = f"출처 : {CREDIT[i]}"
    F = {"canvas": [1080, 1920], "layers": [copy.deepcopy(BG), copy.deepcopy(VIDEO), t, copy.deepcopy(NARR), lab],
         "template_off": None, "made_by": "calcopy_frame v1", "source": i,
         "made_from": {"tool": "mt_preset.hand", "from": f"{i}_auto.json" if how == "to_frame" else "뜯기.json",
                       "notes": [f"제목 글 = {how}", "제목·자막·출처 = 8편 실측 중앙값으로 고정(색톤_실측.md)"]}}
    return F


def main():
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists():
        shutil.rmtree(PRESET)
    for i in IDS:
        J = json.loads((ROOT / "channel/mantem/뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i,
               f"channel/mantem/뜯기/{i}/뜯기.json", (), "나레_노랑", "나레 구간 자막(손질 — 8편 노랑 자막 실측)")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    base = next(l for l in json.loads((PRESET / "frame.json").read_text(encoding="utf-8"))["layers"] if l.get("role") == "caption")
    q = copy.deepcopy(base); q.update(copy.deepcopy(QUOTE))
    M["caption_styles"].append({"name": "원음_흰글자", "layer": q, "status": "손질(8편 흰 자막 실측 — 바로 선 둥근 고딕·검정 외곽·강조 낱말 민트/노랑)",
                                "sources": IDS, "emphasis_rgb": {"민트": [187, 255, 230], "노랑": [249, 245, 183]},
                                "notes": ["원음(연예인 본인 말) 구간 자막. 따옴표 없음 — 색(흰)과 자리(나레보다 약 100px 아래)로 나레와 가른다",
                                          "강조 낱말 색은 편마다 낱말이 달라 층 emphasis 로 못 박지 않았다 — 대본 단계에서 emphasis.words 로 채운다"]})
    M["title_emphasis"] = {"rgb": [249, 245, 157], "where": "2줄 끝 1~2낱말(제품·결말)", "status": "엔진에 제목 낱말 강조 칸 없음 — 요청"}
    M["channel_name"] = {"slot": None, "note": "만템 화면에 채널명·브랜드 자리 없음(8편 프레임 확인). 얜샷템 이름은 설명란·프로필에서만"}
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("변수", M["variables"], "roles", len(M["roles"]), "styles", [s["name"] for s in M["caption_styles"]])


if __name__ == "__main__":
    main()
