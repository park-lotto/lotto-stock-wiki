# 크리에이티브 라이브러리 정본 지도

2026-09-11 로컬 main `16bc986f8` 기준. 운영 서버와 별도 폰트 수집 트랙은 이 실사의 범위 밖이다.

| 대상 | 현재 정본 | 현재 소비 경로 | 통합 원칙 |
|---|---|---|---|
| 등록 폰트 | `shopping_shorts/static/fonts.json` + `fonts/` | `app.py` 폰트 즐겨찾기, `produce.html` 웹폰트 | 원장과 실제 바이너리를 연결. CSS 적용·렌더 QA는 별도 |
| 모션 파일 | `assets/motion/manifest.json` + MOV | `motion_assets.py` | 실물의 SHA256을 버전에 반영 |
| 모션 팩 | `assets/motion/packs.json` | `motion_packs.py` | 자산 manifest와 수명주기를 분리 |
| 음성 프리셋 | `assets/voice_presets.json` + `voice_samples/` | `voice_presets.py` → 운영 DB seed | 샘플 재생 가능과 제공자 계정 사용 권리를 구분 |
| 장식 템플릿 | `deco_templates.py` | 생성기 → `static/templates/`, API·렌더 | 현재 ID 생성 순서 보존 |
| 장면 스타일 | `deco_frame.py`, `produce.html` 프리셋 | 장면 편집·이미지/영상 합성 | 중복 원장 전환 전 각 legacy 출처 보존 |
| 고객 장면/SFX | 운영 `reference.db.scene_assets` | `scene_assets.py`, `scene_match.py` | customer_id=0도 공용으로 추정 금지 |
| 대본 패턴 | `reference.db` pattern/spine 테이블 | `pattern_bank.py`, 스타일 생성 흐름 | 근거 예시와 재사용 구조 구분, 원문을 공개 카탈로그에 노출 금지 |
| 연구 효과 후보 | `effect_mining/`의 별도 연구 저장소 | 워커·후보 생성 | 연구 승격을 고객 배포 승인으로 해석 금지 |

`assets/`는 `shopping_shorts/assets/`의 약기다. 경로는 실제 코드·파일을 확인했다.

## 실제 파일 검사

`tools/audit_creative_sources.py`를 로컬 main과 루트 DB를 명시하여 실행했다. 등록된 폰트 40개, 모션 4개, 음성 샘플 65개 모두 파일 존재와 SHA256을 확인했다. 폰트 40개는 fontTools로 읽혔으며 지정된 한글·숫자·영문 견본의 누락 글리프가 없었다. 모션 4개와 음성 65개는 ffprobe 메타데이터 파싱이 성공했다.

모션은 qtrle/argb이며 swipe 계열은 720×1280, sparkle 계열은 300×300이다. `ph_` 두 파일은 이름상 placeholder 계열이므로 정식 팩 품질 승인과 구분해야 한다. 실제 움직임·음향 품질과 라이선스는 이 파싱 결과로 승인하지 않는다.

로컬 DB는 scene_assets 0, spine 0, pattern_item 37, pattern_source 13, script_usage 0이다. 서버 자산 부족이라는 결론으로 확대하지 않는다.

재현 명령:

```powershell
py -X utf8 tools/audit_creative_sources.py --repo "<저장소 루트>" --db "<루트 reference.db>" --technical --output "<새 보고서.json>"
```

실측 원본: `2026-09-11-source-audit-v2.json`(미등록 파일 조사 포함). 물리 폰트는 41개이며 `OkMallangW.ttf` 1개가 `fonts.json`에서 빠져 있다. 최초 보고서도 보존한다. 파일 파싱, DB 행 수만 기록하며 고객 원문은 내보내지 않는다. 기존 출력 파일 덮어쓰기와 누락 DB 생성은 거절한다.

추가 독립 확인: 등록 폰트 중 완성형 한글 11,172자를 전부 담지 않은 것은 10개다. 지정 견본이 통과했다고 모든 한글을 지원한다고 해석하면 안 된다. OS/2 weight=400은 27개이나 디스플레이 폰트의 실제 시각적 굵기와 반드시 같지는 않으므로, 이 수치로 제목용 부적합을 판정하지 않는다. 미등록 `OkMallangW.ttf`는 실제 한글 완성형 글리프가 0개다. 이를 한글 제목용으로 자동 등록하지 않는다.

## 코어 통합 조회와 이 도구의 범위 차이

기술 실사 도구는 파일 원장 3종과 DB의 익명 행 수만 검사한다. 공통 카탈로그는 6종 어댑터로 기존 레이아웃·대본 구조·고객 장면·DB 음성까지 권한에 따라 읽는다. 따라서 두 도구의 항목 합계는 같아야 하는 수치가 아니다.

최종 로컬 카탈로그 실측은 공용141개(폰트40/레이아웃29/모션6/음성66), 관리자143개다. DB를 생략하면140개다. DB의 tuned 테스트 음성2개는 일반 목록에서 숨기고 관리자 실사에만 보인다. 파일 원장에 없는 curated DB 행1개는 정본 불일치 제약을 붙여 실사에서 확인할 수 있게 한다. 이것들은 운영 승인 팩 개수가 아니다.

실제 루트 DB 연결로 한글 검색, legacy lookup, 반복 fingerprint 일치, 조회 전후 DB SHA256 무변경을 확인했다. 서버 실행·시각 렌더·음향 청취 검증은 수행하지 않았다.

## 아직 남은 실사

- 별도 폰트 수집 트랙과 운영 등록 폰트 연결, 파일별 권리 증빙
- 서버 운영 DB/자산의 읽기 전용 비교
- 장면 프리셋 전체 실제 렌더, 원본 잔여물·한글 타이포·자막자리 검수
- 음성/SFX의 실제 청취와 모션 재생, 소리·동작 타점 검증
- 영속 객체 저장소 위치, 백업 복원, 승인·릴리스 writer 설계

실사 도구는 새 정본이 아니라 진단용 파생 보고서다. 공통 카탈로그는 legacy 어댑터로 원본을 읽는다.
