"""S4 녹화본 → 음성 길이에 맞춘 컷 편집본.
1) 0.25초 활동량으로 '가만히 있는 구간'(1.0초 넘게)은 0.35초만 남기고 잘라낸다
2) 남은 길이 L 이 음성 V 보다 길면: L<=1.4V 면 균일 배속, 넘으면 3초 덩어리를 순서대로 고르게 골라 1.3V 로 줄인 뒤 배속
3) 짧으면 마지막 화면을 잡아 늘린다(멈춤은 컷 경계로 나눠 넣음)
출력: <out>/rec.mp4(무음 30fps) + meta.json{dur, cuts:[출력초], focus:[[출력초,cx,cy,act]]}
사용: cut.py <음성mp3> <out> <녹화1.mp4> [녹화2.mp4 ...]"""
import subprocess, sys, json, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
STEP = 0.25
def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout)
def frames(path, w=160, h=90):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={1/STEP},scale={w}:{h},format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
def main():
    voice, out, recs = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    V = dur(voice)
    keep = []  # (파일, 시작, 끝, [(t, cx, cy, act)])
    for r in recs:
        fr = frames(r); n = len(fr)
        act = np.zeros(n); cen = [(0.5, 0.5)] * n
        for i in range(1, n):
            m = np.abs(fr[i] - fr[i - 1]) > 12
            act[i] = m.mean()
            if m.sum() > 3:
                ys, xs = np.nonzero(m); cen[i] = (xs.mean() / m.shape[1], ys.mean() / m.shape[0])
        busy = act > 0.0015
        # 처음·끝 2초 가만히 = 녹화 시작/정지 → 버린다
        i = 0
        segs = []; s = None; idle = 0
        for i in range(n):
            if busy[i]:
                if s is None: s = max(0, i - 1)
                idle = 0
            elif s is not None:
                idle += 1
                if idle * STEP > 1.0:
                    segs.append((s, i - idle + 2)); s = None; idle = 0
        if s is not None: segs.append((s, n))
        for a, b in segs:
            foc = [(k * STEP, *cen[k], act[k]) for k in range(a, b)]
            keep.append([r, a * STEP, min(b * STEP, dur(r)), foc])
    # 녹화는 음성을 들으며 찍었다 → 원래 흐름이 곧 싱크. 앞뒤 정적만 잘라 그대로 쓸 수 있으면 그게 최선
    raw = []
    for r in recs:
        ks = [k for k in keep if k[0] == r]
        if ks: raw.append([r, ks[0][1], ks[-1][2], [f for k in ks for f in k[3]]])
    RL = sum(b - a for _, a, b, _ in raw)
    if RL <= 1.35 * V:
        keep = raw
    L = sum(b - a for _, a, b, _ in keep)
    if L > 1.4 * V:   # 덩어리 골라 줄이기
        chunks = []
        for r, a, b, foc in keep:
            t = a
            while t < b - 0.5:
                e = min(b, t + 3.0); chunks.append([r, t, e, [f for f in foc if t <= f[0] < e]]); t = e
        tot = sum(c[2] - c[1] for c in chunks); target = 1.3 * V
        acc = 0; pick = []; budget = 0
        for c in chunks:   # 고르게 솎기: 누적 비율이 목표 비율을 넘지 않게
            budget += (c[2] - c[1]) * target / tot
            if budget >= (c[2] - c[1]) * 0.5:
                pick.append(c); budget -= c[2] - c[1]
        # 같은 파일·이어지는 덩어리는 다시 붙인다
        keep = []
        for c in pick:
            if keep and keep[-1][0] == c[0] and abs(keep[-1][2] - c[1]) < 0.01:
                keep[-1][2] = c[2]; keep[-1][3] += c[3]
            else: keep.append(c)
        # 손으로 정한 구간(overrides.json): [녹화번호, 원본시작, 원본끝, 출력시작, 출력끝] — 구간마다 따로 배속
    ov = json.load(open(os.path.join(os.path.dirname(__file__), 'overrides.json'), encoding='utf8')).get(os.path.basename(out))
    if ov:
        return manual(ov, recs, out, V)
    L = sum(b - a for _, a, b, _ in keep)
    speed = max(0.8, L / V)
    hold = max(0.0, V - L / speed) / max(1, len(keep))   # 모자라면 컷마다 멈춤을 나눠 넣는다
    parts = []; cuts = []; focus = []; t = 0.0
    for k, (r, a, b, foc) in enumerate(keep):
        f = os.path.join(out, f'_p{k:03d}.mp4')
        vf = f'trim={a}:{b},setpts=(PTS-STARTPTS)/{speed},fps=30,scale=1280:720'
        if hold > 0.05: vf += f',tpad=stop_mode=clone:stop_duration={hold:.3f}'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', r, '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', f], check=True)
        cuts.append(round(t, 3))
        focus += [[round(t + (ft - a) / speed, 2), round(cx, 3), round(cy, 3), round(ac, 4)] for ft, cx, cy, ac in foc]
        t += (b - a) / speed + (hold if hold > 0.05 else 0)
        parts.append(f)
    lst = os.path.join(out, '_list.txt')
    open(lst, 'w').write(''.join(f"file '{os.path.basename(p)}'\n" for p in parts))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', '_list.txt', '-c', 'copy', 'rec.mp4'], check=True, cwd=out)
    for p in parts: os.remove(p)
    os.remove(lst)
    json.dump({'dur': round(V, 3), 'recLen': round(t, 3), 'speed': round(speed, 3), 'cuts': cuts, 'focus': focus}, open(os.path.join(out, 'meta.json'), 'w'))
    print(f'V={V:.1f} L={L:.1f} speed={speed:.2f} cuts={len(cuts)} out={t:.1f}')
def manual(ov, recs, out, V):
    parts = []; cuts = []; focus = []
    for k, (ri, a, b, o0, o1) in enumerate(ov):
        r = recs[ri]; fr = frames(r); sp = (b - a) / (o1 - o0)
        f = os.path.join(out, f'_p{k:03d}.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', r, '-vf', f'trim={a}:{b},setpts=(PTS-STARTPTS)/{sp},fps=30,scale=1280:720', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', f], check=True)
        cuts.append(o0); parts.append(f)
        for i in range(int(a / STEP) + 1, min(len(fr), int(b / STEP))):
            m = np.abs(fr[i] - fr[i - 1]) > 12
            if m.sum() > 3:
                ys, xs = np.nonzero(m)
                focus.append([round(o0 + (i * STEP - a) / sp, 2), round(xs.mean() / m.shape[1], 3), round(ys.mean() / m.shape[0], 3), round(float(m.mean()), 4)])
    open(os.path.join(out, '_list.txt'), 'w').write(''.join("file '" + os.path.basename(p) + "'" + chr(10) for p in parts))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', '_list.txt', '-c', 'copy', 'rec.mp4'], check=True, cwd=out)
    for p in parts: os.remove(p)
    os.remove(os.path.join(out, '_list.txt'))
    json.dump({'dur': round(V, 3), 'recLen': ov[-1][4], 'manual': True, 'cuts': cuts, 'focus': focus}, open(os.path.join(out, 'meta.json'), 'w'))
    print(f'V={V:.1f} 수동 구간 {len(ov)}개')
main()
