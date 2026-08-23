# 트랙: API매뉴얼 (고객용 API 발급 안내)

## 2026-08-23 — ✅ 라이브 (커밋 7989199ca, main 병합 확인)

**사장님 지시**: 가입 안내문에 있는 "API 발급 전체 매뉴얼 링크"의 실물을 만든다.
단계별로, 링크 경로와 그림을 넣어 최대한 쉽게.

- `shopping_shorts/static/api_manual.html` 신설 → 라이브 주소 `/api_manual.html`
  - 캡컷 매뉴얼(`capcut_manual.html`)과 같은 집: 640px·19px 본문·단계 카드 +
    화면 모양을 그린 **인라인 SVG**(외부 이미지 0개). 다크모드 대응.
  - 서비스별 앵커: `#gemini` `#elevenlabs` `#serpapi` `#vmake` `#youtube`
    (settings.html의 `SERVICES[].id`와 **글자 그대로 일치**해야 한다)
- `settings.html` 서비스 카드에 `📖 그림으로 보는 발급 방법` 버튼 추가.

### 코드에서 실측해 넣은 사실 (추측 아님 — 고치면 매뉴얼도 같이 고쳐라)

| 사실 | 출처 |
|---|---|
| Vmake만 값이 2개 → `앱키:시크릿` 한 줄 | `vmake_client._split_key` |
| 유튜브 키는 **YouTube Data API v3 사용설정**을 해야 산다 | `app.py _probe_user_key` |
| SerpApi 검색 1번 = **3회** 소모 → 무료 250회 ≈ 83번 | `lens_discover._MAX_CALLS_PER_SEARCH` |
| 무료분 소진은 `bad`가 아니라 **`empty`**로 따로 뜬다 | `app.py _key_status` |
| 키 등록은 `BYOK_MASTER_KEY` 없으면 **기능이 꺼진다** | `keycrypt.enabled()` |

### ⚠️ 함정 (실제로 밟았다)

**`<meta charset="utf-8">`가 없으면 한글이 통째로 깨진다.** 라이브(FastAPI StaticFiles)는
charset을 붙여줘서 안 깨지지만, **로컬 파일·다른 정적서버로 열면 깨진다**.
`capcut_manual.html`에도 지금 charset이 **없다** — 같은 함정이 남아 있다.
정적 검토로는 절대 안 보인다. **브라우저로 열어야 보인다.**

## ⏭ 다음

- [ ] **사장님 육안** — `/api_manual.html` 열어 5개 다 맞는지, 특히 Vmake·유튜브 화면이
      실제와 다르지 않은지. 다르면 그 SVG만 고치면 된다.
- [ ] 모바일 폭(360px)에서 안 깨지는지 — **확인 안 했다**(PC 폭만 봤다)
- [ ] 실제 발급 화면 **스크린샷**으로 SVG를 대체할지 결정. 지금은 그림(SVG)이라
      외부 사이트 UI가 바뀌어도 안 깨지지만, 실물과 다르면 헷갈린다
- [ ] `GUIDE_VIDEO`(settings.html)는 아직 **전부 빈 값** — 영상 만들면 그 한 곳만 채우면 버튼이 산다
- [ ] 가입 안내문의 `[API 발급 매뉴얼 링크]`를 `https://<도메인>/api_manual.html`로 교체
- [ ] `capcut_manual.html`에도 charset 추가(같은 함정)
