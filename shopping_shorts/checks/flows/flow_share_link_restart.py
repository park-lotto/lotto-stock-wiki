"""QR 공유 링크가 서버 재시작 뒤에도 열리나(B-40). 사본 DB의 done 영상으로 링크 발급 →
미리보기 웹 재시작(session.restart_web) → /s/{sid}·/api/share/t/{sid} 상태 확인.

★응답 URL 키 실측(app.py:7651-7670 api_share_link): 응답은 `{"ok": True, "url": ..., "qr_svg": ...}`
— "short"라는 키는 없다. 그래서 이 파일은 "url" 하나로 고정한다(브리프의 이중 폴백은 실측 뒤 제거).
★목록 키 실측(app.py:15408-15410 api_produce_works_list / store.py:5258 list_produce_works):
응답은 `{"ok": True, "works": [...]}`이고 각 항목은 work_id/title/step/job_id/updated_at만 가진다
("items"라는 키는 없다) — "works" 하나로 고정한다.

★완성 job 탐색(리뷰 2026-09-07 Important #2): list_produce_works는 "최근 업데이트순"일 뿐 완성
여부와 무관하다. 첫 항목만 쓰면 대부분 렌더 전이라 api_share_link가 404를 주고 검사가 매번
회색으로 스킵돼 아무도 눈치 못 채는 사고가 난다(이 프로젝트가 반복 당한 유형). 그래서 최근
목록에서 최대 _MAX_PROBE개까지 훑어 api_share_link가 실제로 "url"을 주는 첫 job을 쓴다. 끝까지
못 찾으면 회색으로 끝내되 reason에 몇 개를 훑었는지 남긴다(조용한 회색 금지).

★500 판정(리뷰 2026-09-07 Important #1): app.py의 api_share_t 주석 자체가 "여기서 500이 나면
공유 자체가 막힌다"고 명시한다 — 즉 500은 "링크가 죽었다"는 신호에 가깝지 "판정 불가"가 아니다.
그래서 정상으로 인정하는 코드를 화이트리스트(200=정상, 404=썸네일 미선택의 정상 폴백)로만 두고,
그 외(403 만료·500 서버오류·기타)는 전부 빨강으로 본다. 회색으로 두지 않는 이유: 이 검사의
존재 목적이 "재시작 뒤에도 링크가 살아있는가"이므로, 재시작 뒤 응답이 정상 화이트리스트를
벗어나면 그 자체가 "링크가 죽었다"는 관측이지 "판정을 못 했다"가 아니다."""
from shopping_shorts.checks.verdict import GREEN, RED, GRAY, Result

META = {"name": "공유(QR) 링크가 서버 재시작 뒤에도 열리나", "needs_worker": False, "timeout_s": 180}

_MAX_PROBE = 20                 # 완성 job 탐색 상한(라이브 서버 부담 제한)
_OK_SHARE_T_CODES = (200, 404)  # 404=썸네일 미선택(정상 폴백). 그 외(403·500 등)는 빨강.


def _find_shareable(p, base_url, jobs):
    """최근 job 목록을 앞에서부터 최대 _MAX_PROBE개 훑어 실제로 링크가 발급되는 첫 job을 찾는다.
    반환: (link_json, sid, probed_count) — 못 찾으면 (None, None, probed_count)."""
    probed = 0
    for job_id in jobs[:_MAX_PROBE]:
        probed += 1
        link = p.request.get(f"{base_url}/api/share/link/{job_id}").json()
        sid = (link.get("url") or "").rstrip("/").rsplit("/", 1)[-1]
        if sid:
            return link, sid, probed
    return None, None, probed


def run(session):
    restart = getattr(session, "restart_web", None)
    if restart is None:
        return [Result("L2", META["name"], GRAY, reason="restart_web 훅 없음(run_checks가 주입)",
                       signature="L2:share_link_restart", page="/s/")]
    p = session.page
    resp = p.request.get(session.base_url + "/api/produce/works").json()
    jobs = [w.get("job_id") for w in (resp.get("works") or []) if w.get("job_id")]
    if not jobs:
        return [Result("L2", META["name"], GRAY, reason="최근 작업 목록에 job이 없어 판정 불가",
                       signature="L2:share_link_restart", page="/s/")]
    link, sid, probed = _find_shareable(p, session.base_url, jobs)
    if not sid:
        return [Result("L2", META["name"], GRAY,
                       reason=f"최근 {probed}개 작업 중 공유 가능한 완성본이 없어 판정 불가",
                       signature="L2:share_link_restart", page="/s/")]
    restart()
    codes = [p.request.get(session.base_url + path).status for path in (f"/s/{sid}", f"/api/share/t/{sid}")]
    ok = codes[0] == 200 and codes[1] in _OK_SHARE_T_CODES
    return [Result("L2", META["name"], GREEN if ok else RED,
                   reason=f"{probed}개 훑어 job 찾음 / /s,/api/share/t → {codes}",
                   signature="L2:share_link_restart", page=f"/s/{sid}")]
