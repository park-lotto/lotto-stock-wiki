# -*- coding: utf-8 -*-
"""buffer_post 시간 칸·중복 시험(2026-10-26 사장님 "매일 3시·8시 한 번씩, 한 번에 두 개는 없다 / 중복 업로드 절대 금지").
실제 업로드·예약은 전부 가짜 — 아무것도 안 올라간다. 영상 파일도 임시로 만든다.
    py tools/buffer_slot_check.py
기대: ① 칸 계산이 15:00·20:00 만, 지난 칸·찬 칸은 건너뜀  ② 한 영상 = 유튜브·틱톡 같은 칸 1번씩
     ③ 서로 다른 영상이 같은 칸에 안 들어감  ④ 다시 돌리면 업로드 0(중복 금지) ⑤ 이름 바꾼 같은 영상도 막음."""
import os, sys, tempfile, shutil, datetime as dt, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bp", os.path.join(here, "buffer_post.py"))
bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
KST = bp.KST
fails = []


def check(name, got, want):
    print(("OK  " if got == want else "FAIL"), name, got if got != want else "")
    if got != want:
        fails.append(name)


def z(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=KST).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:00.000Z")


F = "21(수창) 쓸데수집"
now = dt.datetime(2026, 10, 27, 10, 0, tzinfo=KST)
check("오전, 영상 2 → 그날 15·20시", bp._slot_dues([], F, 2, now), [z(2026, 10, 27, 15), z(2026, 10, 27, 20)])
check("오후 4시, 영상 1 → 그날 20시(15시 건너뜀)", bp._slot_dues([], F, 1, now.replace(hour=16)), [z(2026, 10, 27, 20)])
check("오후 4시, 영상 2 → 20시, 다음날 15시", bp._slot_dues([], F, 2, now.replace(hour=16)),
      [z(2026, 10, 27, 20), z(2026, 10, 28, 15)])
taken = [{"folder": F, "due": z(2026, 10, 27, 15)}]
check("15시 이미 참 → 20시", bp._slot_dues(taken, F, 1, now), [z(2026, 10, 27, 20)])
check("다른 계정 칸은 상관없음", bp._slot_dues([{"folder": "999 얜샷템", "due": z(2026, 10, 27, 15)}], F, 1, now),
      [z(2026, 10, 27, 15)])
check("지운 예약(deleted) 칸은 빈 칸", bp._slot_dues([dict(taken[0], final_status="deleted")], F, 1, now),
      [z(2026, 10, 27, 15)])

# ── 끝까지: 가짜 Buffer 로 post 두 번 ──
tmp = tempfile.mkdtemp(); d = os.path.join(tmp, F); os.makedirs(d)
for nm, body in (("a.mp4", b"A" * 1000), ("b.mp4", b"B" * 1000), ("a_renamed.mp4", b"A" * 1000)):
    open(os.path.join(d, nm), "wb").write(body)
    open(os.path.join(d, nm[:-4] + ".txt"), "w", encoding="utf-8").write("제목\n\n설명")
rows, calls = [], []
bp.DRIVE = tmp
bp._load = lambda p, default: rows if p == bp.LEDGER else {F: "k"}
bp._save_ledger = lambda r: None
bp._probe = lambda p: (20.0, 1080, 1920)
bp._upload = lambda p: ("r", "http://x")
bp._remove_remote = lambda r: None
bp.cmd_cleanup = lambda a=None: None
bp.buffer_api.channels = lambda k: [{"id": "yt", "service": "youtube", "name": "Y"},
                                    {"id": "tt", "service": "tiktok", "name": "T"},
                                    {"id": "ig", "service": "instagram", "name": "I"}]
bp.buffer_api.schedule_video = lambda key, cid, cap, url, due_at=None, **k: (
    calls.append((cid, due_at)) or {"id": f"p{len(calls)}", "dueAt": due_at})
bp.main(["post", "--folder", F])
by_file = {}
for r in rows:
    by_file.setdefault(r["file"], set()).add((r["service"], r["due"]))
check("올라간 영상 = a·b 2개(이름만 바꾼 같은 영상은 막힘)", sorted(by_file), ["a.mp4", "b.mp4"])
check("한 영상당 유튜브·틱톡 1번씩, 인스타 없음", sorted(len(v) for v in by_file.values()), [2, 2])
check("한 영상의 두 서비스는 같은 칸", [len({due for _s, due in v}) for v in by_file.values()], [1, 1])
dues = [next(iter(v))[1] for v in by_file.values()]
check("서로 다른 영상은 다른 칸", len(set(dues)), 2)
check("칸은 15:00·20:00 KST 뿐",
      all(dt.datetime.strptime(x[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc).astimezone(KST).strftime("%H:%M")
          in ("15:00", "20:00") for x in dues), True)
n1 = len(calls)
for nm in ("a.mp4", "b.mp4"):                       # 예약 폴더로 간 것을 사장님이 실수로 다시 넣었다
    shutil.copy2(os.path.join(d, bp.RESERVED, nm), os.path.join(d, nm))
    shutil.copy2(os.path.join(d, bp.RESERVED, nm[:-4] + ".txt"), os.path.join(d, nm[:-4] + ".txt"))
bp.main(["post", "--folder", F])
check("다시 돌리면 업로드 0(중복 절대 금지)", len(calls) - n1, 0)
shutil.rmtree(tmp)
print("결과:", "통과" if not fails else f"실패 {len(fails)}건 {fails}")
sys.exit(1 if fails else 0)
