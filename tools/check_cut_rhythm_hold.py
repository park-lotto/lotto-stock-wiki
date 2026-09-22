"""컷 리듬 홀드(cut_rhythm.hold)가 정지 화면을 만들지 않는지 — plan_beat_clips_for 계획으로 잰다 (2026-09-22).
  py tools/check_cut_rhythm_hold.py

실사고: job 956a6843cdd5 최종 렌더 3번 비트(7.1초)에 hold 표식 → 첫 조각 s4 9.9~11.0(1.1초)만 남기고 조각 end에서 잘려
나머지 6초가 10.9초 프레임 정지+슬로모+켄번즈 확대. 0·6번 비트도 같은 꼴("10초 부분에 계속 확대되고 일시정지").
미리보기(표식 전)는 정상이었다. 홀드의 뜻은 "첫 조각을 **이어 튼다**"이므로 조각 end를 소스 안에서 비트 길이만큼 연다.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from shopping_shorts import video_assemble as va

fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

src = {'s0': 22.933, 's4': 21.548}
# 실제 job 956a6843cdd5의 3번 비트 모양: 첫 조각 1.1초 + 다른 소스 조각 6개, 나레이션 7.1초, hold
# ★실제 비트는 3단계 편성(scene_override) 조각이다 — primary/alternates 픽스처로는 재현이 안 된다(조각 안에서만 규칙이 override에 걸린다)
segs = [{'video_id': 's4', 'seg_id': 'a', 'start': 9.9, 'end': 11.0}, {'video_id': 's0', 'seg_id': 'b', 'start': 9.9, 'end': 11.0},
        {'video_id': 's0', 'seg_id': 'c', 'start': 11.0, 'end': 12.0}, {'video_id': 's0', 'seg_id': 'd', 'start': 12.0, 'end': 13.4},
        {'video_id': 's0', 'seg_id': 'e', 'start': 14.2, 'end': 15.5}, {'video_id': 's0', 'seg_id': 'f', 'start': 16.3, 'end': 17.3},
        {'video_id': 's0', 'seg_id': 'g', 'start': 17.3, 'end': 18.2}]
beat = {'beat_idx': 3, 'role': '대비', 'target_seconds': 7.1, 'effect': 'cut', 'cut_rhythm': {'max_shot': 4.0, 'hold': True},
        'primary': dict(segs[0]), 'alternates': [dict(x) for x in segs[1:]], 'scene_override': [dict(x) for x in segs],
        # 구절 길이(자막 7구절) — 이게 있으면 구절마다 한 컷씩 자르는 경로를 탄다. 실제 비트 값 그대로.
        'cap_durs': [1.1012908, 1.5342202, 1.3353425, 0.9008011, 0.7355249, 0.5923835, 0.9284369],
        # ★구절 맞춤(phrase_sync, 09-21 라이브)이 켜진 비트가 정지를 만들었다 — 이 두 키가 없으면 재현이 안 된다(실측: 빼면 정지 0)
        'phrase_sync': True,
        'narration': '그저 사진 찍고 끝나는 정적인 케이크와는 달리 칙칙폭폭 소리를 내며 트랙 위를 기차가 스스로 달려서 아이들 혼을 쏙 빼놓는다는 거',
        'caption_lines': ['그저 사진 찍고 끝나는', '정적인 케이크와는 달리', '칙칙폭폭 소리를 내며', '트랙 위를 기차가', '스스로 달려서', '아이들 혼을 쏙', '빼놓는다는 거']}
clips = va.plan_beat_clips_for(beat, 7.1, src)
frozen = [c for c in clips if float(c.get('src_dur', 0)) < 0.2 and float(c['out_dur']) > 0.3]
total_src = sum(float(c.get('src_dur', 0)) for c in clips); total_out = sum(float(c['out_dur']) for c in clips)
print('  계획:', [(c['video_id'], round(c['start'], 2), round(c.get('src_dur', 0), 2), round(c['out_dur'], 2)) for c in clips])
need(bool(clips) and all(c['video_id'] == 's4' for c in clips), '홀드: 첫 조각의 소스(s4) 하나로 이어 튼다')
need(not frozen, f'정지 조각(원본 0.2초 미만을 0.3초 넘게 늘림) 0개 (실제 {len(frozen)}개) — 고치기 전엔 6개')
need(abs(total_out - 7.1) < 0.05 and total_src > 6.5, f'실프레임으로 채운 길이 {total_src:.2f}초 / 비트 {total_out:.2f}초 — 고치기 전엔 실프레임 1.7초')
starts = [float(c['start']) for c in clips]
need(all(b >= a for a, b in zip(starts, starts[1:])), '조각이 소스 시간 순서대로 이어진다(되감기 없음)')
# 홀드 아닌 비트는 종전과 같다(라운드로빈)
beat2 = dict(beat); beat2['cut_rhythm'] = {'max_shot': 4.0, 'hold': False}
clips2 = va.plan_beat_clips_for(beat2, 7.1, src)
need(len({c['video_id'] for c in clips2}) >= 2, f'hold 아니면 종전대로 여러 소스를 번갈아 쓴다 ({sorted({c["video_id"] for c in clips2})})')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
