# -*- coding: utf-8 -*-
"""굿레터(@굿레터) 연예인레시피 프리셋 두 벌 — 자동 설명서(to_frame) → 손질(_hand) → preset_save (관제 097, 2026-10-20).
    PYTHONUTF8=1 py channel/goodletter/preset/gl_preset.py
굿레터는 10-08 무렵 틀을 바꿨다(줄판독 8편 실측):
  ① 「검정틀_주황상자_팝자막」(새 틀, 10-08~ · vcb_-h7Ajwo·753rWbcjHYc·sMx9RWuifCA) ← 지금 채널 틀 = 칼카피 기본
  ② 「검정틀_3색팝자막」(옛 틀, 09-25~10-04 · j-fB·kfmZ·E6SX·m4m5·X9mR) ← 기록·선택지
to_frame 은 OCR 없이(--no-ocr, 제미나이 금지) bg·video 만 잡았다 → 글자·띠 층은 전부 손으로(실측 근거 아래, 1080×1920).
새 틀 실측(sMx9 13.6초 프레임 픽셀):
  제목 1줄 흰 잉크 y173~263(Jalnan2 눈 대조 — 글꼴 대조표 C:/숏템_칼카피/goodletter/work/fr/fontcmp_title.jpg)
  제목 2줄 주황 상자 #FE7813 x182~897 y288~411(글 길이 따라 폭 변함) 안 짙은 글 #0B0F0F
  주황 가로선 #FE7813 y464~475 · y1546~1557(전폭) · 창 1068×1096 at (6,464)(뜯기 layout)
  자막 잉크 y1288~1353(높이 65) 흰 #FDFDFD / 강조 호박 #FCB53F · 검정 외곽 약 6px · Binggrae-Bold 눈 대조(fontcmp_cap.jpg, 확정 아님)
  출처 '출처 · <채널> (YouTube)' 흰 y1583~1626 · P.S. 줄 y1670~1718(P.S. #FD811F + 본문 #FEEB65 손글씨) · 링크 줄 '프로필 링크에서 N번' y1794~1836(번호 주황)
  창 오른쪽 위 '✉ 굿레터' 흰 반투명 · 제품 꼬리표 '● <제품>' 주황 알약 창 왼쪽 위(컷 따라 켜고 끔)
옛 틀: 제목 2줄 모두 글자만(2줄째 이름 주황 #F07106 + 요리 노랑 #F9DE4E / 민트·보라 낱말) · 주황선·상자·P.S.·링크·꼬리표·워터마크 없음
  · 창 1068×1066 at (6,478) · 자막 y1364~1427 · 출처 '출처: <채널>' 흰 · 끝 '제품 이름 자막'(노랑, y1212~1285, 컷과 즉시).
스키마 밖(손글씨 P.S. 두 색·알약 꼬리표·워터마크 투명도)은 brand/label 층 + notes 로 남기고 렌더는 판 설정(styles/굿레터판.json)이 그린다.
"""
import copy, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P

SLUG = "goodletter"
AUTO = Path("C:/숏템_칼카피/goodletter/frames"); HAND = Path(__file__).parent / "_hand"
SETS = {
    "검정틀_주황상자_팝자막": {
        "ids": ["vcb_-h7Ajwo", "753rWbcjHYc", "sMx9RWuifCA"],
        "label": {"vcb_-h7Ajwo": "빅마마 이혜정", "753rWbcjHYc": "도장TV", "sMx9RWuifCA": "성시경 SUNG SI KYUNG"},
        "title": {"vcb_-h7Ajwo": "5년째 유지한 아침\n이혜정 콩국물", "753rWbcjHYc": "5분이면 끝나는\n장윤정 들기름 국수", "sMx9RWuifCA": "1등 레시피로 끓인\n성시경 신라면"},
        "new": True},
    "검정틀_3색팝자막": {
        "ids": ["j-fB61Yhx5g", "kfmZ_t4Bbss", "E6SXj8FdT2s", "m4m5oajgQFo", "X9mRnmvmTD8"],
        "label": {"j-fB61Yhx5g": "JTBC 냉장고를 부탁해", "kfmZ_t4Bbss": "A급 장영란", "E6SXj8FdT2s": "게임부부 김가연",
                  "m4m5oajgQFo": "A급 장영란", "X9mRnmvmTD8": "깡주은"},
        "title": {"j-fB61Yhx5g": "셰프들이 그릇째 먹은\n윤남노 하겐다즈 먹조합", "kfmZ_t4Bbss": "무를 물엿에 3시간\n김가연 오징어젓무침", "E6SXj8FdT2s": "멸치볶음 킥이라는\n김가연 베트남 간장",
                  "m4m5oajgQFo": "밥 한 그릇 뚝딱\n김가연 새우젓무침", "X9mRnmvmTD8": "사먹으면 십만원인데\n강주은 티본스테이크"},
        "new": False},
}
ROLES = ["원음 훅(연예인 본인 말 0~3초: 메뉴·놀람·'~있길래' — 첫 강조색 줄 0.2~1.7초 안)",
         "(선택) 나레 다리 1~2조각('<이름> <장소>에서 나온 <제품>이래요' 전언, 8편 중 2편)",
         "원음 본문(만드는 법·재료·요령 — 말 조각마다 자막 팝, 강조색은 재료·핵심 팁·반문 펀치에)",
         "원음 맛 반응(먹는 얼굴·'맛있다' 류, 강조색)",
         "끝(원음 반전·평 한 줄, 강조색 — 새 틀은 끝까지 원음 / 옛 틀은 무음 제품 컷+제품 이름 자막 또는 나레 질문 '여러분은 ~ 뭐 ~?')"]
BASE = dict(kind="text", align="center", line_rgb=None, line_scale=None, outline=None, line_outline=None, shadow=None, glow=None, box=None,
            italic=False, letter_spacing=0, word_spacing=0, valign="center", enter=None, emphasis=None)
ORANGE = [254, 120, 19]


def layers_new(i, S):
    t = S["title"][i]
    return [
        dict(BASE, role="title", x=540, y=168, w=1040, lines=2, font="Jalnan2", size=96.0, line_h=124, rgb=[255, 255, 255],
             line_rgb=[[255, 255, 255], [11, 15, 15]], text=t),
        {"kind": "band", "x": 182, "y": 288, "w": 715, "h": 123, "rgb": ORANGE, "radius": 14},
        {"kind": "band", "x": 0, "y": 464, "w": 1080, "h": 12, "rgb": ORANGE, "radius": 0},
        {"kind": "band", "x": 0, "y": 1546, "w": 1080, "h": 12, "rgb": ORANGE, "radius": 0},
        dict(BASE, role="caption", x=540, y=1280, w=1020, lines=1, font="BinggraeBold", size=70.0, line_h=80, rgb=[253, 253, 253],
             outline={"px": 6, "rgb": [0, 0, 0]}, enter={"kind": "pop", "ms": 170}),
        dict(BASE, role="label", x=540, y=1580, w=1000, lines=1, font="CcPretendard-Bold", size=40.0, line_h=48, rgb=[255, 255, 255],
             text=f"출처 · {S['label'][i]} (YouTube)"),
        dict(BASE, role="brand", x=940, y=500, w=220, lines=1, font="CcPretendard-Bold", size=34.0, line_h=40, rgb=[230, 230, 230], text="✉ 굿레터"),
    ]


def layers_old(i, S):
    t = S["title"][i]
    return [
        dict(BASE, role="title", x=540, y=168, w=1040, lines=2, font="Jalnan2", size=96.0, line_h=124, rgb=[255, 255, 255],
             line_rgb=[[255, 255, 255], [240, 113, 6]], text=t),
        dict(BASE, role="caption", x=540, y=1356, w=1020, lines=1, font="BinggraeBold", size=70.0, line_h=80, rgb=[253, 253, 253],
             outline={"px": 9, "rgb": [0, 0, 0]}, enter={"kind": "pop", "ms": 170}),
        dict(BASE, role="label", x=540, y=1790, w=1000, lines=1, font="CcPretendard-Bold", size=40.0, line_h=48, rgb=[255, 255, 255],
             text=f"출처: {S['label'][i]}"),
    ]


def hand(i, S):
    F = json.loads((AUTO / f"{i}_auto.json").read_text(encoding="utf-8"))
    keep = [l for l in F["layers"] if l["kind"] in ("bg", "video")]
    for l in keep:
        if l["kind"] == "video":
            l.update(x=6, y=464 if S["new"] else 478, w=1068, h=1096 if S["new"] else 1066)
    F["layers"] = keep + (layers_new(i, S) if S["new"] else layers_old(i, S))
    if not S["title"][i]:
        F["layers"] = [l for l in F["layers"] if l.get("role") != "title"]
    F["made_from"] = {**(F.get("made_from") or {}), "tool": "gl_preset.hand", "from": f"{i}_auto.json",
                      "notes": (F.get("made_from") or {}).get("notes", []) + [
                          "to_frame --no-ocr(제미나이 금지)라 글자·띠 층은 손으로 — 실측 근거는 gl_preset.py 머리",
                          "자막 강조색(새 틀 호박 #FCB53F 한 색 / 옛 틀 주황·노랑·민트 3색)·P.S. 줄·제품 꼬리표·끝 제품 이름 자막은 스키마 밖 → 판 설정 굿레터판.json + 자막팩_보강안",
                          "자막 등장 = 말 조각마다 팝(약 30%→110~115%@0.1초→100%@0.15~0.18초, 60fps 실측) — 스키마 pop 170ms 로 근사"]}
    return F


def main():
    HAND.mkdir(exist_ok=True)
    for style, S in SETS.items():
        ids = [i for i in S["ids"] if (AUTO / f"{i}_auto.json").exists()]
        pdir = ROOT / "channel" / SLUG / "preset" / style
        for i in ids:
            (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i, S), ensure_ascii=False, indent=1), encoding="utf-8")
        if pdir.exists():
            shutil.rmtree(pdir)
        for i in ids:
            J = json.loads((ROOT / "channel" / SLUG / "뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
            P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), pdir, i, f"channel/{SLUG}/뜯기/{i}/뜯기.json", (),
                   "원음팝_강조색", "말 조각마다 팝 · 강조색 줄 23~50%(배치 = styles/굿레터판.json placement)")
        P.set_meta(pdir, roles=ROLES, source_kind="해외영상")   # '국내 원본 재편집' 키가 없어 스타픽룸·안나픽과 같은 값
        M = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
        M["note"] = ("굿레터 지금 틀(10-08~) — 칼카피 기본" if S["new"] else "굿레터 옛 틀(09-25~10-04) — 기록·선택지") + \
            ". 근거 channel/goodletter/스타일분석.md · 줄판독/"
        (pdir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
        print(style, "편", ids, "변수", M.get("variables"), "roles", len(M["roles"]))


if __name__ == "__main__":
    main()
