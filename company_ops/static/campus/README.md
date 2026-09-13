# 메이커스랩 캠퍼스 건설 · 1차

`http://127.0.0.1:8931/campus/` — 실제 Three.js 메시로 구성한 외관. 정면/좌측/후면/본사/숏템메이커 카메라, 자유 회전·팬·줌, 주야간, 승인 원본 비교.

최신 사용자 선택은 A 확장형 캠퍼스. 뒤 중앙 본사, 좌우 프로그램, 앞 프로젝트 스튜디오 등 총12동(가상 배치), 수로·다리·옥상 정원·가로수·확장 부지. `campus-a-layout.js`의 배치와 `campus-a-art.js` 외형을 분리했다. 건물 수는 실제 프로젝트/직원 수가 아니다. 건축/재질/조경 1차 조형이며 원본 품질 재현 완료 아님. 실내 입장·1인칭/충돌·실운영·음성 기능 없음. 로로/내부 기존 파일은 수정하지 않는다. 기존 B 원형 소스는 별도 보존했다.

scene 폴더에서 `npx esbuild campus.js --bundle --format=esm --minify --outfile=../static/campus/campus.bundle.js`.
트랙 루트에서 `node --test company_ops/tests/campus-a.test.mjs`, `node company_ops/tests/campus.cjs`.
브라우저 테스트는 로컬 정적 서버 8931 필요. 화면 `.artifacts/campus-a-*.png`.

반복 기둥·가로수는 InstancedMesh 사용. 관측 draw call/triangle은 진단일 뿐 모든 기기 성능 보장이 아니다. Three.js MIT 고지 번들 포함.
