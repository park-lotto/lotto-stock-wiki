"""관측판 — 서버가 얼마나 버티는지 매일 숫자로 남긴다(2026-08-22).

## 왜

1기 100명을 받기 전에 용량을 계산했지만, 계산은 계산이다. **실제 동시 렌더가
몇 개까지 가는지, 디스크가 하루 몇 GB 늘는지, 송신이 6TB 한도에 얼마나 닿는지는
재봐야 안다.** 그 숫자가 없으면 "16코어로 올릴까"를 감으로 정하게 된다.

실측 근거(2026-08-22, 4코어 서버에서 20초 인코딩 동시 실행):

    동시 1개 →  16.2초
    동시 3개 →  55.7초  (3.4배)
    동시 6개 → 158.6초  (9.8배)   ← 코어를 서로 뺏는 손해가 이만큼 크다

즉 **동시 렌더 최대치**가 증설 판단의 핵심 지표다. 나머지(디스크·송신)는
돈이 새는 곳이라 같이 본다.

## 어떻게

5분마다 한 줄씩 표본을 남긴다(`capacity_samples`). 표본은 가볍다 —
지금 도는 렌더 수, 대기 수, 부하, 디스크, 네트워크 누적, 워커 수.
그걸 날짜별로 접어서 **하루의 최대치**를 본다. 평균은 위험을 숨긴다.

⚠️ 표본을 남기는 일이 서버를 무겁게 하면 안 된다 — 파일 하나 읽고 DB 한 줄 쓰는
   수준으로만 만든다(디스크 전체 스캔 같은 건 하지 않는다).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn):
    """표본 테이블. 이미 있으면 아무 일도 안 한다."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS capacity_samples (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            at           TEXT NOT NULL,      -- UTC
            running      INTEGER,            -- 지금 돌고 있는 작업 수(=동시 렌더)
            queued       INTEGER,            -- 줄 서 있는 작업 수
            workers      INTEGER,            -- 살아있는 워커 수(=동시 상한)
            load1        REAL,               -- 1분 부하
            cores        INTEGER,
            disk_used_gb REAL,
            disk_free_gb REAL,
            net_tx_gb    REAL,               -- 부팅 후 누적 송신(요금이 붙는 쪽)
            net_rx_gb    REAL
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_capacity_at ON capacity_samples(at)")
    # ★웹 체감 지표 두 칸(2026-09-18) — 이미 있는 표에는 ALTER로 붙인다(없으면 무시).
    for col in ("web_latency_ms REAL", "web_main_cpu REAL"):
        try:
            conn.execute(f"ALTER TABLE capacity_samples ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass


def _web_latency_ms(url="http://127.0.0.1:8849/", n=3, timeout=5.0):
    """웹 첫 페이지를 n번 불러 **가장 느린** 응답(ms). 서버 안에서 재므로 망 지연이 없다 —
    정상 10~40ms, 이벤트 루프가 막히면 수백 ms(2026-09-18 실측: 막힘 460ms → 수리 후 20ms)."""
    import urllib.request
    worst = None
    for _ in range(n):
        t = time.time()
        try:
            urllib.request.urlopen(url, timeout=timeout).read(64)
        except Exception:      # noqa: BLE001 — 응답 자체가 없으면 timeout 값으로 친다
            ms = timeout * 1000
        else:
            ms = (time.time() - t) * 1000
        worst = ms if worst is None else max(worst, ms)
    return round(worst, 1) if worst is not None else None


def _web_main_cpu(match="uvicorn shopping_shorts.app", interval=1.0):
    """웹 프로세스 **메인 스레드**의 CPU %(리눅스 /proc). 비동기 서버는 이 스레드 하나가
    모든 요청을 나르므로 이 값이 90%대면 고객 전원이 느려진다(2026-09-18: 요청마다 DB 스키마
    초기화 116개가 여기서 돌아 99.9%였다). 못 재면 None(리눅스 아님·프로세스 없음)."""
    try:
        pid = None
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                with open(f"/proc/{d}/cmdline", "rb") as f:
                    if match.encode() in f.read().replace(b"\0", b" "):
                        pid = int(d)
                        break
            except OSError:
                continue
        if pid is None:
            return None

        def ticks():
            with open(f"/proc/{pid}/task/{pid}/stat") as f:
                parts = f.read().rsplit(")", 1)[1].split()
            return int(parts[11]) + int(parts[12])       # utime + stime
        a = ticks()
        time.sleep(interval)
        b = ticks()
        hz = os.sysconf("SC_CLK_TCK")
        return round((b - a) / hz / interval * 100, 1)
    except Exception:      # noqa: BLE001
        return None


def server_verdict(data):
    """방금 찍은 표본 한 줄로 **지금** 서버가 아픈지 판정한다 — 용량 verdict(7일 최대치, 화면용)와
    달리 이건 즉시 경보용이다(2026-09-18 사장님 "누가 말해줘야 작동이 되면 안 되잖아").
    실사고: 디스크 100%(09-16)와 메인 스레드 99.9%(09-18)를 고객이 말해줘서 알았다."""
    lat, cpu, free = data.get("web_latency_ms"), data.get("web_main_cpu"), data.get("disk_free_gb")
    if free is not None and free < 30:
        return ("danger", f"디스크 여유 {free:.0f}GB — 지금 차고 있습니다. 큰 폴더(du -xh --max-depth=1 /tmp)부터 보세요.")
    if lat is not None and lat > 1000:
        return ("danger", f"웹 첫 페이지 응답 {lat:.0f}ms(정상 40ms 이하) — 이벤트 루프 막힘 의심. "
                          f"메인 스레드 CPU {cpu if cpu is not None else '?'}%. py-spy dump로 확인.")
    if cpu is not None and cpu > 85:
        return ("danger", f"웹 메인 스레드 CPU {cpu:.0f}% — 요청이 줄을 섭니다(응답 {lat}ms). "
                          f"py-spy dump --pid <uvicorn> 로 무엇을 하는지 보세요.")
    if (free is not None and free < 60) or (lat is not None and lat > 400):
        return ("warn", f"디스크 여유 {free}GB / 응답 {lat}ms / 메인 CPU {cpu}%")
    return ("ok", "")


def _net_bytes():
    """부팅 후 누적 (수신, 송신) 바이트. lo·docker는 뺀다(진짜 밖으로 나간 것만)."""
    rx = tx = 0
    try:
        with open("/proc/net/dev", encoding="utf-8") as f:
            for line in f.readlines()[2:]:
                name, _, rest = line.partition(":")
                name = name.strip()
                if name in ("lo",) or name.startswith(("docker", "veth", "br-")):
                    continue
                cols = rest.split()
                rx += int(cols[0])
                tx += int(cols[8])
    except (OSError, ValueError, IndexError):
        pass
    return rx, tx


def sample(db_path):
    """표본 한 줄을 남기고 그 내용을 dict로 돌려준다."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT "
            "  SUM(CASE WHEN state='running' THEN 1 ELSE 0 END), "
            "  SUM(CASE WHEN state='queued'  THEN 1 ELSE 0 END), "
            "  COUNT(DISTINCT CASE WHEN state='running' THEN owner END) "
            "FROM job_queue").fetchone()
        # ★워커 수를 systemd에 묻지 않는다 — 5분마다 systemctl을 부르고 싶지 않고
        #   권한도 필요하다. 알고 싶은 건 '상한'이 아니라 **실제 동시 처리량**이므로
        #   큐를 물고 있던 서로 다른 owner 수로 센다.
        running, queued, owners = (row[0] or 0), (row[1] or 0), (row[2] or 0)

        try:
            # ★윈도우에는 getloadavg 자체가 없다(AttributeError). 서버는 리눅스라
            #   실제로는 안 나지만, 개발 PC에서 테스트가 죽으면 아무도 안 돌린다.
            load1 = os.getloadavg()[0]
        except (OSError, AttributeError):
            load1 = None
        cores = os.cpu_count() or 0
        du = shutil.disk_usage("/")
        rx, tx = _net_bytes()
        gb = 1024 ** 3

        data = {
            "at": _utcnow(), "running": running, "queued": queued,
            "workers": owners,                     # 실제로 일하던 워커 수
            "load1": load1, "cores": cores,
            "disk_used_gb": round(du.used / gb, 2),
            "disk_free_gb": round(du.free / gb, 2),
            "net_tx_gb": round(tx / gb, 3), "net_rx_gb": round(rx / gb, 3),
            # 웹 체감(2026-09-18) — 둘 다 1~2초면 끝난다(요청 3번 + /proc 두 번 읽기)
            "web_latency_ms": _web_latency_ms(), "web_main_cpu": _web_main_cpu(),
        }
        conn.execute(
            "INSERT INTO capacity_samples (at,running,queued,workers,load1,cores,"
            " disk_used_gb,disk_free_gb,net_tx_gb,net_rx_gb,web_latency_ms,web_main_cpu) "
            "VALUES (:at,:running,:queued,:workers,:load1,:cores,"
            " :disk_used_gb,:disk_free_gb,:net_tx_gb,:net_rx_gb,:web_latency_ms,:web_main_cpu)", data)
        conn.commit()
        return data
    finally:
        conn.close()


def daily(db_path, days=14):
    """날짜별 요약 — **최대치**로 본다. 평균은 위험한 순간을 숨긴다.

    ★송신량은 누적 카운터라 (최댓값 − 최솟값)으로 계산하면 안 된다(2026-08-24 수정).
      `/proc/net/dev`는 **재부팅하면 0으로 돌아간다.** 그날 안에 재부팅이 한 번만
      있어도 최솟값이 재부팅 후 값이 돼 그날 송신이 통째로 부풀거나 사라진다.
      실제로 서버 증설(옛 서버 58GB → 새 서버 0.2GB)에서 하루 67GB라는 없는
      숫자가 표에 찍혔다 — 이 숫자로 요금을 판단하면 그대로 오판이다.

      그래서 **연속한 표본 사이의 증가분만 더한다.** 값이 줄어든 구간(=재부팅·교체)은
      건너뛴다. 재부팅 직전까지의 양은 살고, 카운터가 되감긴 만큼만 잃는다.
    """
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        ensure_schema(conn)
        rows = conn.execute(
            "SELECT substr(at,1,10) d, "
            "       MAX(running), MAX(queued), MAX(workers), MAX(load1), "
            "       MIN(disk_free_gb), MAX(disk_used_gb), COUNT(*) "
            "  FROM capacity_samples "
            " WHERE at >= date('now', ?) "
            " GROUP BY d ORDER BY d DESC", (f"-{int(days)} days",)).fetchall()
        tx = _daily_tx(conn, days)
        return [{"date": r[0], "max_running": r[1], "max_queued": r[2],
                 "max_workers": r[3], "max_load1": r[4],
                 "min_disk_free_gb": r[5], "max_disk_used_gb": r[6],
                 "tx_gb": round(tx.get(r[0], 0.0), 2), "samples": r[7]} for r in rows]
    finally:
        conn.close()


def _daily_tx(conn, days):
    """날짜 → 그날 송신량(GB). 누적 카운터의 **증가분만** 더한다.

    카운터가 줄어든 구간은 재부팅이므로 그 구간은 0으로 친다 — 되감긴 양은
    알 방법이 없다. 없는 숫자를 지어내는 것보다 조금 적게 세는 게 낫다.
    """
    out = {}
    prev = None
    for at, v in conn.execute(
            "SELECT at, net_tx_gb FROM capacity_samples "
            " WHERE at >= date('now', ?) AND net_tx_gb IS NOT NULL "
            " ORDER BY at ASC", (f"-{int(days)} days",)):
        day = at[:10]
        out.setdefault(day, 0.0)
        if prev is not None and v >= prev:
            out[day] += v - prev
        prev = v
    return out


def waiting(db_path, limit=40):
    """지금 줄에 서 있는 작업을 **사람 단위로** 보여준다(2026-08-27).

    왜: "대기 8개"라는 숫자만으론 아무 판단도 못 한다. 한 사람이 8개를 몰아넣은
    것과 8명이 한 개씩 기다리는 것은 전혀 다른 상황이고, 처방(워커 증설 vs
    1인 동시 제한)도 반대다. **누가 · 몇 개 · 얼마나 기다렸는지**를 봐야 한다.

    ★대기시간은 `created_at`(줄 선 시각) 기준이다. `claimed_at`이 있으면 이미
      일을 물었으니 그때까지가 대기, 아니면 지금까지가 대기다.
    """
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        tabs = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "job_queue" not in tabs:
            return {"rows": [], "by_customer": []}

        # 고객 이름은 mix_jobs를 거쳐야 나온다(job_queue엔 없다). 없으면 빈칸으로 둔다 —
        # 이름을 못 찾는다고 줄 서 있는 사실 자체를 숨기면 안 된다.
        has_mix = "mix_jobs" in tabs and "customers" in tabs
        # ★있는 컬럼만 고른다. job_queue는 자리마다 컬럼이 조금씩 다르고(테스트용
        #   축약본도 있다), 없는 컬럼 하나 때문에 대기 목록이 통째로 안 나오면
        #   정작 밀렸을 때 못 본다.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(job_queue)")}

        def col(name, default="NULL"):
            return f"q.{name}" if name in cols else default
        sel = ("SELECT q.id, " + col("task", "''") + ", q.state, "
               + col("created_at") + ", " + col("claimed_at") + ", "
               + col("prio", "0") + ", " + col("args_json", "''") + ", "
               + ("COALESCE(NULLIF(c.name,''), NULLIF(c.email,''), c.username, ''), "
                  "m.customer_id "
                  if has_mix else "'', NULL ")
               + "  FROM job_queue q "
               + ("  LEFT JOIN mix_jobs m "
                  "    ON m.job_id = json_extract(q.args_json, '$.job_id') "
                  "  LEFT JOIN customers c ON c.id = m.customer_id "
                  if has_mix and "args_json" in cols else "")
               + " WHERE q.state IN ('queued','running') "
               " ORDER BY CASE q.state WHEN 'running' THEN 0 ELSE 1 END, "
               "          q.prio DESC, q.created_at ASC LIMIT ?")
        try:
            raw = conn.execute(sel, (int(limit),)).fetchall()
        except sqlite3.OperationalError:
            # json_extract이 없는 빌드 — 이름 없이라도 줄은 보여준다.
            raw = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], "", None)
                   for r in conn.execute(
                       "SELECT id, " + col("task", "''").replace("q.", "") + ", state, "
                       + col("created_at").replace("q.", "") + ", "
                       + col("claimed_at").replace("q.", "") + ", "
                       + col("prio", "0").replace("q.", "") + ", "
                       + col("args_json", "''").replace("q.", "") +
                       "  FROM job_queue WHERE state IN ('queued','running') "
                       " ORDER BY id ASC LIMIT ?", (int(limit),))]

        now = datetime.now(timezone.utc)
        rows = []
        for jid, task, state, created, claimed, prio, _args, cname, cid in raw:
            waited = None
            if created:
                try:
                    t0 = datetime.strptime(created, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc)
                    end = now
                    if claimed:
                        end = datetime.strptime(claimed, "%Y-%m-%d %H:%M:%S").replace(
                            tzinfo=timezone.utc)
                    waited = max(0, int((end - t0).total_seconds()))
                except ValueError:
                    pass
            # ★cid 0 = 관리자(사장님) 계정. customers 테이블에 행이 없어 이름이 안 나온다.
            #   "(모름)"으로 두면 남의 고객이 밀린 줄 알고 엉뚱한 처방을 한다.
            if not cname and cid == 0:
                cname = "관리자(사장님)"
            rows.append({"id": jid, "task": task, "state": state,
                         "created_at": created, "prio": prio,
                         "customer": cname or "", "customer_id": cid,
                         "waited_sec": waited})

        # 사람 단위 요약 — 한 명이 몰아넣었는지 여러 명이 한 개씩인지가 여기서 갈린다.
        agg = {}
        for r in rows:
            key = r["customer_id"] if r["customer_id"] is not None else "-"
            a = agg.setdefault(key, {"customer": r["customer"] or "(모름)",
                                     "customer_id": r["customer_id"],
                                     "queued": 0, "running": 0, "max_wait_sec": 0})
            a["queued" if r["state"] == "queued" else "running"] += 1
            if r["waited_sec"]:
                a["max_wait_sec"] = max(a["max_wait_sec"], r["waited_sec"])
        by_customer = sorted(agg.values(),
                             key=lambda a: (-(a["queued"] + a["running"]),
                                            -a["max_wait_sec"]))
        return {"rows": rows, "by_customer": by_customer}
    finally:
        conn.close()


def verdict(db_path, cores=None, now_queued=None):
    """지금 서버를 늘려야 하나 — 숫자로 답한다. 화면 맨 위에 한 줄로 띄운다.

    판단 기준(2026-08-22 실측에서 나온 것)
      · 동시 렌더가 코어 수에 근접 → 서로 뺏기 시작(4코어에서 6개 = 9.8배 지연)
      · 줄이 계속 서 있다 → 상한이 부족하다
      · 디스크 여유 50GB 미만 → 정리로 못 버틴다, 스토리지가 필요하다
      · 월 송신이 6TB(=무료한도)의 80%를 넘본다 → 초과요금이 붙기 시작한다

    ★문구는 **언제의 숫자인지** 반드시 밝힌다(2026-08-27). 판정은 7일 최대치로
      보는데 문장이 "밀렸습니다"라 현재형으로 읽혀, 이미 지나간 이틀 전 최대치를
      지금 사고로 오해했다(실사고). 최대치가 난 **날짜**와 **지금 값**을 같이 박는다.
    """
    d = daily(db_path, days=7)
    cores = cores or (os.cpu_count() or 4)
    if not d:
        return {"level": "unknown", "msg": "아직 표본이 없습니다 — 5분마다 쌓입니다."}
    max_run = max((x["max_running"] or 0) for x in d)
    q_day = max(d, key=lambda x: (x["max_queued"] or 0))
    max_q = q_day["max_queued"] or 0
    min_free = min((x["min_disk_free_gb"] or 9999) for x in d)
    tx_month = sum(x["tx_gb"] for x in d) / max(len(d), 1) * 30

    if min_free < 50:
        return {"level": "danger",
                "msg": f"디스크 여유 {min_free:.0f}GB — 곧 찹니다. 블록스토리지를 붙이세요."}
    if max_run >= cores:
        return {"level": "danger",
                "msg": f"동시 렌더가 {max_run}개까지 갔습니다(코어 {cores}개). "
                       f"서로 뺏어 다 같이 느려지는 구간입니다 — 코어를 늘리세요."}
    if tx_month > 6144 * 0.8:
        return {"level": "warn",
                "msg": f"월 송신 추정 {tx_month / 1024:.1f}TB — 무료 6TB에 근접. "
                       f"초과분은 GB당 $0.09입니다."}
    if max_q >= 3:
        now_txt = ("지금은 대기 없습니다." if now_queued == 0
                   else f"지금은 {now_queued}개." if now_queued is not None else "")
        return {"level": "warn",
                "msg": f"대기가 {q_day['date']}에 최대 {max_q}개까지 밀렸습니다"
                       f"(최근 7일 최대치). {now_txt} 워커를 늘릴 여지가 있는지 보세요."}
    return {"level": "ok",
            "msg": f"여유 있습니다 (동시 렌더 최대 {max_run}/{cores}코어 · "
                   f"디스크 여유 {min_free:.0f}GB · 월 송신 추정 {tx_month / 1024:.1f}TB)"}


if __name__ == "__main__":      # 크론: */5 * * * * python -m shopping_shorts.capacity_watch
    from shopping_shorts.config import DB_PATH

    _s = sample(DB_PATH)
    print(_s)
    # ── 서버 즉시 경보(2026-09-18) — 디스크·응답 지연·메인 스레드 CPU가 문턱을 넘으면
    #    사람이 말해주기 전에 ops_alert(텔레그램+쪽지)로 나간다. 크론 본업을 죽이면 안 되므로 삼킨다.
    try:
        _lv, _msg = server_verdict(_s)
        print(f"[serverwatch] {_lv}: {_msg[:120]}")
        if _lv == "danger":
            from datetime import datetime, timedelta, timezone
            from shopping_shorts import ops_alert
            _when = datetime.now(timezone(timedelta(hours=9))).strftime("%m-%d %H:%M")
            _kind = "server_disk" if "디스크" in _msg else "server_slow"
            ops_alert.raise_alert(
                _kind, f"[서버 {_when}] {_msg[:60]}", f"[발생 {_when} KST] {_msg}",
                grade=ops_alert.GRADE_OPS,
                # 같은 수준의 같은 사고면 쿨다운 뒤에도 재도배하지 않는다(값이 바뀌면 다시)
                signature=f"{_kind}:{int((_s.get('web_latency_ms') or 0) // 500)}:{int((_s.get('disk_free_gb') or 0) // 10)}")
    except Exception as e:      # noqa: BLE001
        print(f"[serverwatch] 판정 실패(무시): {e}")
    # ── API 관측판 무인 경보(2026-09-01) — 아무도 화면을 안 보고 있어도 5분마다
    #    판정이 돌아 danger면 ops_alert(텔레그램+쪽지, 30분 쿨다운)가 나간다.
    #    관측이 크론 본업(용량 표본)을 죽이면 안 되므로 전부 삼킨다.
    try:
        # ★판정 전에 회원 키를 합류시킨다(2026-09-04 실사고). 이 크론은 별도
        #   프로세스라 사장님 키만 보였다 — 사장님 키 1개가 일일 한도에 걸리자
        #   "풀 전멸(살아있는 키 0개)" 고객영향 경보가 났지만, 웹·워커는 회원 키로
        #   정상 생성 중이었다(shorts 풀 성공 424건). 워커와 같은 방식으로 합류한다.
        try:
            from shopping_shorts import keypool
            from shopping_shorts.store import Store
            keypool.resync_pools(Store(DB_PATH))
        except Exception as e:  # noqa: BLE001 — 합류 실패해도 판정은 낸다(사장님 키 기준)
            print(f"[apiwatch] 회원 키 합류 실패(사장님 키만으로 판정): {e}")
        from shopping_shorts import api_health
        v = api_health.verdict()
        print(f"[apiwatch] {v['level']}: {v['msg'][:120]}")
    except Exception as e:      # noqa: BLE001
        print(f"[apiwatch] 판정 실패(무시): {e}")
