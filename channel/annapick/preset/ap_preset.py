# -*- coding: utf-8 -*-
"""안나픽 연예인템 프리셋 「검정띠2줄_출처」 — 자동 설명서 6편 → 손질(창 아래 출처 줄·채널 로고 층 추가) → preset_save (관제 097).
    PYTHONUTF8=1 py channel/annapick/preset/ap_preset.py
★뜯기 기록용 — 렌더에 쓰지 않는다(사장님 10-17: 얜샷템 렌더 = 만템 색톤 프레임 channel/mantem/frame_얜샷템.json).
손질 근거(itYwQVyuCcc 3초 프레임 실측): 창 아래 '출처: 고은언니 한고은' 회색 글 y1518~1551 x403~676(가운데 540) ·
맨 아래 'anna/pick' 회색 로고 2줄 y1748~1830 x478~602. 자동 to_frame 은 제목·자막만 잡고 이 두 층을 못 잡았다."""
import copy, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P
SLUG, STYLE = "annapick", "검정띠2줄_출처"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/annapick/frames"); HAND = Path(__file__).parent / "_hand"
IDS = ["itYwQVyuCcc", "Ww0IZLSL7mY", "hj9O7LmPZjo", "iS0la2aQyl8", "wweUXE86oMM", "rF_-X8jLkdU"]
CREDIT = {"itYwQVyuCcc": "고은언니 한고은", "Ww0IZLSL7mY": "장공장장윤정", "hj9O7LmPZjo": "백지영 Baek Z Young",
          "iS0la2aQyl8": "고은언니 한고은", "wweUXE86oMM": "채널십오야", "rF_-X8jLkdU": "류혜영레몬과밀치회"}
ROLES = ["원음 훅(본인 말 한 마디)", "나레 1줄(~다는데요 전언체, 인물+제품 정체)", "원음 증언(고민·계기)", "원음 디테일(쓰는 법)", "원음 마무리"]
BASE = dict(kind="text", w=960, align="center", line_rgb=None, line_scale=None, outline=None, line_outline=None, shadow=None, box=None,
            italic=False, letter_spacing=0, word_spacing=0, valign="center", enter=None)
SOURCE = dict(BASE, role="label", x=540, y=1515, lines=1, font="CcPretendard-Regular", size=34.0, line_h=40, rgb=[125, 125, 125])
LOGO = dict(BASE, role="brand", x=540, y=1745, lines=2, font="CcPretendard-Regular", size=36.0, line_h=44, rgb=[140, 140, 140], text="anna\npick")

def hand(i):
    F = json.loads((AUTO / f"{i}_auto.json").read_text(encoding="utf-8"))
    F["layers"] += [dict(copy.deepcopy(SOURCE), text=f"출처 : {CREDIT[i]}"), copy.deepcopy(LOGO)]
    F["made_from"] = {"tool": "ap_preset.hand", "from": f"{i}_auto.json", "notes": ["출처 줄(label)·로고(brand) 층 손으로 추가 — 3초 프레임 실측 자리"]}
    return F

def main():
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists(): shutil.rmtree(PRESET)
    for i in IDS:
        J = json.loads((ROOT / "channel/annapick/뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i, f"channel/annapick/뜯기/{i}/뜯기.json", (), "원음자막", "원음·나레 공통 자막(자동)")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")   # 목록에 '국내 원본 재편집'이 없어 아이템홈과 같은 값(원본 영상 재편집)
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["note"] = "기록용 — 렌더는 얜샷템(만템 색톤) 프레임"
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("변수", M["variables"], "roles", len(M["roles"]))
if __name__ == "__main__": main()
