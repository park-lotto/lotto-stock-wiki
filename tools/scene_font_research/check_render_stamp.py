"""렌더 도는 사이에 꾸미기를 바꾸면 **옛 결과물을 완성본으로 박지 않는다** (2026-09-24 제보 "장면꾸미기대로 렌더가 안 된다").

실측 근거(job c52bb437d2c4): 저장된 꾸미기 제목은 '다들 쓰는 채칼 / 정체 알아냈어요'인데 완성본 영상은
'왜 이제 알았지 / 5초 채썰기 비법'이었다. 그 꾸미기로 지금 렌더하면 제대로 나온다 → 파이프라인은 정상,
**옛 완성본이 남은 것**이 원인. 꾸미기 저장이 완성본을 끊어도, 그 뒤 끝난 렌더가 video_path를 다시 박는다.

  ① 설정이 그대로면 도장이 같다(정상 렌더는 완성본으로 박힌다)
  ② 꾸미기(deco)가 바뀌면 도장이 달라진다 → 결과물을 버린다
  ③ 제목·자막 스타일·편성이 바뀌어도 달라진다
  ④ SEO·썸네일은 도장에 안 들어간다(멀쩡한 완성본을 버리지 않게)
  ★편성(edit_plan)도 안 넣는다 — 렌더가 도는 동안 파이프라인이 스스로 편성을 고쳐 써서,
    넣으면 정상 렌더까지 매번 버려진다(test_run_render_happy_path가 실제로 잡았다).
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts.mix_pipeline import _render_stamp
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
BASE = {'edit_plan': {'beats': [{'beat_idx': 0, 'narration': '가'}]},
        'deco': {'scene_style': {'presetId': 't11', 'text': {'hook1': '다들 쓰는 채칼'}}},
        'headcopy': {'text': '제목'}, 'caption_style': {'color': '#fff'}, 'subtitle_removal': False,
        'seo': {'title': '옛 제목'}, 'thumbnail': {'pins': []}, 'video_path': '/x/final.mp4'}
need(_render_stamp(BASE) == _render_stamp(dict(BASE)), '① 그대로면 도장이 같다')
ch = dict(BASE, deco={'scene_style': {'presetId': 't11', 'text': {'hook1': '왜 이제 알았지'}}})
need(_render_stamp(ch) != _render_stamp(BASE), '② 꾸미기를 바꾸면 도장이 달라진다 — 옛 결과물을 버린다')
for key, val, label in (('headcopy', {'text': '새 제목'}, '제목'),
                        ('caption_style', {'color': '#000'}, '자막 스타일'),
                        ('subtitle_removal', True, '자막제거 스위치')):
    need(_render_stamp(dict(BASE, **{key: val})) != _render_stamp(BASE), f'③ {label}이 바뀌면 도장이 달라진다')
for key, val, label in (('seo', {'title': '새 제목'}, 'SEO'),
                        ('thumbnail', {'pins': ['a']}, '썸네일'),
                        ('video_path', '/y/final.mp4', '완성본 경로'),
                        ('edit_plan', {'beats': [{'beat_idx': 0, 'narration': '나'}]}, '편성')):
    need(_render_stamp(dict(BASE, **{key: val})) == _render_stamp(BASE), f'④ {label}만 바뀌면 도장은 그대로(멀쩡한 완성본을 안 버린다)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
