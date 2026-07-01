# NEXT SESSION

**날짜**: 2026-07-01 | **PC**: 집PC

## 세션 요약
- API 에러 텔레 알림 추가 (atomizer._tg_alert)
- 뉴스 키워드 크롤 v2 설계+구현 (pipeline/news_keywords.json + keyword_news_server.py)
  - 교차키워드(A×B) 방식, 중복제거, 광고필터, 하루 2회 텔레 다이제스트
  - 서버 cron 08:20 / 15:40 등록 완료
- 텔레 6월 백로그 복구: 60파일 → 339원자
  - report_relay 외국주 드롭 버그 수정 (telegram_questionnaire.py)
  - 요약하는고잉 타입 report_relay→insight 수정
- Google Flow/$400 크레딧 vs Gemini API 구조 정리
- Gemini Omni 오디오 I/O 활용 방향 논의 (유튜브 자막없이 오디오 직접 처리)

## 완료 항목
- ✅ atomizer.py: _tg_alert (키로테이션⚠️/전소진🚨/RuntimeError❌ 텔레 발송)
- ✅ pipeline/news_keywords.json: 교차키워드 뉴스 크롤 설정
- ✅ pipeline/keyword_news_server.py: 서버 keyword_news.py 로컬 백업
- ✅ telegram_questionnaire.py: report_relay 외국주 → _foreign_sector_atom 분기
- ✅ telegram_channels.json: 요약하는고잉 insight 수정
- ✅ scripts/test_omni.py: Omni/Veo 영상생성 양경로 테스트 스크립트

## 미완료 / 다음 할 것
1. **텔레봇 언블록**: bot 8943764573 블락됨 → 텔레에서 언블락+/start 필요해야 뉴스 다이제스트 수신
2. **Omni 오디오 테스트**: test_omni.py에 --audio 경로 추가 (yt-dlp 봇차단 대체용)
3. **Veo 영상생성**: 무료쿼터=0 → paid billing 활성화 후 테스트 가능
4. **딸깍 market_flow**: 14워커 thundering-herd 버스트 미수정 (사용자 보류)
5. **Google Flow 웹**: $400 크레딧으로 첫 클립 제작 → Remotion 삽입 테스트

## 관련 파일
- `pipeline/atoms/atomizer.py` — _tg_alert
- `pipeline/news_keywords.json` — 교차키워드 설정
- `pipeline/keyword_news_server.py` — 서버 뉴스 크롤러
- `pipeline/atoms/telegram_questionnaire.py` — report_relay 외국주 처리
- `pipeline/atoms/telegram_channels.json` — 채널 타입맵
- `scripts/test_omni.py` — Omni/Veo 테스트
