# 로그인 게이트 v2 라이브 검증 (server.py가 :8090에 떠 있는 상태에서 실행)
import hmac, hashlib, time, requests

B = "http://localhost:8090"
SECRET = open(r"C:\Users\TheRose\Desktop\로또의 주식\db\.session_secret", encoding="utf-8").read().strip()

def sign(uid, ttl=3600):
    exp = int(time.time()) + ttl
    payload = f"{uid}:{exp}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def chk(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))

r = requests.get(B + "/market", allow_redirects=False)
chk("비로그인 /market → 로그인 리다이렉트", r.status_code in (302, 307) and "/login" in r.headers.get("location", ""), r.status_code)

r = requests.get(B + "/api/heatmap_tab", allow_redirects=False)
chk("비로그인 API → 401", r.status_code == 401, r.status_code)

r = requests.post(B + "/api/login", data={"user": "admin", "pass": "wrong"}, allow_redirects=False)
chk("잘못된 비번 → /login?e=", r.status_code == 303 and "/login" in r.headers.get("location", ""), r.headers.get("location", ""))

s = requests.Session()
r = s.post(B + "/api/login", data={"user": "admin", "pass": "testpw123"}, allow_redirects=False)
chk("관리자 로그인 → 쿠키+/market", r.status_code == 303 and "dash_auth" in s.cookies, r.headers.get("location", ""))
r = s.get(B + "/", allow_redirects=False)
chk("관리자 → 홈(/) 접근 200", r.status_code == 200, r.status_code)
r = s.get(B + "/brain", allow_redirects=False)
chk("관리자 → /brain 접근 200", r.status_code == 200, r.status_code)

# 일반 사용자(uid=5, users.db에 없음 → 비관리자 취급) 쿠키 위조가 아닌 '서버 시크릿으로 서명' = 정상 세션 시뮬
u = {"dash_auth": sign(5)}
r = requests.get(B + "/market", cookies=u, allow_redirects=False)
chk("사용자 → /market 200", r.status_code == 200, r.status_code)
r = requests.get(B + "/insights", cookies=u, allow_redirects=False)
chk("사용자 → /insights 200", r.status_code == 200, r.status_code)
r = requests.get(B + "/", cookies=u, allow_redirects=False)
chk("사용자 → 홈(/) 차단 → /market 리다이렉트", r.status_code in (302, 307) and "/market" in r.headers.get("location", ""), r.status_code)
r = requests.get(B + "/brain", cookies=u, allow_redirects=False)
chk("사용자 → /brain 차단", r.status_code in (302, 307), r.status_code)
r = requests.get(B + "/api/heatmap_tab?tab=core", cookies=u, allow_redirects=False)
chk("사용자 → 히트맵 API 허용(401/403 아님)", r.status_code not in (401, 403), r.status_code)
r = requests.post(B + "/api/insights/nlm_relogin", cookies=u, allow_redirects=False)
chk("사용자 → nlm_* 운영자API 403", r.status_code == 403, r.status_code)
r = requests.post(B + "/api/watchlist", cookies=u, json={"code": "005930"}, allow_redirects=False)
chk("사용자 → watchlist POST 403", r.status_code == 403, r.status_code)
r = requests.get(B + "/api/watchlist", cookies=u, allow_redirects=False)
chk("사용자 → watchlist GET 허용", r.status_code not in (401, 403), r.status_code)

# 위조 쿠키(다른 시크릿 서명) → 거부
bad = f"0:{int(time.time())+3600}"
badsig = hmac.new(b"stockbrain-local-secret", bad.encode(), hashlib.sha256).hexdigest()
r = requests.get(B + "/", cookies={"dash_auth": f"{bad}:{badsig}"}, allow_redirects=False)
chk("옛 하드코딩 시크릿으로 위조한 쿠키 → 거부", r.status_code in (302, 307) and "/login" in r.headers.get("location", ""), r.status_code)
