# -*- coding: utf-8 -*-
"""고친 대본으로 **음성·자막을 다시 뽑는다** — 2026-08-14 사장님
"대본 수정 후 음성 자막은 다시 생성 어떻게 하나 / 미리보기에 대본도 안 바뀌고".

실험실에서 대본만 고치면 화면의 자막·음성은 옛 문장 그대로다. 자막을 JS로 다시 나누면
라이브(_caption_segments)와 두 벌이 되어 반드시 어긋나므로(0순위-B), **서버에서 라이브와
같은 코드로 다시 만들어 받아온다**:

    ① 고친 문장을 서버로 보낸다
    ② 서버가 shopping_shorts.tts로 음성을 만들고(라이브와 같은 보이스 설정),
       video_assemble._caption_segments/_caption_durations로 자막을 계산한다
    ③ mp3와 자막을 로컬로 받아 data.json을 갱신하고 페이지를 다시 만든다

쓰는 법(보통은 실험실의 '음성·자막 다시 뽑기' 버튼이 대신 부른다):
    py tools/scene_lab/retts.py <job_id> <beat_idx> "<고친 대본>"
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from fetch import HOST, OUT, REPO, _key, scp, ssh   # noqa: E402  (같은 SSH 설정을 쓴다)


def _py_with_env(code):
    """서버 파이썬을 **서비스와 같은 환경**으로 실행한다.

    ★2026-08-14 실사고: 그냥 python을 띄웠더니 ELEVENLABS_API_KEY가 없어 tts가 무음 mock을
    만들었다(mean_volume -91dB). 키는 저장소 .env가 아니라 systemd EnvironmentFile
    `/etc/shopping-shorts.env`에 있다(systemctl show로 확인). 그래서 그 파일을 읽어 넣는다 —
    안 그러면 '다시 뽑기'가 조용히 무음을 만든다.
    """
    # ★코드를 인라인 -c로 넘기면 따옴표가 겹쳐 깨진다(실측: unexpected EOF).
    #   임시 파일로 올려 실행한다 — 따옴표 문제가 원천적으로 없다.
    tmp = Path(os.environ.get('TEMP', '/tmp')) / '_sl_retts_code.py'
    tmp.write_text(code, encoding='utf-8')
    up = subprocess.run(['scp', '-q', '-i', _key(), str(tmp), HOST + ':/tmp/sl_retts_code.py'],
                        capture_output=True, text=True)
    if up.returncode != 0:
        sys.exit('[중단] 코드 업로드 실패: ' + (up.stderr or '')[-200:])
    return ssh('sudo bash -c ' + chr(39) +
               'set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a; '
               'cd ' + REPO + ' && /home/ubuntu/venv/bin/python /tmp/sl_retts_code.py' + chr(39))


def retts(job_id, beat_idx, text):
    work = OUT / job_id
    data_path = work / "data.json"
    if not data_path.exists():
        sys.exit(f"[중단] 먼저 fetch로 받아라: {data_path}")
    beat_idx = int(beat_idx)
    text = (text or "").strip()
    if not text:
        sys.exit("[중단] 대본이 비었다")

    # 서버에서 음성+자막 생성. 라이브와 같은 함수만 쓴다(새 판단 0).
    code = f"""
import json, os, sys
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')
from shopping_shorts import tts as _tts
from shopping_shorts import video_assemble as va
from shopping_shorts import mix_pipeline as mp
text = {text!r}
out = '/tmp/sl_retts_{beat_idx}.mp3'
if os.path.exists(out):
    os.remove(out)
# ★성우 = 미나(kr-mina-expressive). 값을 여기 옮겨 적지 않는다 — mix_pipeline._DEFAULT_VOICE를
#   그대로 읽어 쓴다(두 벌이 되면 라이브와 목소리가 갈린다, 0순위-B).
vid, vset, spd, _tempo, _trim, _nat, mid, _pace = mp._voice_params(None)
print('   성우:', mp._DEFAULT_VOICE.get('preset_id'), '/ speed', spd)
_tts.synthesize_tts(text, out, voice_id=vid, voice_settings=vset, speed=spd, model_id=mid)
dur = 0.0
try:
    import subprocess as sp
    r = sp.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',out],
               capture_output=True, text=True)
    dur = float((r.stdout or '0').strip())
except Exception:
    pass
segs = va._caption_segments(text, None)
durs = va._caption_durations(segs, dur or 3.0)
t, rows = 0.0, []
for s, d in zip(segs, durs):
    rows.append({{'text': s, 'start': round(t, 3), 'end': round(t + d, 3)}})
    t += d
json.dump({{'dur': round(dur, 3), 'captions': rows}},
          open('/tmp/sl_retts_{beat_idx}.json', 'w'), ensure_ascii=False)
os.chmod(out, 0o644); os.chmod('/tmp/sl_retts_{beat_idx}.json', 0o644)
print('   음성 %.2f초 / 자막 %d구절' % (dur, len(rows)))
"""
    print(f"[1/3] 서버에서 음성·자막 만드는 중… (칸 {beat_idx + 1})")
    print(_py_with_env(code))

    print("[2/3] 내려받는 중…")
    if not scp(f"/tmp/sl_retts_{beat_idx}.mp3", work / "tts" / f"beat_{beat_idx}.mp3"):
        sys.exit("[중단] mp3 다운로드 실패")
    meta_local = work / f"_retts_{beat_idx}.json"
    if not scp(f"/tmp/sl_retts_{beat_idx}.json", meta_local):
        sys.exit("[중단] 자막 다운로드 실패")
    meta = json.loads(meta_local.read_text(encoding="utf-8"))
    meta_local.unlink(missing_ok=True)

    # data.json 갱신 — 대본·길이·자막을 새 것으로. 나머지(장면·썸네일)는 그대로 둔다.
    d = json.loads(data_path.read_text(encoding="utf-8"))
    d["beats"][beat_idx]["narration"] = text
    d["beats"][beat_idx]["target_seconds"] = round(meta["dur"], 1)
    d.setdefault("captions", {})[str(beat_idx)] = meta["captions"]
    d.setdefault("tts_dur", {})[str(beat_idx)] = meta["dur"]
    data_path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    print("[3/3] 페이지 다시 만드는 중…")
    subprocess.run([sys.executable, str(BASE / "build.py"), str(work)], check=True)
    print("완료: 칸 %d, %.2f초, 자막 %d구절" % (beat_idx + 1, meta["dur"], len(meta["captions"])))
    return meta


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    retts(sys.argv[1], sys.argv[2], sys.argv[3])
