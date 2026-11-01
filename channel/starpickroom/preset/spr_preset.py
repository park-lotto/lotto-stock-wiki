# -*- coding: utf-8 -*-
"""스타픽룸(@스타픽룸) 연예인 레시피·추천템 프리셋 「검정틀_금색로고_타이핑나레」 — 자동 설명서 → 손질 → preset_save (관제 097, 2026-10-18).
    PYTHONUTF8=1 py channel/starpickroom/preset/spr_preset.py
★뜯기 기록용 + 얜샷템 스타픽룸판 렌더 틀의 근거. 제목 낱말별 색·창 워터마크·금색 로고는 스키마 밖이라
  렌더에서 channel/starpickroom/_tools/spr_overlay.py 가 덮는다(엔진 빈칸 — 스타일분석.md §틀).
손질 근거(실측, 1080×1920):
  제목  Cafe24Ohsquare 기울임 +10° · 크기 92 · 줄 높이 104 · 잉크 y244~429(VbpdN 9.6초) · 바탕 흰 [252,252,252] + 강조 낱말 노랑 #FDF702 / 보라 #CF04FC
        (to_frame 은 편마다 GmarketSansBold·줄 색으로 잡았다 — 낱말 색을 줄 색으로 오인, 글꼴은 title1.png 대조로 Cafe24Ohsquare)
  자막  GmarketSansBold 62 — 채움 잉크 h56(1112~1167)·폭/높이 10.3(VbpdN 11.0초 '달고 짜고 한국스러운' 575px) = GmarketSansBold 10.34
        (to_frame 의 Pretendard·Spoqa·IBM 1위는 점수 0.26~0.43 '낮음' + 자간 +13·낱말 −22 로 폭을 억지로 맞춘 값) · 흰 · 검정 외곽 7px
  출처  회색 [139,139,136] y1607~1645 가운데 '출처: <채널명>'(편마다)
  워터마크 창 오른쪽 위 '스타픽룸' 흰 반투명 x790~1030 y525~575 (스키마에 투명도 없음 → brand 층 회색으로 기록)
  로고  y1666~1919 금색 '스타픽룸' + 금선 실루엣 2명 + 별 — 우리 판은 '얜샷템'(spr_overlay.logo_layer)
"""
import copy, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P

SLUG, STYLE = "starpickroom", "검정틀_금색로고_타이핑나레"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/starpickroom/frames"); HAND = Path(__file__).parent / "_hand"
FIXED_TT = Path("C:/숏템_칼카피/starpickroom/tteutgi_fix")   # to_frame None bbox 결함 우회본(곡선 첫 칸 bbox None 만 잘라냄)
IDS = ["ASqFulFvhgg", "VbpdNba182M", "21VoGAEK_pU", "onmwSxfco-A", "r5XN6Eilfxs", "EZQlWvvnKPI", "j5D30T2n0-w", "dKczVzmdr00"]
LABEL = {"ASqFulFvhgg": "차장금 차예련", "VbpdNba182M": "당분간 공효진", "21VoGAEK_pU": "냉부해, 스튜디오슬램", "onmwSxfco-A": "오연수 Yun Soo Oh",
         "r5XN6Eilfxs": "차장금 차예련", "EZQlWvvnKPI": "백지영, 셰프이원일", "j5D30T2n0-w": "안녕하세요 최화정이에요", "dKczVzmdr00": "이민정 MJ"}
ROLES = ["원음 훅(연예인 본인 말·반응 3.5~8초, 자막 즉시)", "나레 1~3조각(타이핑, '[수식어] [이름]이 ~한 [것]이 있다는데..?')",
         "원음 본문(쓰는 법·만드는 법, 줄마다 즉시 자막 + 강조 낱말·스티커)", "(선택) 나레 1줄 다리('그리고 ~ 팁이 있다는데..?')", "원음 끝(먹는·쓰는 얼굴 반응, 맺음 나레·CTA 없음)"]
BASE = dict(kind="text", align="center", line_rgb=None, line_scale=None, outline=None, line_outline=None, shadow=None, glow=None, box=None,
            italic=False, letter_spacing=0, word_spacing=0, valign="center", enter=None, emphasis=None)
TITLE = dict(BASE, role="title", x=540, y=236, w=1040, lines=2, font="Cafe24Ohsquare", size=92.0, line_h=104, rgb=[252, 252, 252], italic=True,
             letter_spacing=-1.0)
CAPTION = dict(BASE, role="caption", x=540, y=1106, w=1000, lines=1, font="GmarketSansBold", size=62.0, line_h=70, rgb=[255, 255, 255],
               outline={"px": 7, "rgb": [0, 0, 0]}, enter={"kind": "none", "ms": 300})
LABEL_L = dict(BASE, role="label", x=540, y=1604, w=900, lines=1, font="CcPretendard-Bold", size=36.0, line_h=44, rgb=[139, 139, 136])
BRAND = dict(BASE, role="brand", x=910, y=522, w=260, lines=1, font="GmarketSansBold", size=56.0, line_h=60, rgb=[200, 200, 200], text="스타픽룸")
LOGO = {"kind": "image", "src": "channel/starpickroom/preset/assets/logo_yanshottem.png", "x": 0, "y": 1666, "w": 1080, "h": 254}


def auto_path(i):
    return AUTO / f"{i}_auto.json"


def hand(i):
    F = json.loads(auto_path(i).read_text(encoding="utf-8"))
    old_title = next(l for l in F["layers"] if l.get("role") == "title")
    keep = [l for l in F["layers"] if l["kind"] in ("bg", "video")]
    for l in keep:
        if l["kind"] == "video":
            l.update(x=0, y=483, w=1080, h=1058)
    F["layers"] = keep + [dict(copy.deepcopy(TITLE), text=old_title.get("text")), copy.deepcopy(CAPTION),
                          dict(copy.deepcopy(LABEL_L), text=f"출처: {LABEL[i]}"), copy.deepcopy(BRAND), copy.deepcopy(LOGO)]
    F["made_from"] = {**(F.get("made_from") or {}), "tool": "spr_preset.hand", "from": f"{i}_auto.json",
                      "notes": (F.get("made_from") or {}).get("notes", []) + [
                          "제목·자막 글꼴/크기 손질(실측 근거는 이 파일 머리) · 출처·워터마크(brand)·로고(image) 층 손으로 추가",
                          "제목 낱말별 색·워터마크 투명도·로고는 spr_overlay 로 덮는다(스키마 빈칸)",
                          "나레 줄 = 타이핑(10~15자/초), 원음 줄 = 즉시 — 층 하나라 enter none 으로 두고 자막팩 보강안에 갈라 적음"]}
    return F


def main():
    HAND.mkdir(exist_ok=True)
    ids = [i for i in IDS if auto_path(i).exists()]
    for i in ids:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists():
        shutil.rmtree(PRESET)
    for i in ids:
        tp = FIXED_TT / i / "뜯기.json"
        J = json.loads((tp if tp.exists() else ROOT / "channel" / SLUG / "뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i, f"channel/{SLUG}/뜯기/{i}/뜯기.json", (),
               "원음즉시_나레타이핑", "원음 줄 즉시 · 나레 줄 타이핑(자막팩 보강안 spr_typing)")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")   # 목록에 '국내 원본 재편집'이 없어 안나픽·아이템홈과 같은 값
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["note"] = "기록용 + 얜샷템 스타픽룸판 틀 근거. 렌더 = 이 frame + spr_overlay(제목 낱말 색·워터마크·로고)"
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("편", ids, "변수", M["variables"], "roles", len(M["roles"]))


if __name__ == "__main__":
    main()
