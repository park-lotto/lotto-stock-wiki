# 패키지 marker (2026-08-10).
#
# tools/test_track.py 와 tests/people/test_track.py 는 **파일명이 같다**.
# 둘 다 __init__.py 없는 폴더에 있으면 pytest(rootdir 기준 sys.path 삽입 방식)가
# 두 파일을 같은 모듈명 `test_track`으로 import하려다 충돌한다:
#     import file mismatch / HINT: use a unique basename
# → 저장소 전체 수집이 "Interrupted: 1 error during collection"으로 멈춘다(실측).
#
# __init__.py를 두면 이 폴더가 패키지가 돼 모듈명이 `tests.people.test_track`으로
# 갈라져 충돌이 사라진다. 파일 이름을 바꾸는 것보다 안전하다(다른 곳에서 참조할 수 있고,
# 앞으로 같은 이름이 또 생겨도 이 폴더는 안전하다).
