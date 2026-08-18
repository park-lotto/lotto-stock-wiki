# -*- coding: utf-8 -*-
"""타입캐스트 성우 6명을 voice_presets.json에 추가한다 (2026-08-19).

사장님 지목: 남자 필재·김건·박창수·용식이 / 여자 문정·발키리.
남자 성우 라인업이 일레븐랩스에 없어서 타입캐스트를 나란히 붙이는 것이 목적.

★변형(variant) 이름은 일레븐랩스와 **같은 4종**(stable/natural/expressive/whisper)을 쓴다.
  UI(produce.html)가 이 이름으로 탭을 그리고, naturalize가 whisper일 때 [whispers] 태그를
  넣는다 — 새 이름을 만들면 그 배선이 전부 어긋난다(0순위-B).
  수치 축만 엔진별로 다르다: 일레븐랩스=stability/style, 타입캐스트=emotion/intensity.

실행: py shopping_shorts/scripts/add_typecast_presets.py
      py shopping_shorts/scripts/add_typecast_presets.py --bake   (샘플 mp3까지 굽기)
"""
import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from shopping_shorts import voice_presets  # noqa: E402

# 사장님 지목 6명. voice_id는 /v1/voices 실측(2026-08-19) — 이름으로 찾지 말고 id로 박는다
# (동명이인·이름 변경에 안 흔들린다). 전원 ssfm-v30에 존재하며 감정 7~8종을 지원한다.
VOICES = [
    # (group_id, 표기명, 한줄설명, voice_id, 성별)
    ("tc-piljae",   "필재",   "묵직하고 신뢰가는 남성",       "tc_68257f68bc6e3c161ab5078d", "M"),
    ("tc-gunn",     "김건",   "또렷하고 설득력 있는 남성",     "tc_61c2f7741330d213c238cba6", "M"),
    ("tc-changsu",  "박창수", "친근하고 편안한 남성",         "tc_6059dad0b83880769a50502f", "M"),
    ("tc-yongsik",  "용식이", "능청스럽고 개성있는 남성",      "tc_5feb2085cca1a479e73bac37", "M"),
    ("tc-moonjung", "문정",   "차분하고 단정한 여성",         "tc_68f9c6a72f0f04a417bb136f", "F"),
    ("tc-valkyrie", "발키리", "당차고 힘있는 여성",           "tc_60478557f12456064b353409", "F"),
]

# 일레븐랩스의 변형과 **같은 이름**에 타입캐스트 축(emotion/intensity)을 태운다.
#
# ★whisper는 일부러 뺐다 — 붙일 수 있는데 안 붙인 것이다(2026-08-19).
#   whisper 변형은 "사장님이 실제로 들어보고 통과시킨 성우에게만 준다"는 기존 판정이
#   있다(2026-07-16, test_voice_presets_whisper.py: 베스트 5명만, 탈락 3명은 [whispers]가
#   안 먹혀 제외). 타입캐스트 6명은 아직 그 청취를 안 거쳤으므로 같은 기준을 지킨다.
#   API가 whisper 감정을 지원하는 것과(6명 전원 지원 확인) 그 소리가 쓸 만한 것은 다른
#   문제다. 사장님이 들어보고 좋다고 하시면 그때 추가한다.
VARIANT_SPECS = [
    ("stable",     {"emotion": "normal", "emotion_intensity": 1.0}),
    ("natural",    {"emotion": "normal", "emotion_intensity": 1.3}),
    ("expressive", {"emotion": "toneup", "emotion_intensity": 1.3}),
]

MODEL_ID = "ssfm-v30"
# 사장님 확정(2026-08-19 청취): 1.2배. 일레븐랩스 프리셋(1.5~1.6)과 다른 값이라 그대로 둔다.
DEFAULT_SPEED = 1.2
DEFAULT_SILENCE_TRIM = "mid"
SOURCE_REF = "타입캐스트 지목 성우(2026-08-19)"


def build_rows():
    """6명 x 4변형 = 24행. 순수 계산만 한다(테스트하기 쉽게)."""
    rows = []
    for gid, name, one_liner, voice_id, _sex in VOICES:
        for variant, settings in VARIANT_SPECS:
            pid = f"{gid}-{variant}"
            rows.append({
                "preset_id": pid,
                "group_id": gid,
                "variant": variant,
                "name": name,
                "one_liner": one_liner,
                "lang": "KR",
                "archetype": one_liner,
                "base_voice_id": voice_id,
                "model_id": MODEL_ID,
                "voice_settings": dict(settings),
                "default_speed": DEFAULT_SPEED,
                "default_silence_trim": DEFAULT_SILENCE_TRIM,
                "sample_file": f"{pid}.mp3",
                "source_ref": SOURCE_REF,
                "origin": "curated",
                # ⭐베스트는 사장님 청취 판정 표식이다. 아직 안 들으셨으므로 False —
                # '더보기'에 붙는다. 들으신 뒤 올리면 된다.
                "best": False,
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bake", action="store_true", help="샘플 mp3까지 굽는다(실제 크레딧 사용)")
    args = ap.parse_args()

    path = voice_presets.PRESETS_JSON
    cur = json.loads(path.read_text(encoding="utf-8"))
    new = build_rows()
    new_ids = {r["preset_id"] for r in new}
    our_gids = {gid for gid, *_ in VOICES}
    # 재실행해도 중복이 안 쌓이게 — 같은 preset_id는 새 값으로 교체한다(idempotent).
    # ★VARIANT_SPECS에서 변형을 빼면 옛 행이 파일에 남는다(whisper를 뺀 게 실제 사례).
    #   우리 그룹의 행 중 이번에 안 만든 것은 **지운다** — 안 지우면 화면엔 남는데
    #   아무도 관리하지 않는 유령 프리셋이 된다.
    stale = [p for p in cur if p["group_id"] in our_gids and p["preset_id"] not in new_ids]
    merged = [p for p in cur
              if p["preset_id"] not in new_ids and p["group_id"] not in our_gids] + new
    for p in stale:
        f = voice_presets.SAMPLES_DIR / (p.get("sample_file") or "")
        if p.get("sample_file") and f.exists():
            f.unlink()
            for sc in (".align.json", ".cuts.json"):     # 사이드카도 같이(stale 방지)
                s = f.with_name(f.name + sc)
                if s.exists():
                    s.unlink()
        print(f"  [정리] {p['preset_id']} 제거")
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"voice_presets.json: {len(cur)} → {len(merged)}건 (타입캐스트 {len(new)}건)")

    if not args.bake:
        print("샘플은 안 구웠다. 굽기: --bake")
        return
    from shopping_shorts.mix_pipeline import synthesize_line
    voice_presets.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    from shopping_shorts.scripts.build_voice_samples import DEMO_TEXT
    ok = fail = 0
    for p in new:
        out = voice_presets.SAMPLES_DIR / p["sample_file"]
        try:
            synthesize_line(
                DEMO_TEXT, out,
                voice={"voice_id": p["base_voice_id"], "settings": p["voice_settings"],
                       "speed": p["default_speed"], "silence_trim": p["default_silence_trim"],
                       "naturalize_profile": None, "model_id": p["model_id"]},
                beat_role="훅", beat_index=0, beat_total=5)
            print(f"  [OK] {p['preset_id']:<26} {out.stat().st_size//1024}KB")
            ok += 1
        except Exception as e:
            print(f"  [ERR] {p['preset_id']}: {type(e).__name__} {e}")
            fail += 1
    print(f"샘플: 성공 {ok} · 실패 {fail}")


if __name__ == "__main__":
    main()
