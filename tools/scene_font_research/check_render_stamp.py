"""렌더 도는 사이에 꾸미기를 바꾸면 **옛 결과물을 완성본으로 박지 않는다** (2026-09-24 제보 "장면꾸미기대로 렌더가 안 된다").

실측 근거(job c52bb437d2c4): 저장된 꾸미기 제목은 '다들 쓰는 채칼 / 정체 알아냈어요'인데 완성본 영상은
'왜 이제 알았지 / 5초 채썰기 비법'이었다. 그 꾸미기로 지금 렌더하면 제대로 나온다 → 파이프라인은 정상,
**옛 완성본이 남은 것**이 원인. 꾸미기 저장이 완성본을 끊어도, 그 뒤 끝난 렌더가 video_path를 다시 박는다.

  ① 설정이 그대로면 도장이 같다(정상 렌더는 완성본으로 박힌다)
  ② 꾸미기(deco)가 바뀌면 도장이 달라진다 → 결과물을 버린다
  ③ 제목·자막 스타일·자막제거 스위치가 바뀌어도 달라진다
  ④ 편성(대사·장면)이 바뀌면 도장이 달라진다 — 2026-09-27부터 편성 지문(plan_signature)이 도장에 든다
     (렌더가 편성표를 고쳐 쓰지 않게 됐고, 도장은 TTS 보장 저장 뒤에 찍는다 — 옛 ④'편성만 바뀌면 그대로'는 뒤집혔다)
  ⑤ SEO·썸네일 글자·완성본 경로는 도장에 안 들어간다(멀쩡한 완성본을 버리지 않게)
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
for val, label in (({'beats': [{'beat_idx': 0, 'narration': '나'}]}, '대사'),
                   ({'beats': [{'beat_idx': 0, 'narration': '가',
                                'primary': {'video_id': 's1', 'seg_id': 's1-0', 'start': 0.0, 'end': 2.0}}]}, '장면')):
    need(_render_stamp(dict(BASE, edit_plan=val)) != _render_stamp(BASE), f'④ 편성({label})이 바뀌면 도장이 달라진다')
for key, val, label in (('seo', {'title': '새 제목'}, 'SEO'),
                        ('thumbnail', {'pins': ['a']}, '썸네일'),
                        ('video_path', '/y/final.mp4', '완성본 경로')):
    need(_render_stamp(dict(BASE, **{key: val})) == _render_stamp(BASE), f'⑤ {label}만 바뀌면 도장은 그대로(멀쩡한 완성본을 안 버린다)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
