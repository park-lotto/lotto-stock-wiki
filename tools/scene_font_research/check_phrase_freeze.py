"""구절 맞춤에서 재료가 모자랄 때 **정지로 때우지 않고 실프레임으로 채우나** (2026-09-24 고객 강병주님
 "미리보기에서는 정상인데 완성본에서 한 장면에 애니메이션 효과가 들어가는 오류").

실물: job 86e6cd5bb254 0번 칸 — 말 3.8초 / 조각 s6 4.7~6.533(1.83초) / 릴 s6은 15.23초.
  종전: src_dur가 조각 끝에서 잘려 out_dur와 약 2초 차이 → 슬로모→정지+확대로 채움.
  고침: 릴 뒤 실프레임을 이어 써서 차이가 없어진다.
  ★조각 뒤를 아주 조금(0.35초 미만) 넘는 경우는 종전대로 — 2026-09-17 "중간에 다른 화면이 짧게" 재발 방지.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import video_assemble as va
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
def freeze_of(plan):
    return round(sum(max(0.0, float(c['out_dur']) - float(c['src_dur'])) for c in plan), 2)
BEAT = {'beat_idx': 0, 'role': '훅', 'target_seconds': 3.8, 'phrase_sync': True,
        'cut_rhythm': {'max_shot': 5.0, 'hold': True},
        'narration': '요즘 육아하는 아빠들 사이에서, 이게 왜 그렇게 난리인가 했거든요',
        'caption_lines': ['요즘 육아하는 아빠들 사이에서,', '이게 왜 그렇게 난리인가 했거든요'],
        'cap_durs': [1.9, 1.9],
        'primary': {'video_id': 's6', 'start': 4.7, 'end': 6.533}}
SEGS = [{'video_id': 's6', 'start': 4.7, 'end': 6.533}]
plan = va.plan_beat_clips_for(BEAT, 3.8, {'s6': 15.233}, runout=0.0)
print('  계획:', [{k: round(v, 2) if isinstance(v, float) else v for k, v in c.items()} for c in plan])
need(bool(plan), '계획이 나온다')
need(freeze_of(plan) < 0.35, f'① 정지로 때우는 시간이 거의 없다 ({freeze_of(plan)}초) — 고치기 전엔 약 2초였다')
used_end = max(float(c['start']) + float(c['src_dur']) for c in plan) if plan else 0
need(used_end > 6.533, f'② 조각 끝(6.53초)을 넘어 릴의 실프레임을 쓴다 (끝 {round(used_end, 2)}초)')
need(used_end <= 15.233 + 1e-6, f'② 릴 길이를 넘지 않는다 ({round(used_end, 2)} ≤ 15.23)')
# 잔챙이 모자람은 종전대로(다음 장면이 살짝 비치지 않게)
BEAT2 = dict(BEAT, target_seconds=1.9, cap_durs=[0.95, 0.95],
             primary={'video_id': 's6', 'start': 4.7, 'end': 6.5})
plan2 = va.plan_beat_clips_for(BEAT2, 1.9, {'s6': 15.233}, runout=0.0)
end2 = max(float(c['start']) + float(c['src_dur']) for c in plan2) if plan2 else 0
need(end2 <= 6.5 + 1e-6, f'③ 0.35초 미만 모자람은 조각 안에서만 (끝 {round(end2, 2)} ≤ 6.5)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
