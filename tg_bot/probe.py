"""서버를 HTTPS API로 조사한다.

★SSH를 쓰지 않는다 — 포트 22가 막혀도 돌고(2026-09-02 실측), 서버 파일을 안 건드려
  배포가 멈추지 않는다(auto_deploy는 워킹트리가 더러우면 조용히 스킵한다).
★모든 /api/ 는 로그인 없으면 401이다(app.py:10016 미들웨어, 실측 확인). 그래서
  먼저 로그인해 세션 쿠키를 얻는다.
"""


class ProbeError(Exception):
    """조사 실패. ★사유를 뭉개지 않는다 — 'A 또는 B'로 적으면 원인을 못 찾는다."""


class Prober:
    def __init__(self, base, user, password, *, session=None, timeout=20):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password
        self.timeout = timeout
        self._logged_in = False
        if session is None:
            import requests
            session = requests.Session()
        self.s = session

    def _login(self):
        if self._logged_in:
            return
        r = self.s.post(
            self.base + "/api/login",
            data={"user": self.user, "pass": self.password},
            timeout=self.timeout,
            allow_redirects=False,
        )
        # 성공은 303 리다이렉트다(app.py:9614). 200/302도 통과로 본다.
        if r.status_code not in (200, 302, 303):
            raise ProbeError(
                f"로그인에 실패했습니다 (HTTP {r.status_code}). 계정 설정을 확인하세요.")
        self._logged_in = True

    def job(self, job_id):
        """작업 상태 조회. 실패하면 ProbeError."""
        self._login()
        r = self.s.get(f"{self.base}/api/mix/status/{job_id}", timeout=self.timeout)
        if r.status_code == 404:
            raise ProbeError(
                f"작업 {job_id} 을(를) 찾을 수 없습니다. 주소가 맞는지 확인해 주세요.")
        if r.status_code == 401:
            raise ProbeError("로그인 세션이 없습니다. 봇 계정 설정을 확인하세요.")
        if r.status_code != 200:
            raise ProbeError(f"조회가 실패했습니다 (HTTP {r.status_code}).")
        return r.json()
