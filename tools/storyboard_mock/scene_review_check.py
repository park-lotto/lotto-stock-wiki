"""장면 점검(관제 257) 실물 확인 — 진짜 작업의 2단계 보드·재료로 이 폴더의 storyboard.scene_review 를 **서버 환경(관리자 = 사장님 버텍스)**에서 돌린다.

    py tools/storyboard_mock/scene_review_check.py <work_id> [--rows 1,3] [--alter 2:문장] [--msg 요청] [--model gemini-3.1-pro-preview] [--json out.json]

--alter N:문장 : N번 줄(1부터) 문장을 일부러 바꿔서 판정시킨다(교체·장면 없음 판정이 나오는지 보려고). 작업은 바꾸지 않는다(읽기만).
확인하는 것(사장님 "왜 최선인지 이유를 설명"):
  ① 점검한 줄마다 판정이 하나씩 온다(빠지면 error 로 보인다)
  ② 이유(why)에 적힌 조각 번호가 전부 실제 재료에 있다 — 없는 번호를 지어내면 실패
  ③ 교체 제안 조각이 목록에 있고, 다른 줄이 쓰는 조각이 아니다
  ④ 줄마다 지금 장면·제안 장면의 실제 화면 설명을 나란히 찍는다 — 이유가 설명과 맞는지 사람이 대조한다
서버의 서비스·저장소 파일은 건드리지 않는다(/tmp/sb_rev_chk 에 올려 그 프로세스에서만 갈아끼운다).
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SSH = ["ssh", "-i", os.path.join(os.path.expanduser("~"), "crawling_bot_client", "LightsailDefaultKey-ap-northeast-2.pem"),
       "ubuntu@3.35.251.172"]
_RUNNER = r"""
import importlib.util, json, sys, types
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
import shopping_shorts
def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path); mod = importlib.util.module_from_spec(sp)
    sys.modules[name] = mod; sp.loader.exec_module(mod); return mod
shopping_shorts.script_generate = _load("shopping_shorts.script_generate", "/tmp/sb_rev_chk/script_generate.py")
sb = _load("shopping_shorts.storyboard", "/tmp/sb_rev_chk/storyboard.py"); shopping_shorts.storyboard = sb
from shopping_shorts import app, keyctx
from shopping_shorts.store import Store
a = json.loads(sys.stdin.read())
keyctx.set_owner(0)                                   # 관리자가 부른 것처럼 — 라이브 미들웨어와 같다(사장님 버텍스)
req = types.SimpleNamespace(state=types.SimpleNamespace(customer_id=0))
work = Store(app.DB_PATH).get_produce_work(a["wid"], customer_id=0) or {}
S = (work.get("state") or {}).get("sb") or {}
ek = S.get("view") or next(iter(S.get("made") or {}), "")
bd = (S.get("made") or {}).get(ek) or {}
slots = []
for i, sl in enumerate(bd.get("slots") or []):
    k = "%s#%d" % (ek, i)
    line = ((S.get("edit") or {}).get(ek) or {}).get(str(i), sl.get("line") or "")
    slots.append({"slot": sl.get("slot"), "line": line, "ids": (S.get("ord") or {}).get(k) or sl.get("ids") or []})
if a.get("slots"):                                    # 화면이 보낸 지금 보드(화면 확인 도구 serve) — 저장본 대신
    slots = a["slots"]
for n, t in a.get("alter") or []:
    slots[n]["line"] = t
key, ex, jid = app._sb_job(req, "w:" + a["wid"])
keep = {c for x in slots for c in x["ids"]}
mats = sb._materials(None, key, ex or {}, keep=keep, with_seed=S.get("use_seed") is True)
out = {"ek": ek, "slots": slots, "texts": mats[1], "secs": mats[0]}
try:
    out["res"] = sb.scene_review(slots, a.get("rows"), mats, a.get("msg") or "", "", a.get("model") or "gemini-3.6-flash")
except ValueError as e:
    out["error"] = str(e)
print("@@" + json.dumps(out, ensure_ascii=False))
"""


def run(wid, rows=None, alter=(), msg="", model=""):
    upload()
    cmd = ("cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && "
           "python3 /tmp/sb_rev_chk/run.py 2>/tmp/sb_rev_chk/err.log")
    t0 = time.time()
    p = subprocess.run(SSH + [cmd], input=json.dumps({"wid": wid, "rows": rows, "alter": list(alter), "msg": msg, "model": model}).encode(),
                       capture_output=True)
    txt = p.stdout.decode("utf-8", "replace")
    if "@@" not in txt:
        err = subprocess.run(SSH + ["tail -20 /tmp/sb_rev_chk/err.log"], capture_output=True).stdout.decode("utf-8", "replace")
        raise SystemExit("서버 실행 실패\n" + txt[-1500:] + "\n" + err)
    d = json.loads(txt.split("@@", 1)[1])
    d["secs_taken"] = round(time.time() - t0, 1)
    return d


def upload():
    subprocess.run(SSH + ["mkdir -p /tmp/sb_rev_chk"], check=True)
    subprocess.run(["scp", "-q", "-i", SSH[2], str(ROOT / "shopping_shorts" / "storyboard.py"),
                    str(ROOT / "shopping_shorts" / "script_generate.py"), "ubuntu@3.35.251.172:/tmp/sb_rev_chk/"], check=True)
    subprocess.run(SSH + ["cat > /tmp/sb_rev_chk/run.py"], input=_RUNNER.encode(), check=True)


def serve(wid, body):
    """화면 확인 도구용 — 화면이 /scene_review 로 보낸 body 를 서버에서 이 폴더 scene_review 로 판정 → (상태, 응답 바이트). upload() 먼저."""
    b = json.loads(body or "{}")
    cmd = ("cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && "
           "python3 /tmp/sb_rev_chk/run.py 2>/tmp/sb_rev_chk/err.log")
    p = subprocess.run(SSH + [cmd], input=json.dumps({"wid": wid, "slots": b.get("slots"), "rows": b.get("rows"), "msg": b.get("message") or "",
                                                      "model": b.get("model") or ""}).encode(), capture_output=True, timeout=300)
    txt = p.stdout.decode("utf-8", "replace")
    if "@@" not in txt:
        return 422, json.dumps({"ok": False, "error": "서버 실행 실패"}, ensure_ascii=False).encode()
    d = json.loads(txt.split("@@", 1)[1])
    if d.get("error"):
        return 422, json.dumps({"ok": False, "error": d["error"]}, ensure_ascii=False).encode()
    return 200, json.dumps({"ok": True, **d["res"]}, ensure_ascii=False).encode()


def check(d):
    """→ (통과 여부, 줄 단위 보고 문자열). 판정 내용(유지냐 교체냐)은 사람이 설명과 대조한다 — 여기선 계약만 잰다."""
    if d.get("error"):
        return False, "판정 실패: " + d["error"]
    texts, slots, res = d["texts"], d["slots"], d["res"]
    ok, out = True, ["모델 %s(%s) · %s초" % (res.get("model"), res.get("auth"), d["secs_taken"]), "요약: " + (res.get("reply") or "")]
    # AI 는 번호 앞 공통머리(grab_youtube_)를 빼고 적기도 한다 — 짧은 꼴도 같은 조각으로 친다
    short = {re.sub(r"^grab_[a-z]+_", "", k): k for k in texts}
    ids_re = re.compile("|".join(sorted(map(re.escape, list(texts) + list(short)), key=len, reverse=True)) or "$^")
    used = {}
    for i, s in enumerate(slots):
        for c in s["ids"]:
            used.setdefault(c, set()).add(i)
    for v in res["reviews"]:
        i = v["i"]
        cited = {short.get(c, c) for c in ids_re.findall(v.get("why") or "")}
        fake = {c for c in re.findall(r"[0-9a-f]{12}-\d+", v.get("why") or "") if c not in short}   # 조각 번호 꼴인데 재료에 없는 것
        bad = [c for c in v.get("ids") or [] if c not in texts or (used.get(c, set()) - {i})]
        if v["verdict"] == "error" or fake or bad:
            ok = False
        out.append("\n%d번 [%s] %s  (문장 %s초 / 장면 %s초%s)" % (i + 1, v["verdict"], slots[i]["line"], v["need"], v["have"], " ⚠짧음" if v["short"] else ""))
        out.append("   이유: " + v["why"])
        for c in v["cur_ids"]:
            out.append("   지금 %s: %s" % (c, texts.get(c, "(재료에 없음)")[:110]))
        for c in v.get("ids") or []:
            out.append("   제안 %s: %s" % (c, texts.get(c, "(재료에 없음)")[:110]))
        if v.get("line"):
            out.append("   문장 제안: " + v["line"])
        out.append("   이유에 적힌 조각 %s%s%s" % (sorted(cited) or "-", ("  ❌없는 번호 %s" % sorted(fake)) if fake else "",
                                         ("  ❌못 쓰는 제안 %s" % bad) if bad else ""))
    return ok, "\n".join(out)


def main(argv):
    wid = argv[0]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    rows = [int(x) - 1 for x in opt("--rows").split(",")] if opt("--rows") else None
    alter = []
    for a in [argv[i + 1] for i, x in enumerate(argv) if x == "--alter"]:
        n, t = a.split(":", 1)
        alter.append((int(n) - 1, t))
    d = run(wid, rows, alter, opt("--msg") or "", opt("--model") or "")
    ok, rep = check(d)
    print(rep)
    if opt("--json"):
        pathlib.Path(opt("--json")).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n결과:", "통과" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
