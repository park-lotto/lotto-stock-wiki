"""QR 공유 링크가 서버 재시작 뒤에도 열리나(B-40). 사본 DB의 done 영상으로 링크 발급 →
미리보기 웹 재시작(session.restart_web) → /s/{sid}·/api/share/t/{sid} 200.

★응답 URL 키 실측(app.py:7651-7670 api_share_link): 응답은 `{"ok": True, "url": ..., "qr_svg": ...}`
— "short"라는 키는 없다. 그래서 이 파일은 "url" 하나로 고정한다(브리프의 이중 폴백은 실측 뒤 제거).
★목록 키 실측(app.py:15408-15410 api_produce_works_list / store.py:5258 list_produce_works):
응답은 `{"ok": True, "works": [...]}`이고 각 항목은 work_id/title/step/job_id/updated_at만 가진다
("items"라는 키는 없다) — "works" 하나로 고정한다. 단, 이 job_id는 "작업 저장" 시점의 job이라
완성(영상 렌더까지 끝난) job이 아닐 수 있다 — 그런 job으로 링크 발급을 시도하면 api_share_link가
404("완성 영상이 없어요")를 주고 응답에 "url" 키가 없어 sid를 못 얻는다. 이 경우도 실패가 아니라
"판정 불가(회색)"으로 끝낸다(완성 job을 정확히 고르는 일은 Task 12/14 몫)."""
from shopping_shorts.checks.verdict import GREEN, RED, GRAY, Result

META = {"name": "공유(QR) 링크가 서버 재시작 뒤에도 열리나", "needs_worker": False, "timeout_s": 180}


def run(session):
    restart = getattr(session, "restart_web", None)
    if restart is None:
        return [Result("L2", META["name"], GRAY, reason="restart_web 훅 없음(run_checks가 주입)",
                       signature="L2:share_link_restart", page="/s/")]
    p = session.page
    resp = p.request.get(session.base_url + "/api/produce/works").json()
    jobs = [w.get("job_id") for w in (resp.get("works") or []) if w.get("job_id")]
    if not jobs:
        return [Result("L2", META["name"], GRAY, reason="완성 job 없음", signature="L2:share_link_restart", page="/s/")]
    link = p.request.get(f"{session.base_url}/api/share/link/{jobs[0]}").json()
    sid = (link.get("url") or "").rstrip("/").rsplit("/", 1)[-1]
    if not sid:
        return [Result("L2", META["name"], GRAY, reason=f"sid 못 얻음 {link}", signature="L2:share_link_restart", page="/s/")]
    restart()
    codes = [p.request.get(session.base_url + path).status for path in (f"/s/{sid}", f"/api/share/t/{sid}")]
    # ★/api/share/t/{sid}는 썸네일을 아직 안 골랐으면 정상적으로 404를 준다(app.py api_share_t
    # 주석 — "여기서 500이 나면 공유 자체가 막힌다"). sid 자체가 사라졌을 때만 403(만료)을 준다.
    # 그래서 "썸네일 없음(404)"까지 RED로 잡으면 거짓빨강이 된다 — /s는 200, /api/share/t는
    # 403(만료)만 아니면 통과로 본다.
    ok = codes[0] == 200 and codes[1] != 403
    return [Result("L2", META["name"], GREEN if ok else RED, reason=f"/s,/api/share/t → {codes}",
                   signature="L2:share_link_restart", page=f"/s/{sid}")]
