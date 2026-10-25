# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/신박판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 읽기 전용 참고물 — 설명서 프리셋 생성기는 회원 옛 길이 결과를 읽으므로 지우지 않는다)
"""신박발견(@신박발견) 생활 꿀팁 자막썰 프리셋 「연회색틀_둥근창_창아래자막」 — 자동 설명서 → 손질 → preset_save (관제 097, 2026-10-20).
    PYTHONUTF8=1 py channel/sinbak/preset/sinbak_measure.py   (실측 → C:/숏템_칼카피/sinbak/work/preset/measure.json, 5분)
    PYTHONUTF8=1 py channel/sinbak/preset/sinbak_preset.py    (손질본 _hand/ → preset_save)
★1차 = 벤치 그대로, 로고 자리만 우리 브랜드 '신박리포트'(그림 아직 없음 → 층 비움, 스키마 빈칸 아래).
손질 근거(실측, 1080×1920, 6편 원본 프레임 픽셀 — sinbak_measure.py):
  바탕  [242~243] 단색(창 밖 y1450~1880 중앙값, 6/6) · 로고 줄 잉크 [94,280,773,406] 6/6 같음(마스코트+'a novel discovery'+'신박발견')
  창    [19,541,1060,1287] = x19 y541 w1041 h746 (fzo 행 900 밝기 242→172 가 x18~21, 열 540 y540→541, 아래 1286→1287)
        모서리 반경 87 — 원 맞춤 rmse<2.5 인 모서리 15개(rAt·fzo·CnR·edT·oT) 84~93, 중앙 87 (줄판독 '30·75 눈' 정정)
  제목  SUITBold · 검정 [13,13,13] · 왼쪽 정렬 · 1줄 · 크기/x/y 는 편마다(잉크 높이 역산 68~86, 짧은 제목이 큼) → $per_video
        글꼴: fontmatch.pooled_rank 6줄 1위 NanumMyeongjoEB(정규 0.900·원점수 0.38·일치 2/6)는 명조 부리가 원본에 없어(font_eye_title_caption.png) 뺌
        → 고딕 후보 CcIBMPlexSansKR-Bold 0.824 / SUITBold 0.811 중 획 굵기 눈 대조로 SUITBold. 확신 낮음(원본이 확대 흐림, 원점수 0.35)
        자간 −2.1 · 낱말 간격 +5.6(원본 낱말 틈 중앙 27.5px vs 글꼴 24)
  본문  CcPretendard-SemiBold 71.9 (18줄 묶음 1위 0.946·7/18, 2위 SUITBold 0.930·6/18 — 원본은 둥근 손글씨풍이라 등록 글꼴에 같은 것 없음)
        잉크 y1300~1365 → 줄 칸 y1291 · 가운데 x548(잉크 가운데 18줄 중앙값) · 검정 + 흰 2px 테(고리 밝기 1~2px 245~255 vs 바탕 242, 3px 부터 242)
        자간 −3.3 · 낱말 간격 +20.3(원본 낱말 틈 중앙 40px vs 글꼴 23 — 띄어쓰기가 넓다) · 등장 instant(줄판독 enter 60/60)
  창 안 글씨(스키마 빈칸) BMDOHYEON(16줄 묶음 1위 정규 1.000·원점수 0.763·16/16 일치) · 채움 잉크 높이 82px · 검정 테 9px(행 스캔 중앙값)
        색 = 뜻: 빨강 #F80A50(외침·힘) / 노랑 #EFC716(과정·결과·감탄) / 파랑 #068EF7(도구 소리·이름표) / 초록 #04AF0D(남 대사 1회)
        자리 = 동작 옆 자유 배치(줄마다 다름) → 스키마 글자 층은 고정 자리라 못 담음. manifest.overlay_style 에 값만 적음
  oT-SxFJcQ-4 예외: 1.667초 뒤 창이 y27~1279 로 커지고 제목·로고 사라짐(스키마 frames 로 담을 수 있으나 1차는 처음 틀만)
"""
import copy, json, shutil, statistics as st, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P, to_frame as TF  # noqa: E402

SLUG, STYLE = "sinbak", "연회색틀_둥근창_창아래자막"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/sinbak/frames"); HAND = Path(__file__).parent / "_hand"
MEAS = Path("C:/숏템_칼카피/sinbak/work/preset/measure.json")
IDS = ["rAt34vkQ0OY", "oT-SxFJcQ-4", "fzoZc7V_hDM", "CnRWZ3scVfk", "bpjoacs2S6Q", "edTkyQKrqMk"]   # measure.json 제목 순서와 같다
ROLES = ["훅 '…인데/…다는데'(본문 1줄, 실패 장면)", "다리(문제·실패, 창 안 빨강 외침·노랑 상태)", "과정 본문(컷=자막 바뀜, 창 안 노랑·파랑 소리)",
         "질문 '…하면?'", "공개(창 안 감탄 + 가장 큰 효과음)", "끝 '진짜 ○○하네!!/ㄷㄷ'"]
FAM_T, FAM_C, FAM_O = "SUITBold", "CcPretendard-SemiBold", "BMDOHYEON"
BASE = dict(kind="text", line_rgb=None, line_scale=None, outline=None, line_outline=None, shadow=None, glow=None, box=None,
            italic=False, letter_spacing=0, word_spacing=0, valign="center", enter=None, emphasis=None)
VIDEO = {"kind": "video", "x": 19, "y": 541, "w": 1041, "h": 746, "radius": 87}
CAPTION = dict(BASE, role="caption", x=546, y=1291, w=1000, align="center", lines=1, font=FAM_C, size=71.9, line_h=83, rgb=[0, 0, 0],
               outline={"px": 2, "rgb": [255, 255, 255]}, letter_spacing=-3.3, word_spacing=20.3, enter={"kind": "none", "ms": 0})
LOGO_BOX = [94, 280, 773, 406]


def title_layer(M, k, text):
    b = M["title"]["ink_boxes"][k]
    size = TF.size_and_top(FAM_T, text, b[1], b[3] - b[1], None)["size"]
    r = TF.size_and_top(FAM_T, text, b[1], b[3] - b[1], round(size * 1.15))
    bear = TF._ink_x(TF._pil_font(FAM_T, size), text[0])[0]
    return dict(BASE, role="title", x=round(b[0] - bear), y=r["y"], w=1000, align="left", lines=1, font=FAM_T, size=size, line_h=r["line_h"],
                rgb=[13, 13, 13], letter_spacing=M["title"]["letter_spacing"], word_spacing=M["title"]["word_spacing"], text=text)


def hand(M, k, i):
    F = json.loads((AUTO / f"frame_{i}.json").read_text(encoding="utf-8"))
    R = json.loads((ROOT / "channel" / SLUG / "줄판독" / f"{i}.json").read_text(encoding="utf-8"))
    F["canvas"] = [1080, 1920]                                    # 자동본은 360×640 축소 캔버스 — 1080 실측값으로 다시 쓴다
    F["layers"] = [{"kind": "bg", "rgb": M["bg"][i]}, copy.deepcopy(VIDEO), title_layer(M, k, R["title_lines"][0]["text"]),
                   dict(copy.deepcopy(CAPTION), x=round(st.median((b[0] + b[2]) / 2 for b in M["caption"]["ink_boxes"])),
                        y=M["caption"]["y"], size=M["caption"]["size"])]
    F["made_from"] = {**(F.get("made_from") or {}), "tool": "sinbak_preset.hand", "from": f"frame_{i}.json",
                      "notes": (F.get("made_from") or {}).get("notes", []) + [
                          "캔버스 1080 으로 · 창/제목/본문 손질(실측 근거 = 이 파일 머리, 값 = measure.json)",
                          "로고 줄 [94,280,773,406] = 우리 '신박리포트' 자리 — 그림 없음, 층 비움(스키마 빈칸 아님, 자산 빈칸)",
                          "창 안 글씨(BMDOHYEON·검정 9px 테·색=뜻·자유 자리)는 스키마 글자 층에 못 담음 → manifest.overlay_style"]}
    return F


def main():
    M = json.loads(MEAS.read_text(encoding="utf-8"))
    HAND.mkdir(exist_ok=True)
    for k, i in enumerate(IDS):
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(M, k, i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists():
        shutil.rmtree(PRESET)
    for i in IDS:
        tp = ROOT / "channel" / SLUG / "뜯기" / i / "뜯기.json"
        P.save(json.loads(tp.read_text(encoding="utf-8")), json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i,
               f"channel/{SLUG}/뜯기/{i}/뜯기.json", (), "본문_검정흰테_즉시", "창 아래 본문 1줄 · instant · 컷=자막 바뀜(45/54)")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")
    J = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    o = M["overlay"]
    J["note"] = "1차 = 벤치 그대로. 로고 자리 = 신박리포트(그림 미제작 — 자리만). 창 안 글씨는 overlay_style(스키마 밖)"
    J["logo_slot"] = {"box": LOGO_BOX, "brand": "신박리포트", "asset": None, "bench": "마스코트+'a novel discovery'+'신박발견'(복사 금지)"}
    J["overlay_style"] = {"font": FAM_O, "font_score": o["pooled"]["top"][0], "fill_ink_h": o["fill_ink_h_med"],
                          "size": TF.size_and_top(FAM_O, "(쾌감)", 0, o["fill_ink_h_med"], None)["size"],
                          "outline": {"px": o["outline_px_med"], "rgb": [0, 0, 0]}, "enter": "instant",
                          "colors": {"외침·힘": "#F80A50", "과정·결과·감탄": "#EFC716", "도구 소리·이름표": "#068EF7", "남 대사": "#04AF0D"},
                          "place": "동작 바로 옆 자유 배치(줄판독 x·y) — 스키마 빈칸", "src": str(MEAS)}
    (PRESET / "manifest.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    print("편", IDS, "변수", J["variables"], "roles", len(J["roles"]), "overlay size", J["overlay_style"]["size"])


if __name__ == "__main__":
    main()
