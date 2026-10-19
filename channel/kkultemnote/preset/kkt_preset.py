# -*- coding: utf-8 -*-
"""꿀템노트 연예인템 프리셋 「검정2줄_분홍파랑_출처」 — 자동 설명서 8편 → 손질 → preset_save (관제 097, 2026-10-18).
    PYTHONUTF8=1 py channel/kkultemnote/preset/kkt_preset.py
자동 설명서 = to_frame --title-font SBAggroB --ocr-from <auto>(C:/숏템_칼카피/kkultemnote/frames/<id>_sbaggro.json).
손질 근거(channel/kkultemnote/스타일분석.md, 실측):
  · 제목 글꼴: to_frame 자동은 GmarketSansBold 를 골랐다 — 뜯기 제목 띠 판별 1위는 SBAggroB(BpU 0.450·cLk 0.507·m0E 0.408) → --title-font SBAggroB.
  · 제목 줄 색: 1줄 분홍 #FCB9CE / 2줄 파랑 #0091FD 가 강조색, 어절마다 흰과 섞는다(BpU·m0E·KCx 프레임) — line_rgb 는 강조색 두 개로 고정, 어절 섞기는 notes.
  · 자막 글꼴: 자동은 편마다 CcDokdo·DongleBold·CcYeonSung·CcGBatang·GaeguBold 로 흩어졌다(원음 손글씨 크롭이 흐려 판별 점수 0.06~0.23) —
    눈 대조(fr/fc_orig.png) + 뜯기 합산 1위(BpU·_dz) = Kkubulim → 원음 자막 Kkubulim 90px 흰·검정 5px 로 고정. 나레 자막(굵은 고딕+노랑)은 자막팩 보강안 speakers.narr.
  · 출처 줄(label) 층 추가: '출처 : <채널>' Pretendard Regular 40px #FAFAFA y1615~1650(8/8편 같은 자리).
  · 로고 없음(8/8) — brand 층 넣지 않는다. 댓글 카드 스티커는 틀이 아니라 자막팩 보강안 new_stickers.comment_card.
"""
import copy, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P
SLUG, STYLE = "kkultemnote", "검정2줄_분홍파랑_출처"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/kkultemnote/frames"); HAND = Path(__file__).parent / "_hand"
IDS = ["BpUOIUwkoG4", "m0Ex0y1DN5s", "KCxJ5qJft38", "653bTRm8p6E", "znHaConczpE", "2wJTffElmjk", "cLk6fJly6OY", "_dzncUms1yQ"]
ROLES = ["원음 훅(연예인 반응 한 마디 0~3초)", "나레 전언 한 줄('~한 이유가 있다는데?'·'~라는데요?', 인물+제품)", "원음 증언·시연",
         "나레 짧은 질문·정보('뭐 때문에 ~가요?'·'~다네요?')", "원음 답", "나레 반전·가격('가격은 비싸다는데요?')", "원음 끝(감탄·'둘러보고 올게요^^')"]
BASE = dict(kind="text", w=960, align="center", line_rgb=None, line_scale=None, outline=None, line_outline=None, shadow=None, box=None,
            italic=False, letter_spacing=0, word_spacing=0, valign="center", enter=None)
SOURCE = dict(BASE, role="label", x=540, y=1612, lines=1, font="CcPretendard-Regular", size=40.0, line_h=46, rgb=[250, 250, 250])


def hand(i):
    F = json.loads((AUTO / f"{i}_sbaggro.json").read_text(encoding="utf-8"))
    notes = []
    for L in F["layers"]:
        if L.get("role") == "title":
            L["line_rgb"] = [[252, 185, 206], [0, 145, 253]]
            notes.append("제목 line_rgb = 강조색 분홍·파랑 고정(어절마다 흰과 섞는 규칙은 편마다 다름 — 스타일분석 §2)")
        if L.get("role") == "caption":
            L.update(font="Kkubulim", size=90.0, rgb=[255, 255, 255], outline={"px": 5, "rgb": [0, 0, 0]}, enter={"kind": "none", "ms": 0})
            notes.append("자막 = 원음 꾸불림 90px 흰·검정 5px·컷인(30fps 실측) — 나레 자막은 자막팩 보강안")
    F["layers"].append(dict(copy.deepcopy(SOURCE), text="출처 : $per_video"))
    F["made_from"] = {"tool": "kkt_preset.hand", "from": f"{i}_sbaggro.json", "notes": notes + ["출처 줄(label) 손으로 추가 — y1615~1650 실측"]}
    return F


def main():
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists(): shutil.rmtree(PRESET)
    for i in IDS:
        J = json.loads((ROOT / "channel/kkultemnote/뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i, f"channel/kkultemnote/뜯기/{i}/뜯기.json", (), "원음자막", "원음 꾸불림 자막(손질 고정)")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")   # 목록에 '국내 원본 재편집' 없음 — 안나픽과 같은 값(원본 영상 재편집)
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["note"] = "꿀템노트 벤치 틀 기록 — 나레/원음 두 벌 자막·스티커는 channel/kkultemnote/자막팩_보강안.json, 하이브리드 판은 하이브리드_판설계.md"
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("변수", M["variables"], "roles", len(M["roles"]))


if __name__ == "__main__":
    main()
