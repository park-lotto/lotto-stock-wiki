"""관리자 작업라인 관측판 — 2026-08-26 사장님 "지금 작업중인 사람들 작업 라인을
관리자 페이지에서 라이브로 볼수있어?" → (다)안 확정: 줄 + 오래걸림 경고 + 최근 완료·실패.

## 왜 필요한가 (실측)
관리자 페이지(`admin.html`)에 큐 화면이 **아예 없었다**(`job_queue`·`queue` 검색 0건).
`/api/admin/capacity`가 숫자(running·queued·workers)는 주지만 **누가 무엇을 하는지**는
안 준다 — 사장님이 "3건 대기 중"까지만 보고 그게 누구 것인지 몰랐다.

★이게 실제 피해를 냈다: 2026-08-25 VMake 크레딧 소진 때 **고객이 9번 연속 실패하고
  신고할 때까지 아무도 몰랐다**. 오래 걸리는 작업 경고만 있었어도 그때 바로 보였다.

## 재료는 이미 다 있다 — 새로 만들지 않는다
job_queue: task·state·owner(고객id)·created_at·claimed_at·heartbeat_at·progress·args_json
여기에 customers(이름)와 produce_works(작업 제목)를 이어 붙이면 끝이다.
"""
import json


def test_스토어에_작업라인_조회가_있다():
    from shopping_shorts.store import Store
    assert hasattr(Store, "admin_work_lines"), "작업라인 조회 함수가 없다"


def test_진행_대기_최근완료를_한_번에_준다(tmp_path):
    """★한 번의 조회로 세 가지를 준다 — 화면이 API를 여러 번 부르면 시점이 어긋난다."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    out = st.admin_work_lines()
    for k in ("running", "queued", "recent"):
        assert k in out, f"'{k}'가 없다"
        assert isinstance(out[k], list)


def test_빈_큐에서도_안_터진다(tmp_path):
    """작업이 하나도 없는 서버에서도 화면이 떠야 한다(빈 목록 = 정상)."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    out = st.admin_work_lines()
    assert out["running"] == [] and out["queued"] == []


def _seed(st, rows):
    """job_queue에 직접 넣는다(워커 없이 상태만 만든다)."""
    with st._conn() as c:
        for r in rows:
            c.execute(
                "INSERT INTO job_queue(id,task,args_json,state,created_at,claimed_at,"
                "heartbeat_at,finished_at,owner,error,prio) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,0)", r)


def test_진행중_작업의_경과시간과_주인을_준다(tmp_path):
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    _seed(st, [
        (1, "clean", json.dumps({"job_id": "J1"}), "running",
         "2026-08-26 17:00:00", "2026-08-26 17:00:00", "2026-08-26 17:22:00", None, "241", None),
    ])
    out = st.admin_work_lines()
    assert len(out["running"]) == 1
    r = out["running"][0]
    assert r["task"] == "clean"
    assert r["owner"] == "241"
    assert r["job_id"] == "J1", "args_json에서 job_id를 못 뽑았다"
    assert isinstance(r.get("elapsed_sec"), int), "경과시간이 없다 — 오래걸림을 판정 못 한다"


def test_대기는_줄_순서대로_준다(tmp_path):
    """★워커가 집는 순서와 같아야 한다 — 화면 순서가 실제와 다르면 거짓말이 된다."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    _seed(st, [
        (5, "mix", "{}", "queued", "2026-08-26 17:05:00", None, None, None, "12", None),
        (3, "render", "{}", "queued", "2026-08-26 17:01:00", None, None, None, "241", None),
    ])
    out = st.admin_work_lines()
    assert [q["id"] for q in out["queued"]] == [3, 5], "줄 순서가 id 오름차순이 아니다"


def test_최근완료에_실패도_함께_준다(tmp_path):
    """★실패만 따로 보면 '성공률'을 알 수 없다. 완료·실패를 한 줄에 섞어 최신순으로."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    # ⚠️'최근 60분' 창에 걸려야 하므로 **지금 기준**으로 넣는다(고정 과거날짜를 쓰면
    #   테스트가 며칠 뒤 조용히 깨진다 — 메모리 `테스트_시한폭탄` 교훈).
    from datetime import datetime, timedelta, timezone
    _n = datetime.now(timezone.utc)
    _f = lambda m: (_n - timedelta(minutes=m)).strftime("%Y-%m-%d %H:%M:%S")
    _seed(st, [
        (1, "mix", "{}", "done", _f(10), _f(9), None, _f(8), "12", None),
        (2, "clean", "{}", "failed", _f(6), _f(5), None, _f(4), "241", "[60002] 크레딧 소진"),
    ])
    out = st.admin_work_lines()
    ids = [r["id"] for r in out["recent"]]
    assert ids == [2, 1], "최신순이 아니다"
    fail = out["recent"][0]
    assert fail["state"] == "failed"
    assert "크레딧" in (fail.get("error") or ""), "실패 사유를 안 준다 — 원인을 못 본다"


def test_고객_이름을_붙여준다(tmp_path):
    """★owner는 숫자다. 이름이 없으면 '241'만 보이고 누군지 알 수 없다."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    with st._conn() as c:
        # ⚠️customers는 NOT NULL 컬럼이 많다(실측: username·password_hash·salt·plan·
        #   full_access_until·setup_due·admin·welcome_due) — 짐작하지 말고 다 채운다.
        c.execute("INSERT INTO customers(id,username,password_hash,salt,plan,"
                  "full_access_until,setup_due,admin,welcome_due,email,name,created_at) "
                  "VALUES(241,'derick','x','y','pro',0,0,0,0,'a@b.c','김데릭','2026-01-01')")
    _seed(st, [
        (1, "clean", "{}", "running", "2026-08-26 17:00:00", "2026-08-26 17:00:00",
         None, None, "241", None),
    ])
    out = st.admin_work_lines()
    assert out["running"][0].get("owner_name") == "김데릭"


def test_모르는_주인은_비운다(tmp_path):
    """★고객 정보가 없으면 지어내지 않는다 — 모르면 빈칸(0순위: 추측 금지)."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    _seed(st, [
        (1, "mix", "{}", "running", "2026-08-26 17:00:00", "2026-08-26 17:00:00",
         None, None, "999", None),
    ])
    out = st.admin_work_lines()
    assert out["running"][0].get("owner_name") in ("", None)


# ── 화면 ────────────────────────────────────────────────────────────────
def _admin_html():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "static" / "admin.html"
    return p.read_text(encoding="utf-8")


def test_관리자_화면에_작업라인_섹션이_있다():
    src = _admin_html()
    assert "작업 라인" in src, "작업라인 섹션이 없다"
    assert "/api/admin/work-lines" in src, "API를 안 부른다"


def test_라이브_자동갱신이_걸려있다():
    """사장님: "라이브로 볼수있어?" — 새로고침 없이 스스로 갱신돼야 한다."""
    src = _admin_html()
    assert "setInterval" in src, "자동 갱신이 없다"


def test_오래걸림_경고가_있다():
    """★(다)안의 핵심. 평소보다 오래 도는 작업을 눈에 띄게 — 신고 전에 발견하려는 것."""
    src = _admin_html()
    assert "slow" in src or "오래" in src, "오래걸림 표시가 없다"


def test_서버에_엔드포인트가_있고_관리자_전용이다():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index('@app.get("/api/admin/work-lines")')
    fn = src[i:i + 900]
    assert "_require_admin" in fn, "관리자 권한 검사가 없다 — 고객 이름이 새어나간다"
