"""숏클 롱폼 최종 합치기 + 결과물 검사(조각별 컨펌 뒤 마지막에 한 번).
사용: py assemble_longform.py <pieces.txt> <out.mp4>
  pieces.txt = 한 줄에 조각 mp4 경로 하나(순서대로). # 으로 시작하면 무시.
검사: ①조각마다 1920x1080·30fps·소리 있음 ②합본 길이 = 조각 합(±1초) ③1초 넘는 검은 화면 0 ④3초 넘는 무음 0
하나라도 걸리면 rc=1. 인코딩은 GPU(h264_nvenc)."""
import json, re, subprocess, sys
def probe(p):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', p], capture_output=True, text=True, encoding='utf-8').stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video'); a = [s for s in j['streams'] if s['codec_type'] == 'audio']
    return dict(w=v['width'], h=v['height'], fps=v['r_frame_rate'], audio=bool(a), dur=float(j['format']['duration']))
pieces = [l.strip() for l in open(sys.argv[1], encoding='utf-8') if l.strip() and not l.startswith('#')]
out = sys.argv[2]; bad = []; total = 0
for p in pieces:
    i = probe(p); total += i['dur']
    ok = i['w'] == 1920 and i['h'] == 1080 and i['fps'] == '30/1' and i['audio']
    print(f"{'OK ' if ok else '★X '} {i['dur']:7.2f}s {i['w']}x{i['h']} {i['fps']} 소리={'있음' if i['audio'] else '없음'}  {p}")
    if not ok: bad.append(p)
if bad: print('조각 규격 불일치 — 합치지 않음'); sys.exit(1)
args = ['ffmpeg', '-nostdin', '-v', 'error', '-y']
for p in pieces: args += ['-i', p]
fc = ''.join(f'[{k}:v][{k}:a]' for k in range(len(pieces))) + f'concat=n={len(pieces)}:v=1:a=1[v][a]'
args += ['-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '19', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out]
r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
if r.returncode: print(r.stderr[-800:]); sys.exit(1)
d = probe(out)['dur']; print(f'합본 {d:.2f}s (조각 합 {total:.2f}s) = {int(d // 60)}분 {d % 60:.0f}초')
fail = abs(d - total) > 1.0
log = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', out, '-vf', 'blackdetect=d=1:pix_th=0.06', '-af', 'silencedetect=n=-45dB:d=3', '-f', 'null', '-'],
                     capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', log); sil = re.findall(r'silence_start: ([\d.]+)', log)
print(f'검은 화면(1초+) {len(blacks)}곳 {blacks[:5]} / 무음(3초+) {len(sil)}곳 {sil[:5]}')
sys.exit(1 if (fail or blacks or sil) else 0)
