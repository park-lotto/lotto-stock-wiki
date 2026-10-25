# -*- coding: utf-8 -*-
"""납품 자물쇠 자가 시험(10-25) — 봉인·관문 ○ 인 새 렌더 1편으로 통과/거절 13가지를 잰다. 잠금을 바꾸면 다시 돌린다.

    PYTHONUTF8=1 py tools/calcopy/engine/deliver_selftest.py <빈 시험 폴더> <봉인된 final.mp4> <그 편 doc 폴더>

옛 납품본 3개(봉인 없음)는 드라이브에서 읽기만 한다. 시험 복사는 시험 폴더 안 가짜 드라이브로만(진짜 드라이브에 안 올린다)."""
import sys, json, shutil, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import deliver as D, finalize as FZ
SP = Path(sys.argv[1]); ROOT = SP / "drive"; DEST = ROOT / "잇템로그 대기중"; DEST.mkdir(parents=True, exist_ok=True)
DOC = Path(sys.argv[3])
FIN = Path(sys.argv[2])
G = Path("G:/내 드라이브/칼카피영상")
def show(tag, final, dest, name, doc=None, root=ROOT):
    ok, why, _ = D.check(final, dest, name, doc, root)
    print(f"{'○ 통과' if ok else '× 거절'} | {tag} | " + (" / ".join(why) if why else ""))
show("새 렌더 ep13 (봉인+관문 ○)", FIN, DEST, "13_salmon_cream_1025_0900.mp4", DOC)
show("이름 한글", FIN, DEST, "13_연어크림_1025_0900.mp4", DOC)
show("--doc 없음(관문 기록 못 봄)", FIN, DEST, "13_salmon_cream_1025_0900.mp4", None)
show("드라이브 밖 폴더", FIN, SP, "13_salmon_cream_1025_0900.mp4", DOC)
# 옛 납품본(봉인 없음)
for p in [G/"잇템로그 대기중"/"13_salmon_cream_1024_1037.mp4", *list((G/"트롯파파 대기중").glob("*.mp4"))[:1], *list((G/"6번 잇템라인_998").glob("04*.mp4"))[:1]]:
    show(f"옛 납품본 {p.name}", p, DEST, "13_salmon_cream_1025_0900.mp4", DOC, G if False else ROOT)
# 봉인 뒤 바뀜: 복사해서 다시 쓰기(remux)
t = SP / "mod" / "final.mp4"; t.parent.mkdir(exist_ok=True); shutil.copy(FIN, t); shutil.copy(FZ.seal_path(FIN), FZ.seal_path(t))
show("봉인 그대로 복사본", t, DEST, "13_salmon_cream_1025_0900.mp4", DOC)
subprocess.run(["ffmpeg","-y","-v","error","-i",str(t),"-c","copy","-metadata","title=x",str(t.with_name("m.mp4"))]); shutil.move(t.with_name("m.mp4"), t)
show("봉인 뒤 다시 쓴 파일", t, DEST, "13_salmon_cream_1025_0900.mp4", DOC)
# 대본 바뀜: doc 복사본에서 대본 수정 + 봉인의 script 를 복사본으로
d2 = SP / "doc2"; shutil.rmtree(d2, ignore_errors=True); shutil.copytree(DOC, d2, dirs_exist_ok=True)
t2 = SP / "mod2" / "final.mp4"; t2.parent.mkdir(exist_ok=True); shutil.copy(FIN, t2)
rec = json.loads(FZ.seal_path(FIN).read_text(encoding="utf-8")); rec["script"] = str(d2 / "대본.json"); FZ.seal_path(t2).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
show("대본 그대로(복사본)", t2, DEST, "13_salmon_cream_1025_0900.mp4", d2)
s = (d2/"대본.json").read_text(encoding="utf-8").replace("딸기 버블티", "딸기 버블티  ", 1); (d2/"대본.json").write_text(s, encoding="utf-8")
show("렌더 뒤 대본 수정", t2, DEST, "13_salmon_cream_1025_0900.mp4", d2)
# 관문 × 기록
d3 = SP / "doc3"; shutil.rmtree(d3, ignore_errors=True); shutil.copytree(DOC, d3, dirs_exist_ok=True)
gp = d3 / "품질관문" / f"{rec['md5']}.json"; g = json.loads(gp.read_text(encoding="utf-8")); g["ok"] = False; g["rows"][7]["ok"] = False; gp.write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
show("관문 × 인 판", FIN, DEST, "13_salmon_cream_1025_0900.mp4", d3)
gp.unlink(); show("관문 기록 없음", FIN, DEST, "13_salmon_cream_1025_0900.mp4", d3)
# 실제 복사(가짜 드라이브 뿌리)
r = D.to_drive(FIN, DEST, "13_salmon_cream_1025_0900.mp4", DOC, drive_root=ROOT); print("복사:", r["ok"], r.get("dest"))
show("같은 이름 또 올리기", FIN, DEST, "13_salmon_cream_1025_0900.mp4", DOC)
print("※ 시험 기록 납품.json 은 doc 에 남는다 — 지워라:", DOC / "납품.json")
