"""점검 진입점 하나. health: 라이브 DB 읽기만(미리보기 불필요, 5분 타이머가 매번 부른다).
deploy/daily: 미리보기(8850)를 띄우고 L0~L2 화면 점검까지 돌린다."""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from shopping_shorts.checks import db, discover, static_invariants
from shopping_shorts.checks.ro import LIVE_DB
from shopping_shorts.checks.verdict import GRAY, GREEN, RED, Result, Sample, summarize

SERVICE = "shopping-shorts"
REPO = Path(__file__).resolve().parents[2]
PREVIEW_SH = REPO / "deploy" / "preview.sh"
PREVIEW_URL = "http://127.0.0.1:8850"
LIVE_REPO = Path("/home/ubuntu/lotto-stock-wiki")


def head_sha(repo=REPO):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _record_discover_errors(conn, run_id):
    """discover.py 계약: LAST_ERRORS에 담긴 import 실패 항목마다 GRAY Result를 남긴다.
    항목 파일이 문법 오류로 깨지면 그 점검은 영영 안 돌면서 화면은 초록으로 보이는
    사고를 막는다 — 깨진 모듈도 화면에 '판정 불가'로 보여야 한다."""
    out = []
    for full_name, exc_repr in discover.LAST_ERRORS:
        mod_name = full_name.rsplit(".", 1)[-1]
        r = Result(
            layer="L3",
            name=f"점검 항목 로드 실패 — {mod_name}",
            verdict=GRAY,
            reason=f"import 실패: {exc_repr}",
            signature=f"L3:import:{mod_name}",
        )
        if run_id is not None:
            db.add_result(conn, run_id, r)
        out.append(r)
    return out


def run_health(conn, ctx, force=False, run_id=None):
    """discover된 health 모듈을 전부 돌려 Sample을 쌓는다.
    due-체크는 모듈 단위(last_sample_ts_prefix)로 본다 — Sample.item은 항상
    '<모듈명>::<서브키>'라 정확일치 조회로는 절대 못 찾기 때문(리뷰 3번 지적)."""
    out = []
    mods = discover.discover("health")
    _record_discover_errors(conn, run_id)
    for m in mods:
        item = m.__name__.rsplit(".", 1)[-1]
        if not force and not discover.is_due(m.META["every"], db.last_sample_ts_prefix(conn, item)):
            continue
        try:
            samples = m.measure(ctx)
        except Exception as e:  # noqa: BLE001 — 항목 하나의 예외가 나머지를 막지 않는다
            samples = [Sample(item, m.META["name"], None, None, detail=f"measure 예외: {e!r}")]
        for s in samples:
            db.add_sample(conn, s)
            out.append(s)
    return out


def _overall_verdict(conn, run_id, samples):
    """이번 run의 종합 판정. health_samples(방금 쌓인 것)와 check_results(discover
    import 에러)를 함께 verdict.summarize()에 넘긴다 — 손으로 2분기 짜지 않고
    Task2가 만든 그 함수를 그대로 쓴다. '샘플이 빨강이면 run도 빨강'이 성립해야 한다
    (리뷰 1번 — 이전 코드는 check_results만 보고 health_samples를 무시해 랭킹이
    전부 RED여도 check_runs.verdict가 'green'으로 찍히는 거짓 초록이었다)."""
    rows = [{"verdict": s.verdict, "signature": s.item, "name": s.name} for s in samples]
    rows += [{"verdict": r["verdict"], "signature": r["signature"], "name": r["name"]}
             for r in db.latest_results(conn, run_id)]
    return summarize(rows, prev={})["overall"]


def live_head_sha():
    """'배포 직후'는 시각이 아니라 라이브 HEAD sha가 바뀌었는가로 판정한다(자동배포가
    KST 02~06시 창 밖에선 pull조차 안 하므로 '시각'은 신호가 못 된다). 라이브 repo가
    이 서버에 없으면(로컬 개발기) 이 트랙 repo의 HEAD로 대신한다."""
    return head_sha(LIVE_REPO if LIVE_REPO.exists() else REPO)


def needs_ui_run(conn, sha):
    """직전에 화면 점검(deploy/daily)이 이미 이 sha로 끝났으면 다시 돌 필요 없다.
    5분 타이머가 계속 부르는데 라이브가 안 바뀌었으면 미리보기를 매번 새로 기동할 이유가 없다."""
    row = conn.execute(
        "SELECT head_sha FROM check_runs WHERE trigger IN ('deploy','daily') "
        "AND finished IS NOT NULL ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    return (row is None) or (row["head_sha"] != sha)


def preview_start(sha):
    subprocess.run(["bash", str(PREVIEW_SH), "start", sha, "--with-db"], check=True, timeout=600)


def preview_stop():
    subprocess.run(["bash", str(PREVIEW_SH), "stop"], timeout=60)


def restart_preview():
    """공유링크·재시작류 흐름(flow_share_link_restart)이 주입받는 훅. 미리보기 워크트리의
    현재 sha로 다시 기동한다 — preview.sh start는 내부에서 _stop을 먼저 부르므로 그대로 재시작이 된다."""
    sha = head_sha(Path("/home/ubuntu/preview"))
    preview_start(sha)


def alert_if_needed(conn, run_id, results, send=None):
    """같은 signature가 2회 연속 빨강 → 알림. 회색은 즉시(=점검기 상태를 사람이 봐야 한다).
    초록·노랑은 조용(설계 D11). 새 알림을 만들지 않고 기존 ops_alert.raise_alert를 그대로 쓴다
    (CLAUDE.md 0순위-B — 같은 판단을 두 곳에 적지 않는다)."""
    if send is None:
        from shopping_shorts import ops_alert

        def send(**kw):
            return ops_alert.raise_alert(
                kw["kind"], kw["title"], kw.get("detail", ""),
                cooldown_sec=6 * 3600, signature=kw.get("signature"),
            )

    grays = [r for r in results if r.verdict == GRAY]
    if grays:
        send(kind="checks_gray", title=f"[검수] 판정 불가 {len(grays)}건 — 점검기 상태 확인",
             detail="; ".join(f"{r.name}: {r.reason}" for r in grays[:5]), signature="gray")
    twice = [r for r in results
             if r.verdict == RED and db.previous_verdict(conn, r.signature, run_id) == RED]
    if twice:
        send(kind="checks_red",
             title=f"[검수] 2회 연속 빨강 {len(twice)}건: " + "·".join(r.name for r in twice[:3]),
             detail="; ".join(f"{r.name}: {r.reason}" for r in twice[:10]),
             signature=",".join(sorted(r.signature for r in twice)))


def _run_with_timeout(fn, timeout_s):
    """fn()을 timeout_s 안에 못 끝내면 TimeoutError를 던지고 즉시 돌아온다(초과분을 기다리지 않는다).

    운영 서버(리눅스, run_checks.main이 메인 스레드에서 도는 oneshot 프로세스)에서는 SIGALRM으로
    실제 강제 인터럽트가 걸린다 — CPython은 블로킹 syscall(소켓 등, playwright의 내부 통신 포함) 도중에도
    알람 신호가 오면 즉시 예외를 던진다. SIGALRM이 없는 곳(윈도우 개발기, 또는 메인 스레드가 아닌 곳)에서는
    워치독 스레드로 '감지'만 한다 — 그 자리에서 강제로 끊지는 못하지만, 호출자는 timeout_s를 넘겨
    기다리지 않고 바로 GRAY로 넘어갈 수 있다(순수 파이썬 함수는 join(timeout)로 실측 검증됨)."""
    if hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread():
        def _handler(signum, frame):
            raise TimeoutError(f"{timeout_s}s 초과")
        old = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, timeout_s))
        try:
            return fn()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    result = {}

    def _target():
        try:
            result["value"] = fn()
        except BaseException as e:  # noqa: BLE001 — 워치독 스레드 예외를 호출 스레드로 전달
            result["exc"] = e

    th = threading.Thread(target=_target, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        raise TimeoutError(f"{timeout_s}s 초과(감지만 — 백그라운드 스레드는 계속 돌 수 있음)")
    if "exc" in result:
        raise result["exc"]
    return result["value"]


def run_flow_with_budget(session, module):
    """L2 흐름 하나를 META['timeout_s'] 예산 안에서 돌린다. 넘기면 그 항목만 GRAY로
    기록하고 다음 항목으로 넘어간다(리뷰 지적 — 선언만 있고 아무도 안 읽던 timeout_s를 집행)."""
    from shopping_shorts.checks.flows import base as flow_base

    timeout_s = module.META.get("timeout_s", 180)
    try:
        return _run_with_timeout(lambda: flow_base.run_flow(session, module), timeout_s)
    except TimeoutError as e:
        mod_name = module.__name__.rsplit(".", 1)[-1]
        return [Result("L2", module.META["name"], GRAY,
                       reason=f"시간초과({timeout_s}s) — 다음 항목으로 넘어감: {e}",
                       signature=f"L2:timeout:{mod_name}", page="/produce")]


def run_ui(conn, run_id, session, quick=False):
    """L0(카나리·스로틀·정적) + L1(전수) + L2(흐름). 스로틀 게이트는 sweep 안에서 L1에는 이미
    적용돼 있고, L2(flows)에는 여기서 같은 게이트(sweep._apply_throttle_gate)를 배선한다
    (리뷰 지적 — flows는 base.run_flow의 GRAY 가드만 있고 스로틀 게이트가 없었다)."""
    from shopping_shorts.checks import browser, sweep

    results = []
    n = browser.timer_probe(session.page)
    throttled = n < 25
    results.append(Result("L0", "브라우저 타이머 스로틀", GRAY if throttled else GREEN,
                          reason=f"100ms 인터벌 3초에 {n}회", signature="L0:timer_probe"))
    results.append(browser.canary(session.page))
    results.extend(static_invariants.run_all(REPO))
    if throttled:
        for r in results:
            db.add_result(conn, run_id, r)
        return results
    results.extend(sweep.sweep_produce(session))
    results.append(sweep.reporter_alive(session))
    results.extend(sweep.sweep_sidebar(session))
    if not quick:
        results.extend(sweep.sweep_lists(session))
    for m in discover.discover("flows"):
        if m.META["needs_worker"]:
            continue
        flow_results = run_flow_with_budget(session, m)
        flow_results = sweep._apply_throttle_gate(session, flow_results)
        results.extend(flow_results)
    for r in results:
        db.add_result(conn, run_id, r)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", choices=["health", "deploy", "daily"], required=True)
    ap.add_argument("--force", action="store_true", help="주기 무시하고 전부")
    ap.add_argument("--db", default=None)
    ap.add_argument("--base-url", default=PREVIEW_URL)
    ap.add_argument("--no-preview", action="store_true", help="이미 떠 있는 서버를 쓴다(로컬 디버그)")
    a = ap.parse_args(argv)
    conn = db.open_db(a.db)
    try:
        ctx = {"live_db": LIVE_DB, "base_url": None, "now": datetime.now(timezone.utc)}
        if a.trigger == "health":
            run_id = db.start_run(conn, SERVICE, "health", head_sha())
            try:
                samples = run_health(conn, ctx, force=a.force, run_id=run_id)
            except Exception as e:  # noqa: BLE001 — run이 죽어도 finish_run은 반드시 남긴다
                db.finish_run(conn, run_id, GRAY, l0_json=f"run_health 예외: {e!r}")
                print(f"[gray  ] 점검 실행 자체가 실패했습니다 — {e!r}", file=sys.stderr)
                return 1
            overall = _overall_verdict(conn, run_id, samples)
            db.finish_run(conn, run_id, overall)
            for s in samples:
                print(f"[{s.verdict:6}] {s.name} — {s.detail}")
            for r in db.latest_results(conn, run_id):
                print(f"[{r['verdict']:6}] {r['name']} — {r['reason']}")
            return 0

        sha = live_head_sha()
        if a.trigger == "deploy" and not a.force and not needs_ui_run(conn, sha):
            print(f"[skip  ] 라이브 sha 그대로({sha}) — 화면 점검 생략")
            return 0
        run_id = db.start_run(conn, SERVICE, a.trigger, sha)
        results = []
        try:
            if not a.no_preview:
                preview_start(sha)
            from shopping_shorts.checks import browser
            s = browser.open_session(a.base_url, os.environ["DASH_USER"], os.environ["DASH_PASS"])
            # ★--no-preview는 "이미 떠 있는 걸 그대로 쓴다"는 뜻이다(2026-09-07 실측 발견: 이 줄이
            # 무조건 restart_preview를 심어놔서, flow_share_link_restart가 그 훅을 부르는 순간
            # --no-preview를 줬어도 남이 띄워둔 미리보기가 내려갔다 재기동됐다). --no-preview일 땐
            # 아예 훅을 안 심는다 — flow_share_link_restart는 훅이 없으면 회색(판정 불가)으로
            # 정상 후퇴하도록 이미 짜여 있다(getattr(session,"restart_web",None) 폴백).
            if not a.no_preview:
                s.restart_web = restart_preview
            try:
                cid = browser.login(s)
                if cid != 0:
                    raise RuntimeError(f"cid {cid} — 점검 계정은 0이어야 한다")
                ctx["base_url"] = a.base_url
                ctx["cookies"] = {c["name"]: c["value"] for c in s.context.cookies()}
                results = run_ui(conn, run_id, s, quick=(a.trigger == "deploy"))
                for smp in run_health(conn, ctx, force=(a.trigger == "daily")):
                    results.append(Result("L3", smp.name, smp.verdict, reason=smp.detail, signature=smp.item))
            finally:
                browser.close_session(s)
        except Exception as e:  # noqa: BLE001 — 기동·로그인 실패는 회색이지 빨강이 아니다
            gray = Result("L0", "미리보기 기동·로그인", GRAY,
                          reason=f"{type(e).__name__}: {str(e)[:200]}", signature="L0:boot")
            results.append(gray)
            db.add_result(conn, run_id, gray)
        finally:
            if not a.no_preview:
                preview_stop()
        prev = {r.signature: db.previous_verdict(conn, r.signature, run_id) for r in results}
        rows = [{"verdict": r.verdict, "signature": r.signature, "name": r.name} for r in results]
        summ = summarize(rows, prev)
        db.finish_run(conn, run_id, summ["overall"], json.dumps(summ["counts"], ensure_ascii=False))
        alert_if_needed(conn, run_id, results)
        print(summ["headline"])
        return 0 if summ["overall"] != GRAY else 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
