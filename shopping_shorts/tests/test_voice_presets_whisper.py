"""whisper 프리셋 — 베스트 5명만, 나머지는 없다(사장님 청취 판정 2026-07-16)."""
from shopping_shorts.voice_presets import load_presets_file, SAMPLES_DIR

BEST = {"kr-yooni", "kr-mina", "kr-chloecha", "kr-hanabad", "kr-kanna"}
REJECTED = {"kr-hanna", "kr-juha", "kr-jiana"}      # [whispers] 안 먹힘


def _by_variant(v):
    return [p for p in load_presets_file() if p["variant"] == v]


def test_whisper_presets_are_exactly_the_best_five():
    assert {p["group_id"] for p in _by_variant("whisper")} == BEST


def test_rejected_voices_have_no_whisper():
    """탈락 3명에게 whisper가 생기면 안 된다 — 억지로 붙이면 품질이 떨어진다(설계 §8)."""
    assert not (REJECTED & {p["group_id"] for p in _by_variant("whisper")})


def test_best_flag_matches_best_five():
    """best 플래그는 성우 단위 — 그 성우의 모든 variant가 같은 값이어야 한다.

    어긋나면 API가 첫 행에서 집는 값이 어느 variant가 먼저 오느냐에 따라 달라진다.
    """
    for p in load_presets_file():
        assert p.get("best", False) is (p["group_id"] in BEST), p["preset_id"]


def test_non_best_voices_keep_three_tones():
    """나머지 9명은 감추는 게 아니라 그대로 둔다 — 3톤이 살아있는가."""
    groups = {}
    for p in load_presets_file():
        groups.setdefault(p["group_id"], set()).add(p["variant"])
    for gid, variants in groups.items():
        assert {"stable", "natural", "expressive"} <= variants, gid
        if gid not in BEST:
            assert "whisper" not in variants, gid


def test_whisper_presets_carry_full_role_profile():
    """whisper 프리셋 = roles가 전체 role = ASMR 영상(설계 §3 표)."""
    for p in _by_variant("whisper"):
        roles = p["naturalize_profile"]["whisper"]["roles"]
        assert set(roles) == {"훅", "페인포인트", "반전", "실용", "CTA"}, p["preset_id"]


def test_whisper_samples_exist_and_are_real_audio():
    """무음 mock이 아닌 실합성본인가 — 크기가 제각각이면 실합성이다.

    `synthesize_tts`는 키가 없으면 조용히 무음 mp3를 쓴다. 프로브를 짤 때 이 함정에
    실제로 걸렸다(가드가 없었으면 "속삭임이 한국어에 안 먹힌다"는 틀린 결론을 낼 뻔했다).
    """
    sizes = []
    for p in _by_variant("whisper"):
        f = SAMPLES_DIR / p["sample_file"]
        assert f.exists(), f
        assert f.stat().st_size > 10_000, f
        sizes.append(f.stat().st_size)
    assert len(set(sizes)) > 1, "전부 같은 크기 = 무음 mock 의심"


def test_eleven_preset_total_is_47():
    """일레븐랩스 큐레이션은 47건(42 + whisper 5)이다.

    ★종전엔 파일 전체를 47로 잠갔는데, 그건 "엔진이 하나뿐"이라는 전제였다.
    2026-08-19에 타입캐스트 성우 6명(x3톤=18건)이 붙으면서 그 수가 깨졌다 — 잠글 대상은
    '파일 전체'가 아니라 '일레븐랩스 큐레이션 47건'이다. 다른 엔진을 더해도 이 판정은
    그대로 유효하고, 일레븐랩스 쪽이 실수로 늘거나 줄면 여전히 잡힌다."""
    from shopping_shorts import typecast_tts
    eleven = [p for p in load_presets_file()
              if not typecast_tts.is_typecast(p.get("model_id"))]
    assert len(eleven) == 47      # 42 + 5
