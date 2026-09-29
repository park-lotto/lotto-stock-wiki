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

## Higgsfield API 내부 시험

관리자 화면의 `Higgsfield 시험실`에서 공개 상품 이미지 URL을 5초·720p 영상으로
시험할 수 있다. 일반 웹 구독이 아니라 Open Higgsfield API의 별도 잔액을 사용한다.

- 권장: 시험실의 `결제 후 API 키 연결`에서 Key ID와 Key Secret을 등록한다.
  기존 `BYOK_MASTER_KEY` 기반 암호화 저장소에 보관되며 평문은 다시 표시하지 않는다.
- 환경변수 방식도 지원한다: `HIGGSFIELD_API_KEY_ID`,
  `HIGGSFIELD_API_KEY_SECRET`을 모두 등록하면 암호화 저장소보다 우선한다.
- 키와 공급자 상태 URL은 브라우저에 전달하지 않는다.
- 현재는 관리자 내부 검증 전용이며 고객 포인트를 실제 차감하지 않는다.
- 동시에 한 건만 실행해 공급자 비용 폭주를 막는다.

## 탭
- 📊 전체: 댓글수 / ⚡ 속도: 시간당 댓글 / 📈 가속: 어제 대비 증가속도 변화 / 💥 참여밀도: 댓글÷팔로워
