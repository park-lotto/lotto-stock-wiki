# 같은 장면 반복 점검 — 완성본에 실제로 나가는 컷 순서를 렌더 정본 함수로 뽑아 반복을 센다.
# (2026-09-18 사장님: 케이크 영상 "장면 같은걸로 튀고 바로 뒤에 반복")
#
# 사용(서버):  python3 check_repeats.py <job_id> [<job_id> ...]
#
# 잡는 것:
#   되돌아옴  앞에서 이미 보여준 구간을 다시 보여줌(겹침) → ★불합격. 케이크 job 616ee19b6187에서 사장님이 본 반복
#   같은영상연속(참고)  바로 앞 컷과 같은 영상 + 3초 이내로 이어짐. 손동작·각도가 바뀌면 다른 그림이라
#             불합격이 아니다(행주 4쌍 프레임 실측 전부 다른 그림, 09-18). 가만히 있는 장면이면 반복으로 보일 수 있어 표시만
#   0초컷     0.3초 미만 컷(깜빡임)
#   몰림      한 영상이 화면 시간의 50% 넘게 차지
# 판정: 되돌아옴이 0이면 PASS
import sys, glob, os, subprocess
sys.path.insert(0, "/tmp/ab")
from shopping_shorts.store import Store
from shopping_shorts.video_assemble import plan_beat_clips_for

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
WORK = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
NEAR = 3.0      # 이 안쪽으로 이어지면 같은 장면으로 본다
TINY = 0.3


def dur(p):
    try:
        return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                     "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip())
    except Exception:
        return 0.0


def src_durs(jid):
    out = {}
    for d in glob.glob(os.path.join(WORK, jid, "s*")):
        mp4s = [f for f in glob.glob(os.path.join(d, "*.mp4"))]
        if mp4s:
            out[os.path.basename(d)] = max(dur(f) for f in mp4s)
    return out


def check(st, jid):
    job = st.get_mix_job(jid)
    beats = (job.get("edit_plan") or {}).get("beats") or []
    sd = src_durs(jid)
    seq = []
    for b in beats:
        t = dur(b["tts_path"]) if b.get("tts_path") and os.path.exists(b["tts_path"]) else float(b.get("target_seconds") or 0)
        for c in plan_beat_clips_for(b, t, sd):
            seq.append((b["beat_idx"], c["video_id"], float(c["start"]), float(c["start"]) + float(c["src_dur"]), float(c["out_dur"])))
    near, back, tiny, lines = 0, 0, 0, []
    for i, (bi, v, s, e, o) in enumerate(seq):
        tag = ""
        if i and seq[i - 1][1] == v and -0.05 <= s - seq[i - 1][3] <= NEAR:
            near += 1; tag += " 같은영상연속"
        if any(pv == v and s < pe - 0.05 and e > ps + 0.05 for (_, pv, ps, pe, _) in seq[:i]):
            back += 1; tag += " 되돌아옴"
        if o < TINY:
            tiny += 1; tag += " 0초컷"
        lines.append("   줄%d %-3s %6.1f~%-6.1f %.1fs%s" % (bi, v, s, e, o, tag))
    tot = sum(x[4] for x in seq) or 1
    share = {}
    for x in seq:
        share[x[1]] = share.get(x[1], 0) + x[4]
    top = max(share, key=share.get) if share else "-"
    heavy = share.get(top, 0) / tot > 0.5
    ok = back == 0
    print("== %s 컷%d | 되돌아옴 %d · 같은영상연속 %d · 0초컷 %d · 최다 %s %.0f%%%s → %s" % (
        jid, len(seq), back, near, tiny, top, 100 * share.get(top, 0) / tot, " 몰림" if heavy else "", "PASS" if ok else "FAIL"))
    if "-v" in sys.argv:
        print("\n".join(lines))
    return ok


if __name__ == "__main__":
    st = Store(DB)
    jobs = [a for a in sys.argv[1:] if not a.startswith("-")]
    res = [check(st, j) for j in jobs]
    print("REPEAT_PASS" if all(res) else "REPEAT_FAIL")
