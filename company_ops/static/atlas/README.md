# 워커 관제 탐색 검토본

예시 워커 200개, 프로젝트 30개의 고정 배치 탐색용. 실제 회사 인원/실행 현황이 아니다.

- 로컬: static 폴더에서 `py -m http.server 8931 --bind 127.0.0.1`, `http://127.0.0.1:8931/atlas/`.
- 빌드: `company_ops/scene`에서 `npm run build:atlas`.
- 검증: 트랙 루트에서 `node --test company_ops/tests/atlas-data.test.mjs`, `node company_ops/tests/atlas.cjs` (8931 서버 필요).
- 드래그 이동, 휠/핀치 확대, 회전 버튼/오른쪽 드래그 회전, 검색·상태·부서 필터, 워커 선택, 프로젝트 참여자 강조, 예시 로그. Ctrl+K 검색, Esc 상세 닫기.
- 실제 API·실행기·명령·중단·비용·결과물 미연결. 데이터는 atlas-data.js 한 곳. 필터는 자리를 바꾸지 않는다.
- 최종 3D 아트, 캠퍼스 입장, 층별 내부 공간, 실제 인벤토리 연결은 후속 범위다.
- Three.js MIT 라이선스: `../hq/THIRD_PARTY_LICENSES.txt`. 번들에도 라이선스 고지 유지.
