# -*- coding: utf-8 -*-
"""박힌 자막 지우기(VMake) — 해외원본형 원본의 덧씌운 글자를 지우고 원본은 `<이름>_orig.mp4` 로 보존 (관제 263 지시서 08 · 표준 §3-3 C2).

옛 자리: 세션 scratchpad `vmake.py`·`vfetch.sh`(10-22~24 잇템로그 v3 13편 — 쓰는 구간만 잘라 서버 VMake Pro → 원본 소리 붙임).
두 길(둘 다 돈이 든다 — VMake Pro 초당 4크레딧):
  · 우리 PC(사장님 키)  = `server_clean` — 파일을 서버로 보내 서버의 키(mix_pipeline._vmake_keys → keyroute)로 Pro. 40분 제한에 걸려 5400초(10-23 rc=124).
  · 회원 PC(회원 키)    = `member_clean` — 회원 VMake 키('app_key:secret', 환경변수 VMAKE_API_KEY)로 이 PC 에서 바로(vmake_client.remove_subtitles).
    회원 키·크레딧이 없으면 **부르지 않고** 흐림(재료.blur — rules.text_blur_all)으로 대체한다 — 판단 = runner_ops.c_clean_text(과금 경로 동의 규칙).
  · SHORTEM_NO_PAID=1 이면 어느 길도 부르지 않는다(시험·개발 완주의 '돈 0' 스위치).
지운 결과: `<이름>.mp4` = 지운 영상 + 원본 소리(같은 이름이라 대본·재료의 src 가 그대로) · `<이름>_orig.mp4` = 원본 · 장부 `<폴더>/vmake_log.json`(호출마다 한 줄).

    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py server <a.mp4> [b.mp4 …]     # 우리 PC — 서버 Pro(돈 듦). 한 번에 여러 개면 순서대로
    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py fetch <폴더> <이름 …>          # 서버에 끝난 *_clean 만 받아 끼우기(40분 제한으로 끊겼을 때)
    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py log <폴더>                     # 장부 보기
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SERVER_TIMEOUT = 5400      # 서버 한 번 호출 상한(초) — 40분 제한(rc=124)에 걸려 올림(10-23)
REMOTE_DIR = "/tmp/calcopy_vmake"
LEDGER = "vmake_log.json"


def paid_off() -> bool:
    return os.environ.get("SHORTEM_NO_PAID") == "1"


def member_key() -> str:
    """회원 VMake 키 자리 한 곳 — 환경변수 VMAKE_API_KEY('app_key:secret'). 회원 PC 설정 화면 → 실행기 환경(숏템MCP 09 가 넘긴다)."""
    return (os.environ.get("VMAKE_API_KEY") or "").strip()


def log_entry(folder: Path, entry: dict) -> None:
    """장부 = <폴더>/vmake_log.json [{at, file, mode, ok, sec, calls, why}] — 호출 0 인 대체(흐림)도 한 줄 남긴다(돈 든 호출 수를 셀 수 있게)."""
    p = Path(folder) / LEDGER
    rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    rows.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), **entry})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def swap_in(orig: Path, cleaned_video: Path) -> Path:
    """지운 영상(소리 없음일 수 있다) + 원본 소리 → <이름>.mp4, 원본은 <이름>_orig.mp4 로. 이미 _orig 가 있으면 원본을 덮지 않는다."""
    orig = Path(orig)
    keep = orig.with_name(orig.stem + "_orig" + orig.suffix)
    src_audio = keep if keep.exists() else orig
    tmp = orig.with_name(orig.stem + "_c" + orig.suffix)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cleaned_video), "-i", str(src_audio), "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-shortest", str(tmp)],
                   check=True, stdin=subprocess.DEVNULL)
    if not keep.exists():
        orig.replace(keep)
    tmp.replace(orig)
    try:
        if Path(cleaned_video).resolve() != orig.resolve():
            Path(cleaned_video).unlink()
    except OSError:
        pass
    return orig


def member_clean(files: list, api_key: str, log=print, tier: str = "pro") -> dict:
    """회원 PC — 회원 키로 이 PC 에서 바로. 반환 {cleaned:[이름], calls:n, fail:{이름: 이유}}. 돈이 든다(호출부가 키·동의를 확인한 뒤에만)."""
    if paid_off():
        raise PermissionError("SHORTEM_NO_PAID=1 — VMake 호출 막음")
    from shopping_shorts import vmake_client as VC
    out = {"cleaned": [], "calls": 0, "fail": {}}
    for f in files:
        f = Path(f)
        t0 = time.time()
        tmp = f.with_name(f.stem + "_vclean" + f.suffix)
        out["calls"] += 1
        try:
            VC.remove_subtitles(str(f), api_key, str(tmp), tier=tier, resume_key=f"calcopy:{f.name}:{f.stat().st_size}")
            swap_in(f, tmp)
            out["cleaned"].append(f.name)
            log_entry(f.parent, {"file": f.name, "mode": "member", "ok": True, "sec": round(time.time() - t0, 1), "calls": 1})
        except Exception as e:  # noqa: BLE001 — 실패는 이유를 남기고 다음 파일(그 파일은 흐림으로)
            out["fail"][f.name] = f"{type(e).__name__}: {str(e)[:200]}"
            log_entry(f.parent, {"file": f.name, "mode": "member", "ok": False, "sec": round(time.time() - t0, 1), "calls": 1, "why": out["fail"][f.name]})
            log(f"[vmake] {f.name} 실패: {out['fail'][f.name]}")
    return out


def server_clean(files: list, log=print, timeout: int = SERVER_TIMEOUT) -> dict:
    """우리 PC — 서버의 사장님 키로 Pro(scratchpad vmake.py 이식). 한 번에 여러 개 보내면 40분 제한에 걸리니 파일마다 따로 부른다."""
    if paid_off():
        raise PermissionError("SHORTEM_NO_PAID=1 — VMake 호출 막음")
    from tools.calcopy.hybrid import server_ai
    code = r'''
import json, sys
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.vmake_client import TIER_PRO
a=json.loads(sys.stdin.read()); keys=mp._vmake_keys(Store(DB_PATH),0); out={}
for n in a['names']:
    try: mp._vmake_clean(f'/tmp/calcopy_vmake/{n}.mp4', keys, f'/tmp/calcopy_vmake/{n}_clean.mp4', tier=TIER_PRO); out[n]='ok'
    except Exception as e: out[n]=repr(e)[:300]
print('@@JSON@@'+json.dumps(out))
'''
    out = {"cleaned": [], "calls": 0, "fail": {}}
    subprocess.run(["ssh", "-i", server_ai.KEY, server_ai.HOST, f"mkdir -p {REMOTE_DIR}"], check=True, stdin=subprocess.DEVNULL)
    for f in files:
        f = Path(f)
        n = f.stem
        t0 = time.time()
        subprocess.run(["scp", "-q", "-i", server_ai.KEY, str(f), f"{server_ai.HOST}:{REMOTE_DIR}/{n}.mp4"], check=True, stdin=subprocess.DEVNULL)
        out["calls"] += 1
        try:
            res = server_ai._ssh_py(code, {"names": [n]}, timeout=timeout)
        except Exception as e:  # noqa: BLE001 — 시간 초과면 서버에서는 끝났을 수 있다 → fetch 로 받는다
            res = {n: f"{type(e).__name__}: {str(e)[:200]}"}
        if res.get(n) == "ok":
            fetch(f.parent, [n], log)
            out["cleaned"].append(f.name)
            log_entry(f.parent, {"file": f.name, "mode": "server", "ok": True, "sec": round(time.time() - t0, 1), "calls": 1})
        else:
            out["fail"][f.name] = str(res.get(n))[:300]
            log_entry(f.parent, {"file": f.name, "mode": "server", "ok": False, "sec": round(time.time() - t0, 1), "calls": 1, "why": out["fail"][f.name]})
            log(f"[vmake] {f.name} 실패: {out['fail'][f.name]} — 서버에서 끝났으면 `vmake_clean.py fetch {f.parent} {n}`")
    return out


def fetch(folder: Path, names: list, log=print) -> list:
    """서버에 끝난 <이름>_clean.mp4 를 받아 원본 소리를 붙여 끼운다(scratchpad vfetch.sh 이식). 받은 이름 목록."""
    from tools.calcopy.hybrid import server_ai
    got = []
    for n in names:
        local = Path(folder) / f"{n}_v.mp4"
        r = subprocess.run(["scp", "-q", "-i", server_ai.KEY, f"{server_ai.HOST}:{REMOTE_DIR}/{n}_clean.mp4", str(local)], stdin=subprocess.DEVNULL)
        if r.returncode != 0 or not local.exists():
            log(f"[vmake] {n}: 서버에 끝난 파일 없음")
            continue
        swap_in(Path(folder) / f"{n}.mp4", local)
        got.append(n)
        log(f"[vmake] {n} 끼움(원본 = {n}_orig.mp4)")
    return got


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(__doc__); return 2
    cmd = a.pop(0)
    if cmd == "server":
        print(json.dumps(server_clean(a), ensure_ascii=False))
        return 0
    if cmd == "fetch":
        print(fetch(Path(a[0]), a[1:]))
        return 0
    if cmd == "log":
        p = Path(a[0]) / LEDGER
        print(p.read_text(encoding="utf-8") if p.exists() else "[]")
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
