# -*- coding: utf-8 -*-
"""잇템로그 회원 프리셋 「외국인+한국제품반응」(사장님 10-25 화면 이름) — 자동 설명서(to_frame) 2편 → 판 숫자로 손질 → preset_save (기미크림 10-25).
    PYTHONUTF8=1 py channel/ititemlog/preset/ititemlog_preset.py

틀 숫자 주인 = tools/calcopy/hybrid/styles/잇템로그판.json frame(6/6 픽셀 실측) — 여기서 숫자를 다시 적지 않고 판에서 읽는다(두 벌 금지).
자동 설명서가 틀린 곳(10-25 실측, C:/숏템_칼카피/ititemlog/frames/frame_<편>_auto 대신 frame_<편>.json):
  ① 제목: 2줄을 한 층·흰 한 색으로 잡음(y236) → 판 frame.title 2줄(흰 #FDFDFD / 노랑 #FDDE01, 가운데 y271·408, TmonMonsori 132·120)
  ② 자막 층은 자동 그대로(기록용) — 렌더는 자막팩 ititemlog(판 caption.pack)이 정한다
렌더 숫자는 판(잇템로그판·잇템로그판_v2) — 이 폴더는 숏템프리셋 기록·회원 기본값(defaults.json)용."""
import copy, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_save as P
from tools.calcopy.hybrid import styles as STY
SLUG, STYLE = "ititemlog", "외국인+한국제품반응"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
AUTO = Path("C:/숏템_칼카피/ititemlog/frames"); HAND = Path(__file__).parent / "_hand"
IDS = {  # 편: 제목 2줄 — 화면 글자 그대로(3초 프레임 판독, 10-25)
    "aUicTeDoW04": ("한국 화장품 쓰고", "커버력에 당황한 외국인"),
    "ro1l3u734v4": ("한국 콜라겐 마스크", "쓰고 충격받은 외국인"),
}
ROLES = ["훅 나레(결과 먼저 — '~는데요')", "원음 반응(본인 말)", "나레 경과·원리", "원음 반응", "둘째 원본 다리 나레", "끝 전언 '~던데,'", "끝 전언 '~고 하고.'", "끝 혼잣말 '아, …야겠다.'"]


def _hex(c):
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def hand(i):
    A = json.loads((AUTO / f"frame_{i}.json").read_text(encoding="utf-8"))
    F = STY.load("잇템로그판")["frame"]
    t1, t2 = F["title"]
    lh = t2["center"] - t1["center"]
    layers = []
    for L in A["layers"]:
        L = copy.deepcopy(L)
        if L.get("role") == "title":
            L.update(y=t1["center"] - lh / 2, line_h=lh, size=float(t1["px"]), font=t1["font"].rsplit(".", 1)[0], w=max(t1["max_w"], t2["max_w"]),
                     rgb=_hex(t1["color"]), line_rgb=[_hex(t1["color"]), _hex(t2["color"])], line_scale=[1.0, round(t2["px"] / t1["px"], 3)],
                     lines=2, text=IDS[i][0] + chr(10) + IDS[i][1])
        layers.append(L)
    out = dict(A, layers=layers)
    out["made_from"] = {"tool": "ititemlog_preset.hand", "from": f"frames/frame_{i}.json",
                        "notes": ["제목 = 판 잇템로그판.json frame.title(흰/노랑 2줄 6/6) — 자동은 한 색 한 덩어리로 잡음", "자막 층 = 자동 그대로(렌더는 자막팩 ititemlog)"]}
    return out


def main():
    HAND.mkdir(exist_ok=True)
    for i in IDS:
        (HAND / f"frame_{i}.json").write_text(json.dumps(hand(i), ensure_ascii=False, indent=1), encoding="utf-8")
    if PRESET.exists():
        shutil.rmtree(PRESET)
    for i in IDS:
        J = json.loads((ROOT / "channel" / SLUG / "뜯기" / i / "뜯기.json").read_text(encoding="utf-8"))
        P.save(J, json.loads((HAND / f"frame_{i}.json").read_text(encoding="utf-8")), PRESET, i, f"channel/{SLUG}/뜯기/{i}/뜯기.json", (),
               "잇템로그자막", "노랑·흰 굵은 고딕 + 진한 외곽선 · 훅 첫 나레 빨강 · 등장 cut")
    P.set_meta(PRESET, roles=ROLES, source_kind="해외영상")
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["note"] = "기록용 — 렌더 숫자는 tools/calcopy/hybrid/styles/잇템로그판.json(·_v2), 자막 효과는 자막팩 ititemlog(_v2). 회원 화면 이름 '외국인+한국제품반응'(사장님 10-25)"
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    V = STY.load("잇템로그판")
    D = {"_rule": "기본값 = 이 프리셋 원본 영상(사장님 10-20). 글꼴·자막 외곽선은 frame.json 그대로. 회원이 바꾼 칸만 회원 값. 읽는 곳 = tools/calcopy/preview_request.preset_defaults",
         "_from": "판 잇템로그판.json 한 곳에서 읽음 — voice(유라, 사장님 10-20 '유라가 괜찮고') · bgm.id/db_below_voice(handconst 6편 실측) · caption 쌓기 없음(enter 4칸 cut = replace) · 뜯기 6편 bgm 있음 6/6(제미나이 판독 10-25)",
         "tts": {"provider": "typecast", "voice_id": V["voice"]["voice_id"], "name": V["voice"]["name"], "tempo": 1.25},
         "bgm": {"candidates": [V["bgm"]["id"]] + list(V["bgm"].get("candidates") or [])},   # gain 은 안 적음 — 판은 나레 대비 dB(db_below_voice)로 정하고 선형 gain 실측이 없다
         "caption": {"mode": "replace"}}
    (PRESET / "defaults.json").write_text(json.dumps(D, ensure_ascii=False, indent=1), encoding="utf-8")
    print("변수", M["variables"], "roles", len(M["roles"]))


if __name__ == "__main__":
    main()
