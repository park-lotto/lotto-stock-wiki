"""작업 대기열 모의 실행 — 실제 7일 기록(들어온 시각·처리 시간)을 옛/새 배분 규칙으로 다시 돌려 고객 대기를 비교한다(관제 246).

    py tools/queue_sim.py <jq_rows.json>      (서버에서 job_queue 를 읽기 전용으로 내보낸 파일)

근사: store.claim_next 의 규칙을 그대로 옮겼다 — 우선순위·id 순 / 고객당 동시 1개(관리자 2, 가벼운 작업 3)
/ 인스타 독점 작업(prewarm·durfill)은 인스타 표식이면 하나씩 / 새 규칙: 놀 때(가동 < 6) 같은 고객 다른 job_id 2개.
"""
import heapq, json, sys, statistics

LIGHT = ("durfill", "prewarm")
EXCL = ("durfill", "prewarm")
CUST = ("render", "mix", "preview", "clean")


def simulate(rows, workers=12, burst=False, idle_below=6, burst_jobs=2):
    pending = []                     # 아직 안 들어온 작업(들어온 시각 순)
    for r in rows:
        jid, task, owner, prio, job_id, ig, t_in, dur = r
        pending.append(dict(id=jid, task=task, owner=owner, prio=prio, job=job_id, ig=bool(ig), t=t_in, dur=max(1.0, dur or 1.0)))
    pending.sort(key=lambda x: x["t"])
    queue, running, done = [], [], []
    now, i = pending[0]["t"], 0

    def can(q):
        run = [x for _, _, x in running]
        if q["task"] in EXCL and q["ig"] and any(x["task"] in EXCL and x["ig"] for x in run):
            return False
        if q["owner"] is None:
            return True
        mine = [x for x in run if x["owner"] == q["owner"] and ((x["task"] in LIGHT) == (q["task"] in LIGHT))]
        if q["owner"] == "0":
            lim = 2
        elif q["task"] in LIGHT:
            lim = 3
        elif (burst and q["job"] is not None and len(run) < idle_below
              and not any(x["owner"] == q["owner"] and (x["job"] is None or x["job"] == q["job"]) for x in run)):
            lim = burst_jobs
        else:
            lim = 1
        return len(mine) < lim

    while i < len(pending) or queue or running:
        while i < len(pending) and pending[i]["t"] <= now:
            queue.append(pending[i]); i += 1
        queue.sort(key=lambda x: (x["prio"], x["id"]))
        started = True
        while started and len(running) < workers:
            started = False
            for q in queue:
                if can(q):
                    queue.remove(q); q["start"] = now
                    heapq.heappush(running, (now + q["dur"], q["id"], q)); started = True
                    break
        nxt = [running[0][0]] if running else []
        if i < len(pending):
            nxt.append(pending[i]["t"])
        if not nxt:
            break
        now = min(nxt)
        while running and running[0][0] <= now:
            _, _, q = heapq.heappop(running); done.append(q)
    return done


def report(done, label):
    cw = [q["start"] - q["t"] for q in done if q["task"] in CUST]
    over = sum(1 for w in cw if w > 60)
    print(f"{label}: 고객 제작작업 {len(cw)}건 · 평균 대기 {statistics.mean(cw):.0f}초 · 최대 {max(cw):.0f}초 · 60초 넘게 기다린 것 {over}건")


if __name__ == "__main__":
    rows = json.load(open(sys.argv[1], encoding="utf-8"))
    report(simulate(rows, burst=False), "옛 규칙")
    report(simulate(rows, burst=True), "새 규칙")
