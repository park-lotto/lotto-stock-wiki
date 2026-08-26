# -*- coding: utf-8 -*-
"""히트작 자막 수집 — yt-dlp 자동자막(ko). 429 방지로 순차+간격."""
import subprocess, json, io, os, re, time, sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
vids = json.load(open('hits.json', encoding='utf-8'))[:N]
os.makedirs('subs', exist_ok=True)
ok = 0; fail = 0
res = []
for i, v in enumerate(vids):
    vid = v['video_id']
    dst = 'subs/%s' % vid
    vtt = dst + '.ko.vtt'
    if not os.path.exists(vtt):
        cmd = ['yt-dlp', '--skip-download', '--write-auto-subs', '--sub-langs', 'ko',
               '--sub-format', 'vtt', '--no-warnings', '-o', dst + '.%(ext)s',
               'https://www.youtube.com/watch?v=' + vid]
        try:
            subprocess.run(cmd, capture_output=True, timeout=90)
        except Exception:
            pass
    if os.path.exists(vtt):
        lines = io.open(vtt, encoding='utf-8').read().split('\n')
        out = []; last = ''
        for j, l in enumerate(lines):
            m = re.match(r'(\d\d:\d\d:\d\d\.\d\d\d) --> ', l)
            if m:
                t = re.sub(r'<[^>]*>', '', lines[j+1] if j+1 < len(lines) else '').strip()
                if t and t != last:
                    out.append((m.group(1)[3:], t)); last = t
        full = ' '.join(t for _, t in out)
        if full.strip():
            ok += 1
            res.append({**v, 'segments': out, 'full_text': full})
        else:
            fail += 1
    else:
        fail += 1
    if (i+1) % 10 == 0:
        print('  ...%d/%d  ok=%d fail=%d' % (i+1, len(vids), ok, fail))
    time.sleep(1.2)          # 429 회피

io.open('hits_subs.json','w',encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1))
print('자막 확보:', ok, '| 실패:', fail)
