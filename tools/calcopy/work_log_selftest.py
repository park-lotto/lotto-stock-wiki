# -*- coding: utf-8 -*-
"""작업 기록지 자가 시험(관제 263/265) — 기록지·납품 고리·이미 만든 편 검사를 바꾸면 다시 돌린다. 진짜 기록지·드라이브는 안 건드린다.

  PYTHONUTF8=1 py tools/calcopy/work_log_selftest.py <빈 시험 폴더>

① append/find/중복 안 씀/멈춘 편은 이유 필수  ② 가짜 드라이브로 deliver.to_drive → 기록지 1줄(md5·길이 = 봉인)
③ done_list 가 기록지(엔진·회원)로 잡고, 멈춘 편은 '이미 만듦'이 아니다  ④ 사보타주: deliver.py 의 기록 줄을 빼면 ②가 실패해야 한다
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SP = Path(sys.argv[1]).resolve(); SP.mkdir(parents=True, exist_ok=True)
os.environ["SHORTEM_HOME"] = str(SP / "member_home")
from tools.calcopy import work_log as WL, done_list as DL  # noqa: E402
from tools.calcopy.engine import deliver as D, finalize as FZ  # noqa: E402

WL.LOG = SP / "작업기록.jsonl"
for f in (WL.LOG, WL.member_log()):
    f.unlink(missing_ok=True)
bad = []


def ok(cond, what):
    print(("○ " if cond else "× ") + what)
    if not cond:
        bad.append(what)


# ① append / find
r = WL.append({"person": "박세리", "product": "선크림", "our_channel": "kitchit", "final_md5": "a" * 32, "drive_path": "G:/x/01_a.mp4"})
ok(r["status"] == "delivered" and r["made_by"] == "owner" and r["date"].endswith("+09:00"), "append 기본값(delivered·owner·KST)")
WL.append({"person": "박세리", "product": "선크림", "our_channel": "kitchit", "final_md5": "a" * 32, "drive_path": "G:/x/01_a.mp4"})
ok(len(WL.read(WL.LOG)) == 1, "같은 md5·드라이브 경로는 두 번 안 쓴다")
ok(len(WL.find("박세리", "선크림")) == 1 and not WL.find("박세리", "로션"), "find(인물, 제품)")
try:
    WL.append({"status": "stopped", "person": "이영자"}); ok(False, "멈춘 편 이유 없으면 거절")
except ValueError:
    ok(True, "멈춘 편 이유 없으면 거절")
try:
    WL.append({"colour": 1}); ok(False, "모르는 칸 거절")
except ValueError:
    ok(True, "모르는 칸 거절")
WL.append({"status": "stopped", "person": "이영자", "product": "실내화", "note": "원본 못 찾음"})
WL.member_log().parent.mkdir(parents=True, exist_ok=True)
WL.member_log().write_text(json.dumps({"date": "2026-10-25T10:00:00+09:00", "person": "한고은", "product": "채소통", "made_by": "member:abc",
                                       "status": "delivered", "final_path": "C:/Users/m/Desktop/숏템작업/완성본/x.mp4"}, ensure_ascii=False) + "\n", encoding="utf-8")

# ③ done_list
DL.WORK = SP / "no_work"; DL.DRIVE = SP / "no_drive"; DL.ROOT = SP      # 기록지만 보게
ok(any("기록지" in s for _, s in DL.made("박세리", "선크림")), "done_list: 엔진 기록지로 이미 만든 편 잡음")
ok(any("기록지" in s for _, s in DL.made("한고은", "채소통")), "done_list: 회원 기록지(~/.shortem)도 잡음")
ok(not DL.made("이영자", "실내화") and DL.stopped("이영자", "실내화") == [(DL.stopped("이영자")[0][0], "원본 못 찾음")],
   "done_list: 멈춘 편은 '이미 만듦' 아님 + 이유 보여 줌")
rc = subprocess.run([sys.executable, "-c", "import os,sys;from pathlib import Path;from tools.calcopy import work_log as W, done_list as L;"
                     "W.LOG=Path(os.environ['WL_T_LOG']);L.WORK=L.DRIVE=L.ROOT=Path(os.environ['WL_T_SP']);"
                     "raise SystemExit(L.main(sys.argv[1:]))", "이영자", "실내화"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                    env={**os.environ, "PYTHONUTF8": "1", "WL_T_LOG": str(WL.LOG), "WL_T_SP": str(SP)})
ok(rc.returncode == 0 and "멈춘 편(원본 못 찾음)" in rc.stdout, f"done_list CLI: 멈춘 편 출력·rc=0 ({(rc.stdout + rc.stderr).strip()[:200]})")


# ② 가짜 드라이브로 납품
def fake_final(name):
    d = SP / name; d.mkdir(exist_ok=True)
    f = d / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:r=30:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(f)], check=True, stdin=subprocess.DEVNULL)
    FZ.seal(f, "test", log=lambda *_: None)
    return f


drive = SP / "drive"; dest = drive / "키치잇 대기중"; dest.mkdir(parents=True, exist_ok=True)
for p in dest.glob("*.mp4"):
    p.unlink()
fin = fake_final("ep1")
seal = json.loads(FZ.seal_path(fin).read_text(encoding="utf-8"))
before = len(WL.read(WL.LOG))
res = D.to_drive(fin, dest, "01_fake_test.mp4", None, log=lambda *_: None, drive_root=drive)
rows = WL.read(WL.LOG)
ok(res["ok"] and len(rows) == before + 1, f"납품 성공 → 기록지 1줄 (ok={res['ok']} {before}→{len(rows)})")
last = rows[-1]
ok(last["final_md5"] == seal["md5"] and last["drive_path"] == str(dest / "01_fake_test.mp4") and last["our_channel"] == "키치잇 대기중"
   and last["duration"] is not None and abs(last["duration"] - 2.0) < 0.1, f"기록 칸 = 봉인 md5·길이·드라이브 폴더 ({last['duration']})")
res2 = D.to_drive(fin, dest, "01_fake_test.mp4", None, log=lambda *_: None, drive_root=drive)
ok(not res2["ok"] and len(WL.read(WL.LOG)) == before + 1, "납품 거절이면 기록 안 씀")

# ④ 사보타주 — deliver.py 에서 기록 줄을 뺀 판으로 같은 납품 → 줄이 안 생겨야 이 시험이 그 줄을 재는 것이다
src = Path(D.__file__).read_text(encoding="utf-8")
cut = "\n".join(ln for ln in src.splitlines() if "from_delivery" not in ln)
ok(cut != src, "사보타주 판 만들기(기록 줄 제거)")
sp = SP / "deliver_sabotage.py"; sp.write_text(cut, encoding="utf-8")
spec = importlib.util.spec_from_file_location("deliver_sabotage", sp); DS = importlib.util.module_from_spec(spec); spec.loader.exec_module(DS)
fin2 = fake_final("ep2")
n0 = len(WL.read(WL.LOG))
r3 = DS.to_drive(fin2, dest, "02_fake_test.mp4", None, log=lambda *_: None, drive_root=drive)
ok(r3["ok"] and len(WL.read(WL.LOG)) == n0, "사보타주: 기록 줄 없으면 납품은 되고 기록은 안 생긴다(= ②가 그 줄을 잰다)")

print(f"\n{'전부 통과' if not bad else f'실패 {len(bad)}건'}")
sys.exit(1 if bad else 0)
