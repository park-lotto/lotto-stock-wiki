"""#4239(11-04 윤상길): 일본어판 대본이 렌더 전 관문 ② gate_sent(줄별 받아쓰기 대조)에서 'TTS 빠뜨림'으로 멈춤 — 대조에 언어 갈래가 없다.
회원 PC 수정이 업데이트로 덮여 재발. 일본어 대조를 만들 때까지 script_lang=='ja' 면 건너뛰고 경보(임시 — 뿌리 수리 아님)."""
from tools.calcopy.engine import narr_verify as NV


def test_일본어_대본은_건너뛰고_경보(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(NV, "verify", lambda *a, **k: called.append(1) or {"sure": [{"line": "L1", "type": "TTS 빠뜨림"}], "maybe": []})
    logs = []
    S = {"lines": [{"id": "L1", "kind": "tts", "tts": "これはすごいですね"}]}
    assert NV.gate_sent(S, [{"id": "L1", "wav": "x.wav"}], tmp_path, log=logs.append) == []
    assert not called and any("일본어" in x for x in logs)


def test_한국어_대본은_그대로_대조(tmp_path, monkeypatch):
    monkeypatch.setattr(NV, "verify", lambda *a, **k: {"sure": [{"line": "L1", "type": "TTS 빠뜨림"}], "maybe": []})
    S = {"lines": [{"id": "L1", "kind": "tts", "tts": "이거 정말 좋아요"}]}
    assert NV.gate_sent(S, [{"id": "L1", "wav": "x.wav"}], tmp_path, log=lambda *_: None)
