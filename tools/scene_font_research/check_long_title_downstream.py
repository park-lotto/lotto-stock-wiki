"""관제 163 — 이븐쇼핑(t11) 틀에서 제목이 한도(첫 줄 11자·둘째 줄 10자)를 넘거나 둘째 줄이 비어도
화면이 막지 않게 바꿨다(2026-10-08 사장님). 그 스냅샷이 **썸네일·최종렌더·캡컷**까지 실제로 가는지 잰다.
  ① 서버 검증 통과  ② 렌더·캡컷 레이어(render_layers)  ③ 썸네일 한 장(render_layer_one)  ④ 최종 합성(compose)
사용: py tools/scene_font_research/check_long_title_downstream.py <출력폴더>
"""

import sys, pathlib, shutil
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble as va
from PIL import Image
out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
tts = out / 'v.wav'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '1', str(tts)])
src = out / 'src.mp4'; va._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920:d=2', '-r', '30', '-pix_fmt', 'yuv420p', str(src)])
timeline = [{'beat_idx': i, 't0': i, 'dur': 1, 'narration': c, 'caption_lines': [c], 'tts_path': str(tts), 'target_seconds': 1,
             'role': 'hook' if i == 0 else 'body', 'primary': {'video_id': 's0', 'start': i, 'end': i + 1}}
            for i, c in enumerate(['주부들도 감탄한 천재 아이디어', '이건 바로 핑거 찹스틱'])]
TEXT = {'channel': '숏템메이커', 'hook1': '주부들도 깜짝 놀란 천재 아이디어', 'hook2': '', 'bodyTitle': '주부들도 깜짝 놀란 천재 아이디어 상품 공개합니다'}   # 첫 줄 18자·둘째 줄 비움
for mode, fk in (('story', 'hook'),):
    try:
        scene_style.validate_snapshot({'version': 1, 'mode': mode, 'presetId': 't11', 'sceneIndex': 0, 'frameKind': fk, 'text': TEXT})
        need(True, f'① 서버 검증 통과 ({mode})')
    except Exception as exc:
        need(False, f'① 서버 검증 실패 ({mode}): {exc}')
snap = scene_style.validate_snapshot({'version': 1, 'mode': 'story', 'presetId': 't11', 'sceneIndex': 0, 'frameKind': 'hook', 'text': TEXT})
def ink(png, a0, a1):
    im = Image.open(png).convert('RGBA'); w, h = im.size; al = im.split()[3]
    return sum(1 for y in range(int(h * a0), int(h * a1), 3) for x in range(int(w * .1), int(w * .9), 6) if al.getpixel((x, y)) > 40)
# ② 렌더·캡컷이 쓰는 레이어 — 자막은 제목 바로 아래(19~30%, 2026-09-25 사장님 인스타식)
scene_style.render_layers(timeline, snap, out / 'layers', {'text': '주부들도 감탄한\n천재 아이디어'}, 'dsqa')
pngs = sorted((out / 'layers').rglob('*.png'))
need(len(pngs) >= 2, f'② 렌더·캡컷용 레이어 {len(pngs)}장')
if len(pngs) >= 2:
    need(ink(pngs[0], .05, .25) > 300 and ink(pngs[0], .19, .30) > 300,
         f'② 훅 레이어에 제목·자막이 모두 찍힌다 (제목 {ink(pngs[0], .05, .25)} / 자막 {ink(pngs[0], .19, .30)})')
    need(ink(pngs[1], .05, .25) > 300 and ink(pngs[1], .19, .30) > 300,
         f'② 본문 레이어도 마찬가지 (제목 {ink(pngs[1], .05, .25)} / 자막 {ink(pngs[1], .19, .30)})')
# ③ 썸네일이 쓰는 한 장
one = pathlib.Path(scene_style.render_layer_one(timeline, snap, out / 'thumb_style', 0,
                   {'text': '주부들도 감탄한' + chr(10) + '천재 아이디어'}, 'dsqa'))   # 폴더를 주고 PNG 경로를 돌려받는다
need(one.exists() and ink(one, .05, .25) > 300, f'③ 썸네일용 한 장에도 제목이 찍힌다 ({ink(one, .05, .25) if one.exists() else "없음"})')
# ④ 최종 합성 mp4
final = out / 'final.mp4'
scene_style.compose(str(src), timeline, snap, str(final), out / 'cw', {'text': '주부들도 감탄한\n천재 아이디어'})
need(final.exists() and final.stat().st_size > 1000, f'④ 최종 합성 mp4 생성 ({final.stat().st_size if final.exists() else 0} 바이트)')
if final.exists():
    frame = out / 'f.png'; va._run_ffmpeg(['ffmpeg', '-y', '-ss', '0.5', '-i', str(final), '-frames:v', '1', str(frame)])
    im = Image.open(frame).convert('RGB'); w, h = im.size
    top = [im.getpixel((x, y)) for y in range(int(h * .05), int(h * .25), 4) for x in range(int(w * .2), int(w * .8), 6)]
    notblue = sum(1 for p in top if not (p[2] > 150 and p[0] < 80))
    need(notblue > 200, f'④ 완성 영상 프레임 위쪽에 글자가 남아 있다 (파랑 아닌 점 {notblue})')
# ⑤ 캡컷 — app.api_mix_capcut 이 render_layers 뒤에 부르는 세 함수를 그대로 부른다
try:
    _hc = {'text': '주부들도 감탄한' + chr(10) + '천재 아이디어'}
    _lay = scene_style.render_layers(timeline, snap, out / 'cc', _hc, 'dsqa')
    _sc = scene_style.context_for(timeline, _hc, snap, 'dsqa')['scenes']
    _ov = scene_style.overlay_spans(_sc, _lay, out / 'cc')
    scene_style.dim_spans(_sc, snap, _lay, out / 'cc'); scene_style.capcut_fx_spans(_sc, snap, _lay)
    need(bool(_ov), f'⑤ 캡컷 장면 레이어 구간 {len(_ov or [])}개')
except Exception as exc:
    need(False, f'⑤ 캡컷 경로 예외: {exc}')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
