# -*- coding: utf-8 -*-
"""editor_vs_final_video 를 **자기 결과 폴더**로 돌리는 얇은 실행기(2026-09-27).

왜: 도구는 결과를 늘 /tmp/evf 에 쓴다(report.txt 를 'w'로 연다). 병합 관문(track.py finish)·매일 점검·
사람의 조사 실행이 같은 날 겹치면 서로의 report 를 덮어쓴다. 도구 파일은 건드리지 않고
모듈 전역 OUT 만 바꿔 끼운다(check·main 둘 다 전역 OUT 을 읽는다).

서버(저장소 폴더에서, env 적재 뒤):
    EVF_OUT=/tmp/gate_x/out [PATCH_DIR=/tmp/gate_x] python3 /tmp/gate_x/_tool/evf_run.py 6
    EVF_OUT=... python3 tools/evf_run.py <job_id> <job_id> ...
끝에 'EVF_DONE rc=0' 한 줄을 report 옆 done.txt 에 남긴다 — 폴링하는 쪽이 '끝났다'와 '죽었다'를 가른다.
"""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, ".")                      # 도구와 같다 — 저장소 폴더에서 돈다


def main():
    out = Path(os.environ.get("EVF_OUT") or "/tmp/evf")
    out.mkdir(parents=True, exist_ok=True)
    # 장면 전환 캐시(seg_snap)는 결과 폴더 아래 — 도구는 읽기 전용(소재 옆 = 고객 폴더에 쓰지 않는다). 부르는 쪽이 주면 그걸 쓴다
    os.environ.setdefault("SEG_SNAP_CACHE_DIR", str(out / "snapcache"))
    done = out / "done.txt"
    if done.exists():
        done.unlink()
    rc = 1
    try:
        import editor_vs_final_video as evf       # PATCH_DIR 얹기는 import 때 일어난다
        evf.OUT = out
        sys.argv = ["editor_vs_final_video.py"] + sys.argv[1:]
        evf.main()
        rc = 0
    except BaseException:                         # noqa: BLE001 — 죽은 이유를 판정 쪽이 볼 수 있게 남긴다
        (out / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
    done.write_text("EVF_DONE rc=%d\n" % rc, encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
