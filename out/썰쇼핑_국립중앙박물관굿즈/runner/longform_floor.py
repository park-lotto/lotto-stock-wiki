"""인물형 롱폼 최소 구성 — 오드리 헵번 마지막 편이 바닥 (2026-10-20 사장님 결정).

이 파일은 두 곳에 바이트 그대로 있다: 서버 src/longform/floor.py(longform_seed 반려) · 실행기
assets/stage_runner/runner/longform_floor.py(longform_contract.validate). 서버(Worker)는 실행기 팩을 import 못 해서
사본을 두고, tests/test_longform_floor.py 가 두 파일의 바이트가 같은지 본다. 고칠 때는 둘 다 같이.

숫자는 지어낸 것이 아니라 오드리 편 실제 제품 제작표를 한 번 훑어 잰 값이다:
  output/reference-reengineering/audrey-rebuild/full-production/public-config.json (public_path.py 가 쓴 제품 경로 제작표)
  sha256 a83ad60666a8118fc1d22d58ee19a6f81e42009a4a911afad6d05d5d54b866e7 · 완성본 영상 sha256 8c9e52bd…(874.6초)
  67블록 = graphic(authored) 41 · montage 20(그중 영상 컷이 든 것 19 · 사진만 h11 1) · video 6 ·
  photo/split/cutout 0 · 같은 종류 연속 최대 graphic 13 · montage 3 · video 2 · 원음(source_audio) 0 ·
  누끼는 블록 종류로 드러나지 않는다(그래픽 안 그림) — 누끼 장면은 «설계한 장면»이라 cutout 블록은 사진 한 장으로 치지 않는다
  (10-20 사장님: 누끼 이미지·모션 그래픽이 다채로움의 일부 · «더 다채로운 것은 환영»).
바닥 셋(블록 n 개): ① 실사 영상 블록 ≥ n×25/67 내림 ② 사진 한 장 블록(photo/split)은 오드리 편처럼 0 —
그 자리는 그래픽·누끼(cutout)·몽타주·영상으로 ③ 같은 visual.kind 연속 ≤ 13. 그래픽 수는 따로 바닥을 두지 않는다 — 그래픽을 영상·몽타주로
바꾼 제작표는 오드리 편보다 단조롭지 않다(«더 다채로운 것은 환영»). 그래픽끼리의 다양성은 graphic_variety unique-v1 이 본다.
"""

MARK = 'audrey-v1'
SOURCE = {
    'plan': 'output/reference-reengineering/audrey-rebuild/full-production/public-config.json',
    'plan_sha256': 'a83ad60666a8118fc1d22d58ee19a6f81e42009a4a911afad6d05d5d54b866e7',
    'video_sha256': '8c9e52bddf33a29ba9e657d7ef58ede03fe4f3b195433fa93f3a9c766ff4b055',
}
#: 오드리 편에서 잰 값(위 SOURCE). blocks 는 분모, 나머지는 그 편의 블록 수.
AUDREY = {'blocks': 67, 'graphic': 41, 'footage': 25, 'cut_sequence': 26, 'still': 0, 'max_run': 13}
STILL = ('photo', 'split')

LABEL = {
    'footage': '실사 영상 블록(visual.kind="video", 또는 영상 컷이 하나 이상 든 "montage")',
    'still': '사진 한 장 블록(visual.kind="photo"/"split")',
}
NO_FOOTAGE = ('영상 자료가 정말 없는 인물(예: 영상 기록 이전의 고대 인물)은 제작표에 footage_unavailable:"<왜 없는지 · 찾아본 곳>"을 적는다. '
              '그러면 실사 영상 바닥만 빠지고, 그 몫은 authored 그래픽 장면과 생성 그림(media.generate)·기록 사진으로 만든 montage 로 채운다 — '
              '사진 한 장 블록 0 과 연속 상한은 그대로다.')


def floors(n):
    """블록 n 개 제작표의 바닥(footage 이상) · 상한(still 이하) — 오드리 비율을 내림."""
    return {key: n * AUDREY[key] // AUDREY['blocks'] for key in ('footage', 'still')}


def measure(plan):
    """한 번 훑기(O(n)): 종류별 블록 수와 같은 종류 연속 최대(그 블록 ID 범위)."""
    count = {'footage': 0, 'still': 0}
    kinds = {}
    run = 0
    previous = None
    longest = {'kind': None, 'length': 0, 'first': None, 'last': None}
    first = None
    for block in plan['blocks']:
        visual = block['visual']
        kind = visual['kind']
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind in STILL:
            count['still'] += 1
        if kind == 'video' or (kind == 'montage' and any(shot.get('kind') == 'video' for shot in visual.get('shots', []))):
            count['footage'] += 1
        if kind == previous:
            run += 1
        else:
            run, first = 1, block.get('id')
        previous = kind
        if run > longest['length']:
            longest = {'kind': kind, 'length': run, 'first': first, 'last': block.get('id')}
    return {'blocks': len(plan['blocks']), 'kinds': kinds, 'count': count, 'longest_run': longest}


def check(plan):
    """(보고, 고칠 것 목록). 고칠 것이 비면 통과. 보고는 반려 응답에 그대로 싣는다."""
    found = measure(plan)
    need = floors(found['blocks'])
    waived = isinstance(plan.get('footage_unavailable'), str) and len(plan['footage_unavailable'].strip()) >= 10
    fixes = []
    short = need['footage'] - found['count']['footage']
    if short > 0 and not waived:
        fixes.append(f"{LABEL['footage']} {short}개 더 — 지금 {found['count']['footage']}개, 바닥 {need['footage']}개"
                     f"(블록 {found['blocks']} × 오드리 편 {AUDREY['footage']}/{AUDREY['blocks']} 내림)")
    extra = found['count']['still'] - need['still']
    if extra > 0:
        fixes.append(f"{LABEL['still']} {extra}개를 그래픽(authored)·누끼(cutout)·몽타주·영상 블록으로 바꾼다 — 지금 {extra}개, "
                     f"오드리 편 {AUDREY['still']}/{AUDREY['blocks']}")
    run = found['longest_run']
    if run['length'] > AUDREY['max_run']:
        fixes.append(f"같은 종류 화면 연속 {run['length']}블록({run['kind']} · {run['first']}~{run['last']}) — "
                     f"오드리 편 최대 {AUDREY['max_run']}블록 이하로, 사이에 다른 종류(그래픽·영상·몽타주)를 넣어 끊는다")
    report = {'mark': MARK, 'measured': found, 'floors': need, 'max_run': AUDREY['max_run'],
              'footage_unavailable': waived, 'source': SOURCE, 'audrey': AUDREY, 'no_footage_path': NO_FOOTAGE}
    return report, fixes


def message(fixes):
    return ('제작표가 최소 구성(오드리 헵번 편 바닥)보다 단조롭습니다. 고칠 것: ' + ' · '.join(fixes) +
            '. 같은 사진을 잘라 블록 수만 늘리지 말고 내용에 맞는 장면을 설계한다. ' + NO_FOOTAGE)


#: 지시서(editing_brief)에 그대로 싣는 안내 — 숫자는 위 AUDREY 에서 만든다(손으로 다시 적지 않는다).
GUIDE = {
    'required': f'새 제작표는 composition_floor:"{MARK}" 필수(시작한 작업은 제외).',
    'floors': (f"블록 n 개일 때(내림): {LABEL['footage']} ≥ n×{AUDREY['footage']}/{AUDREY['blocks']} · "
               f"{LABEL['still']} ≤ n×{AUDREY['still']}/{AUDREY['blocks']}(= 0) · "
               f"같은 visual.kind 연속 ≤ {AUDREY['max_run']}블록. 그래픽을 영상·몽타주로 더 채우는 것은 환영."),
    'measured_from': ('오드리 헵번 마지막 편 67블록: graphic 41 · montage 20(영상 컷 든 것 19) · video 6 · '
                      'photo/split 0 · 같은 종류 연속 최대 13(graphic) · 누끼는 그래픽 안에 있었다'),
    'no_footage': NO_FOOTAGE,
    'source': SOURCE,
}
