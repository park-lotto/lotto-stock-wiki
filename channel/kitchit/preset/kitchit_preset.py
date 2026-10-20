# -*- coding: utf-8 -*-
"""키치잇 연예인템 프리셋 「검정창_노랑박스제목」 — 자동 설명서(to_frame) 7편 → 손질(실측 notes) → preset_save (관제 097, 2026-10-18).
    PYTHONUTF8=1 py channel/kitchit/preset/kitchit_preset.py

자동 설명서가 틀린 곳(10-18 실측, 손질 근거 = Cs-Ka_S8nDM 3.0초 프레임 · channel/kitchit/스타일분석.md §2):
  ① 영상 창: BRa 자동 [0,383,1080,1171] — 실제 8편 공통 y420~1499 1080x1080(밝기 행 실측: 7편 420~1499, vSE 418~1501)
  ② 제목: 2줄을 한 층으로 잡고 2줄째 노랑 박스를 못 잡음 → 1줄(흰 기울임) / 2줄(검정 글) 두 층 + 노랑 띠(band) 한 장
  ③ 자막 글꼴: BRa 자동 Dokdo(0.09, 확신 낮음) — 눈 대조로 Jalnan2(Cs-Ka 합산 1위 0.36) · 크기 = '1년 내내' 잉크 폭 275 → 73
  ④ 로고(창 왼쪽 위 '키치잇')·출처 줄(창 아래)은 자동이 못 잡음 → brand·label 층 손으로
vSEaZ-BCELY(08-17, 옛 틀: 박스 없음·출처가 창 안 위)는 to_frame 이 frames id 중복으로 실패(공용 결함 보고) + 틀이 달라 뺐다.
★렌더 기록용 — 이 편 렌더는 channel/kitchit/preset/kitchit_frame.json(렌더 숫자)·channel/kitchit/하이브리드_성시경/render_kitchit.py."""
import copy, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P
SLUG, STYLE = "kitchit", "검정창_노랑박스제목"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/kitchit/frames"); HAND = Path(__file__).parent / "_hand"
FR = json.loads((Path(__file__).parent / "kitchit_frame.json").read_text(encoding="utf-8"))
IDS = {  # 편: (제목 1줄, 제목 2줄, 2줄 박스 있음, 출처 채널) — 화면 글자 그대로(2fps 시트 판독)
    "Cs-Ka_S8nDM": ("50살 최강희 찐애착백!", "명품 아니고 백화점 브랜드?", True, "나도 최강희"),
    "BRa5Iv4A3Y8": ("최화정 피부 실화?", "추석 선물 효도 끝판왕", False, "성시경 SUNG SI KYUNG"),
    "Ks5kYYKAUlQ": ("가을 햇볕에 피부 찢어질 때?", "박세리가 '몇 통째' 쓴 선크림!", True, "박세리의 속사정"),
    "Nv99RyxmrfU": ("실장님도 탐낸 베이스", "알고 보니 1만원대?", True, "윤쥬르 YOONJOUR 장윤주"),
    "oTi41R74WIY": ("에르메스인줄! 고현정가방", "가격듣고 놀란 반전브랜드", True, "고현정"),
    "cNo91ddBwB8": ("선우용여가 픽한 눈가 꿀템", "뻑뻑하고 눈곱낄 때 슥-", True, "옥탑방의 문제아들"),
    "_Wa4IehA6yE": ("가을 피부 쩍쩍 갈라질 때?", "50살 최강희의 피부소생법!", True, "전참시"),
}
ROLES = ["나레 훅(전언 ~다네요?/~다고?, 인물+제품 정체)", "원음 증언(본인 말)", "나레 질문 한 줄(대체 어떤 ~길래?)", "원음 답(디테일)", "나레 마무리(~말 다했죠/~래)"]
BASE = dict(kind="text", align="center", line_rgb=None, line_scale=None, outline=None, line_outline=None, shadow=None, box=None,
            italic=False, letter_spacing=0, word_spacing=0, valign="center", enter=None)


def hand(i):
    A = json.loads((AUTO / f"{i}_auto.json").read_text(encoding="utf-8"))
    t1, t2, boxed, credit = IDS[i]
    T1, T2, LG, CR, CP = FR["title1"], FR["title2"], FR["logo"], FR["credit"], FR["caption"]
    cap = next((L for L in A.get("layers") or [] if L.get("role") == "caption"), None) or dict(BASE, role="caption", x=540, lines=1, rgb=[255, 255, 255])
    layers = [{"kind": "bg", "rgb": [0, 0, 0]}, dict(FR["window"], kind="video", radius=0)]
    if boxed:
        b = T2["box"]; layers.append({"kind": "band", "x": b[0], "y": b[1], "w": b[2] - b[0] + 1, "h": b[3] - b[1] + 1, "rgb": T2["box_rgb"], "radius": 0})
    # 제목 = 한 층 2줄(스키마가 title 한 장만 허용) — 줄 칸 높이 133(1줄 잉크 가운데 y201·2줄 y334). 1줄 기울임은 층 하나로 줄마다 못 줘서 italic=false + notes
    layers.append(dict(BASE, role="title", x=540, y=135, w=1000, lines=2, font="Jalnan2", size=78.0, line_h=133, rgb=T1["rgb"],
                       line_rgb=[T1["rgb"], (T2["rgb"] if boxed else [243, 252, 50])], line_scale=[1.013, 0.987], text=t1 + chr(10) + t2))
    c = copy.deepcopy(cap)
    c.update(x=540, align="center", box=None, font="Jalnan2", size=float(CP["size"]), line_h=82, y=CP["center_y"] - 41, w=CP["max_w"], rgb=[255, 255, 255],
             outline={"px": 7, "rgb": [21, 22, 24]}, enter={"kind": "pop", "ms": 400},
             emphasis={"words": "auto", "rgb": [254, 221, 0], "style": "color"})
    layers.append(c)
    layers.append(dict(BASE, role="brand", x=LG["x"], y=LG["y"] - 4, w=300, align="left", lines=1, font="Jalnan2", size=float(LG["size"]), line_h=52,
                       rgb=LG["rgba"][:3], outline={"px": LG["stroke"], "rgb": LG["stroke_rgba"][:3]}, text="키치잇"))
    layers.append(dict(BASE, role="label", x=540, y=CR["ink_top"] - 8, w=900, lines=1, font="CcPretendard-Bold", size=float(CR["size"]), line_h=56,
                       rgb=CR["rgb"] if i != "BRa5Iv4A3Y8" else [92, 93, 92], text=f"출처: {credit}"))
    F = {"canvas": [1080, 1920], "layers": layers, "template_off": None, "made_by": "calcopy_frame v1", "source": i,
         "made_from": {"tool": "kitchit_preset.hand", "from": f"{i}_auto.json",
                       "notes": ["창 y420 1080x1080(8편 밝기 행 실측)", "제목 1줄 흰 기울임 Jalnan2 79 · 2줄 노랑 박스 #FDE600 x42~1037 y269~399 + 검정 Jalnan2 77(박스 없는 편은 노랑 글)",
                                 "자막 Jalnan2 73·가운데 y1351·외곽선 7px #151618 + 흰 바깥 테두리 약 2px(층 하나로 표현 못 함 — 자막팩 보강안)",
                                 "자막 등장 pop 400ms(0프레임 22% → 0.27초 109% → 0.40초 100%, Cs-Ka '1년 내내' 30fps 실측)",
                                 "강조색 돌림(노랑·초록·하늘·분홍·연보라)은 설명서 한 색만 — 돌림은 자막팩 보강안",
                                 "로고 '키치잇' x75 y435 회색 + 출처 줄 y1535 회색(자동이 못 잡아 손으로)"]}}
    return F


def main():
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists(): shutil.rmtree(PRESET)
    for i in IDS:
        J = json.loads((ROOT / "channel/kitchit/뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i, f"channel/kitchit/뜯기/{i}/뜯기.json", (),
               "키치잇자막", "흰 글+진한 외곽선+흰 바깥 테두리 · 핵심 낱말 하나 색 돌림 · pop 등장 · 원음 구간 타이핑")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")   # 목록에 '국내 원본 재편집'이 없어 안나픽·아이템홈과 같은 값
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["note"] = "기록용 — 렌더 숫자는 channel/kitchit/preset/kitchit_frame.json, 자막 효과는 channel/kitchit/자막팩_보강안.json"
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("변수", M["variables"], "roles", len(M["roles"]))


if __name__ == "__main__":
    main()
