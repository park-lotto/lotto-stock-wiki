# -*- coding: utf-8 -*-
"""아이템홈 연예인템 프리셋 「검정띠2줄」 — 자동 설명서 8편 → 손질(자막 나레 굵은체 통일) → preset_save (관제 097).
    PYTHONUTF8=1 py channel/itemhome/preset/ih_preset.py
손질 근거(눈으로 본 것, 프레임 7편 대조): 나레 자막 = 굵은 둥근 고딕(SBAggroB·잰 점수 0.93) + 검정 외곽선 + 강조어 노랑/분홍,
원음(따옴표) 자막 = 기울인 가는 고딕 + “ ” + 가는 외곽선. 자동 to_frame 은 첫 자막 하나만 재서 편마다 글꼴·상자(갈색 노이즈)가 달라졌다."""
import json, sys, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P
SLUG, STYLE = "itemhome", "검정띠2줄"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/itemhome/frames"); HAND = Path(__file__).parent / "_hand"
IDS = ["MfptnwqlGKs", "dNthcAKrj5U", "mtMtHzG1GHk", "cLxEI_U1e_E", "2uPIHITVEX8", "agEwVlDn25U", "-RgN_DncvWQ", "AoHnZ43GuZ4"]
ROLES = ["훅(인물+상황+제품 정체 한 줄)", "원음 증언 1(본인 말 “따옴표”)", "디테일(어디서·몇 통째·누가 맡아봄)", "제3자 반응·맥락", "원음 증언 2(본인 말)", "원음 마무리(본인 한 마디)"]
NARR = dict(font="SBAggroB", size=75.0, line_h=86, y=1222, outline={"px": 4, "rgb": [0, 0, 0]}, box=None, letter_spacing=0, word_spacing=0, italic=False)
QUOTE = dict(font="SUITBold", size=70.0, line_h=82, y=1222, outline={"px": 3, "rgb": [0, 0, 0]}, box=None, letter_spacing=0, word_spacing=0, italic=True)

def hand(i):
    F = json.loads((AUTO / f"{i}_auto.json").read_text(encoding="utf-8")); notes = []
    for l in F["layers"]:
        if l.get("role") == "caption":
            l.update(copy.deepcopy(NARR)); l["rgb"] = [252, 250, 250]
        if l.get("role") == "title" and l["font"] != "Pretendard":
            notes.append(f"제목 글꼴 {l['font']}→Pretendard(8편 중 7편 Pretendard-ExtraBold)"); l["font"] = "Pretendard"
    F["made_from"] = {"tool": "ih_preset.hand", "from": f"{i}_auto.json", "notes": ["자막 = 나레 굵은체로 통일(SBAggroB 75·검정 외곽 4)"] + notes}
    return F

def main():
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    import shutil
    if PRESET.exists(): shutil.rmtree(PRESET)
    for i in IDS:
        J = json.loads((ROOT / "channel/itemhome/뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i, f"channel/itemhome/뜯기/{i}/뜯기.json", (), "나레_굵은체", "나레 구간 자막(손질)")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    base = next(l for l in json.loads((PRESET / "frame.json").read_text(encoding="utf-8"))["layers"] if l.get("role") == "caption")
    q = copy.deepcopy(base); q.update(copy.deepcopy(QUOTE))
    M["caption_styles"].append({"name": "원음_따옴표", "layer": q, "status": "손질(프레임 7편 눈 대조 — 기울인 가는 고딕·“ ”·강조어 노랑)", "sources": IDS,
                                "notes": ["원음(연예인 본인 말) 구간 자막. 글꼴은 잰 점수가 낮다(0.2~0.38, SUIT-Bold 6표·Pretendard-SemiBold 4표) — 기울임 때문. 렌더 대조 전"]})
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("변수", M["variables"], "roles", len(M["roles"]), "styles", [s["name"] for s in M["caption_styles"]])
if __name__ == "__main__": main()
