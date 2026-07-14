"""각 큐레이션 프리셋으로 공통 데모 문장을 읽어 assets/voice_samples/<sample_file>를 생성.

ElevenLabs 실호출(크레딧 소모)이라 큐레이션/튜닝 시 수동 1회 실행.
  python -m shopping_shorts.scripts.build_voice_samples
--only <preset_id> 로 특정 프리셋만 재생성 가능."""
import argparse

from shopping_shorts import voice_presets, audio_post
from shopping_shorts.tts import synthesize_tts

DEMO_TEXT = ("[warmly] 시어머니가 알려주신 이 세제로 욕실을 청소했더니 구석구석 반짝반짝, "
             "[amused] 찌든 때가 싹 없어졌더라고요.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="특정 preset_id만")
    args = ap.parse_args()

    voice_presets.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    presets = voice_presets.load_presets_file()
    for p in presets:
        if args.only and p["preset_id"] != args.only:
            continue
        out = voice_presets.SAMPLES_DIR / p["sample_file"]
        speed = p.get("default_speed", 1.0)
        synthesize_tts(DEMO_TEXT, str(out), voice_id=p["base_voice_id"],
                       voice_settings=p.get("voice_settings"), speed=speed,
                       model_id=p.get("model_id"))
        # 1.2 초과 속도·무음삭제 후처리(미리듣기도 실제 출력과 동일 조건)
        extra = speed / 1.2 if speed > 1.2 else 1.0
        audio_post.post_process(str(out), str(out), tempo=extra,
                                silence_trim=p.get("default_silence_trim", "off"))
        print(f"OK {p['preset_id']} -> {out}")


if __name__ == "__main__":
    main()
