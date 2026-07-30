# STOCK BRAIN 대시보드 — 지인 배포 가이드 (Lightsail + DuckDNS + 로그인)

구성: `폰/PC → https://stockbrain.duckdns.org → nginx(SSL) → 127.0.0.1:8090 (대시보드, 로그인 필요)`

접속: **admin / (서버 `/etc/stockbrain.env`의 `DASH_PASS`에 설정한 비번)** — 자격증명은 git에 안 올림

---

## 0) 사전 (서버에 있어야 하는 것)
- 이 repo가 서버에 clone 되어 있어야 함 (`git pull`로 최신화)
- `pipeline/taerini_stock.json` 등 데이터 (repo에 커밋돼 있어 pull하면 옴)
- **KIS API 키 설정** (실시간 시세용) — 로컬에서 쓰던 kis 키 설정을 서버에도 동일하게. 없으면 시세/ETF가 0으로 뜸
- python3 + 패키지: `pip install fastapi uvicorn openpyxl`

## 1) DuckDNS (무료 서브도메인)
1. https://www.duckdns.org 로그인(구글) → `stockbrain` 도메인 add
2. current ip 에 **Lightsail 고정 IP(3.39.179.148)** 입력 → update
3. 확인: `nslookup stockbrain.duckdns.org` → 3.39.179.148

## 2) Lightsail 방화벽
Lightsail 콘솔 → Networking → 80(HTTP), 443(HTTPS) 인바운드 허용

## 3) 로그인 자격증명 (서버에만)
```bash
sudo cp deploy/stockbrain.env.example /etc/stockbrain.env
sudo nano /etc/stockbrain.env      # DASH_PASS=원하는비번, DASH_SECRET는 아래로 생성
openssl rand -hex 32               # 나온 값을 DASH_SECRET에 붙여넣기
```

## 4) 서비스 등록 (systemd — 24시간·재부팅 자동)
```bash
# stockbrain.service 안의 WorkingDirectory를 실제 경로로 수정 후
sudo cp deploy/stockbrain.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stockbrain
sudo systemctl status stockbrain          # active(running) 확인
curl -s localhost:8090/healthz            # {"ok":true}
```

## 5) nginx 리버스프록시
```bash
sudo apt install -y nginx
sudo cp deploy/nginx-stockbrain.conf /etc/nginx/sites-available/stockbrain
sudo ln -s /etc/nginx/sites-available/stockbrain /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# → http://stockbrain.duckdns.org 접속되면 로그인창 떠야 함
```

## 6) 무료 SSL (https)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d stockbrain.duckdns.org   # 이메일 입력, 리다이렉트 yes
# → https://stockbrain.duckdns.org 완성
```

## 갱신·운영
- **자동배포(권장)**: 로컬 `main`에 `git push`만 하면 서버 크론(`deploy/auto_deploy.sh`, 3분마다)이
  새 커밋 감지 시 `git pull --ff-only` + 코드변경 시에만 `stockbrain` 재시작. 로그 `/tmp/auto_deploy.log`.
  → **push 후 최대 3분 내 자동반영.** `feat/*` 아닌 `main`에 push해야 함(서버는 main만 추적).
- 수동 즉시반영: `git pull --ff-only origin main && sudo systemctl restart stockbrain`
- 비번 변경: `/etc/stockbrain.env` 수정 → `sudo systemctl restart stockbrain`
- 로그: `journalctl -u stockbrain -f`

## ⚠️ 주의
- 지인이 접속할 때마다 **당신 KIS 시세 쿼터** 소모 (인원 많으면 시세 끊길 수 있음)
- 수급빈집·태린이 지표는 당신 자산 — 무료 공개 범위 유의
- 폰: 로그인 후 `stockbrain.duckdns.org` → "홈 화면에 추가"로 앱처럼 사용 (반응형 적용됨)

---

# 쇼핑쇼츠(shopping_shorts) 배포 — 같은 서버, 별도 서비스 (2026-07-09)

구성: `직원 폰/PC → https://shoppingshorts.duckdns.org → Apache(mod_proxy, SSL) → 127.0.0.1:8849`

접속: **admin / (서버 `/etc/shopping-shorts.env`의 `DASH_PASS`)** — 자격증명은 git에 안 올림

⚠️ **서버는 nginx가 아니라 Apache(mod_proxy)로 80/443을 담당한다** (stockbrain도 동일).
`deploy/apache-shoppingshorts.conf`가 실제 사용하는 파일 — nginx 관련 파일은 이 서비스엔 없음.

## 절차 (한 번만)

```bash
# 1) 채널 리스트 엑셀 업로드 (로컬 카톡파일, git 미추적)
mkdir -p /home/ubuntu/lotto-stock-wiki/shopping_shorts/data
scp -i <pem키> "벤치마킹시트 신규.xlsx" ubuntu@3.39.179.148:/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/벤치마킹시트.xlsx

# 2) 의존성 (fastapi/uvicorn/requests는 이미 설치돼있음 — stockbrain과 공유)
python3 -m pip install --user --break-system-packages openpyxl google-genai

# 3) 자격증명
sudo cp deploy/shopping-shorts.env.example /etc/shopping-shorts.env
sudo nano /etc/shopping-shorts.env   # DASH_PASS, APIFY_TOKEN~4 채우기
openssl rand -hex 32                 # DASH_SECRET용
sudo chmod 600 /etc/shopping-shorts.env

# 4) systemd
sudo cp deploy/shopping-shorts.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shopping-shorts
curl -s localhost:8849/healthz       # {"ok":true} 확인

# 5) Apache
sudo cp deploy/apache-shoppingshorts.conf /etc/apache2/sites-available/shopping-shorts.conf
sudo a2ensite shopping-shorts.conf
sudo apache2ctl configtest && sudo systemctl reload apache2

# 6) SSL
sudo certbot --apache -d shoppingshorts.duckdns.org --non-interactive --agree-tos -m <이메일> --redirect
```

## 갱신·운영
- **자동배포**: `git push`만 하면 서버 크론(`deploy/auto_deploy.sh`)이 `shopping_shorts/` 변경
  감지 시 `shopping-shorts` 서비스만 재시작(stockbrain은 안 건드림, 2026-07-09 분기 수정).
- 수동 즉시반영: `git pull --ff-only origin main && sudo systemctl restart shopping-shorts`
- 비번 변경: `/etc/shopping-shorts.env` 수정 → `sudo systemctl restart shopping-shorts`
- 로그: `journalctl -u shopping-shorts -f`
- Apify 계정 4개 로테이션 — 하나 소진되면 자동으로 다음 계정 사용(시작 거부·실행중 소진 둘 다 대응)

## 매일 유튜브 자동수집 타이머 (2026-07-25)
무료 경로(계정·키워드·카테고리 프리셋)만 매일 1회 자동 수집 → 랭킹·가속 갱신.
`git pull`로는 systemd 유닛이 설치 안 되니 **서버에 1회 설치**한다(이후 코드 변경은 자동배포로 반영).
```
# 서버 시간대 확인(UTC면 OnCalendar을 23:10로, KST면 08:10 그대로)
timedatectl
sudo cp deploy/shopping-shorts-collect.service /etc/systemd/system/
sudo cp deploy/shopping-shorts-collect.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shopping-shorts-collect.timer
# 즉시 1회 테스트: sudo systemctl start shopping-shorts-collect.service
#            로그: journalctl -u shopping-shorts-collect -n 30
# 다음 실행시각: systemctl list-timers shopping-shorts-collect.timer
```
스크립트 본체 = `scripts/daily_youtube_collect.py`(HTTP 우회, `service.collect("youtube")` 직접).

## 인스타 자동수집 타이머 (2026-07-29)
Playwright 무료 경로(세션쿠키+서버직결, `INSTAGRAM_SCRAPER=playwright`)로 하루 3회(09/15/21시 KST)
자동 수집 → 랭킹·가속 갱신. 서버에 이미 `/etc/shopping-shorts.env`의 `INSTAGRAM_SCRAPER=playwright`와
`INSTAGRAM_SESSION_PATH=/home/ubuntu/instagram_session.json`이 설정돼 있어야 무료 경로로 돈다
(비어 있으면 기본값 apify=유료로 폴백하니 배포 전 서버 env를 확인).
```
sudo cp deploy/shopping-shorts-instagram-collect.service /etc/systemd/system/
sudo cp deploy/shopping-shorts-instagram-collect.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shopping-shorts-instagram-collect.timer
# 즉시 1회 테스트: sudo systemctl start shopping-shorts-instagram-collect.service
#            로그: journalctl -u shopping-shorts-instagram-collect -n 30
# 다음 실행시각: systemctl list-timers shopping-shorts-instagram-collect.timer
```
스크립트 본체 = `scripts/daily_instagram_collect.py`(HTTP 우회, `service.collect("instagram")` 직접).
세션쿠키 만료 시 재발급 절차: handoff/AI픽자동적재.md "세션 만료 시 재발급 절차" 참고.

## 인스타 신규채널 발굴 타이머 (2026-07-30)
"신규채널 픽업"(discover.html) 화면의 카테고리별(#주방템·#살림템·#인테리어·#자취템·
#생활꿀템·#뷰티템) 검색→릴스수집→팔로워조회를 매일 07:00 KST 자동 실행 후, 발굴 전부를
사람 확인 없이 `discovered_channels`에 자동 등록한다(사장님 지시, 2026-07-30). 09:00
인스타 자동수집(`shopping-shorts-instagram-collect.timer`)보다 2시간 앞서 돌아,
새로 발굴된 채널이 그날 09시 레퍼런스랭킹 수집부터 바로 반영되게 순서를 맞췄다.
무료 Playwright 경로(`INSTAGRAM_SCRAPER=playwright`, 릴스수집과 동일 킬스위치) —
과금 없음. max_total=300(기존 화면 기본 40, 상한 120에서 대폭 확대).
```
sudo cp deploy/shopping-shorts-instagram-discover.service /etc/systemd/system/
sudo cp deploy/shopping-shorts-instagram-discover.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shopping-shorts-instagram-discover.timer
# 즉시 1회 테스트: sudo systemctl start shopping-shorts-instagram-discover.service
#            로그: journalctl -u shopping-shorts-instagram-discover -n 30
# 다음 실행시각: systemctl list-timers shopping-shorts-instagram-discover.timer
```
스크립트 본체 = `scripts/daily_instagram_discover.py`(HTTP 우회, `discover_jobs._run(..., auto_register=True)` 직접).
⚠️ 소요시간이 김(300개 × 릴스수집+프로필조회, 실측 6채널=99초 → 300개는 대략 40~80분대
예상, 07시~09시 사이 2시간 여유). 최초 배포 후 1회는 반드시 수동 테스트로 07~09시
사이에 끝나는지 실측 확인할 것.

## 동시 처리(고객이 겹쳐도 안 느리게) — 2026-07-30

한 명이 제작하는 동안 다른 고객이 기다리던 구조를 없앴다. 순서대로 적용한다.

```
① DB WAL — 코드에 들어감(store._conn이 매 연결에서 PRAGMA journal_mode=WAL).
   ⚠️ 이게 없으면 워커를 늘리는 순간 'database is locked'가 터진다(실측 선행조건).

② 워커 복제 — 템플릿 유닛으로 원하는 개수만큼:
   sudo cp deploy/shopping-shorts-worker@.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now shopping-shorts-worker@1 shopping-shorts-worker@2 shopping-shorts-worker@3
   (기존 shopping-shorts-worker.service는 그대로 둬도 되고, 템플릿으로 갈아타면 stop/disable)

③ ffmpeg 스레드 상한 — /etc/shopping-shorts.env 에 추가:
   FFMPEG_THREADS=2        # 4코어 + 워커 3개 기준. 미설정이면 제한 없음(=기존 동작)

④ 확인:
   systemctl list-units 'shopping-shorts-worker*'
   sqlite3 없이: python3 -c "import sqlite3;print(sqlite3.connect('shopping_shorts/data/reference.db').execute('pragma journal_mode').fetchone())"
```

**공평 분배**: `job_queue.owner`(계정) + `prio`(우선순위)가 붙었다. 한 계정은 동시에 1건만
처리되고, 고객이 기다리는 작업(render·mix)이 배경작업(prewarm·overseas)보다 먼저 나간다.
즉 워커 N개면 **서로 다른 고객 N명**이 동시에 진행된다(같은 고객이 큐를 독점하지 못한다).

**서버 사이징**(실측 기준): 렌더 1건당 ffmpeg 약 0.7코어, 병목은 메모리(2GB에서 swap 상시).
동시 3~4명이면 4 vCPU / 8GB가 최소선.
