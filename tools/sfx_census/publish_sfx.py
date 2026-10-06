# -*- coding: utf-8 -*-
"""사장님이 고른 효과음 → 라이브 효과음 서랍(관리자 0번 장면 자산 asset_type "sfx", category=storyboard.SFX_CATS, tone=맞는 짤 감정).

    py tools/sfx_census/publish_sfx.py [--dry]

- 목록(PICKS)이 정본. 긴 소리는 앞부분만 잘라(MAX) 올린다 — 짤은 1~2초다.
- 이미 올린 것(source_kind "sfx_pick" + source_ref=파일명)은 건너뛰고, 목록에서 뺀 것은 서버 행·파일도 지운다(동기화).
- 다른 경로로 들어온 효과음(category 빈 81개 등)은 건드리지 않는다.
"""
import json, os, subprocess, sys, tarfile, tempfile

SRC = os.path.join(os.path.expanduser("~"), "Desktop", "효과음 종합", "튜브렌즈가 자주 사용하는 효과음")
HOST = "ubuntu@3.35.251.172"
KEY = os.path.join(os.path.expanduser("~"), "crawling_bot_client", "LightsailDefaultKey-ap-northeast-2.pem")
REPO = "/home/ubuntu/lotto-stock-wiki"
DEST = REPO + "/shopping_shorts/data/scene_assets/sfx_pick"
MAX = 2.0
# 파일 → (분류, 맞는 짤 감정들) — 2026-10-06 사장님이 고른 13개, 분류는 이름 기준(사장님 확인)
PICKS = {
    "WOW 1.mp3": ("리액션 탄성", "감탄_박수,놀람"),
    "와우!.mp3": ("리액션 탄성", "감탄_박수,기쁨_환호,놀람"),
    "왓.mp3": ("리액션 탄성", "의심_황당,충격_입막"),
    "어이없음.mp3": ("리액션 탄성", "의심_황당,당황_멘붕"),
    "예에에.mp3": ("박수/환호", "기쁨_환호"),
    "하하하 정신나간웃는소리.mp3": ("웃음", "웃음"),
    "넷플 두둥.mp3": ("긴장", "충격_입막,공포_움찔"),
    "놉.mp3": ("실패", "거절_절레"),
    "삐.mp3": ("실패", "거절_절레,분노_짜증"),
    "효과음 히잉 [시무룩 효과음 _ 실속 효과음] #15.mp3": ("실패", "슬픔"),
    "자막 나올때 포인트 소리.mp3": ("팝/띵", "끄덕_엄지"),
    "키보드 소리.mp3": ("팝/띵", ""),
    "화면전화소리.mp3": ("휙/전환", ""),
}

SERVER = r'''
import json, os, sqlite3, sys
sys.path.insert(0, "%(repo)s")
from shopping_shorts.store import Store
DB = "%(repo)s/shopping_shorts/data/reference.db"
rows = json.load(open("/tmp/sfx_pick_rows.json", encoding="utf-8"))
want = {r["ref"]: r for r in rows}
st = Store(DB); c = sqlite3.connect(DB, timeout=20)
have = {ref: (aid, mp) for aid, ref, mp in c.execute(
    "select id, source_ref, media_path from scene_assets where customer_id=0 and asset_type='sfx' and source_kind='sfx_pick'")}
added = removed = 0
for ref, (aid, mp) in have.items():
    if ref not in want:
        c.execute("delete from scene_assets where id=?", (aid,)); removed += 1
        if mp and os.path.exists(mp): os.remove(mp)
c.commit()
for ref, r in want.items():
    if ref in have:
        c.execute("update scene_assets set category=?, tone=?, duration=? where id=?", (r["cat"], r["tone"], r["dur"], have[ref][0]))
        continue
    st.add_scene_asset({"asset_type": "sfx", "render_mode": "sfx", "media_path": "%(dest)s/" + r["file"], "duration": r["dur"],
                        "title": r["title"], "category": r["cat"], "tone": r["tone"], "source_kind": "sfx_pick",
                        "source_ref": ref, "source_origin": "효과음 종합"}, customer_id=0)
    added += 1
c.commit()
print(json.dumps({"added": added, "removed": removed, "total": len(want)}, ensure_ascii=False))
'''


def _dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(o.stdout.strip() or 0)


def main(dry):
    tmp = tempfile.mkdtemp(prefix="sfxpick_")
    rows = []
    for i, (name, (cat, tone)) in enumerate(PICKS.items()):
        src = os.path.join(SRC, name)
        if not os.path.exists(src):
            print("없음:", src); return 1
        out = "sfx_%02d.mp3" % i
        cut = ["-t", str(MAX)] if _dur(src) > MAX else []
        if cut:      # 긴 소리는 앞 2초 + 끝 0.15초 페이드(뚝 끊김 방지)
            cut += ["-af", "afade=t=out:st=%.2f:d=0.15" % (MAX - 0.15)]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src] + cut + ["-ar", "44100", "-b:a", "192k", os.path.join(tmp, out)], check=True)
        rows.append({"ref": name, "file": out, "dur": round(_dur(os.path.join(tmp, out)), 3), "cat": cat, "tone": tone,
                     "title": os.path.splitext(name)[0][:60]})
    for r in rows:
        print("%-28s %-8s %.2f초  %s" % (r["title"][:26], r["cat"], r["dur"], r["tone"]))
    if dry:
        return 0
    tarp = os.path.join(tmp, "sfx.tar")
    with tarfile.open(tarp, "w") as t:
        for r in rows:
            t.add(os.path.join(tmp, r["file"]), arcname=r["file"])
    json.dump(rows, open(os.path.join(tmp, "rows.json"), "w", encoding="utf-8"), ensure_ascii=False)
    open(os.path.join(tmp, "srv.py"), "w", encoding="utf-8").write(SERVER % {"repo": REPO, "dest": DEST})
    ssh = ["ssh", "-i", KEY, HOST]
    subprocess.run(["scp", "-q", "-i", KEY, tarp, os.path.join(tmp, "rows.json"), os.path.join(tmp, "srv.py"), HOST + ":/tmp/"], check=True)
    subprocess.run(ssh + ["mkdir -p %s && tar -xf /tmp/sfx.tar -C %s && chmod 644 %s/*.mp3 && cp /tmp/rows.json /tmp/sfx_pick_rows.json && python3 /tmp/srv.py" % (DEST, DEST, DEST)], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry" in sys.argv))
