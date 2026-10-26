"""검수단축 ⑤(10-26): 계획이 같은 입력으로 시간표 관문을 전부 통과했으면 렌더는 다시 안 잰다 — 입력 지문 = render_bench.gate_stamp.
지문이 바뀌어야 하는 것(원본을 VMake 로 지움·컷 ss·썸네일)이 바뀌면 다시 잰다. 실측 재현 job: 건너뜀/전부 렌더 완성본 md5 같음."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402


def test_stamp_changes_with_inputs(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x" * 10)
    T = {"cuts": [{"src": "a.mp4", "ss": 1.0, "t0": 0.0, "t1": 1.0}], "end": 1.0}
    M = {"cand_dir": str(tmp_path), "blur": {}}
    st = {"name": "t"}
    a = RB.gate_stamp(T, M, st, tmp_path)
    assert a == RB.gate_stamp(json.loads(json.dumps(T)), M, st, tmp_path)
    assert a != RB.gate_stamp({**T, "cuts": [{**T["cuts"][0], "ss": 1.1}]}, M, st, tmp_path)
    (tmp_path / "썸네일.json").write_text("{}", encoding="utf-8")
    b = RB.gate_stamp(T, M, st, tmp_path)
    assert b != a
    t = time.time() + 5
    os.utime(tmp_path / "a.mp4", (t, t))                 # 원본을 다시 씀(VMake 로 지움) = 다시 잰다
    assert RB.gate_stamp(T, M, st, tmp_path) != b
