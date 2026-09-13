"""Render the actual QA job saved by qa_lines_server, preserving its caption splits."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shopping_shorts.store import Store
from shopping_shorts import video_assemble as va
work=Path(__file__).resolve().parents[1]/'.tmp/scene-style-qa'
job=Store(str(work/'qa.db')).get_mix_job('scene-style-qa')
plan=job['edit_plan']
with va.preview_preset():
    va.assemble(plan,{i:str(work/'voice.wav') for i in range(3)},{'s0':str(work/'source.mp4')},work/'saved-lines.mp4',deco=job['deco'])
for t in (1.1,1.7):
    va._run_ffmpeg(['ffmpeg','-y','-ss',str(t),'-i',str(work/'saved-lines.mp4'),'-frames:v','1',str(work/f'saved-lines-{t}.png')])
print({'duration':va._probe_duration(work/'saved-lines.mp4'),'output':str(work/'saved-lines.mp4')})
