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
- 코드 업데이트: `git pull && sudo systemctl restart stockbrain`
- 비번 변경: `/etc/stockbrain.env` 수정 → `sudo systemctl restart stockbrain`
- 로그: `journalctl -u stockbrain -f`

## ⚠️ 주의
- 지인이 접속할 때마다 **당신 KIS 시세 쿼터** 소모 (인원 많으면 시세 끊길 수 있음)
- 수급빈집·태린이 지표는 당신 자산 — 무료 공개 범위 유의
- 폰: 로그인 후 `stockbrain.duckdns.org` → "홈 화면에 추가"로 앱처럼 사용 (반응형 적용됨)
