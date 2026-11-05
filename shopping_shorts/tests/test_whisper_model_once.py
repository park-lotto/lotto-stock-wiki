"""11-05 박상혁 #8049: 받아쓰기 병렬 스레드가 각자 첫 모델·tqdm 잠금을 만들다 맥에서 멈춤 — 모델 만들기는 한 번(잠금)·tqdm 잠금은 스레드용."""
import sys, threading, types
from tools.calcopy.engine import check_line_sync as C


def test_model_made_once_across_threads(monkeypatch):
    made = []
    fake = types.ModuleType("faster_whisper")
    class WM:
        def __init__(self, *a, **k):
            made.append(1)
    fake.WhisperModel = WM
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    monkeypatch.setattr(C, "_WHISPER", {})
    ts = [threading.Thread(target=C.whisper_model) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(made) == 1
