# 유료강의 판독 도구 (관제 267)
개인 학습용. 강의 내용물(영상·받아쓰기·카드)은 저작권·수강규정상 **git에 넣지 않는다** — `C:\Users\TheRose\강의\<강의명>\` 에만 둔다.

1. 네이버 카페 로그인(한 번): `py tools/lecture/naver_login.py` — 프로필 `~/.claude/naver_browser_profile`, 사장님이 직접 로그인
   (크롬 확장은 cafe.naver.com 차단 → 플레이라이트 지속 프로필)
2. 게시판·글·첨부: `naver_board.py` / `naver_art.py` / `naver_files.py` / `naver_save.py`
3. 영상: Vimeo 임베드 → `yt-dlp --referer https://cafe.naver.com/ <player.vimeo.com/video/ID>`
4. 판독: `py -I tools/lecture/lecture_gemini.py <영상.mp4> <분석폴더>` (10분 조각, 키 .env GEMINI*, 모델 번갈아, 이어하기)
5. 카드: `py -I tools/lecture/lecture_cards.py <분석폴더> <바탕화면\접두어>` → _원본기록.md / _노하우카드.md
6. HTML: `py -I tools/lecture/cards_html.py <노하우카드.md> <출력.html>` (분류 필터·검색)

⚠ 프롬프트의 "5시간 15분"·"3주차" 문구, 카드 합본 제목은 강의마다 바꿀 것.
