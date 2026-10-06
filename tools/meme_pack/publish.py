"""감정짤 밈팩 → 라이브 서버 짤 팩(관리자 0번 장면 자산 clip·category "meme", 감정=tone)에 올린다.

    py tools/meme_pack/publish.py <작업폴더> [--dry]

- 무엇을 올리나: build_pack.build_manifest() 의 목록 = 지금 뷰어에서 '지우지 않은' 짤의 2초 하이라이트(library/clips).
- 어떻게: 새로 올릴 클립·표지만 tar 로 묶어 scp → 서버에서 Store.add_scene_asset(customer_id=0) 로 등록.
  이미 올린 것(source_kind "meme_pack" + source_ref=짤 id)은 건너뛰고, 뷰어에서 지운 것은 서버 행·파일도 지운다(동기화).
  다른 경로로 넣은 짤(예: 시험용 meme_test)은 건드리지 않는다.
- 노출: 서버 스위치 meme_enabled 가 짤을 누구에게 보일지 정한다(이 도구는 스위치를 바꾸지 않는다).
"""
import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_pack  # noqa: E402

HOST = "ubuntu@3.35.251.172"
KEY = os.path.join(os.path.expanduser("~"), "crawling_bot_client", "LightsailDefaultKey-ap-northeast-2.pem")
REPO = "/home/ubuntu/lotto-stock-wiki"
DEST = REPO + "/shopping_shorts/data/scene_assets/meme_pack"
KIND = "meme_pack"

# 서버에서 도는 쪽 — 등록·동기화. 입력은 /tmp/meme_pack_rows.json (지금 팩 전체 목록)
SERVER = r'''
import json, os, sqlite3, sys
sys.path.insert(0, "%(repo)s")
from shopping_shorts.store import Store
DB = "%(repo)s/shopping_shorts/data/reference.db"
rows = json.load(open("/tmp/meme_pack_rows.json", encoding="utf-8"))
want = {r["id"]: r for r in rows}
st = Store(DB)
c = sqlite3.connect(DB)
have = {ref: (aid, mp) for aid, ref, mp in c.execute(
    "select id, source_ref, media_path from scene_assets where customer_id=0 and category='meme' and source_kind=?", ("%(kind)s",))}
added = removed = retagged = 0
for ref, (aid, mp) in have.items():
    if ref not in want:
        c.execute("delete from scene_assets where id=?", (aid,)); removed += 1
        for p in (mp, mp[:-4] + ".jpg"):
            if p and os.path.exists(p): os.remove(p)
    elif c.execute("select tone from scene_assets where id=?", (aid,)).fetchone()[0] != want[ref]["emotion"]:
        c.execute("update scene_assets set tone=? where id=?", (want[ref]["emotion"], aid)); retagged += 1
c.commit()
miss = 0
for ref, r in want.items():
    if ref in have:
        continue
    mp = "%(dest)s/" + ref + ".mp4"
    if not os.path.exists(mp):
        miss += 1; continue
    st.add_scene_asset({"asset_type": "clip", "render_mode": "clip", "media_path": mp,
                        "poster_path": mp[:-4] + ".jpg" if os.path.exists(mp[:-4] + ".jpg") else "",
                        "duration": r["dur"], "title": r["title"][:120], "scene_desc": r.get("what") or "",
                        "category": "meme", "tone": r["emotion"], "source_kind": "%(kind)s", "source_ref": ref,
                        "source_origin": r.get("group") or "모름"}, customer_id=0)
    added += 1
from collections import Counter
now = c.execute("select tone from scene_assets where customer_id=0 and category='meme' and asset_type='clip'").fetchall()
print(json.dumps({"added": added, "removed": removed, "retagged": retagged, "missing_file": miss,
                  "server_total": len(now), "by_emotion": Counter(t for (t,) in now)}, ensure_ascii=False))
'''


def ssh(cmd, timeout=600):
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ssh 실패: {(r.stderr or r.stdout)[-400:]}")
    return r.stdout


def scp(src, dst, timeout=1800):
    r = subprocess.run(["scp", "-q", "-i", KEY, src, f"{HOST}:{dst}"], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"scp 실패: {r.stderr[-400:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    m = build_pack.build_manifest(work)
    import serve
    serve.WORK = work
    group = {it["id"]: it["group"] for it in serve.items()}
    rows = [{"id": c["id"], "emotion": c["emotion"], "dur": c["dur"], "title": c["title"], "what": c.get("what", ""),
             "group": group.get(c["id"], "")} for c in m["clips"]]
    on_server = set(ssh(f"mkdir -p {DEST} && ls {DEST}").split())
    new = [r for r in rows if f'{r["id"]}.mp4' not in on_server]
    print(f"팩 {len(rows)}개 · 서버에 파일 있음 {len(rows) - len(new)} · 새로 올릴 것 {len(new)}")
    if a.dry:
        return
    tmp = tempfile.mkdtemp()
    if new:
        tar = os.path.join(tmp, "meme_pack.tar")
        with tarfile.open(tar, "w") as t:
            for r in new:
                t.add(os.path.join(work, "library", "clips", f'{r["id"]}.mp4'), arcname=f'{r["id"]}.mp4')
                th = os.path.join(work, "library", "thumbs", f'{r["id"]}.jpg')
                if os.path.exists(th):
                    t.add(th, arcname=f'{r["id"]}.jpg')
        print(f"묶음 {os.path.getsize(tar) / 1e6:.0f}MB 올리는 중…", flush=True)
        scp(tar, "/tmp/meme_pack.tar")
        ssh(f"tar -xf /tmp/meme_pack.tar -C {DEST} && rm -f /tmp/meme_pack.tar")
    rows_path = os.path.join(tmp, "rows.json")
    json.dump(rows, open(rows_path, "w", encoding="utf-8"), ensure_ascii=False)
    scp(rows_path, "/tmp/meme_pack_rows.json")
    srv = os.path.join(tmp, "srv.py")
    open(srv, "w", encoding="utf-8").write(SERVER % {"repo": REPO, "dest": DEST, "kind": KIND})
    scp(srv, "/tmp/meme_pack_srv.py")
    print(ssh("python3 /tmp/meme_pack_srv.py; rm -f /tmp/meme_pack_srv.py /tmp/meme_pack_rows.json").strip())


if __name__ == "__main__":
    main()
