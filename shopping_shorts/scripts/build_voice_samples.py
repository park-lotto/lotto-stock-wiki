"""각 큐레이션 프리셋으로 공통 데모 문장을 읽어 assets/voice_samples/<sample_file>를 생성.

ElevenLabs 실호출(크레딧 소모)이라 큐레이션/튜닝 시 수동 1회 실행.
  python -m shopping_shorts.scripts.build_voice_samples
--only <preset_id> 로 특정 프리셋만 재생성 가능."""
import argparse

from shopping_shorts import voice_presets
from shopping_shorts.mix_pipeline import synthesize_line

# ★손으로 박은 감정태그를 뺐다(2026-07-17). 옛 문장은 "[warmly] …, [amused] …"였는데,
# 엔진이 감정태그를 자동으로 넣게 된 뒤로는 그 둘이 비트당 태그 상한(caps.max_tags_per_beat=2)을
# 먼저 먹어버려 **whisper 프리셋의 샘플이 안 속삭였다**(실측: `[curious] 음, [warmly] …`로
# 나오고 [whispers]가 밀려남 → 탭 이름이 거짓말이 된다). 태그는 이제 naturalize가 넣는다.
DEMO_TEXT = "시어머니가 알려주신 이 세제로 욕실을 청소했더니 구석구석 반짝반짝, 찌든 때가 싹 없어졌더라고요."


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
        # ★synthesize_line을 쓴다 — 여기서 tts.synthesize_tts를 직접 부르면 파이프라인을
        # 따로 조립하는 꼴이라 샘플이 실제 출력과 갈린다(2026-07-15 whole-branch 리뷰가
        # 잡은 seam 10건이 정확히 그 패턴이었다: "작업대에서 들은 소리 ≠ 영상 소리").
        # 직접 호출은 실제로 두 가지를 빠뜨렸다(2026-07-17 실측):
        #   ① naturalize 미적용 → whisper 프리셋의 샘플이 **안 속삭였다**(탭 이름이 거짓말)
        #   ② speed·후처리를 호출부가 각자 계산 → 엔진이 바뀌면 조용히 어긋난다
        # synthesize_line은 naturalize→TTS→후처리를 렌더와 같은 순서·같은 인자로 한다.
        natural = synthesize_line(
            DEMO_TEXT, out,
            voice={"voice_id": p["base_voice_id"], "settings": p.get("voice_settings"),
                   "speed": p.get("default_speed", 1.0),
                   "silence_trim": p.get("default_silence_trim", "off"),
                   "naturalize_profile": p.get("naturalize_profile"),
                   "model_id": p.get("model_id")},
            beat_role="훅", beat_index=0, beat_total=5)
        print(f"OK {p['preset_id']} -> {out}  |  {natural[:48]}")


if __name__ == "__main__":
    main()
