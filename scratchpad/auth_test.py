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

# 일반 사용자 = 승인된 계정(uid 102, 아래 승인제 섹션에서 미리 생성)으로 시뮬
import sqlite3 as _sq
_c = _sq.connect(r"C:\Users\TheRose\Desktop\로또의 주식\db\users.db")
_c.execute("INSERT OR IGNORE INTO users(id, google_sub, email, approved, blocked, created) VALUES(102,'t-approved','ok@test.com',1,0,'2026-08-06')")
_c.execute("UPDATE users SET approved=1, blocked=0 WHERE id=102")
_c.commit(); _c.close()
u = {"dash_auth": sign(102)}
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

# ── 승인제 검증 ──
import sqlite3
DB = r"C:\Users\TheRose\Desktop\로또의 주식\db\users.db"
conn = sqlite3.connect(DB)
conn.execute("INSERT OR IGNORE INTO users(id, google_sub, email, approved, blocked, created) VALUES(101,'t-pending','pend@test.com',0,0,'2026-08-06')")
conn.execute("UPDATE users SET approved=0, blocked=0 WHERE id=101")   # 재실행 대비 초기화
conn.execute("INSERT OR IGNORE INTO users(id, google_sub, email, approved, blocked, created) VALUES(102,'t-approved','ok@test.com',1,0,'2026-08-06')")
conn.execute("INSERT OR IGNORE INTO users(id, google_sub, email, approved, blocked, created) VALUES(103,'t-blocked','ban@test.com',1,1,'2026-08-06')")
conn.commit(); conn.close()

pend, appr, ban = {"dash_auth": sign(101)}, {"dash_auth": sign(102)}, {"dash_auth": sign(103)}
r = requests.get(B + "/market", cookies=pend, allow_redirects=False)
chk("미승인 → /market 403 대기화면", r.status_code == 403 and "승인 대기중" in r.text, r.status_code)
r = requests.get(B + "/api/heatmap_tab", cookies=pend, allow_redirects=False)
chk("미승인 → API 403", r.status_code == 403, r.status_code)
r = requests.get(B + "/market", cookies=appr, allow_redirects=False)
chk("승인됨 → /market 200", r.status_code == 200, r.status_code)
r = requests.get(B + "/market", cookies=ban, allow_redirects=False)
chk("차단됨 → 403 제한화면", r.status_code == 403 and "제한된 계정" in r.text, r.status_code)
r = requests.get(B + "/admin", cookies=appr, allow_redirects=False)
chk("일반 사용자 → /admin 차단", r.status_code in (302, 307), r.status_code)
r = requests.get(B + "/api/admin/users", cookies=appr, allow_redirects=False)
chk("일반 사용자 → 관리 API 403", r.status_code == 403, r.status_code)
r = s.get(B + "/admin", allow_redirects=False)
chk("관리자 → /admin 200", r.status_code == 200 and "회원 관리" in r.text, r.status_code)
r = s.get(B + "/api/admin/users", allow_redirects=False)
users = r.json().get("users", [])
chk("관리자 → 가입자 목록 조회", r.status_code == 200 and any(u["id"] == 101 for u in users), len(users))
r = s.post(B + "/api/admin/user_update", json={"id": 101, "approved": 1})
chk("관리자 → 승인 처리 ok", r.status_code == 200 and r.json().get("ok"), r.text[:60])
r = requests.get(B + "/market", cookies=pend, allow_redirects=False)
chk("승인 직후 → /market 200", r.status_code == 200, r.status_code)
r = s.post(B + "/api/admin/user_update", json={"id": 101, "blocked": 1})
r = requests.get(B + "/market", cookies=pend, allow_redirects=False)
chk("차단 직후 → 403", r.status_code == 403, r.status_code)

# 위조 쿠키(다른 시크릿 서명) → 거부
bad = f"0:{int(time.time())+3600}"
badsig = hmac.new(b"stockbrain-local-secret", bad.encode(), hashlib.sha256).hexdigest()
r = requests.get(B + "/", cookies={"dash_auth": f"{bad}:{badsig}"}, allow_redirects=False)
chk("옛 하드코딩 시크릿으로 위조한 쿠키 → 거부", r.status_code in (302, 307) and "/login" in r.headers.get("location", ""), r.status_code)
