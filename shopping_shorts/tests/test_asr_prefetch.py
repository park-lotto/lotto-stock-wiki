"""검수단축 ⑥(10-26): 렌더 전 ② 받아쓰기 9작업을 동시에(상한 ASR_PAR) 미리 받아 캐시 — 판정은 뒤 순차 heard_words 가 캐시를 읽어 그대로.
실측(재현 job 9작업, 진짜 스피치매틱스): 순차 53.8초 → 19.0초, verify 결과 같음."""
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import narr_verify as NV  # noqa: E402


def test_prefetch_runs_uncached_files_together(tmp_path, monkeypatch):
    monkeypatch.setattr(NV, "CACHE", tmp_path / "c")
    fs = []
    for i in range(5):
        p = tmp_path / f"{i}.wav"
        p.write_bytes(bytes([i]) * 10)
        fs.append(p)
    fs.append(fs[0])                                   # 같은 파일 두 번 = 한 번만
    live, peak, calls = [0], [0], []
    lock = threading.Lock()

    def fake(p, lang="ko"):
        with lock:
            live[0] += 1; peak[0] = max(peak[0], live[0]); calls.append(Path(p).name)
        time.sleep(0.2)
        with lock:
            live[0] -= 1
        if Path(p).name == "3.wav":
            raise RuntimeError("x")
        return []
    monkeypatch.setattr(NV, "heard_words", fake)
    errs = NV.prefetch(fs)
    assert sorted(calls) == [f"{i}.wav" for i in range(5)] and peak[0] > 1
    assert list(errs.values()) == ["RuntimeError"]
