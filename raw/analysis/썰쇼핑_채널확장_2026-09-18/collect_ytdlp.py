# -*- coding: utf-8 -*-
"""썰쇼핑 채널에서 조회수 터진 쇼츠 수집 — yt-dlp 사용(YouTube API 쿼터 0).
채널 shorts 탭은 대체로 최신순이라 넉넉히 긁어 조회수로 정렬한다."""
import subprocess, io, json, sys, concurrent.futures as cf

PULL = int(sys.argv[1]) if len(sys.argv) > 1 else 25   # 채널당 훑을 편수
WORKERS = 6

chans = []
for line in io.open('sul_channels.txt', encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) >= 2 and p[0].startswith('UC'):
        chans.append((p[0], p[1]))

def grab(item):
    cid, name = item
    url = 'https://www.youtube.com/channel/%s/shorts' % cid
    cmd = ['yt-dlp', '--flat-playlist', '--no-warnings', '--playlist-end', str(PULL),
           '--print', '%(view_count)s\t%(id)s\t%(duration)s\t%(title)s', url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
        out = r.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return name, [], str(e)[:50]
    rows = []
    for ln in out.split('\n'):
        parts = ln.rstrip('\r').split('\t')
        if len(parts) < 4:
            continue
        try:
            vc = int(parts[0]) if parts[0] not in ('NA', '') else 0
        except Exception:
            vc = 0
        try:
            du = float(parts[2]) if parts[2] not in ('NA', '') else 0
        except Exception:
            du = 0
        rows.append({'views': vc, 'video_id': parts[1], 'duration': du,
                     'title': parts[3], 'channel': name, 'channel_id': cid})
    return name, rows, ''

allv = []
done = 0
with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
    for name, rows, err in ex.map(grab, chans):
        done += 1
        allv.extend(rows)
        if err:
            print('  ERR %s: %s' % (name[:14], err))
        if done % 20 == 0:
            print('  ...%d/%d  누적 %d편' % (done, len(chans), len(allv)))

allv.sort(key=lambda x: -x['views'])
io.open('hits.json', 'w', encoding='utf-8').write(json.dumps(allv, ensure_ascii=False, indent=1))
print('총 수집:', len(allv))
print('조회수 100만+:', sum(1 for v in allv if v['views'] >= 1000000))
print('조회수 50만+ :', sum(1 for v in allv if v['views'] >= 500000))
print('조회수 10만+ :', sum(1 for v in allv if v['views'] >= 100000))
