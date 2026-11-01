"""회원 목소리 합성 — provider 분기 주인(관제 266). preset_make(프리셋 만드는 기술, 회원 묶음 금지)에서 떼어 냈다:
회원 PC 의 render_bench(narr_align)·runner_ops 가 부르는데 preset_make 는 설치 묶음에 못 들어가기 때문(engine_bundle hand_deps 가 잡음, 10-26).
preset_make 는 여기 것을 그대로 다시 내보낸다(옛 import 호환)."""
from __future__ import annotations

from pathlib import Path


def _member_key(name: str) -> str:
    """회원 키 자리 — 환경변수 → ~/.shortem/keys/<name>(vmake_clean.MEMBER_KEY_FILE 과 같은 방식). 값은 출력하지 않는다."""
    import os
    v = os.environ.get({"elevenlabs": "ELEVENLABS_API_KEY", "fish": "FISH_API_KEY", "typecast": "TYPECAST_API_KEY"}[name], "").strip()
    if v:
        return v
    p = Path.home() / ".shortem" / "keys" / name
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def make_synth(provider: str, voice: str, tempo, emotion):
    """provider 분기 → synth(text, out_path). 타입캐스트 = 기존 providers.typecast_synth 그대로(+감정) · 일레븐 = narr_align.eleven_direct
    (회원 키 직접, 추천 프리셋·검색 성우) · 피쉬 = fish_tts 요청 꼴(build_payload·headers)을 회원 키로. 일레븐·피쉬는 1.0 으로 받고 narration() atempo 가 맞춘다."""
    if provider == "typecast":
        import os
        from shopping_shorts.channelkit import providers
        kf = Path.home() / ".shortem" / "keys" / "typecast"     # 회원 키가 있으면 그것(없으면 기존 자리 ~/.volcano/keys/typecast 그대로)
        base = providers.typecast_synth(voice, tempo=tempo, key_file=str(kf) if kf.is_file() and not os.environ.get("TYPECAST_API_KEY") else None)
        return (lambda text, out: base(text, out, emotion=emotion)) if emotion else base
    if provider == "elevenlabs":
        key = _member_key("elevenlabs")
        if not key:
            raise RuntimeError("일레븐랩스 키가 없습니다 — ~/.shortem/keys/elevenlabs 에 회원 키를 넣어 주세요")
        from tools.calcopy.engine import narr_align as NA
        return lambda text, out: NA.eleven_direct(text, voice, Path(out), key)
    if provider == "fish":
        key = _member_key("fish")
        if not key:
            raise RuntimeError("피쉬 키가 없습니다 — ~/.shortem/keys/fish 에 회원 키를 넣어 주세요")
        from tools.calcopy.engine import voices as VO
        ref = (VO.preset_row(voice) or {}).get("base_voice_id") or voice      # 'fs-…' 추천 프리셋 → reference_id

        def fish(text, out):
            import requests
            from shopping_shorts import fish_tts as FT
            r = requests.post(FT._ENDPOINT, headers=FT.headers(key, FT.DEFAULT_MODEL_ID), json=FT.build_payload(text, ref), timeout=120)
            FT.raise_with_body(r)
            if not r.content:
                raise RuntimeError("피쉬 응답에 음성이 없습니다")
            Path(out).write_bytes(r.content)
        return fish
    raise ValueError(f"모르는 목소리 엔진: {provider}")
