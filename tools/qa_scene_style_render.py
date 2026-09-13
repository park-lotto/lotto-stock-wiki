"""실제 임시 DB 저장 및 실제 FFmpeg 합성. 라이브 DB/외부 API는 사용하지 않는다."""
import json
import sys
import shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shopping_shorts import video_assemble as va
from shopping_shorts.scene_style import compose, context_for, validate_snapshot
from shopping_shorts.store import Store

work=Path(__file__).resolve().parents[1]/".tmp/scene-style-qa"
work.mkdir(parents=True,exist_ok=True)
snapshot=json.loads((work/(sys.argv[1] if len(sys.argv)>1 else "snapshot.json")).read_text(encoding="utf-8"))
source=work/"source.mp4"
va._run_ffmpeg(["ffmpeg","-y","-loop","1","-i",str(Path(__file__).resolve().parents[1]/"out/assets/scene-style/uniform-household-demo.png"),"-f","lavfi","-i","sine=frequency=440:sample_rate=44100","-t","3","-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-r","30","-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p","-c:a","aac",str(source)])
timeline=[{"beat_idx":i,"t0":i,"dur":1,"narration":caption,"caption_lines":[caption]} for i,caption in enumerate(["첫 번째 실제 자막","두 번째 실제 자막","마지막 실제 자막"])]
tts=work/"voice.wav"
va._run_ffmpeg(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=440:sample_rate=44100","-t","1",str(tts)])
plan={"beats":[{**b,"tts_path":str(tts),"target_seconds":1,"role":"hook" if i==0 else "body","primary":{"video_id":"s0","start":i,"end":i+1}} for i,b in enumerate(timeline)]}
from shopping_shorts import app as module
from fastapi.testclient import TestClient
module.DB_PATH=str(work/"qa.db");module._AUTH_ON=False
module._MIX_WORK_DIR=work
media_dir=work/'scene-style-qa/s0';media_dir.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,media_dir/'source.mp4')
store=Store(module.DB_PATH)
if not store.get_mix_job('scene-style-qa'):
    store.create_mix_job('scene-style-qa',[],3,'free')
store.update_mix_job('scene-style-qa',edit_plan=plan)
with TestClient(module.app) as client:
    response=client.post('/api/produce/mix/settings',json={"job_id":"scene-style-qa","deco":{"scene_style":snapshot}})
    assert response.status_code==200,response.text
    saved=Store(module.DB_PATH).get_mix_job('scene-style-qa')['deco']['scene_style']
    assert saved==validate_snapshot(snapshot)
    assert client.get('/api/produce/scene-style/assets/out/scene-style-connect.js').status_code==200
    assert client.get('/api/produce/scene-style/assets/.env').status_code==404
    response=client.get('/api/produce/scene-style/context/scene-style-qa')
    assert response.status_code==200,response.text
    assert len(response.json()['context']['scenes'])==3
    assert client.get(response.json()['context']['scenes'][0]['media']).status_code==200
with va.preview_preset():
    va.assemble(plan,{i:str(tts) for i in range(3)},{"s0":str(source)},work/"final.mp4",deco={"scene_style":saved})
for i in range(3):
    va._run_ffmpeg(["ffmpeg","-y","-ss",str(i+.5),"-i",str(work/"final.mp4"),"-frames:v","1",str(work/f"final-{i}.png")])
for moment in (.1,.65):
    va._run_ffmpeg(["ffmpeg","-y","-ss",str(moment),"-i",str(work/"final.mp4"),"-frames:v","1",str(work/f"motion-{moment}.png")])
story={**saved,"mode":"story","presetId":"t11","captionTexts":{},"effects":{}}
with va.preview_preset():
    compose(source,timeline,story,work/"story-final.mp4",work)
for i in range(2):
    va._run_ffmpeg(["ffmpeg","-y","-ss",str(i+.5),"-i",str(work/"story-final.mp4"),"-frames:v","1",str(work/f"story-final-{i}.png")])
print(json.dumps({"ok":True,"db_saved":True,"duration":va._probe_duration(work/"final.mp4"),"output":str(work/"final.mp4")},ensure_ascii=False))
