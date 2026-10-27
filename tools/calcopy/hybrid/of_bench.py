"""원본 찾기 한 단계만 따로 재기(사장님 10-27 "원본 찾기만 계속 해 봐 될 때까지").

    py tools/calcopy/hybrid/of_bench.py <편 flow 폴더(…/home/창고/flow/<sid>)> [--slot 1|2] [--out <폴더>]

그 편의 소재 영상(bench/bench.mp4)·검색어(지시서 상태 read.queries_en)로 c_origin_foreign(mode lens)을 새 작업 폴더에서 그대로 돌리고
구간별 시간([구간] 줄)·후보 수·전체 시간을 찍는다. 기억(_of_memo)은 새 폴더라 비어 있다(실전 첫 바퀴와 같은 조건)."""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import tempfile
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def state_of(flow_dir: Path) -> dict:
    f = json.loads((flow_dir / "flow.json").read_text(encoding="utf-8"))
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(f["payload"].split(".")[2].encode())).decode("utf-8"))


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("flow")
    ap.add_argument("--slot", type=int, default=1)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    fd = Path(a.flow)
    st = state_of(fd)
    slots = st.get("slots") or []
    # 원본 찾기를 마친 편은 이긴 소재가 맨 위(st.read·job/bench)로 옮겨져 있다 — 그때는 맨 위 상태를 쓴다(10-27: 칸 1 검색어 + 이긴 소재 영상을 섞어 잼)
    s = st if st.get("origins") and st.get("read") else ((slots[a.slot - 1].get("st") or {}) if slots and len(slots) >= a.slot else st)
    if s is st:
        a.slot = 1
    read = s.get("read") or st.get("read") or {}
    bench = s.get("bench") or st.get("bench") or {}
    qs = [q for q in read.get("queries_en") or [] if q][:4]
    sub = "" if a.slot == 1 else f"alt{a.slot - 1}"
    src = fd / "job" / sub / "bench" / "bench.mp4" if sub else fd / "job" / "bench" / "bench.mp4"
    if not src.exists():
        print("소재 영상 없음:", src)
        return 1
    W = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="of_bench_"))
    (W / "bench").mkdir(parents=True, exist_ok=True)
    shutil.copy(src, W / "bench" / "bench.mp4")
    print(f"소재 {bench.get('id')} · 검색어 {qs} · 작업 {W}")
    from tools.calcopy.hybrid import runner_ops as R
    t0 = time.time()
    r = R.c_origin_foreign(W, {"mode": "lens", "bench_id": bench.get("id"), "queries": qs})
    print(f"전체 {time.time() - t0:.0f}초 · 후보 {len(r.get('cands') or [])} · 시트 {len(r.get('sheets') or [])} · 오류 {r.get('error')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
