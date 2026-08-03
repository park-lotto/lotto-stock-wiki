# NEXT_SESSION — 이어서 할 일 (병행 트랙)

> ⚠️ **내용은 `handoff/<트랙>.md`로 옮겼습니다** (2026-07-15).
> 이 파일은 **목록만** 유지합니다. **여기에 작업 내용을 쓰지 마세요** — 세션끼리 덮어씁니다.
> 자기 트랙 파일에 쓰세요. 규칙: `handoff/README.md`

| 트랙 | 파일 |
|---|---|
| ⭐**품앗이 트래픽 플랫폼**(브레인스토밍 재개점 2관문) | `handoff/품앗이.md` |
| 영상제작소 모션효과 | `handoff/모션효과.md` |
| 장면 라이브러리(재사용 짤 뱅크) | `handoff/장면라이브러리.md` |
| 영상제작소 대본·영상믹스 통합 | `handoff/대본믹스통합.md` |
| 대본생성 소재고정 리메이크 | `handoff/대본소재고정.md` |
| 꾸미기(5단계) 피팅룸 — 완료 | `handoff/꾸미기.md` |
| 보이스 프리셋 라이브러리 | `handoff/보이스.md` |
| 렌즈 유사영상 발굴 | `handoff/렌즈유사영상.md` |
| 쇼핑쇼츠 레퍼런스 랭킹 | `handoff/레퍼런스랭킹.md` |
| 대본위키 학습소재 선택기 | `handoff/대본위키_학습소재선택기.md` |
| 틱톡 키워드검색 발굴 | `handoff/틱톡발굴.md` |
| 쇼핑쇼츠 대본 위키(도서관) | `handoff/대본위키_도서관.md` |
| VMake 자막제거 | `handoff/VMake자막제거.md` |
| 동시세션 충돌차단(트랙격리) | `handoff/트랙격리.md` |
| 카테고리 분류 정확도(Gemini 이관) | `handoff/카테고리분류.md` |

---

## 동시세션 규칙

- **main 고정.** `git add`는 **내 파일만** — `git add -A` 금지. 6세션이 `.git`과 **인덱스를 공유**하므로 남의 변경이 내 커밋에 실린다.
- **커밋 = 즉시 push = 3분 뒤 라이브** (`.git/hooks/post-commit`이 `git push`를 무조건 실행). 커밋 전 `git diff --cached --name-only`로 내 파일만 있는지 확인.
- 커밋 순서: 내 파일만 stage → 커밋 → `git pull --rebase` → (push는 훅이 자동). 커밋 후 HEAD에 내 변경이 있는지 grep 확인(덮임 감지).
- 작업 로그는 `wiki/log.d/<트랙>.md`. 합쳐 보기: `py tools/log_view.py --days 7`
- `wiki/log.md`는 **동결된 아카이브**(2026-07-15까지). 새 기록은 `log.d/`에.

설계: `docs/superpowers/specs/2026-07-15-동시세션-충돌차단-트랙격리-design.md`
