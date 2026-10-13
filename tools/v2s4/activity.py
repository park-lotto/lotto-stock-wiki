"""녹화본 활동량: 0.25초마다 이전 프레임과 바뀐 화소 비율(0~1). 사용: activity.py <mp4> → json 리스트"""
import subprocess, sys, json, numpy as np
def activity(path, step=0.25, w=160, h=90):
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={1/step},scale={w}:{h},format=gray', '-f', 'rawvideo', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    d = [0.0] + [float((np.abs(fr[i] - fr[i - 1]) > 12).mean()) for i in range(1, len(fr))]
    return d
if __name__ == '__main__':
    print(json.dumps([round(x, 4) for x in activity(sys.argv[1])]))
