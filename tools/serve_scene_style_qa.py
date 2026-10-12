"""qa_scene_style_render.py가 만든 임시 DB로 로컬 연결 검증 서버를 띄운다."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shopping_shorts import app as module
import uvicorn
work=Path(__file__).resolve().parents[1]/'.tmp/scene-style-qa'
if not (work/'qa.db').exists():
    raise SystemExit('먼저 qa_scene_style_render.py를 실행하세요')
module.DB_PATH=str(work/'qa.db');module._MIX_WORK_DIR=work;module._AUTH_ON=False
# Synthetic sine-wave QA audio has no words; never request external transcription.
module.mix_pipeline._beat_words_src=lambda *args,**kwargs:([], 'estimate')
if __name__=='__main__':
    uvicorn.run(module.app,host='127.0.0.1',port=8768,log_level='warning')
