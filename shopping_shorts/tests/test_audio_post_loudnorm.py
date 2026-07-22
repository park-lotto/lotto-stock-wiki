"""TTS 비트별 라우드니스 정규화(2026-07-22).

증상: 비트마다 별도 합성한 ElevenLabs 원음 크기가 제각각 → 최종 나레이션 볼륨/톤이
오르락내리락(사장님 청취 2026-07-22). 뿌리: audio_post 후처리에 loudnorm이 없어 비트
음성이 native 라우드니스 그대로 concat됨.

fix: post_process(loudnorm=True)면 EBU loudnorm을 **마지막 필터**로 얹어 모든 비트를
같은 통합 라우드니스(I=-16)로 맞춘다. 호출부(synthesize_line)는 실제 ElevenLabs 키가
있을 때만 켠다 — 키 없는 개발용 무음 mock에 loudnorm을 걸면 무음 바닥을 끌어올려
노이즈를 만든다(reference_local_tts_silent_mock_trap).
"""
from shopping_shorts import audio_post


def _capture_af(monkeypatch):
    """subprocess.run을 가로채 -af 필터 문자열을 잡고, target 파일을 만들어준다."""
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        if "-af" in cmd:
            seen["af"] = cmd[cmd.index("-af") + 1]
        # target(마지막 인자)을 실제로 만들어 os.replace가 성공하게 한다.
        open(cmd[-1], "wb").close()
        class R:  # subprocess.run 반환 흉내(check=True라 예외만 안 나면 됨)
            returncode = 0
        return R()

    monkeypatch.setattr(audio_post.subprocess, "run", fake_run)
    return seen


def test_loudnorm_added_as_last_filter(tmp_path, monkeypatch):
    seen = _capture_af(monkeypatch)
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x")
    out = tmp_path / "out.mp3"
    audio_post.post_process(str(src), str(out), tempo=1.4,
                            silence_trim="mid", loudnorm=True)
    af = seen["af"]
    assert "loudnorm" in af
    # 정규화는 속도·무음삭제 뒤에 와야 최종 출력을 기준으로 맞춘다.
    assert af.split(",")[-1].startswith("loudnorm")


def test_loudnorm_runs_even_when_no_other_filter(tmp_path, monkeypatch):
    """tempo=1.0·silence off라 원래는 in_path 그대로 반환하던 경우에도,
    loudnorm=True면 반드시 ffmpeg를 거쳐 정규화한다(모든 비트 커버)."""
    seen = _capture_af(monkeypatch)
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x")
    out = tmp_path / "out.mp3"
    res = audio_post.post_process(str(src), str(out), tempo=1.0,
                                  silence_trim="off", loudnorm=True)
    assert "cmd" in seen, "loudnorm=True인데 ffmpeg가 실행되지 않았다"
    assert "loudnorm" in seen["af"]
    assert res == str(out)


def test_loudnorm_off_keeps_passthrough(tmp_path, monkeypatch):
    """loudnorm=False(기본)이고 다른 필터도 없으면 옛 동작대로 in_path 그대로."""
    seen = _capture_af(monkeypatch)
    src = tmp_path / "in.mp3"
    src.write_bytes(b"x")
    out = tmp_path / "out.mp3"
    res = audio_post.post_process(str(src), str(out), tempo=1.0, silence_trim="off")
    assert res == str(src)
    assert "cmd" not in seen, "필터가 없는데 ffmpeg가 돌았다"
