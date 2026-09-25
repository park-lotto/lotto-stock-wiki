"""썸네일 후보 핀이 **꾸민 화면**(제목·띠 포함)으로 가는지 — 진짜 앱(격리 DB)·진짜 렌더러로 잰다 (2026-09-23 사장님 "훅 장면을 쓰고 싶은 건데").
  py tools/scene_font_research/check_thumb_pin_styled.py <출력폴더>

  ① styled=false(종전) → 원본 프레임(파랑) 그대로
  ② styled=true + 장면꾸미기 저장본 있음 → 위쪽에 제목 띠(어두움)가 얹힌 그림, 아래는 원본(파랑)
  ③ 저장본이 없는 job에 styled=true → 조용히 원본 프레임(막히지 않는다)
"""
import sys, time, shutil, threading, pathlib, json, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / 'mixwork'; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
from PIL import Image
from shopping_shorts import video_assemble as va, scene_style
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn

JOB, PORT = 'pin-styled-qa', 8779
BASE = f'http://127.0.0.1:{PORT}'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)

tts = work / 'voice.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
(work / JOB).mkdir(parents=True)
va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920:d=3', '-r', '30', '-pix_fmt', 'yuv420p', str(work / JOB / 'final.mp4')])
caps = ['빗질 한 번에 무슨 일이', '아침마다 머리 감고', '소파 틈새 낀 먼지까지']
plan = {'beats': [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
                   'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}} for i, c in enumerate(caps)]}
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module._MIX_WORK_DIR = work; module._THUMB_DIR = work / '_thumbs'
store = Store(module.DB_PATH); store.create_mix_job(JOB, [], 3, 'free')
store.update_mix_job(JOB, edit_plan=plan, headcopy={'text': '빗질 한 번에 무슨\n일이 벌어질까', 'subline': '손에 에센스 묻혀가며'})
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

def post(body):
    r = urllib.request.urlopen(urllib.request.Request(f'{BASE}/api/produce/thumb/pin', data=json.dumps(body).encode('utf-8'), headers={'Content-Type': 'application/json'}))
    return json.loads(r.read())
def pin_file(name): return module._thumb_dir(JOB) / name
def bands(png):
    im = Image.open(png).convert('RGB'); w, h = im.size
    top = [im.getpixel((x, y)) for y in range(int(h * .02), int(h * .08), 6) for x in range(int(w * .3), int(w * .7), 20)]
    mid = [im.getpixel((x, y)) for y in range(int(h * .60), int(h * .80), 10) for x in range(int(w * .3), int(w * .7), 20)]
    lum = lambda px: sum(sum(p) / 3 for p in px) / len(px)
    blue = lambda px: sum(1 for p in px if p[2] > 150 and p[0] < 80 and p[1] < 80) / len(px)
    return {'top_lum': round(lum(top)), 'top_blue': round(blue(top), 2), 'mid_blue': round(blue(mid), 2)}

# ③ 저장본 없음 + styled → 원본 그대로
d3 = post({'job_id': JOB, 'beat_idx': 0, 'scene_index': 1, 'styled': True})
b3 = bands(pin_file(d3['name']))
need(d3.get('ok') and not d3.get('styled') and b3['top_blue'] > 0.9, f"③ 꾸미기 저장본 없으면 원본 프레임 그대로 (styled {d3.get('styled')}, {b3})")
# 장면꾸미기 저장본 적용
snap = scene_style.validate_snapshot({'version': 1, 'mode': 'story', 'presetId': 't11', 'sceneIndex': 1, 'frameKind': 'hook'})
store.update_mix_job(JOB, deco={'scene_style': snap})
# ① 종전(styled 없음)
d1 = post({'job_id': JOB, 'beat_idx': 0})
b1 = bands(pin_file(d1['name']))
need(not d1.get('styled') and b1['top_blue'] > 0.9, f"① styled 없으면 종전대로 원본(파랑) ({b1})")
# ② styled
t0 = time.time(); d2 = post({'job_id': JOB, 'beat_idx': 0, 'scene_index': 1, 'styled': True}); took = time.time() - t0
b2 = bands(pin_file(d2['name']))
need(d2.get('styled') and b2['top_blue'] < 0.2 and b2['top_lum'] < 150 and b2['mid_blue'] > 0.9, f"② styled → 위쪽은 제목 띠(어둡고 파랑 아님), 아래는 원본(파랑) ({b2}, {took:.1f}초) — 고치기 전엔 위도 파랑")
shutil.copyfile(pin_file(d2['name']), out / 'pin_styled.jpg')
need(len(d2.get('pins') or []) >= 1 and d2['pins'][0]['name'] == d2['name'], '② 후보 목록 맨 앞에 들어간다')

# ── 2026-09-25 고객 job 92976b481a86: 핀 6번 중 그림 수신 2번 + 핀이 저장보다 먼저 나감 ──
# ④ 저장 전(서버 저장본 없음)이라도 편집기가 보낸 **지금 화면 설정**으로 찍는다 — 고치기 전엔 원본(파랑)
store.update_mix_job(JOB, deco={})
d4 = post({'job_id': JOB, 'beat_idx': 0, 'scene_index': 1, 'styled': True, 'scene_style': snap})
b4 = bands(pin_file(d4['name']))
need(d4.get('styled') and b4['top_blue'] < 0.2 and b4['mid_blue'] > 0.9, f"④ 저장 전 화면 설정으로 찍힘 ({b4}) — 고치기 전엔 위도 파랑")
# ⑤ 화면에서 '템플릿 없음'(null)을 골랐으면 저장본(t11)이 있어도 원본 — 고치기 전엔 저장본 띠가 찍힘
store.update_mix_job(JOB, deco={'scene_style': snap})
d5 = post({'job_id': JOB, 'beat_idx': 0, 'scene_index': 1, 'styled': True, 'scene_style': None})
b5 = bands(pin_file(d5['name']))
need(not d5.get('styled') and b5['top_blue'] > 0.9, f"⑤ 화면이 템플릿 없음이면 원본 ({b5})")
# ⑥ 같은 장면을 다시 보내면 7단계가 받는 주소가 바뀐다(같은 파일명 덮어쓰기라 주소가 같으면 화면이 옛 그림을 쓴다)
def pin_urls():
    th = (Store(module.DB_PATH).get_mix_job(JOB).get('thumbnail') or {})
    return [f['url'] for f in module._with_pins(JOB, th, []) if f.get('pin')]
u_before = pin_urls(); time.sleep(0.05)
post({'job_id': JOB, 'beat_idx': 0, 'scene_index': 1, 'styled': True, 'scene_style': snap})
u_after = pin_urls()
need(len(u_before) == 1 and len(u_after) == 1 and u_before != u_after, f"⑥ 다시 보내면 핀 주소가 바뀐다 ({u_before} → {u_after}) — 고치기 전엔 같은 주소")
try:
    r = urllib.request.urlopen(BASE + u_after[0]); need(r.status == 200 and len(r.read()) > 1000, '⑥ ?v 붙은 주소로 그림이 실제로 내려온다')
except Exception as e:
    need(False, f'⑥ ?v 붙은 주소 요청 실패 {e}')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
