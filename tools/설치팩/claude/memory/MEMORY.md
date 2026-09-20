# Memory Index

## 쇼핑쇼츠(숏템탑스) — 활성
- [★꾸미기 자막잔존은 브라우저 캐시였다](reference_꾸미기_자막잔존은_브라우저캐시였다.md) — 서버는 청소본에서 뜨고 있었다. 주소가 청소 전후로 같아 옛 그림이 남음. 판정=beatframes 파일 태그(_src/_clean). 파일명을 가르면 주소도 갈라라(?v=fkey)
- [★자동저장이 오려낸 조각을 지운다](reference_자동저장이_오려낸조각을_지운다.md) — "완성본 만들어도 자막제거·꾸미기 반영 안 됨"의 뿌리. scene_lab이 사람 없이 1.2초마다 apply를 쏘고, EXTRA 없이 보내면 film_ 조각이 소멸 → 편성 서명이 바뀌어 방금 만든 청소본이 즉시 무효. 판정=렌더 스냅샷 plan.json과 현재 재료 대조. ★DEPLOY_NOW는 pull 시간창용이라 웹 재시작 연기는 못 푼다
- [장면 중복=설명 겹침으로 판정(phash 불가)](reference_scene_dup_by_desc_not_phash.md) — 실측 465쌍: 같은장면 거리11 vs 다른장면 거리13이라 DUP_MAX 못 올림. 자카드 0.6으로 3곳 통일. 하드차단 금지(재사용 폴백이 더 나쁨)
- [장면편집 실측 경로](reference_shopping_shorts_scene_lab_verify.md) — 로그인게이트 우회=/scene_lab.html?job=<id> 단독 열기. let/const는 window에 없음→contentWindow.eval. 편성 스냅샷·복구 필수
- [채널스타일 3각(trio) 라이브](project_채널스타일_시스템.md) — 메종/채이/스탠다드 후보별 배정. 본체=리라이트 2차패스(생성프롬프트만으론 실패). style_penalty로 추천 보호. 잔여=가명UI·믹스확장
- [제미니 키 운영 체제 25키+예약2](project_gemini_key_ops_2026_08_04.md) — 사장님 키 계속 추가(메모장→KEY_26+, 상한30). 태거=BULK_MODE 예약분리. 반영절차·리셋시점 함정 기록
- [레퍼런스랭킹 5플랫폼 확장](project_레퍼런스랭킹_5플랫폼.md) — 인스타→5토글. Phase1(틱톡 무료 yt-dlp 자동랭킹)+통합관리페이지 /refs(엑셀식 일괄등록, 기존API재사용) 라이브. Apify금지·숏폼만. ★유료끄며 월예산게이트가 무료수집 429차단 버그 스킵. ★틱톡 랭킹 계정들은 옛 키워드캐시-account시드 0개. 다음=틱톡 실등록테스트·P2유튜브채널·P3 CN담기랭킹
- [유튜브 쇼츠 차단=데이터센터IP만](reference_youtube_shorts_datacenter_block.md) — 쿠키·우회 다 기각, 주거용IP는 쿠키없이 됨(실측). 제보시 로컬PC 실측으로 즉판별. 해법=프록시(추천)/로컬릴레이
- [해외HOT Reddit 익명RSS 429=데이터센터IP](reference_reddit_anon_rss_datacenter_429.md) — 완료0건 뿌리=AWS IP 익명RSS 429(계정나이 아님). OAuth앱생성은 신규계정이라 막힘(about.json 확정). 백오프 라이브(0→24, 부분). 진짜=프록시/OAuth(숙성계정)
- [조용한 폴백+파이프라인 되돌림=쳇바퀴 뿌리](reference_silent_fallback_pipeline_undo.md) — "고쳤는데 그대로"면 코드 전에 그 job이 실제 탄 경로 실측(candidates_json·503로그·voice스냅샷). 처방=P1 폴백 명시화+P2 렌더직전 불변식 게이트(승인대기)
- [목업이 정본 — 실렌더 대조](feedback_mockup_is_source_of_truth.md) — 사장님 final-mock-*이 정본, 실브라우저 대조 구현. 오브바=라벨+진행선 8단계. "모든페이지 v6틀로"
- [생성 순응 검열(라이브)](project_생성순응검열.md) — 은행이 실제 대본 형성했나 매 job 관측. 3층+샘플LLM 신호등. SDD 8태스크 라이브. 후속=흡수성공률
- [제작소 간단편집강화](project_제작소_간단편집강화.md) — 버튼식 간단편집. 문장별 트림 라이브, 발견성 문제. 다음=완성본화면 편집노출·문장 재녹음·순서·트림UI
- [레퍼런스정보 출처표시(라이브)](project_레퍼런스정보_출처표시.md) — 렌즈+제작소 카드에 채널·구독자·댓글·캡션. 유튜브 자동, 비유튜브 Apify 스텁. 후속=Apify실조회·no_data캐시
- [자막제거 하드섭 리무버(판매용)](project_자막제거_하드섭리무버.md) — VSR fork+LaMa 품질검증 완료. Desktop\자막제거. 다음=속도·영역자동·클라우드
- [track finish 겹쳐돌리기 금지](reference_track_finish_no_overlap.md) — `_merge-` 스테이지 공유라 겹치면 가짜 충돌. prune은 폴더 안 지움→rm -rf. 라이브안전=origin/main 조상여부
- [프리즈 재발=두더지잡기 뿌리](reference_freeze_whackamole_root.md) — 틈 채우는 방법만 매번 바꿔 재발. 진짜fix=fill 실TTS 재보정+conform. "프리즈 고쳤다" 보고 조심
- [mix 단계 무한멈춤=staleness 가드 누락](reference_mix_stage_staleness_gap.md) — 재시작이 BackgroundTask 죽이면 상태 고착. _render_is_stale을 단계마다. 새 단계 추가시 잊지말것
- [CapCut draft 포맷 역공학](reference_capcut_draft_format.md) — 웹앱+showDirectoryPicker 직접쓰기. draft_content.json 구조=design 부록A. T1 ZIP 라이브. device_id 커밋금지
- [브랜드 이름 = 숏템메이커](project_brand_name_shottemtops.md) — 숏템탑스·숏템박스 아님(08-30 정정). 도메인 stmaker.kr로 서비스 본체 이전 예정
- [유료게이트+구글OAuth 라이브](project_유료게이트.md) — deny-by-default·계정별크레딧·OAuth(sub 매칭). ★admin 백도어 교훈(DASH_PASS 빈값)
- [회원승인 화이트리스트](project_회원승인_화이트리스트.md) — 승인자만 사용. Task1~6 완료, Task7~8·finish 남음. create_customer 기본 approved=True 유지가 핵심
- [진짜 목표=백본인터리브](feedback_anchor_to_real_goal_backbone_interleave.md) — 백본(순서·싱크앵커)+비트별 best-of-N화면+말투변주. 게이트=A7 행위커버율 실측
- [부품은행(대본 학습층)](project_pattern_bank_script_layer.md) — Phase0+1 라이브. 스파인 승격게이트 source≥3+사람승인·R4필터·Gemini 주입점. 다음=큐레이션UI·Phase2
- [대본자유·화면교차고정](feedback_대본자유_화면교차고정.md) — 2026-08-03 사장님 확정: 대본은 한 소스만 써도 됨(각색이 본체), 화면 교차 규칙은 절대 불변
- [장면 스파인 먼저(라이브·검증완료)](project_scene_spine_first.md) — 카테고리5+스파인템플릿, 태깅장면 슬롯순서 먼저배치→대본 나중. ★실측검증 성공(job cfba13cc: 순서 문제→해결→결과→CTA, 장면↔멘트 맞음). 남은건 문장표현 품질(말투)=별건. B1추출은 플래그off 보류
- [검증안된 플래그 라이브 켜지마라](feedback_no_unverified_flag_in_live.md) — B1 프레임추출을 미검증 라이브점화→제미니503+폴백없음→대본 빈구조 에러. 플래그뒤 기본off·라이브밖 실측후 켜기·문제시 즉롤백
- [제작소 2트랙 모델(장면스파인)](project_scene_spine_2track.md) — 화면=시간순 스파인/대본=스토리. P1 슬로우제거·P2 시간순 라이브. 후속 P2b·P3앵커·P5
- [샤오홍슈 담기 토큰앵커+yt-dlp 경로](feedback_xhs_grab_token_anchor_and_ytdlp_path.md) — 반복실패 제보엔 실경로 브라우저 재현+서버DB 실측. 오진 3회 뒤 해결
- [렌즈 CN 검색](project_lens_cn_search.md) — 한국어→중국어 Gemini 번역 필수. Apify 실필드 함정(썸네일 스프라이트 등). 서버서 probe
- [제작소 어긋남구제(스왑버튼)](project_제작소_어긋남구제.md) — fit≤2 빨간버튼→썸네일 탭 교체. 후속=신호등·글자카드·라이브러리
- [발음교정 전역사전+작업대(라이브)](project_발음교정_전역사전_작업대.md) — 서버DB global_pron_dict+관리자작업대+loudnorm+best-of-2. 잔여=UI 브라우저 그라운딩
- [딸깍/시니어 북극성](feedback_ttalkkak_senior_northstar.md) — 편집은 원클릭, 시니어 타깃. 편집 빼지 말고 슬라이더 대신 버튼
- [쇼핑쇼츠 코드점검(P0)](project_shopping_shorts_code_audit.md) — P0 5건 라이브. 지시서 맹종=옛 사고 재발. 다음=P0-7 XSS
- [쇼핑쇼츠 자동화](project_쇼핑쇼츠_자동화.md) — 소스매칭: 임베드 폐지→링크전용(채널×키워드×언어)
- [틱톡 키워드검색 발굴(Apify B2)](project_tiktok_keyword_discovery.md) — Apify $1.70/1000 채택, 노브3개 설계확정 코드만 남음
- [쇼핑쇼츠 채널 발굴·정리](project_shopping_shorts_discovery.md) — 완성·배포. 미결=팔로워 Apify 403. 핸드오프 발굴_NEXT.md

- [키 로테이션이 통째로 놀았다](reference_gemini_key_rotation_never_ran.md) — 키 12개인데 1개만 사용(_current_key_and_idx가 늘 live[0]). 페이서를 만들고 호출부 15곳이 옛 함수를 부름. "고쳤다" 주석 말고 호출부를 grep하라
- [프롬프트가 말해도 아무도 검사 안 하면 안 지켜진다](reference_prompt_says_but_nobody_checks.md) — EDL이 확정 대본에 없는 문장 창작. 처방=프롬프트 강화가 아니라 저장 단일출구 불변식(fail-open)
- [나머지 통 이름이 회귀를 숨긴다](reference_catchall_bucket_hides_regression.md) — not_found=죽은채널로 두 번 오독(08-09·08-17), 진짜는 고정 2.5초 대기. 실패율은 코드 주석 기준선(2.6%)과 대조. 재시도 먼저 붙이면 회귀를 덮는다
- [★slice 이모지 반토막→URIError→전체 빈 화면](reference_slice_이모지_반토막_URIError_전체빈화면.md) — '다 지워졌다'는 데이터 무사, 카드 1장 예외가 목록 전체를 죽임. 코드포인트 slice+try/catch. ★Bash heredoc의 역슬래시n은 실제 개행으로 들어간다(chr(92)로 우회)
- [렌더 예외가 '버퍼'처럼 보인다](reference_render_crash_looks_like_buffering.md) — 탭·지표·카테고리 안 먹힘 4증상이 toFixed 예외 1개. 제보 받으면 콘솔부터. thumb/thumbnail 이름 어긋남도 같은 날
- [어휘축 단독신호 함정](reference_어휘축_단독신호_함정.md) — '주방'(08-19)·'만들기'(08-21)가 같은 함정. 한 번 배운 교훈을 같은 모양의 다른 단어에도 적용하라. 정확도를 자동카테고리로 재지 말 것, 채널 문턱≠영상 문턱

- [쓰레드 수집 축(라이브)](project_쓰레드수집.md) — 로그인 불필요, ★헤더가 열쇠(Accept·Sec-Fetch 빼면 껍데기). 캐러셀은 carousel_media 안에 영상. 담기 성공≠제작 가능(download_any 화이트리스트 세트로 확인). 문턱 미정
- [QR 링크가 재시작마다 죽었다](reference_share_link_memory_dies_on_restart.md) — 단축 sid가 프로세스 메모리 dict라 자동배포 재시작에 전멸(403). DB 이관 후 라이브 3경로 200. "링크 만료" 제보엔 TTL 말고 저장소가 메모리인지부터 봐라
- [인스타 슬롯조립 다이소축](project_인스타_슬롯조립_다이소축.md) — 템플릿고정+재료갈아끼우기, 모델호출0회. 한국5편 7/7·중국3편 5/7 실측. ★쿠팡 안씀(다이소146편중 product_facts 0편). 엔진공용·슬롯표만 분리. 미결=장면근거 게이트
- [인스타는 음성=스토리/화면=시연 분리](reference_인스타_음성스토리_화면시연_분리.md) — 대사에 사람 나오는 컷 49개중 화면에도 나온건 1개(2%). 장면슬롯 4종이면 어떤 스토리든 얹힌다. 장면게이트는 사물슬롯에만(가격·효과는 화면에 없는게 정상). 어간2글자로 매칭
- [꾸미기 '내용물 있는 틀'](project_꾸미기_내용물있는틀.md) — 빈 색띠→채널명·☰🔍·[광고]·제목·조회수. ★미리보기와 렌더가 같은 그림 파일(deco_frame 한 곳). 폰트·크기 조절은 이미 있음(접힘 문제). two_lines는 거른 뒤 접으면 중복제거 무력화. 남은=B 형광훅·C 카드형

- [제작소 단계바 도크형(라이브)](project_제작소_단계바_도크.md) — 동그라미+선→무지개띠+색아이콘. ★되돌리기=renderSteps() 한 곳(옛 orbbar CSS 남김). 단계 늘리면 배열 4개(LABELS·COLORS·ICONS·SHORT) 다 늘려야(안 그러면 조용히 회색). SEO해시테크→제목·태그 / 최종렌더→완성본. final-mock-v6는 "정본"인데 7단계 시절에 멈춰 썩어 있었다
- [영문전용 폰트가 한글목록에=두부](reference_영문전용폰트가_한글목록에_두부.md) — 최종렌더 네모X의 뿌리는 깨진 파일이 아니라 영문전용 폰트(옥말랑, 한글 0자)를 한글목록에 넣은 것. 파일 존재만 보는 검사는 못 잡는다. 판정=.notdef 마스크(Pillow만·fontTools 없음). 공백은 제외(빙그레 우회와 충돌). 한글판 옥말랑은 없다(W·B 둘 다 영문)
- [★async 핸들러 블로킹이 "남탓" 에러로 보인다](reference_async핸들러_블로킹이_남탓처럼_보인다.md) — Buffer "Video could not be read from its URL"의 진짜 원인은 async 핸들러가 blocking 호출로 이벤트루프를 10초 멈춘 것. HEAD/Range/faststart 3번 오진. ★"내 스크립트는 되는데 화면은 안 된다"는 차이 자체가 답. 판정=상대 요청 도착시각 vs 우리 응답 완료시각 대조
- [모드 클래스에 자리와 취향이 섞였다](reference_모드클래스에_자리와_취향이_섞였다.md) — scene_lab body.tight에 배치·높이·overflow가 함께 묶여 [넓게]가 틀을 무너뜨렸다. body.MODE와 body:not(.MODE) 양쪽 전수 grep. ★반쪽 수정을 세 번 나눠 배포해 2차 사고
- [★.main{overflow:auto}가 sticky를 죽인다](reference_main_overflow가_sticky를_죽인다.md) — produce.html previewSlot 3곳이 처음부터 무력이었다. 스크롤조상 자리는 차지하고 정작 scrollHeight==clientHeight. 진단=그 조상이 진짜 스크롤되는지부터. collection·discover·index 등에 같은 함정 남음
- [목록에만 적힌 예외는 아무것도 안 막는다](reference_목록에만_적힌_예외는_아무것도_안막는다.md) — data-maskbox가 셀렉터엔 있고 요소엔 없어 예외가 통째 무력. 예외목록과 표식은 짝. ★같은 증상을 요소별로 두 번 막았으면 막는 방식 자체가 틀린 것(진짜 뿌리=클릭확대가 늘 켜짐)
- [★투명 체크박스가 track 아래 깔려 스위치 클릭 무효](reference_투명체크박스가_track아래깔려_스위치클릭무효.md) — label 밖으로 빼자 뒤 형제가 위에 그려짐. 판정=elementFromPoint(track중앙)==input. 자동화 좌표클릭은 배율에 어긋나니 hit-test로
- [아이콘은 확대해 눈으로 봐라](reference_아이콘은_확대해_눈으로_봐라.md) — 해시(#) 아이콘이 24x24에서 뭉쳐 ≠로 읽혔다. SVG 코드·전체 스샷으론 못 잡는다. zoom으로 실제 크기 확인
- [네이버클립 수집축(라이브)](project_네이버클립_수집축.md) — HTTP 2번(목록+card API)으로 조회수·mp4 직링크까지, 로그인·프록시 불필요. ★yt-dlp 불가(tv.naver.com은 옛 서비스). 한 키워드 천장 500건→키워드를 쪼갠다. 뷰티 2,935건. 해시태그는 적을수록 터진다(1~2개 31% vs 8개+ 5.6%)
- ["안 뜬다"는 데이터 0건일 수 있다](reference_안뜬다는_데이터0건일수있다.md) — 코드 의심 전에 수집 POST 호출 기록부터. ★랭킹 저장 위치=reference.db의 settings 테이블 key=last_run::<platform>(last_run 테이블 아님). 기본탭 48시간 필터·재시작 연기도 같이 확인
- [볼채널등록(개인 채널 즐겨찾기·라이브)](project_볼채널등록_개인채널즐겨찾기.md) — 회원용 순수 북마크. 전역 수집과 분리해 담아도 크롤 0 증가. 상한50·열때1회+6시간캐시. 남은=라이브 버튼 실동작·팔로워 미연결
- [★다시 그리기가 스크롤을 깎는다](reference_다시그리기가_스크롤을_깎는다.md) — innerHTML 교체 순간 안에 있던 필름이 사라져 clamp. 폭은 2.9초 뒤 복귀하지만 스크롤은 안 돌아옴. ★첫 진단('교체=리셋')은 실측으로 반증됨. rAF는 숨은 탭에서 멈춰 안 돎 → setInterval
- [★sticky 슬롯 안 도구 높이가 미리보기를 민다](reference_sticky슬롯_도구높이가_미리보기를_민다.md) — "미리보기 크기가 바뀐다"의 뿌리는 아래 줄나누기 칸이 82/123/164로 변해 슬롯이 1430/1471/1512로 튄 것. 상자는 460x818 고정. ★로딩 기다리고 전 구간 재라(12컷만 재고 '변화없음' 오답)
- [★청소본 시간축=청소 시점 편성](reference_청소본_시간축은_청소시점_편성.md) — 전/후 비교가 편집 뒤 또 갈림. 파생파일 초는 만든 시점 편성 좌표. 스냅샷+정본함수 하나. 비교는 컷 수(4소스→23컷), 프레임은 유료 0
- [★`not cid`로 로그인 판정하면 관리자가 막힌다](reference_로그인판정_not_cid는_관리자를_막는다.md) — cid==0이 falsy. 비로그인도 0 폴백이라 값으론 못 가른다. 정본=_verify_session의 None 여부. 브라우저에서 눌러봐야 드러난다

- [★인스타 3건 상한이 9건을 버렸다](reference_인스타수집_3건상한이_9건을_버렸다.md) — 한 번 열면 12건 오는데 3건만 씀(자르기만 하므로 12로 올려도 비용 0). 유실은 전부 C·D=물건 채널(70~77%). 등급제는 빈도만 정하고 카테고리는 안 본다. 랭킹 헛돎=하루 153채널 중 135개가 매일 같은 채널. ★fetch_limit은 정의만 되고 아무도 안 부른다
- [★계정을 한꺼번에 되살리면 묶인다](reference_계정을_한꺼번에_되살리면_묶인다.md) — 세션 10개가 같은 날(8/31) 죽은 이유. 인스타 조치 '여러 세션을 만들 수 없습니다'. 수집은 계정↔IP 1:1이지만 **로그인 순간의 IP는 그 PC 것**. 하루 1~2개씩 나눠 복구. 도구=tools/ig_session_from_firefox.py
- [신비한 시리즈 채널 확장](project_신비한시리즈_채널확장.md) — 건축이 되면 동물·식물(아이 교육용)·무기·연애로. 엔진은 도메인 층을 갈아끼울 수 있어야 하고, 시청자 연령도 함께 갈라야 한다

## 숏템메이커 로그인/계정
- [1기 모집 신청폼(구글폼)](project_1기모집_신청폼.md) — Apps Script rebuildForm()으로 링크 유지한 채 문항 교체. 77만원·카드 8/31 11시·카카오뱅크 3333-13-9497518. 환불=서비스개시후 불가(고지동의+귀책조항 필수). ★OAuth 승인 팝업은 사장님이 직접 눌러야 뜬다
- [사장님 로그인 이중신원](reference_shopping_shorts_admin_dual_identity.md) — 관리자비번=cid0(도서관31건 데이터 전부 여기)/구글=cid2(빈계정). 기기간 작업·AI PICK 안맞으면 admin으로 통일(이관 불필요). 고객은 구글단일이라 무관

- [쿠팡 재료는 PC 릴레이가 긁는다](reference_coupang_prefetch_relay.md) — 서버는 한국IP여도 403(지문 차단). 1단계에서 선수집→PC가 긁고 서버가 분석. ★배포해도 릴레이는 재시작해야 새 코드

- [★서버 0건은 헤드리스 차단일 수 있다](reference_서버0건은_헤드리스차단일수있다.md) — 4환경 갈라 재라(PC창 24개/PC헤드리스 0/서버xvfb 0/서버직결 0). 세션·IP 멀쩡해도 사이트가 서버환경을 거른다. except가 원인을 삼킴. 처방=PC 릴레이(kind 추가), 반환은 None과 [] 구분. ★세션 변수명 확인하고 보라(XIAOHONGSHU_SESSION_PATH)

## 쇼핑쇼츠 키/로테이션
- [도우인 수신=헤드리스 크롬만 가능](reference_douyin_download_headless.md) — yt-dlp 전 방법 실패(IP문제 아님). discover?modal_id SSR에서 서명 CDN 추출. hevc→h264 정규화·600초·동시2개 필수. DouyinBusy는 except Exception에 삼켜지니 주의
- [타입 확인 전 .strip() 금지](feedback_check_shape_before_string_ops.md) — 하루 라이브 500 3회. source_brief는 dict. ★새 데이터를 하류로 흘리기 전에 받는 쪽부터 읽어라(잠자던 버그가 깨어난다). 사고 뒤 전수리뷰는 남에게
- [태깅캐시 키 lens_ 접두사 불발](reference_extract_cache_key_lens_prefix.md) — "재태깅했는데 대본 그대로"의 진짜 원인. 틱톡은 lens_tiktok_<id>로 저장/<id>로 조회해 통째 불발(실측 1/3→3/3). 서버DB=reference.db(app.db 아님), 라이브API는 유료게이트 401
- [제작소 키죽음 403/401 로테이션 트랩](reference_shorts_key_403_permission_denied_rotation.md) — "키소진"은 오진, 실제=서비스계정 27/28 사망(401/403). is_account_disabled가 403 못잡아 죽은 live[0] 반복. 403추가+죽은키 우회 walk로 자동복구(라이브). 생사는 SDK로 판정, raw HTTP 무효

- [믹스확정이 원래대로 되돌아간다=고아 폴러](reference_mix_poll_orphan_undoes_confirm.md) — POST 200·preview ready인데 화면만 안내문. MIX_POLL 3곳이 앞 인터벌을 안 죽여 좀비가 매초 loadMixReview→상태 리셋. ★서버로그는 grep -a 없으면 통째로 놓친다. produce 게이트 하네스는 함수 부분집합만 실행
- [★확정대본 칸구조가 3단계로 안 넘어갔다](reference_확정대본_칸구조가_3단계로_안넘어갔다.md) — B안 8줄이 공백 통짜로 가서 훅에 두 줄 뭉침. 줄=칸 단위(s2ScriptLines·script_sentences·재조립). 제보엔 given_script 개행부터, 판정축에 개수
- [구어체 대본이 2덩이로 뭉쳐 칸에 꽂힌다](reference_구어체대본_문장분리_2덩이.md) — 마침표만 보는 문장분리가 8칸 대본을 141자·131자 2조각으로. resynth가 target_seconds 안 고쳐 초가 두 벌. "자막 안 맞는다/끝나면 반복" 제보엔 대본글자수·mp3실길이·target 셋 대조부터
- [말속도 상수가 여러 벌 = 길이버그 재발 뿌리](reference_말속도_상수_4벌.md) — edit_plan 5.7×1.44가 정본. script_gate는 단일화 완료, produce.html JS·backbone은 아직 사본. 초 계산은 상수 박지 말고 빌려 써라
- [★조립 빈칸이 문장을 깨다 — 생성기로 전환](reference_조립vs생성기_빈칸이_문장을_깬다.md) — 조립은 틀을 글자 그대로 써 조사·어미가 안 맞물린다. 생성기도 role 대조로 구조 강제됨 → 조립 이점은 모델호출 0회뿐. assemble_off=1로 끄기(배포 불필). 반환값 3개 주의. pattern_source 512건에 실제 대사가 있다
- [★브라우저 검증 3함정](reference_브라우저검증_인자형태와_타이머스로틀.md) — 인자 형태 짐작하면 검증 통째로 무효(객체 vs 문자열, [object Object] 키로 발각)·자동화 탭은 setInterval이 3초에 4회로 스로틀·고친 걸 되돌려 실패하는지 반드시 확인
- [★같은 이름으로 새로 만들면 기존 함수가 조용히 죽는다](reference_같은이름_함수를_새로만들어_기존것을_죽였다.md) — 만들기 전에 grep. 기존 함수·테스트에 "왜 그렇게 뒀는지"가 적혀 있다(칸 분할은 화면 중복 때문에 일부러 막아둔 것이었다)
- [하네스는 호출부 형태 그대로](feedback_하네스는_호출부_형태_그대로.md) — 하루에 라이브 500 두 번(sys를 내가 넣어줌 / 반환값 3개를 2개로). docstring 말고 호출부를 grep해 그 형태로 부른다. 되돌릴 스위치를 함께 만들어라

## git·인프라 교훈
- [캡처 이미지 Ctrl+V가 텍스트로 붙음=3겹](reference_클립보드_이미지붙여넣기_3겹.md) — ShareX F1 단축키별 설정·Windows Terminal Ctrl+V·PowerToys Advanced Paste 전역훅. 판별=STA 클립보드 포맷부터
- [게이트 간헐 실패=node stdin+가드 구멍](reference_gate_flaky_node_stdin_guard_hole.md) — pytest stdin 캡처 중 node 직접 호출→WinError 6. 금지 가드가 소문자 변수를 놓쳐 무력. ★게이트가 헛돌면 단독 실행으로 먼저 갈라라(단독 통과=오염). 가드는 실제로 잡는지 시험할 것
- [raw eol 병합레이스](reference_git_raw_eol_merge_renormalize.md) — raw/*.md 수백 충돌=eol-only. merge.renormalize true로 해소
- [git stash는 워크트리 공유](reference_git_stash_shared_across_worktrees.md) — stash 쓰면 남의 것 뽑음. 회귀비교는 커밋 후 diff
- [로컬 TTS 무음 mock 함정](reference_local_tts_silent_mock_trap.md) — 로컬 TTS=무음mp3, 길이 재면 거짓결론. config키+mean_volume 확인
- [auto커밋이 충돌마커를 라이브로](feedback_auto_commit_staged_conflict_broke_live.md) — 미해결 병합 add→JS SyntaxError. 게이트는 HTML/JS 못잡음
- [★자동배포는 새벽 2~6시에만 돌다](reference_자동배포_시간창_2시6시.md) — "push하면 3분 뒤 라이브"는 낮에는 거짓. 고객 접속 중이면 재시작도 연기. 급하면 touch DEPLOY_NOW(사장님 확인 뒤). 낮에는 0순위-A1 실측을 못 할 수 있다
- [배포 진실: 서버=main 추적](reference_deploy_truth_branch_ssh.md) — feat push는 서버 안 감. ubuntu@3.39.179.148, 키=crawling_bot_client
- [origin/main 반쪽커밋 크래시](feedback_origin_main_broken_by_half_commit.md) — 배포 전 origin import 검증
- [배포규율(사고교훈)](feedback_deploy_discipline_during_incident.md) — 재시작중 조작 금지, WorkingDirectory 확인, 새파일 같이배포
- [동시세션 커밋섞임](feedback_concurrent_session_commit_bundling.md) — 태스크 시작 전 git log 확인
- [공유워킹트리 브랜치 확인](feedback_shared_worktree_branch_check.md) — 커밋 전 git branch --show-current
- [공유파일 hunk 분리 커밋법](feedback_shared_file_hunk_isolation.md) — git apply --cached로 내 hunk만
- [SDD 공유작업공간 파일명충돌](feedback_sdd_shared_workspace_collision.md) — task-brief에 고유접두사 OUTFILE
- [윈도우 python 스토어스텁 PATH](reference_python_path_windows_stub.md) — WindowsApps 스텁 문제, PATH 재정렬함
- [크롬 확장 자동화 원천차단](reference_chrome_extension_automation_blocked.md) — chrome:// 페이지 자동화 불가, 사용자 직접클릭 안내
- [Gemini 프리뷰모델 쿼터 함정](reference_gemini_quota_preview_model.md) — 프리뷰는 쿼터 공유소진. 안정판으로 교체 먼저
- [Gemini/YouTube 예비키 10쌍](reference_gemini_youtube_key_reserve_2026_07_10.md) — 미배치 비상 예비. 소진사고 시 여기부터
- [Claude Max를 서버에서 호출](reference_claude_max_on_server.md) — claude -p 헤드리스(API과금X). 토큰 스테일 리스크
- [일부만 끊기면 계정차단 아님](feedback_partial_block_not_account.md) — 공개접근으로 소스 상태 먼저 확인

## 작업 방식(피드백)
- [★사장님께는 사장님만 답할 것만 묻는다](feedback_사장님께는_사장님만답할것만_묻는다.md) — 기술 결정을 묻지 마라. 돈·우선순위·방향·포기할것만. 방법은 내가 정하고 결과만 보고. 서브에이전트용 질문목록 노출 금지
- [★사장님 말을 받아적지 말고 스스로 발굴하라](feedback_사장님말을_받아적지말고_스스로_발굴하라.md) — 제보는 씨앗이지 명세가 아니다. memory 224건·handoff·git이력 전수로 훑어 항목을 발굴하고 "모르고 계셨을 위험 TopN"을 가져와라
- [★보고는 세 줄로](feedback_보고는_세줄로.md) — 결론 3줄 먼저(뭔게됐나/뭔걸믿나/다음뭐). 표·배율·표본수 나열 금지 — 물으면 그때. ⚠️"확인 못한 것"은 짧게라도 반드시
- [★프로그램 수정은 실제로 돌려보고 확실할 때만 '됐다'](feedback_프로그램수정은_실제로_돌려보고_확실할때만.md) — 사장님 규칙(09-04, CLAUDE.md 0순위-A1). 라이브 실제 job으로 진짜 저장·렌더까지. 주입·스텁·pytest는 중간 단계. 하루 3번 틀린 날의 교훈
- [★숨겨도 60대가 쓰기 편하게(모든 기능 전제)](feedback_숨겨도_60대가_쓰기편하게.md) — 첫 화면 3~4개+세부설정 2단, 일상어 이름, −＋·끌기, 되돌리기 상시 · [결과물은 바탕화면으로](feedback_deliver_outputs_to_desktop.md) — out/ 저장 후 Desktop에도 복사. 사장님이 바로 열게
- [묻지말고 진행](feedback_묻지말고_진행.md) — 방향 정해지면 빠르게 계속 · [끊지 말고 자율 진행](feedback_keep_going_autonomous.md) — 작은 결정은 추천대로 바로 실행
- [긴 작업 분할 원칙](feedback_break_long_tasks.md) — 조각내서 중간 검증 · [규칙은 파일에, 주문 강요 금지](feedback_rule_in_file_not_user_memory.md) — 사용자에게 외우게 시키지 말 것
- [기능명 표면의미로 넘겨짚지 말 것](feedback_confirm_literal_feature_intent.md) — 방향 확인 없이 큰 기능 만들지 말 것 · [실데이터로 검증](feedback_verify_with_real_data.md) — 합성fixture 통과≠완료
- [보고 전 직접 검증](feedback_self_verify_before_reporting.md) — DOM/API 직접 확인, 눈대중 금지 · [검증 후 주장·조작](feedback_verify_before_claim_and_act.md) — 짧은관찰로 hang 단정말것(진행중 게이트 죽인 사고). 파괴전 재확인, 완료주장…
- [하네스가 계약을 발명하면 0% 동작도 초록](feedback_harness_invented_contract.md) — 주입값을 실제 코드가 넣는지 grep 확인 · [whole-branch 리뷰가 seam 잡음](feedback_whole_branch_review_catches_seams.md) — SDD 최종 리뷰 생략금지
- [파생물을 원본 키에 저장 금지](feedback_derived_output_must_not_overwrite_source.md) — 쓰기 전 "이 키의 주인?" 물을 것 · [SDD 리뷰어는 Opus로](feedback_sdd_reviewer_model_opus.md)
- [쉬운 길 먼저](feedback_simple_before_complex.md) — 복잡한 인프라는 확인 후 · [토큰 절약 1번 규칙](feedback_token_conservation.md) — 출력 1줄 요약·단순=Haiku·대량=Gemini
- [모델 자동 분기](feedback_model_switching.md) — 단순=Haiku 위임 / 분석·창작=직접 · [MCP 최우선 사용](feedback_mcp_first.md)
## 주식위키·대시보드
- [User Profile](user_profile.md) — 20년 경력 주식 전문가, 채널 "로또의 주식" · [서비스 방향](project_service_direction.md) — "나는 이렇게 본다" 시각 판매. 정보정리+수급빈집+주도섹터강도
- [배포·호스팅](project_dashboard_deploy.md) — stockbrain1.duckdns.org 상시가동. market_flow KIS 이관 · [GitHub Pages 호스팅](project_hosting.md) — park-lotto.github.io. 도메인 미구매
- [크롤봇 서버+소스관리 대시보드](project_crawl_dashboard_server.md) — Lightsail 크롤+8090/sources 연동. 유튜브자막=Gemini · [크롤링봇 수신 폴더](reference_crawling_bot_data.md) — C:\Users\TheRose\crawling_bot_data\ ingest 시…
- [크롤링 인제스트 자동점검 v2](project_daily_ingest_autopilot.md) — 크론 가동중, 롤백 실증(v1 daily_verify 대체) · [원격 인제스트 자동화](project_remote_ingest_automation.md) — 원격 크론. atoms.db git추적 위험 미해결
- [텔레그램 인제스트 시스템](project_telegram_ingest.md) — 17채널 2층 원자. 미결=2채널 서버측 리드제한 · [뉴스타임라인 개편](project_news_timeline_enrich.md) — 다음=순환매감지기·공시형 enrich
- [뉴스 매칭 시스템](project_news_matching.md) — 섹터=네이버검색+must필수어·종목=네이버증권API · [스탁브레인 대시보드](project_stockbrain_dashboard.md) — SaaS MVP 완성·배포
- [딸깍 대시보드](project_ttalkkak_dashboard.md) — 장전버튼 완성. 장중·마감 남음 · [딸깍 스튜디오](project_ttalkkak_studio.md) — 브리핑카드 자동생성→텔레전송 완성
- [KIS 토큰 공유 문제](project_kis_token_sharing.md) — 앱키 공유→무효화. 자동재발급 일부만. 근본=앱키 분리 · [KIS 장애+서킷브레이커](project_kis_outage_2026_07_04.md) — kis_api 서킷브레이커+naver 폴백 전체 배선
- [골-루프 오케스트레이터](project_goal_loop_orchestrator.md) — Task1-2완료, 3-7 남음 · [인사이트 리디자인 v5](project_insights_redesign_v5.md) — 애플라이트 완성. 잔여 L1~L6 구조
- [인사이트허브→NotebookLM 다리](project_insights_notebooklm_bridge.md) — 완성·검증 · [네이버 종토방 여론분석](project_naver_board_sentiment.md) — 완성
- [위키 종합엔진](project_wiki_synth_engine.md) — 프로토타입 미완(수율14%). 쓸모 먼저 검증, 과설계 금물 · [사람 브레인](project_person_brain.md) — 태린이아빠 MVP완성. 2단계=질의엔진
- [원자 DB 구멍 해결 목록](project_atom_db_gaps.md) — 구멍1(자동ingest) 진행 중 · [Wiki Project](project_wiki.md) — L1·L2 완성, L3부터. GitHub 세팅 완료(project_github.md)
## 분석 원칙(주식)
- [위키 먼저](feedback_wiki_first.md) — · [이슈 먼저](feedback_issue_first.md) · [리서치 우선]… · [리서치 방법론](feedback_research_methodology.md) — 뉴스 단독 금지, 실제 주가 반응+날짜+재료강도
- [주가 상승 인과관계 검증](feedback_price_cause_verification.md) — 날짜+종목+이유 검색으로 확인 · [종목 언급 2단계 프레임](feedback_stock_pick_framework.md) — 1군 먼저, 2군 나중, 빠져나갈 구멍
- [종목 분석 규칙](feedback_stock_analysis_rules.md) — 후발주 2종, 데이터없으면 모른다고 · [종목 분석 논리 체계 v1](project_research_logic_v1.md) — 5단계
- [데이터 공백 = 틀린 분석](feedback_data_gap_analysis.md) · [매일 시장 냄새 맡기](feedback_market_smell.md) — 가는 놈이 더 간다, 4가지 매일 측정
- [반복 질문으로 파고들기](feedback_iterative_research.md) — Q10→Q11→Q12 확장 · [인제스트 1개씩 원칙](feedback_ingest_one_by_one.md) — 대량 묶음 시 유실
- [페이지 없는 자료는 _pending](feedback_no_adhoc_page_creation.md) — 즉석 생성 금지 · [섹터 라벨 정합성](feedback_sector_label_integrity.md) — 라벨 말고 실제 종목 일치 검증
- [수출데이터 활용 원칙](feedback_export_data_usage.md) — 보조지표, RS+모멘텀 섹터에서만 · [주도업종 판단 시스템](project_leading_sector_system.md) — · [주도업종×컨센상향](project_consensus_sector_combo.…
- [위키 데이터 구축 방법론](project_wiki_data_methodology.md) — · [섹터 리서치 시스템](project_sector_research_system… · [투경 백테스팅](project_투경_백테스팅.md) — 급등형/불건전형 구분·4/4 검증
- [Update Date Required](feedback_update_date.md) — 위키 갱신 시 날짜 명시
## 채널·영상(YT/Remotion)
- [★영상 대본작업 = 공식문서대로](project_영상대본작업_표준.md) — "대본작업 하자"→channel/strategy/영상제작_대본작업_표준.md. 7단계 설득구조(6단계에 절반 이상)+산출물 3종(대본md·수정모드html·녹화콜시트html)+금지선(금액·결제내역·경쟁사화면). 기능은 git log 실측 · [YouTube 파이프라인](project_yt_pipeline.md) — 채널=로또의 스탁브레인. Claude→Gemini→Claude
- [유튜브 영상 타입 규칙](feedback_yt_video_type.md) — 70/20/10은 채널 전체 비율, 첫 질문 A/B/C형 · [YT 레퍼런스 창고](project_yt_reference_warehouse.md) — 로컬완성, 서버미배포
- [시황 브리핑 엔진](project_briefing_weather_engine.md) — Phase0 배포·E2E 완료, 관측·튜닝 · [영상제작 대시보드](project_yt_planning_dashboard.md) — Task5(yt.html) 남음
- [전문가 인용 몽타주 엔진](project_quote_montage_engine.md) — 엔진 검증완료. 다음=인용스튜디오 UI · [경쟁채널 분석 로보](project_competitor_로보.md) — 로보=방법판매, 우리=결과판매
- [Remotion 스타일](feedback_remotion_style.md) — · [레퍼런스 규칙](feedback_remotion_reference_rule.… · [Creative Freedom](feedback_creative_freedom.md) — 씬 구성은 매번 독창적으로
- [카카오EP1 Remotion 재설계](project_kakao_ep1_remotion.md) — 자막=Whisper 1:1 철칙 · [에이전트직원 영상 진행](project_agents_video_progress.md) — 실화면 촬영 대기
- [브리핑 디자인·카드](project_briefing_design.md) — 검정+골드. [Sector Dashboard+카드](project_dashboar… · [브리핑 날짜 검증 의무](feedback_briefing_date_verification.md) — V-1~V-5 검증 필수
- [브리핑 카드 인사이트 기준](feedback_briefing_card_quality.md) — 양면론 금지, 수치+판단 · [브리핑 소스 인용 원칙](feedback_briefing_source_citation.md) — 직접 인용+출처+날짜
- [이미지 적극 활용](feedback_use_images.md) · [이미지 시스템](project_image_system.md) · [브랜드 스타일 인포그래픽](project_brand_style_infographics.md) — · [작업순서](feedback_brand_style_workflow.md)
- [Obsidian 파일 자동 열기](feedback_obsidian_open.md)
## 기타/아카이브
- [STOCK BRAIN 서비스](project_stockbrain_service.md) — · [고객 전달 3단계](project_customer_delivery_model… · [다음 할 작업](project_next_tasks.md) — MVP→크롤링자동화→RAG
- [태린이 파이프라인](project_taerini_pipeline.md) — · [시각화 도구](project_viz_tools.md) · [Oscillato… · [채널 인사이트 시스템](project_channel_insight_system.md) — · [크롤링봇 ingest 파이프라인](project_crawling_pipeli…
- [Claude Code 플러그인 현황](project_claude_code_plugins.md) · [로컬 안씀, 서버 대시보드만](feedback_server_dashboard_only.md)
- [★서버 IP는 계속 바뀐다 — SSH 전 nslookup](reference_server_ip_changed_2026_08_05.md) — 3.39.179.148→43.200.48.69→3.35.251.172. ★옛 IP가 살아있으면 더 위험(옛 데이터로 틀린 결론). 붙은 뒤 git log·is-active로 검증 · [사용자에게 보이는 글은 전부 한국어](feedback_always_korean_to_user.md) — 영어 스킬 지시문이어도 질문창·선택지·보고는 번역해서 낸다. 규칙은 전역 CLAU…
- [핸드오프의 '없다'를 직접 확인하라](reference_핸드오프_없다는말_직접확인.md) — 틱톡 수집은 이미 있었다(4줄 삭제로 끝). 배포확인=mtime vs 프로세스 기… · [vmake_paused 편법 행이 과금을 계속한다](reference_vmake_paused_편법행이_과금을_계속한다.md) — 옛 이름으로 끈 키는 "키 없음"이 돼 본사 키로 돌며 포인트를 깎는다(cid57 2.1P까지 소진). 복구=service/status 되돌리기. ★검수는 /etc/shopping-shorts.env 실은 환경에서(그냥 셸은 마스터키 없어 복호 실패로 오판)
- [체험과 유료가 같은 필드를 쓴다](reference_체험과_유료가_같은_필드를_쓴다.md) — full_access_until=입금 승인 기간(체험 아님). '체험 없애기'로 판정 분기를 지우면 결제고객이 랭킹만으로 추락. 막을 곳은 부여 경로 3개(가입체험·★ack_customer 이관·admin free+days). 강등은 payments 0건만 · [미리보기 전환/복귀 = ?pv=1 / ?pv=0](reference_미리보기_pv쿠키_되돌리기.md) — 같은 도메인이 쿠키(ssprev)로 라이브(8849)↔미리보기(8850) 갈린다.…
- [Revert가 브라우저에 남긴 값이 재배포를 이긴다](reference_revert가_남긴_localStorage.md) — '고객만 옛 화면'이 서버 버전이 아니라 localStorage(촘촘히='0')… · [편집안 비었다=분당 429](reference_edl_plan_empty_rpm_429.md) — plan_empty 뿌리는 RPM 429인데 대기 없이 키 4개를 0.7초에 태우…
- [★EDL 실패 라벨은 사후 추측](reference_edl실패라벨은_사후추측이다.md) — extract_empty를 믿고 '대사 없는 영상이라 안 된다'고 오진. 진짜는 429+401. 그 시각 _vault_call 로그를 봐라 · [회원키 49개가 제작에 안 쓰였다](reference_회원키가_제작에_안쓰였다.md) — 합류가 웹 startup에만, 워커는 별도 프로세스라 0건. 응급=.env에 직접…
- [서버 IP 3.35.251.172로 또 변경](reference_server_ip_2026_08_31.md) — SSH 전 nslookup 필수. 옛 IP는 죽은 인스턴스라 '서비스 다운'으로… · [iframe 캐시버스터가 옛 코드를 물린다](reference_iframe_캐시버스터가_옛코드를_물린다.md) — scene_lab의 t=는 페이지 로드 1회 고정 → 배포 전 열어둔 탭은 옛 filmroll.js 실행. '고쳤는데 안 된다' 판정 전 contentWindow.filmroll.toString()로 실행 코드 확인. ★숨은 iframe(0x0)은 rAF가 안 돈다
- [유튜브 릴레이 쿠키·bat 파싱 함정](reference_유튜브릴레이_쿠키와_bat파싱.md) — 성공/실패 섞이면 IP 아니라 쿠키 의심. 크롬은 ABE로 못 뽑음(닫아도)→파이어폭스. ★bat REM 안의 <URL>이 리다이렉션 파싱돼 set 줄을 죽인다. ★서버 IP 3.35.251.172(nslookup 먼저) · [하루 1회 스킵 = 그날 0건](reference_하루1회_스킵은_그날0건.md) — 양보엔 같은 날 재시도가 짝. "다음 회차"가 진짜 있는지 스케줄로 확인. ★타이머 파일은 auto_deploy가 안 건드림(수동 cp+daemon-reload). ★테스트가 라이브 DB에 상태 쓰면 운영 망가짐. run_date는 전날 23:10 기준
- [인스타 세션 전멸과 복구](reference_인스타세션_전멸과_복구.md) — 0건 원인은 프록시 아닌 세션 전멸(오진 2회). ★판정은 _scrape_one_playwright 실측으로(API코드·쿠키존재는 헛다리). 잠김은 이메일인증으로 풀림. 적립 전 파폭 완전종료. 인스타만 snapshots 테이블(platform_snapshots 아님) · [Buffer 유튜브 type 칸은 없다](reference_buffer_youtube_type_field_없다.md) — 유튜브 예약 100% 실패 뿌리. SNS별 metadata는 칸이 전혀 다르다(틱…
- [auto커밋이 되돌린 것을 복구하는 법](reference_auto커밋이_되돌린것을_복구하는법.md) — key_vault 회전·TTL이 하루 넘게 사라져 있었다. 통째 덮기 금지(이후…
- [★피드 타기가 어휘 발굴을 이겼다](reference_피드타기가_어휘발굴을_이겼다.md) — 사장님 채점 121개중 O 6개로 검색어 발굴 기각. 추천 피드는 24% 적중·API 0 units. ★단 멀리 가면 DIY·캠핑·주식으로 샌다(411개) → 등록 전 사람이 본다. 판정기는 양방향 구멍(디에디트 놓침/따니네 만들기 오통과)
- [★랭킹 정렬 안 갈림 = 뿌리 2개](reference_랭킹정렬_두뿌리_탭셀렉터와_발행시각.md) — .tab 셀렉터가 기간 탭까지 잡아 STATE.tab을 지움 + upload_ts가 9203건 중 0건(수집 items에 timestamp 키 없음). ★비로그인 curl로 랭킹 판정 무효(랜딩 페이지)
- [★스타일 예시가 재료를 이긴다](reference_스타일예시가_재료를_이긴다.md) — "AI생성이 엉뚱한 제품 대본" 뿌리는 코드가 아니라 프롬프트 분량(재료 233자 vs 스타일예시 1,985자+은행 1,832자). 스타일 블록에만 소재 격리 경고가 없었다. ★갈라보기=style_id 유무로 스타일/픽업 경로 판별. spine 26~45는 구조 아닌 특정제품 대본이라 승인해제
- [★다 되면 보고하라](feedback_다되면_보고하라.md) — 진행 중 "아직 고쳐졌다고 말할 단계는 아닙니다" 같은 유보 문구 금지. 조용히 끝내고 결과만 3줄. 끝난 뒤 한계를 밝히는 건 그대로(0순위-A1)
- [★배선은 짝으로 확인하라](reference_배선은_짝으로_확인하라.md) — 하루에 같은 사고 3번(회원키 config만 갱신·수집스크립트 keypool 누락·지킴이 pgrep 자기잡기). 전부 에러0·로그정상인데 실제로는 아무 일도 안 남. 판정=config.X와 그모듈.X 길이 대조, ps로 프로세스 확인, 로그말고 결과수치
- [★문장틀에 박힌 판매처가 지시대로 거짓말이 된다](reference_문장틀에_박힌_판매처가_지시대로_거짓말이_된다.md) — 대본 후보 하나가 "다이소 매니저 지인" 허위. 스파인 문장틀+"틀 새로 짓지 마라" 강제=지시 준수. 게이트는 "남의 것이 섞였나"도 봐야. seed가 pending 되살리면 격리 무효. 아스트라(codex -m gpt-6-astra) 협업으로 규명
