# 쇼핑쇼츠 레퍼런스 랭킹

인스타 레퍼런스 채널 443개의 48h 이내 릴스를 강도별로 랭킹.

## 준비
1. Apify 계정 → API 토큰 발급 (console.apify.com → Settings → Integrations)
2. 환경변수 설정 (PowerShell):
   `$env:APIFY_TOKEN = "apify_api_xxx"`
3. (선택) 엑셀 경로 변경: `$env:SHORTS_EXCEL = "다른경로.xlsx"`

## 실행
```
python -m uvicorn shopping_shorts.app:app --port 8848
```
브라우저에서 http://127.0.0.1:8848 열기 → 「⚡ 지금 수집」 클릭.

## 무료 크레딧 아끼며 테스트
첫 테스트는 소량 채널만:
```
curl -X POST "http://127.0.0.1:8848/api/collect?limit=10"
```

## 탭
- 📊 전체: 댓글수 / ⚡ 속도: 시간당 댓글 / 📈 가속: 어제 대비 증가속도 변화 / 💥 참여밀도: 댓글÷팔로워
