"""장면꾸미기 컨텍스트 속도 — 진짜 앱(격리 DB)으로 잰다. 가짜 응답 없음 (2026-09-22).
  py tools/scene_font_research/check_context_speed.py <출력폴더> [비트수=12]

무엇을 재나(사장님: "뜨는 로딩이 10초 이상, 영상 화면 사진이 제일 늦다"):
  ① 컨텍스트 1회 호출 → 그 job의 장면 사진(beatframes/*.jpg)이 **뒤에서 전부** 만들어지는가, 몇 초 걸리나
     (고치기 전: 사진은 장면을 넘길 때 한 장씩 ffmpeg로 뽑혔다 — 라이브 저널 1~2.5초 간격)
  ② 같은 컨텍스트 두 번째 호출이 첫 호출보다 빠른가(ffprobe 캐시) — 첫/둘째 소요초를 찍는다
  ③ 미리 뽑힌 뒤 beatframe 요청이 즉시(0.2초 안) 오는가
라이브 DB·외부 API는 쓰지 않는다. check_thumb_pin.py와 같은 방식으로 job을 만든다.
"""
import sys, time, shutil, threading, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn

JOB, PORT = 'scene-ctx-qa', 8775
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

# N초짜리 영상(초마다 색이 바뀜) + 1초 TTS N개(파일이 달라야 ffprobe가 N번 돈다)
final = work / JOB / 'final.mp4'; final.parent.mkdir(parents=True)
va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', f'testsrc2=s=540x960:d={N}', '-r', '30', '-pix_fmt', 'yuv420p', str(final)])
beats = []
for i in range(N):
    tts = work / f'voice{i}.wav'
    va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
    beats.append({'beat_idx': i, 't0': i, 'dur': 1, 'narration': f'자막 {i}', 'caption_lines': [f'자막 {i}'], 'tts_path': str(tts),
                  'target_seconds': 1, 'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}})
plan = {'beats': beats}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work
module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], N, 'free'); store.update_mix_job(JOB, edit_plan=plan)

server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(50):
    try: urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/produce/scene-style/assets/out/precision20-data.js', timeout=1); break
    except Exception: time.sleep(0.2)

def get(path):
    t = time.perf_counter(); r = urllib.request.urlopen(f'http://127.0.0.1:{PORT}{path}', timeout=60); r.read(); return r.status, time.perf_counter() - t

frames = work / JOB / 'beatframes'
need(not frames.exists() or not list(frames.glob('*.jpg')), '시작 전엔 장면 사진이 하나도 없다')
st, t1 = get(f'/api/produce/scene-style/context/{JOB}')
need(st == 200, f'컨텍스트 1회 200 ({t1:.2f}초)')
deadline = time.time() + 60
while time.time() < deadline and len(list(frames.glob('*.jpg'))) < N: time.sleep(0.2)
made = len(list(frames.glob('*.jpg'))); took = 60 - (deadline - time.time())
need(made == N, f'① 컨텍스트만 불렀는데 장면 사진 {made}/{N}장이 뒤에서 만들어졌다 ({took:.1f}초)')
st, t2 = get(f'/api/produce/scene-style/context/{JOB}')
need(st == 200 and t2 < t1 / 5, f'② 두 번째 컨텍스트 {t2:.2f}초 ≤ 첫 번째 {t1:.2f}초 (ffprobe 캐시)')
st, t3 = get(f'/api/produce/mix/beatframe/{JOB}/{N - 1}')
need(st == 200 and t3 < 0.2, f'③ 미리 뽑힌 마지막 장면 사진 응답 {t3:.3f}초')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
