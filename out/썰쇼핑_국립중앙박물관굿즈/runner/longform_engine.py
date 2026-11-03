"""Geumbit production runtime: explicit plans, preserved paid audio, incremental local film."""
from pathlib import Path
import base64
import faulthandler
import importlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import wave
from film_editor import command,digest,file_lock,request_tts,PaidUncertain,typecast_body
from longform_state import VERSION,Stages,ProductionError,read,save,files,native_path,file_sha256,digest_file as file_digest
from longform_contract import validate,validate_requested_duration,FONT_NAMES,opening_review,render_key_visual
import longform_audio
import longform_source_audio

VOICE={'provider':'typecast','endpoint':'https://api.typecast.ai/v1/text-to-speech/with-timestamps',
       'voice_id':'tc_68257f68bc6e3c161ab5078d','model':'ssfm-v30','language':'kor',
       'emotion':'normal','tempo':1.05,'seed':42}
NARRATION_PROFILE={'tempo':1.05,'sentence_gap_add_seconds':.3}

def chosen_voice(cfg=None):
 """VOICE with the job's Typecast voice/language (server config typecast_voice). Korean default jobs carry none, so their
 settings — and every paid-voice identity digest built from them — stay byte-identical (2026-10-23 · 인물형 롱폼 영어)."""
 chosen=(cfg or {}).get('typecast_voice') or {}
 return dict(VOICE,**{k:chosen[k] for k in ('voice_id','language') if isinstance(chosen.get(k),str) and chosen[k]})

def voice_settings(plan,cfg=None):
 # Old plans must retain their exact paid identity when resumed after update.
 return dict(chosen_voice(cfg),tempo=1.05 if plan.get('narration') else 1.15)

def source_paths(plan):return [Path(x['path']) for x in plan['media'].values()]

def scene_media_paths(visual,media):
 # Transition textures are dependencies, not extra subject-photo/video slots.
 ids=list(visual['media'])
 if visual.get('grain_wipe'):ids.append(visual['grain_wipe']['media'])
 from longform_cut_review import review_dependencies
 from longform_video_treatment import dependencies
 return [media[mid]['path'] for mid in dict.fromkeys(ids)]+review_dependencies(visual)+dependencies(visual)

# Runner code identities are hashed once per process (6-00: no re-hashing the same files for every block and
# stage). The installed runner folder does not change under a running process (a production run executes its own
# frozen_runtime copy, verified by sha256 when frozen), so a per-process value is the same value. An explicit
# directory (tests, other copies) is never cached.
_CODE_IDS={}

def code_id():
 # 배급 목록(runner_files.STUDENT_FILES)에 있는 파일만 — 실행기 갱신은 옛 폴더를 복사한 뒤 새 팩을 풀어서, 팩에서 빠진 파일
 # (2026-10-05 2차 D 의 longform_video_cache.py)이 남는다. 그 찌꺼기가 열쇠에 섞이면 새로 깐 PC 와 갱신한 PC 의 값이 갈린다(검토 minor).
 if 'code' not in _CODE_IDS:
  from runner_files import STUDENT_FILES
  _CODE_IDS['code']=digest({p.name:file_digest(p) for p in Path(__file__).parent.glob('longform_*.py') if p.name in STUDENT_FILES})
 return _CODE_IDS['code']

def render_code_id(kind,directory=None):
 if directory:return _render_code_id(kind,Path(directory))
 if ('render',kind) not in _CODE_IDS:_CODE_IDS[('render',kind)]=_render_code_id(kind,Path(__file__).resolve().parent)
 return _CODE_IDS[('render',kind)]

def _render_code_id(kind,folder):
 names=['longform_render.py','longform_caption_motion.py','film_editor.py','longform_ink.py','longform_tear.py','longform_transitions.py','longform_shatter.py']
 names+= {'photo':['longform_photo.py'],'cutout':['longform_photo.py'],'split':['longform_photo.py'],'video':['longform_video.py','longform_montage.py'],'graphic':['longform_groups.py','longform_texture.py','longform_hyperframes.py','longform_native.py','longform_iris.py','longform_graphic.py','longform_video.py','longform_paper_reveal.py','longform_object_glitch.py'],'montage':['longform_montage.py','longform_shatter.py','longform_video.py','longform_photo.py']}.get(kind,[])
 if kind in ('video','montage','graphic'):names+=['longform_cut_review.py','longform_video_treatment.py','longform_video_tools.py','onnx_providers.py','longform_reframe.py','subject_focus.py']
 return digest({name:file_digest(folder/name) for name in names})

def assembly_code_id():
 import inspect
 return digest({'assemble':inspect.getsource(assemble),'output_name':inspect.getsource(output_name),'endcard':file_digest(Path(__file__).with_name('longform_endcard.py')),'upload':file_digest(Path(__file__).with_name('longform_upload.py')),'audio':file_digest(Path(__file__).with_name('longform_audio.py')),'source_audio':file_digest(Path(__file__).with_name('longform_source_audio.py')),'layout':render_code_id('layout')})

def scratch_environment(cfg):
 # Node/Chromium/Python must use the same work volume on both operating systems.
 # Do not consume a nearly-full system drive while a selected external SSD is free.
 scratch=(Path(cfg['workdir'])/'geumbit'/'tmp').resolve();scratch.mkdir(parents=True,exist_ok=True)
 selected={name:str(scratch) for name in ('TMPDIR','TEMP','TMP')}
 selected.update(NPM_CONFIG_CACHE=str(scratch.parent/'npm-cache'),NPM_CONFIG_PREFER_OFFLINE='true')
 return {**{k:v for k,v in os.environ.items() if k.upper() not in selected},**selected}

def check_graphic_layouts(probe,visuals,fonts,media,lang='ko'):
 from concurrent.futures import ThreadPoolExecutor,as_completed
 from longform_graphic import document
 unique=list({digest(v):v for v in visuals}.values())
 if not unique:return 0
 common=[fonts/n for n in FONT_NAMES]+[fonts.parent/n for n in ('approved-graphic.css','gsap.min.js','charcoal-paper.png','brown-wallpaper.png')]
 import inspect
 implementation=digest({'renderer':render_code_id('graphic'),'checker':inspect.getsource(check_graphic_layouts)})
 def check(visual):
  def render(folder):
   document(folder,visual,5,fonts,media,preview=True,lang=lang)
   from longform_native import check_document,require_resolved_layout
   native_report=check_document(folder)
   require_resolved_layout(folder,native_report)
   snapshots=[Path(v['path']) for v in native_report.get('layout',{}).get('snapshots',[])]
   snapshots += [Path(v) for item in native_report.get('layout',{}).get('inkEvidence',[]) for v in item.get('files',{}).values()]
   snapshots += [Path(v) for item in native_report.get('layout',{}).get('contrastEvidence',[]) for v in item.get('files',{}).values()]
   proof=folder/'layout-check.txt'
   proof.write_text('Native Chrome runtime/resources, authored motion and sampled text geometry passed. Contrast diagnostics retained; not whole-video/style approval.\n',encoding='utf-8')
   return {'checked':True},[folder/'index.html',folder/'motion.json',proof,folder/'native-layout.json',*snapshots]
  dependencies=common+scene_media_paths(visual,media)
  key={'visual':render_key_visual(visual),'code':implementation,'probe_seconds':5}
  if lang!='ko':key['lang']=lang  # Korean keeps its existing cache key (resumed jobs).
  return Stages(probe/'layout-checks').run('layout',key,dependencies,render)
 # Independent local browser checks, never concurrent paid API requests.
 # Distinct cache keys isolate files; repeated layouts are checked once.
 with ThreadPoolExecutor(max_workers=min(2,len(unique))) as pool:
  pending=[pool.submit(check,v) for v in unique]
  try:
   for completed in as_completed(pending):completed.result()
  except Exception:
   for future in pending:future.cancel()
   raise
 return len(unique)

def pause_plan(block,plan,source,characters,*,original_source=None,samples,rate):
 """The pause edit list for one block's voice — ONE place for imported_duration and timed_voice (2026-10-15).

 Approved breath (plan_sentence_pauses, narration profile) + authored listening gaps (merge_editorial_pauses), minus
 the automatic breaths this block's plan cannot carry (longform_timing.fit_pauses — judged with the gate's own code).
 Before, imported_duration and timed_voice each built the list; the length check and the made voice must use the same
 list, so it is built here once. Returns (specification or None, verified): verified = the points the planner just
 proved quiet on this same PCM, so sentence_pauses does not test them again (6-00 ③); authored ones still are."""
 specification=block.get('sentence_pauses');verified=()
 profile=plan.get('narration')
 if profile:
  specification=longform_audio.plan_sentence_pauses(source,characters,original_source=original_source,extra=profile['sentence_gap_add_seconds'])
  verified=tuple((e['after_character'],e['at_seconds']) for e in (specification or {}).get('entries',[]))
 specification=longform_audio.merge_editorial_pauses(specification,block.get('editorial_pauses'),original_source or source)
 if profile and specification:
  # Only the planner's breaths are droppable; a plan without the profile keeps its explicit, authored edit list.
  from longform_timing import fit_pauses
  specification=fit_pauses(block,specification,samples=samples,rate=rate,characters=characters,
                           timing_basis=plan.get('timing_basis','original_voice'))
 return specification,verified

def imported_duration(plan,cfg=None):
 # Complete preserved narration already has a measurable delivery clock.
 # Check it before browser/media work; never estimate unknown paid speech.
 blocks=plan.get('blocks',[])
 if not blocks or any('existing_voice' not in b for b in blocks):return None
 voices=[]
 for block in blocks:
  audio,chars=verify_import(block,required_tempo=plan.get('narration',{}).get('tempo'),cfg=cfg)
  with wave.open(str(audio),'rb') as stream:
   rate=stream.getframerate()
   if (stream.getnchannels(),stream.getsampwidth())!=(1,2) or not 8000<=rate<=192000:
    raise ProductionError('voice_format','유효한 표본율의 모노 PCM16 WAV가 필요합니다. 기존 음성은 보존합니다.')
   spec,_=pause_plan(block,plan,audio,chars,samples=stream.getnframes(),rate=rate)
   added=sum(round(e['add_seconds']*rate) for e in (spec or {}).get('entries',[]))
   voices.append({'frames':((stream.getnframes()+added)*60+rate-1)//rate})
 return check_duration(plan,voices)

#: Narration length model for the approved voice (VOICE · tempo 1.05 · narration profile), fitted 2026-10-14 by least
#: squares on 22 real student jobs that bought every block and reported their exact length (운영 diag
#: duration_mismatch 원문 + 그때의 제작표): seconds ≈ 0.1141·characters(spaces included) + 0.530·blocks
#: (each paid block carries its own lead/tail breath) + 0.3·sentence ends + 9 (end card). Leave-one-out worst
#: error 6.14% → ESTIMATE_BAND 7%. (This Mac's own receipts are the old 1.15 voice — not used.)
SECONDS_PER_CHARACTER=.1141
SECONDS_PER_BLOCK=.530
ESTIMATE_BAND=.07

def estimated_duration(plan,root,cfg=None):
 """Narration length BEFORE any new paid voice (2026-10-14).

 check_duration() measured length only after every block was bought, so a script 24% short (실측 411.78 vs 540초)
 was found after paying, the fix was a rewrite = a second purchase, and the per-job TTS budget (≈1× the script)
 then stopped the job (duration_mismatch 23 · tts_budget_exhausted 4 / 24h). Already-bought blocks use their real
 PCM length; only blocks still to be bought are estimated. Blocks only when even the most favourable end of the
 measured speed spread misses the tolerance — borderline scripts go on to the exact post-purchase check as before."""
 # The speed was measured for the approved profile only (narration tempo 1.05). Old 1.15 plans without a profile
 # carry imported voices and are measured exactly by imported_duration(); they are not estimated here.
 if not plan.get('narration'):return {'applies':False,'certain_mismatch':False,'say':''}
 # The speed model is Typecast's; a Gemini TTS job (voice_engine) is measured exactly after its free voice is made.
 if (cfg or {}).get('voice_engine'):return {'applies':False,'certain_mismatch':False,'say':''}
 settings=voice_settings(plan,cfg)
 # The fitted speed is the Korean voice's; another language/voice is measured exactly after purchase (as Gemini above).
 if settings['language']!=VOICE['language'] or settings['voice_id']!=VOICE['voice_id']:return {'applies':False,'certain_mismatch':False,'say':''}
 gap=plan['narration'].get('sentence_gap_add_seconds',0)
 known=0.;unknown=0.;bought=0;new=0
 for block in plan['blocks']:
  text=block['text'];pauses=gap*len(re.findall(r'[.!?。！？](?=\s|$)',text))
  if block.get('existing_voice'):
   from longform_external_voice import is_external,pcm
   if is_external(block['existing_voice']):wav=pcm(block['existing_voice'],root)[0]  # author's file, as PCM16 once
   else:
    wav=Path(block['existing_voice']['path'])  # header length only; its fingerprint is verified once in timed_voice
    if not wav.is_file():wav=None
  else:
   wav=next((p.with_name('narration.wav') for p in (root/'voice'/digest({'text':text,'voice':settings})).glob('paid/*/receipt.json')
             if p.with_name('narration.wav').is_file()),None)
  if wav is not None:
   with wave.open(str(wav),'rb') as stream:known+=stream.getnframes()/stream.getframerate()+pauses
   bought+=1
  else:
   unknown+=len(text)*SECONDS_PER_CHARACTER+SECONDS_PER_BLOCK+pauses;new+=1
 target=plan['target_seconds'];tolerance=max(2.0,target*.05)
 low=known+unknown*(1-ESTIMATE_BAND)+9;high=known+unknown*(1+ESTIMATE_BAND)+9
 # The band is a whole-script statistic (fitted jobs: 227~854 s of narration); a few seconds of new text vary
 # more per block, so only ≥60 s of not-yet-bought narration is judged before purchase.
 certain=unknown>=60 and (high<target-tolerance or low>target+tolerance)
 mid=(low+high)/2
 say=(f'대본 글자 수로 잰 예상 길이 {low:.0f}~{high:.0f}초가 목표 {target:.0f}초(허용 ±{tolerance:.0f}초)를 확실히 벗어납니다 — '
      f'음성을 사기 전에 대본 분량을 {"늘리세요" if mid<target else "줄이세요"}(대략 {abs(target-mid)/SECONDS_PER_CHARACTER:.0f}자 · 새로 살 블록 {new}개).') if certain else ''
 return {'applies':True,'low_seconds':low,'high_seconds':high,'target_seconds':target,'tolerance_seconds':tolerance,
         'bought_blocks':bought,'new_blocks':new,'certain_mismatch':certain,'say':say}

def editorial_evidence(root,plan,voices=None,*,source_plan=None,plan_id=None,source_plan_id=None):
 # plan_id / source_plan_id: the caller's digest of that same plan object (6-00: hash it once).
 from longform_editorial import audit
 report=audit(plan,voices,plan_id=plan_id)
 if source_plan is not None:
  # Keep plan_id truthful: these findings inspect the rendered timing plan.
  # Bind the authored input separately so timing changes cannot reuse approval.
  report['source_plan_id']=digest(source_plan) if source_plan_id is None else source_plan_id
  report['findings_id']=digest({'audit_findings_id':report['findings_id'],
   'source_plan_id':report['source_plan_id'],'execution_plan_id':report['plan_id']})
 path=Path(root)/'editorial-review.json';save(path,report)
 return {'path':str(path),**({'source_plan_id':report['source_plan_id'],'execution_plan_id':report['plan_id']} if source_plan is not None else {}),'findings_id':report['findings_id'],
         'inspection_coverage':report['inspection_coverage'],
         'repeated_source_candidates':len(report['repeated_sources']),
         'repeated_video_candidates':len(report['repeated_video_intervals']),
         'similar_composition_candidates':len(report['similar_compositions']),
         'pose_motion_restart_candidates':len(report['pose_motion_restarts']),
         'recurring_layout_families':len(report['recurring_layout_families']),
         'recurring_photo_treatments':len(report['recurring_photo_treatments']),
         'repeated_style_reference_groups':len(report['repeated_style_references']),
         'style_reference_occurrences':sum(len(row['uses']) for row in report['style_reference_uses']),
         'invalid_style_reference_candidates':len(report['invalid_style_references']),
         'source_audio_unassigned_candidates':sum(bool(row['unassigned']) for row in report['audio_coverage']['video_source_audio_assignments']) if voices is not None else None,
         'source_audio_picture_mismatch_candidates':len(report['audio_coverage']['source_audio_picture_mismatches']) if voices is not None else None,
         'blocks_without_style_reference':report['blocks_without_style_reference'],
         'effect_reference_note_count':len(report['effect_reference_notes']),
         'blocks_without_any_reference_notes':report['blocks_without_any_reference_notes'],
         'status':'review_required'}

def plan_failures(error):
 """One preflight «missing» row per contract violation (2026-10-17 #117): longform_contract.gathered carries every
 violation of one pass in .violations, and the server (geumbit longform_run) hands all of them back to the author.
 Any other error (a changed source, a missing runtime asset) stays one row, as before."""
 rows=getattr(error,'violations',None) or [{'message':str(error)}]
 return [{'what':'production_plan','how':row['message'],**({'code':row['code']} if row.get('code') else {})} for row in rows]

def preflight(cfg,*,checked=None):
 """checked: produce() already ran validate() and validate_requested_duration() on this same cfg['plan'] object
 and wrote its editorial evidence into the same preflight folder; pass that evidence so the identical checks do
 not run twice (6-00). Standalone preflight (checked=None) runs them itself, as before."""
 missing=[];found={'python':sys.executable,'os':platform.platform()}
 scratch=Path(scratch_environment(cfg)['TMPDIR']);space=shutil.disk_usage(scratch)
 found['scratch']={'path':str(scratch),'free_bytes':space.free,'minimum_free_bytes':2*1024**3}
 if space.free<2*1024**3:missing.append({'what':'disk_space','how':'작업 볼륨에 최소 2GiB의 여유 공간을 확보하세요: '+str(scratch)})
 for mod in ('PIL','numpy','psutil'):
  try:importlib.import_module(mod)
  except ImportError:missing.append({'what':mod,'how':sys.executable+' -m pip install '+('Pillow' if mod=='PIL' else mod)})
 for executable in ('ffmpeg','ffprobe'):
  found[executable]=shutil.which(executable)
  if not found[executable]:missing.append({'what':executable,'how':'실행 환경에 '+executable+' 설치'})
 fonts=Path(cfg['fonts'])
 try:
  from longform_fonts import ensure_fonts
  found['font_sources']=ensure_fonts(fonts)
 except Exception as error:missing.append({'what':'font_supply','how':str(error)})
 if 'PIL' not in [x['what'] for x in missing]:
  from PIL import ImageFont
  for name in FONT_NAMES:
   try:
    f=ImageFont.truetype(str(fonts/name),55)
    if not f.getmask('금빛폭발 2000').getbbox():raise ValueError('empty glyphs')
   except (OSError,ValueError):missing.append({'what':name,'how':'글꼴 자산 팩 복원: '+str(fonts)})
 plan=cfg.get('plan')
 if plan:
  try:
   if checked is None:
    validate(plan)
    validate_requested_duration(plan,cfg.get('requested_target_seconds'))
   duration=imported_duration(plan,cfg)
   if duration is not None:found['imported_voice_duration']=duration
   else:
    estimate=estimated_duration(plan,Path(cfg['workdir'])/'geumbit',cfg)
    found['estimated_voice_duration']=estimate
    if estimate['certain_mismatch']:
     missing.append({'what':'narration_length','how':estimate['say']})
   found['editorial_review']=checked if checked is not None else editorial_evidence(Path(cfg['workdir'])/'geumbit'/'preflight',plan)
   for asset in [*plan['media'].values(),*plan.get('sound_assets',{}).values()]:
    # Same per-process memo as Stages.files(): the stages that read these sources later do not re-hash them.
    # An unreadable file still raises the exact OSError (and message) the direct read raised before.
    try:sha=file_sha256(native_path(asset['path']))[0]
    except OSError:sha=file_digest(asset['path'])
    if sha!=asset['sha256']:raise ProductionError('asset_changed','소재가 제작표와 다릅니다: '+asset['path'])
   from longform_video_treatment import dependencies,preflight_evidence
   if dependencies([b['visual'] for b in plan['blocks']]):
    found['video_treatment_evidence']=preflight_evidence(plan)
    from longform_video_tools import probe_tools
    found['video_treatment_runtime']=probe_tools(fonts.parent,Path(cfg['workdir'])/'geumbit'/'preflight'/'video-treatment')
   if any(b['visual']['kind']=='graphic' for b in plan['blocks']):
    # Validate the renderer actually used by graphic(), before paid narration.
    # Finding a Node executable does not prove it runs or Chrome is available.
    from longform_native import runtime as native_runtime
    found['graphic_runtime']=native_runtime()
    if any(b['visual'].get('renderer')=='hyperframes' for b in plan['blocks']):
     from longform_hyperframes import runtime as hyperframes_runtime
     found['hyperframes_runtime']=hyperframes_runtime(Path(cfg['workdir'])/'geumbit'/'preflight'/'hyperframes-runtime')
    if not (fonts.parent/'gsap.min.js').is_file():raise ProductionError('asset_missing','그래픽 런타임 자산이 없습니다.')
  except (OSError,ValueError) as error:missing.extend(plan_failures(error))
 # Test the selected Python and ffmpeg before ANY paid work, including real text rendering.
 if not missing:
  from PIL import Image,ImageDraw,ImageFont
  probe=Path(cfg['workdir'])/'geumbit'/'preflight';probe.mkdir(parents=True,exist_ok=True)
  im=Image.new('RGB',(320,180),'#141844');ImageDraw.Draw(im).text((10,40),'금빛폭발',font=ImageFont.truetype(str(fonts/FONT_NAMES[0]),40),fill='white');im.save(probe/'font.png')
  try:
   if plan:
    from longform_media import inspect as inspect_media
    media_report=inspect_media(plan,probe/'media')
    found['media_duplicates']=media_review_summary(media_report,probe/'media'/'duplicates.json',
        video_ranges=media_report['video_ranges'],image_occurrences=media_report['image_occurrences'])
    longform_source_audio.preflight(probe/'source-audio',plan['blocks'],plan['media'])
    for sid,asset in plan.get('sound_assets',{}).items():
     # Decode the exact paid-work inputs now, not after narration has been bought.
     command(probe,['ffmpeg','-v','error','-xerror','-i',asset['path'],'-vn','-f','null','-'],'sound-preflight-'+digest(sid)[:12])
    from longform_render import thumbnail,Layout,image_layout,source_label,photo_source
    checked_layout=Layout(fonts,styles=plan.get('styles'),headline=plan['subject']['headline'],lang=cfg.get('screen_language','ko'))
    thumbnail(plan,checked_layout,probe/'thumbnail.png')
    graphic_visuals=[];caption_notes=[]
    for block in plan['blocks']:
     if block.get('sentence_pauses') or block.get('editorial_pauses') or (plan.get('narration') and block.get('existing_voice')):
      if not block.get('existing_voice'):
       raise ProductionError('pause_voice_required','호흡 조정은 이미 보존된 음성의 파형을 확인한 뒤 지정하세요.',action='review_audio')
      # Validate quiet insertion points and derived timing before any new TTS.
      voice=timed_voice(block,cfg,probe.parent,checked_layout)
      from longform_timing import conform_plan,validate_source_capacity
      local_plan={'blocks':[block],'timing_basis':plan.get('timing_basis','original_voice')}
      validate_source_capacity(conform_plan(local_plan,[voice]),[voice])
     checked_layout.overlay(plan['subject']['name'],block['visual'],source_label(block['visual'],plan['media'],checked_layout.lang))
     for part in block['visual'].get('shots',[]):
      if 'work' in part:
       view=dict(block['visual'],work=part['work'])
       checked_layout.overlay(plan['subject']['name'],view,source_label(view,plan['media'],checked_layout.lang))
     # caption_cards draws every card once with the real style; drawing them again here was the same check twice (6-00).
     caption_notes.extend(card['range_note'] for card in caption_cards(block,checked_layout) if card.get('range_note'))
     if block['visual']['kind'] in ('split','cutout'):image_layout(block['visual'],plan['media'])
     if block['visual']['kind']=='photo':photo_source(block['visual'],plan['media'],probe)
     if block['visual']['kind']=='video':
      from longform_render import video_crop_filter
      video_crop_filter(plan['media'][block['visual']['media'][0]]['path'],block['visual'].get('crop'))
     if block['visual']['kind']=='graphic':
      from longform_graphic import document
      graphic_probe=probe/('text-'+block['id']);graphic_probe.mkdir(exist_ok=True)
      document(graphic_probe,block['visual'],5,fonts,plan['media'],preview=True,lang=checked_layout.lang)
      # Font widths alone missed a rotated question mark touching its title.
      # Check each authored layout in the real browser before any paid voice.
      # This cache is independent of captions/audio, so resumes do not repeat
      # browser checks for unchanged layouts. The delivered duration is checked
      # again by graphic() when rendering the actual scene.
      graphic_visuals.append(block['visual'])
    found['graphic_layouts_checked']=check_graphic_layouts(probe,graphic_visuals,fonts,plan['media'],checked_layout.lang)
    # #118: caption ranges the code placed (not a rejection) — said once, in the preflight result the author reads.
    if caption_notes:found['caption_range_notes']=caption_notes
   if plan and any(b['visual']['kind']=='montage' for b in plan['blocks']):
    command(probe,['ffmpeg','-y','-v','error','-filter_complex_threads','1','-f','lavfi','-i','color=red:s=64x64:r=60:d=0.5','-f','lavfi','-i','color=blue:s=64x64:r=60:d=0.5','-filter_complex','[0:v][1:v]xfade=transition=fade:duration=0.1:offset=0.4','-f','null','-'],'montage-runtime')
   if plan and plan.get('music'):
    command(probe,['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=0.5','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=0.5','-filter_complex','[0:a]asplit[v][key];[1:a][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=250[d];[v][d]amix=inputs=2:duration=first:normalize=0','-f','null','-'],'music-runtime')

   command(probe,['ffmpeg','-y','-v','error','-loop','1','-i',probe/'font.png','-frames:v','2','-c:v','libx264','-pix_fmt','yuv420p',probe/'probe.mp4'],'preflight')
   command(probe,['ffmpeg','-v','error','-xerror','-i',probe/'probe.mp4','-f','null','-'],'preflight-decode')
   # A binary named ffmpeg is not proof that the deployed audio filters exist.
   # Exercise the exact limiter options and AAC encoder before any TTS request.
   audio_filters='volume=12dB,alimiter=limit=0.707945784:level=false:attack=5:release=100:latency=true,acompressor=threshold=0.1:ratio=2:attack=20:release=250:knee=2.828:makeup=1:detection=rms,loudnorm=I=-16:TP=-2:LRA=7'
   def render_audio_probe(folder):
    target=folder/'probe.m4a'
    command(folder,['ffmpeg','-y','-v','error','-f','lavfi','-i','anoisesrc=color=pink:amplitude=0.15:seed=42:sample_rate=48000:duration=1.2','-af',audio_filters,'-ar','48000','-ac','1','-c:a','aac','-b:a','192k',target],'audio-probe')
    command(folder,['ffmpeg','-v','error','-xerror','-i',target,'-f','null','-'],'audio-probe-decode')
    return {'path':str(target),'filters':audio_filters},[target]
   found['audio_runtime']=Stages(probe/'audio').run('runtime',{'filters':audio_filters,'sample':'pink48k1.2s','codec':'aac192k'},[found['ffmpeg']],render_audio_probe)
   if plan and any(b['visual']['kind']=='graphic' for b in plan['blocks']):
    from longform_render import graphic,Layout
    layout=Layout(fonts,lang=cfg.get('screen_language','ko'));stages=Stages(probe/'graphics')
    deps=[fonts/n for n in FONT_NAMES]+[fonts.parent/n for n in ('approved-graphic.css','gsap.min.js','charcoal-paper.png','brown-wallpaper.png')]
    sample={'template':'numbers','title':'사전 검사','labels':['1','2'],'dates':['첫째','둘째'],'total':'3','total_label':'합계','media':[]}
    renderers=sorted({b['visual'].get('renderer','native') for b in plan['blocks'] if b['visual']['kind']=='graphic'})
    for renderer in renderers:
     selected=dict(sample,renderer=renderer)
     def render_probe(folder,selected=selected):
      path=graphic(folder,selected,.5,layout,{})
      command(folder,['ffmpeg','-v','error','-xerror','-i',path,'-f','null','-'],'graphic-probe-decode')
      return {'path':str(path),'renderer':selected['renderer']},[path]
     stages.run('runtime',{'code':code_id(),'os':platform.platform(),'renderer':renderer},deps,render_probe)

  except ValueError as error:missing.append({'what':'render_smoke','how':str(error)})
 return {'ok':not missing,'missing':missing,'found':found,'engine':VERSION,'code_id':code_id()}

def native_sequence_payload(text,parts,separators,required_tempo=None):
 # A derived sequence is not a provider response. Every leaf retains its own
 # native receipt, exact request text, returned characters and unmodified PCM.
 import io
 if (not isinstance(parts,list) or not 2<=len(parts)<=100
     or not isinstance(separators,list) or len(separators)!=len(parts)-1
     or any(not isinstance(x,str) or not x or not x.isspace() for x in separators)):
  raise ProductionError('voice_sequence_contract','문장별 원본과 공백 연결 목록이 필요합니다.')
 if any(not isinstance(p,dict) or not isinstance(p.get('text'),str)
        or p.get('existing_voice',{}).get('format')!='typecast-native-v2' for p in parts):
  raise ProductionError('voice_sequence_contract','문장별 실제 Typecast 원본 기록만 결합할 수 있습니다.')
 combined=''.join(p['text']+(separators[i] if i<len(separators) else '') for i,p in enumerate(parts))
 if combined!=text:raise ProductionError('alignment_mismatch','문장 결합 결과와 대본이 다릅니다.')
 raw=[];characters=[];samples=0;rate=None
 for i,part in enumerate(parts):
  source,chars=verify_import(part,required_tempo=required_tempo)
  with wave.open(str(source),'rb') as w:
   current=w.getframerate()
   if (w.getnchannels(),w.getsampwidth())!=(1,2) or not 8000<=current<=192000 or (rate is not None and current!=rate):
    raise ProductionError('voice_sequence_format','문장별 음성은 같은 표본율의 모노 PCM16이어야 합니다.')
   rate=current;count=w.getnframes();pcm=w.readframes(count)
  if not chars:raise ProductionError('alignment_invalid','문장별 문자 시간이 없습니다.')
  # Provider character times have millisecond precision; only a terminal
  # punctuation rounded up by <=0.5ms may be bounded to the exact PCM end.
  # Native response remains unchanged and is reverified on every import.
  chars=[dict(c) for c in chars]
  final=chars[-1]
  if final['text'] in '.!?。！？' and count/rate<final['end']<=count/rate+.0005:
   final['end']=count/rate
  last=0
  for c in chars:
   a,b=c['start'],c['end']
   if not all(type(x) in (int,float) and math.isfinite(x) for x in (a,b)) or not 0<=a<=b<=count/rate or a<last-.002:
    raise ProductionError('alignment_invalid','문장별 문자 시간이 파형 범위를 벗어났습니다.')
   last=b
  offset=samples/rate
  if i:
   # Separator time is the actual retained tail + following leading silence.
   # Its quietness is still checked by the ordinary sentence-pause gate.
   start=characters[-1]['end'];end=offset+chars[0]['start'];sep=separators[i-1]
   if end<start:raise ProductionError('alignment_invalid','문장 연결 시간이 역전됐습니다.')
   characters.extend({'text':ch,'start':start+(end-start)*j/len(sep),'end':start+(end-start)*(j+1)/len(sep)} for j,ch in enumerate(sep))
  characters.extend({**c,'start':c['start']+offset,'end':c['end']+offset} for c in chars)
  raw.append(pcm);samples+=count
 output=io.BytesIO()
 with wave.open(output,'wb') as w:
  w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(b''.join(raw))
 return output.getvalue(),characters

def create_native_sequence(path,text,parts,separators,required_tempo=1.05):
 from film_editor import atomic_bytes
 payload,_=native_sequence_payload(text,parts,separators,required_tempo)
 path=Path(path)
 if path.exists() and path.read_bytes()!=payload:
  raise ProductionError('voice_import_changed','이미 저장된 결합 음성을 덮어쓰지 않습니다.')
 if not path.exists():atomic_bytes(path,payload)
 return {'format':'typecast-native-sequence-v1','path':str(path),'sha256':file_digest(path),'parts':parts,'separators':separators}

def verify_import(block,required_tempo=None,cfg=None):
 from longform_external_voice import is_external,load
 if is_external(block['existing_voice']):
  # Author-supplied narration (2026-10-16): measured word times, no Typecast record exists or is required.
  cfg=cfg or {}
  return load(block['existing_voice'],block['text'],Path(cfg.get('workdir') or '.')/'geumbit',cfg.get('asr'))
 if block['existing_voice'].get('format')=='typecast-native-sequence-v1':
  item=block['existing_voice'];payload,characters=native_sequence_payload(block['text'],item.get('parts'),item.get('separators'),required_tempo)
  audio=Path(item['path'])
  if file_digest(audio)!=item['sha256'] or audio.read_bytes()!=payload:
   raise ProductionError('voice_import_changed','결합 음성과 원본 문장 파형이 다릅니다.')
  return audio,characters
 item=block['existing_voice'];metadata=Path(item['metadata']);audio=Path(item['path']);receipt=Path(item['receipt'])
 for p,key in ((metadata,'metadata_sha256'),(audio,'sha256'),(receipt,'receipt_sha256')):
  if file_digest(p)!=item[key]:raise ProductionError('voice_import_changed','기존 음성/기록의 지문이 다릅니다.',action='restore_asset')
 data=read(metadata);paid=read(receipt)
 voice=chosen_voice(cfg)
 if item.get('format')=='typecast-native-v2':
  # Exact receipt match allows explicitly preserved historical 1.15 voices.
  # An approved new profile requires 1.05 and never relabels old speech.
  tempos=[required_tempo] if required_tempo is not None else [voice['tempo'],1.15]
  valid=False
  for tempo in tempos:
   body=typecast_body(block['text'],dict(voice,tempo=tempo))
   expected=digest({'version':2,'endpoint':voice['endpoint'],'body':body})
   if (paid.get('status') in ('response_received','complete')
         and paid.get('request_identity_version')==2
         and paid.get('endpoint')==voice['endpoint']
         and paid.get('request_id')==expected and paid.get('body_sha256')==digest(body)
         and paid.get('response_sha256')==item['metadata_sha256']):valid=True;break
  try:
   characters=data['characters']
   valid=valid and base64.b64decode(data['audio'],validate=True)==audio.read_bytes()
   valid=valid and isinstance(characters,list) and ''.join(c['text'] for c in characters)==block['text']
  except (KeyError,TypeError,ValueError):
   pass
  else:
   if valid:return audio,characters
  raise ProductionError('voice_import_mismatch','기존 Typecast 요청·응답·대본·음성이 일치하지 않습니다. 자동 재요청하지 않습니다.',action='reconcile_request')
 if required_tempo is not None and data.get('tempo',data.get('speed'))!=required_tempo:
  raise ProductionError('voice_tempo_unverified','기존 음성에서 승인된 1.05 속도를 확인할 수 없습니다. 원본을 보존하고 음성 설정을 확인하세요.',action='review_audio')
 if paid.get('status')!='complete' or paid.get('wav_sha256')!=item['sha256']:
  raise ProductionError('paid_request_uncertain','기존 음성의 완료 기록을 확인할 수 없습니다.',action='reconcile_request')
 if data.get('text')!=block['text'] or data.get('voice_id')!=voice['voice_id'] or data.get('model')!=voice['model']:
  raise ProductionError('voice_import_mismatch','대본/성우/모델이 기존 음성 기록과 다릅니다.',action='edit_plan')
 if ''.join(data['chars'])!=block['text'] or len(data['chars'])!=len(data['char_end']):raise ProductionError('alignment_mismatch','기존 음성 문자 시간이 맞지 않습니다.')
 ends=data['char_end'];characters=[{'text':ch,'start':0 if i==0 else ends[i-1],'end':ends[i]} for i,ch in enumerate(data['chars'])]
 return audio,characters

def caption_cards(block,layout):
 from longform_contract import checked_captions
 captions=checked_captions(block)
 # Measure the authored phrase with the actual drawing style. Never change its
 # linguistic boundary to make it fit; return to the author before any payment.
 for card in captions:layout.caption(card['text'],block.get('highlights',[]),style=card.get('style'))
 return captions

def timed_voice(block,cfg,root,layout):
 plan=cfg.get('plan') or {};profile=plan.get('narration');settings=voice_settings(plan,cfg)
 if block.get('existing_voice'):audio,characters=verify_import(block,required_tempo=profile['tempo'] if profile else None,cfg=cfg)
 else:
  paid=root/'voice'/digest({'text':block['text'],'voice':settings});paid.mkdir(parents=True,exist_ok=True)
  # Per-block request guard from film_editor is the authority; interrupted POSTs never replay.
  result,audio,_=request_tts(paid,block['text'],{'tts':settings},cfg.get('tts_headers'))
  characters=result['characters']
 quality_root=root/'audio-quality'/file_digest(audio);quality_root.mkdir(parents=True,exist_ok=True)
 prepared=longform_audio.prepare_voice(quality_root,audio,block.get('audio_repair'))
 with wave.open(str(audio),'rb') as stream:
  rate=stream.getframerate()
  if (stream.getnchannels(),stream.getsampwidth())!=(1,2) or not 8000<=rate<=192000:
   raise ProductionError('voice_format','유효한 표본율의 모노 PCM16 WAV가 필요합니다. 기존 음성은 보존합니다.')
  source_samples=stream.getnframes();duration=source_samples/rate;samples=round(duration*48000)
 if ''.join(x['text'] for x in characters)!=block['text']:raise ProductionError('alignment_mismatch','음성과 대본이 다릅니다.')
 last=0
 for char in characters:
  a,b=char['start'],char['end']
  if not all(type(x) in (int,float) and math.isfinite(x) for x in (a,b)) or not 0<=a<=b<=duration+.05 or a<last-.002:
   raise ProductionError('alignment_invalid','음성 문자 시간이 겹치거나 범위를 벗어났습니다.')
  last=b
 pause_result=None
 original_frames=(source_samples*60+rate-1)//rate;source_characters=characters
 specification,verified=pause_plan(block,plan,prepared,characters,original_source=audio,samples=source_samples,rate=rate)
 if specification:
  pause_result=longform_audio.sentence_pauses(quality_root,prepared,characters,specification,original_source=audio,editorial=bool(block.get('editorial_pauses')),verified=verified)
  audio=Path(pause_result['path']);characters=pause_result['characters']
  with wave.open(str(audio),'rb') as stream:
   source_samples=stream.getnframes();rate=stream.getframerate();samples=round(source_samples*48000/rate)
 frames=(source_samples*60+rate-1)//rate;captions=caption_cards(block,layout)
 rows=[]
 for i,card in enumerate(captions):
  # Only actual returned character timestamps determine boundaries.
  a=0 if i==0 else characters[card['start']]['start'];b=characters[captions[i+1]['start']]['start'] if i+1<len(captions) else frames/60
  if b<=a:raise ProductionError('caption_empty','자막 시간 범위가 비었습니다.')
  rows.append({'start':a,'end':b,'text':card['text'],**{key:dict(card[key]) for key in ('style','motion') if key in card}})
 # Keep narration cards out of explicitly inserted source-listening windows.
 gaps=[];offset=0
 for change in (pause_result or {}).get('timing_adjustments',[]):
  start=change['at_seconds']+offset;offset+=change['add_seconds']
  if change.get('editorial'):
   following=change['after_character']+1
   while following<len(block['text']) and block['text'][following].isspace():following+=1
   if following<len(block['text']) and following not in {c['start'] for c in captions}:
    raise ProductionError('editorial_caption_boundary','원음 청취 쉼 다음 문장은 별도 자막 카드로 나누세요.',action='edit_plan')
   gaps.append({'start':start,'end':start+change['add_seconds'],'after_character':change['after_character']})
 for gap in gaps:
  remaining=[]
  for row in rows:
   if row['end']<=gap['start'] or row['start']>=gap['end']:remaining.append(row);continue
   if row['start']<gap['start']:remaining.append({**row,'end':gap['start']})
   # Never flash the previous sentence again during the tiny natural silence
   # between the inserted listening gap and the next aligned caption.
  rows=remaining
 result={'path':str(audio),'sha256':file_digest(audio),'frames':frames,'samples':samples,'captions':rows,'characters':characters}
 if gaps:result['editorial_gaps']=gaps
 if pause_result:
  result.update(timing_adjustments=pause_result['timing_adjustments'],pause_report=pause_result['report'],audio_repair_applied=bool(block.get('audio_repair')),original_frames=original_frames,source_characters=source_characters)
 return result

def paid_preflight(root,plan,cfg):
 settings=voice_settings(plan,cfg)
 # Inspect every previous block before allowing any new block request, even after a script edit.
 for p in (root/'voice').glob('*/paid/*/receipt.json'):
  receipt=read(p);response=p.parent/'response.json'
  valid=(receipt.get('status') in ('complete','response_received') and response.is_file()
         and receipt.get('response_sha256')==file_digest(response))
  if valid:
   try:
    data=read(response);decoded=base64.b64decode(data['audio'],validate=True)
    valid=bool(decoded) and isinstance(data['characters'],list) and bool(data['characters'])
   except (KeyError,TypeError,ValueError):valid=False
  if not valid:raise ProductionError('paid_request_uncertain','확인되지 않거나 손상된 이전 음성 요청이 있습니다: '+str(p),action='reconcile_request')
 maximum=cfg.get('max_tts_characters',0)
 new=0;spent=0;pending=set()
 for p in (root/'voice').glob('*/paid/*/receipt.json'):spent+=read(p).get('characters',0)
 for block in plan['blocks']:
  if block.get('existing_voice'):
   verify_import(block,required_tempo=plan.get('narration',{}).get('tempo'),cfg=cfg);continue
  folder=root/'voice'/digest({'text':block['text'],'voice':settings})
  if folder not in pending and not list(folder.glob('paid/*/receipt.json')):
   new+=len(block['text']);pending.add(folder)
 if new and (type(maximum) is not int or maximum<=0 or spent+new>maximum):
  raise ProductionError('tts_budget_exhausted',f'음성 문자 예산 초과: 사용 {spent}, 신규 {new}, 한도 {maximum}. 자동 요청하지 않습니다. 이 비용이 맞으면 payload.max_tts_characters 를 {spent+new} 이상으로 넣어 longform_seed 를 다시 부르세요.',action='adjust_budget')
 return {'previous_characters':spent,'new_characters':new,'limit':maximum}

def build_audio(folder,voices,plan):
 folder=Path(folder)
 with wave.open(str(folder/'narration.wav'),'wb') as joined:
  joined.setparams((1,2,48000,0,'NONE','not compressed'))
  for i,v in enumerate(voices):
   audio_root=folder/'audio'/str(i);audio_root.mkdir(parents=True,exist_ok=True)
   leveled=audio_root/'leveled.wav'
   repair=None if v.get('audio_repair_applied') else plan['blocks'][i].get('audio_repair')
   longform_audio.level_voice(audio_root,v['path'],leveled,repair)
   with wave.open(str(leveled),'rb') as w:raw=w.readframes(w.getnframes())
   frame_bytes=v['frames']*800*2
   if len(raw)>frame_bytes+2:raise ProductionError('audio_timing_changed','음성이 장면 길이를 초과했습니다.')
   joined.writeframes(raw[:frame_bytes]+b'\0'*max(0,frame_bytes-len(raw)))
  # Measure the exact delivered timeline. Appending silence after loudnorm
  # changes EBU gating windows (observed -16.00 -> -15.62 on a short episode).
  joined.writeframes(b'\0'*(9*48000*2))
 mixed=folder/'narration.wav'
 if any(b.get('sfx') for b in plan['blocks']):
  mixed=longform_audio.mix_effects(folder,mixed,folder/'mix.wav',voices,plan['blocks'],plan.get('sound_assets',{}))
 music_key=folder/'narration.wav'
 if any(b.get('source_audio') for b in plan['blocks']):
  mixed,music_key=longform_source_audio.mix(folder,mixed,music_key,folder/'source-mix.wav',voices,plan['blocks'],plan['media'])
 if plan.get('music'):
  mixed=longform_audio.mix_music(folder,mixed,folder/'music-mix.wav',plan['music'],plan.get('sound_assets',{}),sidechain=music_key,sidechain_role='narration + foreground original audio' if music_key.name=='source-dialogue-key.wav' else 'narration only')
 # AAC is the delivery codec: master, encode and measure it (one measured correction) before spending time on pictures.
 checked=longform_audio.master_for_delivery(folder,mixed,folder/'master.wav',folder/'audio-preview.m4a')
 outputs=[folder/'master.wav',folder/'audio-preview.m4a',folder/'audio-verification.json',folder/'aac-peak-correction.json']
 if (folder/'source-audio-mix.json').is_file():outputs.append(folder/'source-audio-mix.json')
 if (folder/'sfx-mix.json').is_file():outputs.append(folder/'sfx-mix.json')
 if (folder/'music-mix.json').is_file():outputs.append(folder/'music-mix.json')
 return {'path':str(folder/'master.wav'),'preview':str(folder/'audio-preview.m4a'),'verification':checked},outputs

# 2026-10-05 이전 완성 이름. 새로 조립하면 쓰지 않는다 — 이미 이 이름으로 끝난 작업은 status.json·조립 영수증에 «기록된 경로» 로
# 남아 있고 accept·deliver·validate_output 은 이름을 다시 짓지 않고 그 기록된 경로를 읽으므로 그대로 전달된다
# (tests/test_longform_output_name.py 가 지킨다).
LEGACY_OUTPUT='금빛폭발.mp4'
FALLBACK_OUTPUT='완성본'
# 파일 이름 한 칸의 공식 한도: NTFS 255 UTF-16 단위(learn.microsoft.com «Naming Files, Paths, and Namespaces» · Maximum Path Length) ·
# APFS 255 UTF-8 바이트(developer.apple.com «File System Programming Guide»). 장면 폴더 경로 위에 붙으므로(윈도우 MAX_PATH 260)
# 훨씬 짧게 둔다 — 60자·180 UTF-8 바이트(우리 결정 · 공식 숫자 아님).
OUTPUT_NAME_CHARS=60
OUTPUT_NAME_BYTES=180
_WINDOWS_RESERVED={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}


def output_name(plan):
 """완성 MP4 이름 = 제작표 업로드 제목(upload.title) — 윈도우·맥 금지 글자를 빼고 길이를 줄인다. 못 쓰면 «완성본».

 2026-10-05 오케스트레이터 결정(23:2x): 예전 이름 «금빛폭발.mp4» 를 학생이 그대로 올리면 유튜브 기본 제목이 다른 채널 이름이 된다.
 금지: 윈도우 < > : " / \\ | ? * 와 제어 문자(0~31) · 끝의 점·공백 · 예약 이름(CON·PRN·AUX·NUL·COM1~9·LPT1~9) · 맥 / : .
 앞의 점(맥 숨김 파일)·하이픈(명령 인자로 읽힘)도 뺀다. 유니코드는 NFC 로(맥 NFD 와 윈도우가 같은 이름을 보게).
 """
 import re
 import unicodedata
 upload=plan.get('upload') if isinstance(plan,dict) else None
 title=upload.get('title') if isinstance(upload,dict) else None
 name=unicodedata.normalize('NFC',title) if isinstance(title,str) else ''
 name=re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]',' ',name)
 name=re.sub(r'\s+',' ',name).strip()
 name=name[:OUTPUT_NAME_CHARS]
 while len(name.encode('utf-8'))>OUTPUT_NAME_BYTES:name=name[:-1]
 name=name.strip(' .').lstrip('-').strip(' .')
 if not name or name.split('.')[0].strip().upper() in _WINDOWS_RESERVED:name=FALLBACK_OUTPUT
 # 같은 조립 폴더의 재료(scene-0000.mp4 · endcard.mp4)와 같은 이름이면 입력을 덮어쓴다 — 그때는 «완성본».
 # 대소문자를 가리지 않는 볼륨(윈도우 NTFS·맥 APFS 기본)이라 소문자로 견준다.
 if re.fullmatch(r'(scene-\d+|endcard)',name.lower()):name=FALLBACK_OUTPUT
 return name+'.mp4'


def assemble(folder,scenes,endcard,voices,plan,layout,audio):
 from longform_render import thumbnail
 # Every piece joined with `-c copy` comes from one encoder (render_joined guarantees it; checked here once).
 encoders={s.get('encoder') for s in scenes}|{endcard.get('encoder')}
 if len(encoders)>1:
  raise ProductionError('joined_encoder_mismatch','이어 붙일 장면과 끝카드의 인코더가 다릅니다: '+', '.join(sorted(map(str,encoders))),action='repair_environment')
 folder=Path(folder);parts=[]
 # Relative entries AND input keep FFmpeg from resolving an extended Windows
 # path (\\?\) as a URL and losing the containing directory. command sets cwd.
 for i,scene in enumerate(scenes):
  dst=folder/f'scene-{i:04d}.mp4'
  if not dst.exists():
   try:os.link(scene['path'],dst)
   except OSError:shutil.copy2(scene['path'],dst)
  parts.append(dst.name)
 card=folder/'endcard.mp4'
 if not card.exists():
  try:os.link(endcard['path'],card)
  except OSError:shutil.copy2(endcard['path'],card)
 parts.append('endcard.mp4');(folder/'concat.txt').write_text(''.join("file '"+p+"'\n" for p in parts),encoding='utf-8')
 output=folder/output_name(plan)
 command(folder,['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i','concat.txt','-i',audio['path'],'-map','0:v','-map','1:a','-c:v','copy',*longform_audio.DELIVERY_AAC,'-shortest','-movflags','+faststart',output],'assemble',timeout=1800)
 thumbnail(plan,layout,folder/'thumbnail.png')
 from longform_upload import upload_text
 (folder/'업로드문구.md').write_text(upload_text(plan,layout.lang),encoding='utf-8')
 save(folder/'sources.json',{'references':plan['references'],'media':plan['media'],'sound_assets':plan.get('sound_assets',{}),'music':plan.get('music')})
 timeline=[];cursor=0
 for block,v in zip(plan['blocks'],voices):
  timeline.append({'id':block['id'],'start':cursor,'duration':v['frames']/60,'captions':v['captions']});cursor+=v['frames']/60
 save(folder/'timeline.json',timeline)
 result={'video':str(output),'thumbnail':str(folder/'thumbnail.png'),'upload':str(folder/'업로드문구.md'),'sources':str(folder/'sources.json'),'timeline':str(folder/'timeline.json'),'duration':cursor+9}
 return result,[Path(result[x]) for x in ('video','thumbnail','upload','sources','timeline')]

def validate_output(root,result):
 for key in ('video','thumbnail','upload','sources','timeline'):
  if not Path(result[key]).is_file():raise ProductionError('output_missing','완성 파일이 없습니다: '+key,action='resume')
 raw=command(root,['ffprobe','-v','error','-show_streams','-show_format','-of','json',result['video']],'output-probe');probe=json.loads(raw)
 v=next(x for x in probe['streams'] if x['codec_type']=='video');a=next(x for x in probe['streams'] if x['codec_type']=='audio')
 if (v['width'],v['height'],v['r_frame_rate'])!=(1920,1080,'60/1') or abs(float(v['duration'])-result['duration'])>.05 or abs(float(v['duration'])-float(a['duration']))>.1:
  raise ProductionError('render_contract_mismatch','렌더 규격 또는 음성/영상 길이가 다릅니다.')
 command(root,['ffmpeg','-v','error','-xerror','-i',result['video'],'-f','null','-'],'full-decode',timeout=1800)
 audio=longform_audio.verify(root,result['video'])
 return {'audio':audio,'full_decode':'pass','os':platform.platform(),'streams':probe['streams'],'files':files([result[x] for x in ('video','thumbnail','upload','sources','timeline')])}

def check_duration(plan, voices):
 # A target must constrain the actual narration, not just label a short result.
 # Editorial tolerance is explicit; no slowing/repeating speech to fill time.
 actual=sum(voice['frames'] for voice in voices)/60+9
 target=plan['target_seconds'];tolerance=max(2.0,target*.05)
 if abs(actual-target)>tolerance:
  raise ProductionError('duration_mismatch',f'실제 길이 {actual:.2f}초, 목표 {target:.2f}초 (허용 ±{tolerance:.2f}초). 대본을 수정하세요. 기존 음성은 보존했습니다.',action='edit_plan')
 return {'actual_seconds':actual,'target_seconds':target,'tolerance_seconds':tolerance}

def render_scenes(stages,plan,voices,fonts,layout,cfg):
 """Cache clean pictures independently, then compose editorial overlays.

 Keeps sources available for cross-scene transitions without baking captions
 into their fragments. Explicit graphic scene_handoff connects normalized surfaces before overlays.
"""
 from longform_render import prepare_picture,render_scene
 from longform_contract import validate_scene_handoffs
 validate_scene_handoffs(plan['blocks'],voices)
 pictures=[];scenes=[];failed=[]
 for block,voice in zip(plan['blocks'],voices):
  visual=block['visual'];deps=scene_media_paths(visual,plan['media'])+fonts
  if visual.get('source_style',{}).get('font_file'):deps.append(Path(cfg['fonts'])/visual['source_style']['font_file'])
  if visual['kind']=='graphic':deps += [Path(cfg['fonts']).parent/n for n in ('approved-graphic.css','gsap.min.js','charcoal-paper.png','brown-wallpaper.png')]
  # Only picture-alignment data belongs here. Caption styling and wording are
  # overlay inputs; changing those must not recapture an unchanged graphic.
  picture_voice={k:v for k,v in voice.items() if k in ('frames','characters')}
  inputs={'code':render_code_id(visual['kind']),'render_epoch':cfg.get('render_epoch'),
          'visual':render_key_visual(visual),'voice':picture_voice}
  try:
   picture=stages.run('picture-'+block['id'],inputs,deps,
       lambda folder,b=block,v=voice:prepare_picture(folder,b,plan['media'],v,layout,handle_frames=b['visual'].get('scene_handoff',{}).get('frames',0)))
  except ProductionError as error:
   # 2026-10-17 #128: a plan problem in one block (short source cut, too-short source, …) used to stop the run at
   # the first block, and the author learnt the next block's problem only on the next run (8+ runs on a 40-block
   # episode). Keep rendering the other pictures (their stages are reused on the next run) and return every
   # block's plan problem at once. Environment/runtime failures still stop here.
   if error.action!='edit_plan':raise
   failed.append(ProductionError(error.code,block['id']+': '+str(error),action=error.action));continue
  pictures.append(picture)
 if failed:
  from longform_contract import gathered
  raise gathered(failed)
 def normalize(folder,b,p,v):
  surface,outputs=render_scene(folder,b,plan['media'],v,plan['subject']['name'],layout,picture=p,picture_only=True)
  return dict(p,path=surface['path'],start=0,normalized=True),outputs
 # Normalize only surfaces participating in a cross-scene transition. Keep
 # ordinary scenes on their existing direct composition path.
 active=set()
 for i,b in enumerate(plan['blocks']):
  if b['visual'].get('scene_handoff'):active.update((i,i+1))
 for i in sorted(active):
  b=plan['blocks'][i];p=pictures[i];v=dict(voices[i],frames=p['frames'],captions=[])
  deps=[p['path']]+scene_media_paths(b['visual'],plan['media'])
  pictures[i]=stages.run('surface-'+b['id'],{'picture':p,'code':render_code_id(b['visual']['kind'])},deps,
      lambda folder,b=b,p=p,v=v:normalize(folder,b,p,v))
 surfaces=list(pictures)
 for i,b in enumerate(plan['blocks'][:-1]):
  spec=b['visual'].get('scene_handoff')
  if not spec:continue
  from longform_shatter import handoff
  outgoing=surfaces[i];incoming=surfaces[i+1]
  pictures[i+1]=stages.run('handoff-'+b['id'],
      {'outgoing':outgoing,'incoming':incoming,'transition':spec,'code':render_code_id('graphic')},
      [outgoing['path'],incoming['path']],
      lambda folder,a=outgoing,z=incoming,t=spec:handoff(folder,a,z,t))
 from longform_photo import planned_encoder
 encoder=planned_encoder()   # scene.mp4 is joined with `-c copy`: the key names the encoder that makes it
 for block,voice,picture in zip(plan['blocks'],voices,pictures):
  inputs={'code':render_code_id(block['visual']['kind']),'render_epoch':cfg.get('render_epoch'),
          'picture':picture,'subject':plan['subject'],'styles':plan.get('styles',{}),
          'voice':voice,'highlights':block.get('highlights',[]),'encoder':encoder}
  deps=[picture['path']]+fonts
  if picture.get('montage_proof'):deps.append(picture['montage_proof'])
  # Effects such as grain_wipe still read explicit texture dependencies while
  # compositing; source_style fonts are also part of this receipt.
  deps+=scene_media_paths(block['visual'],plan['media'])
  if block['visual'].get('source_style',{}).get('font_file'):deps.append(Path(cfg['fonts'])/block['visual']['source_style']['font_file'])
  scene=stages.run('scene-'+block['id'],inputs,deps,
      lambda folder,b=block,v=voice,p=picture:render_scene(folder,b,plan['media'],v,plan['subject']['name'],layout,picture=p))
  scenes.append(scene)
 return scenes

def endcard_stage(stages,plan,layout,fonts):
 """End card as its own stage — joined after the scenes with `-c copy`, so its receipt names its encoder."""
 from longform_endcard import render
 from longform_photo import planned_encoder
 here=Path(__file__).parent
 inputs={'code':digest({'endcard':file_digest(here/'longform_endcard.py'),'photo':file_digest(here/'longform_photo.py'),
                        'layout':render_code_id('layout')}),
         'endcard':plan.get('endcard',{}),'encoder':planned_encoder()}
 def make(folder):
  path,encoder=render(folder,layout,plan)
  return {'path':str(path),'encoder':encoder},[Path(path),Path(folder)/'endcard.png']
 return stages.run('endcard',inputs,fonts,make)

def render_joined(stages,plan,voices,fonts,layout,cfg):
 """Scenes + end card — the pieces the assembly joins with `-c copy` — all from one encoder.

 A GPU that fails on any joined piece is marked broken for this process (EncoderFailed); then every joined piece
 is rendered again: the stage keys carry the encoder, so the second pass renders on CPU and reuses nothing made
 on the GPU. At most two passes — the second has no GPU left to fail."""
 from longform_photo import EncoderFailed
 for attempt in (1,2):
  try:
   scenes=render_scenes(stages,plan,voices,fonts,layout,cfg)
   return scenes,endcard_stage(stages,plan,layout,fonts)
  except EncoderFailed:
   if attempt==2:raise

def media_review_summary(report,path,**counts):
 # 중복 검사 결과 전문은 파일(path · longform_media.inspect/inspect_timed 가 쓴다)에 있다 — 서버로 돌아가는 값에는 경로와 개수만.
 # 후보 목록은 원본 구간 쌍마다 늘어 225컷 편에서 6.4MB(조각 하나 1KB 남짓이라 실행기 분할 전송 단위 16KiB 에 못 미쳐 통째로 남는다)
 # → 사전 점검 결과가 전송 상한 2MiB 를 넘어 «증거 인라인 … 나누지 못했습니다» 로 longform_seed·run 이 멈췄다(2026-10-22 신고 4건).
 # 서버는 이 목록을 읽지 않고, 작가 안내(geumbit timed_media_review)는 duplicates.json 을 직접 읽게 한다.
 return {'path':str(path),'status':'review_required',
         'similar_composition_candidates':len(report['similar_video_compositions']),
         'sampled_duplicate_candidates':len(report['matches']),'plan_id':report['plan_id'],**counts}

def timed_media_review(stages, plan, voices):
 from longform_media import inspect_timed
 def review(folder):
  report=inspect_timed(plan,voices,folder)
  path=folder/'duplicates.json'
  return media_review_summary(report,path,video_windows=len(report['source_windows']),
                              voice_clock_id=report['voice_clock_id']),[path]
 return stages.run('timed-media-review',{'code':code_id(),'plan':plan,'voices':voices},
                   sorted({a['path'] for a in plan['media'].values()}),review)


def produce(cfg):
 from longform_render import Layout,render_scene
 root=Path(cfg['workdir'])/'geumbit';root.mkdir(parents=True,exist_ok=True)
 with file_lock(root/'production.lock'):
  try:
   plan=validate(cfg['plan']);validate_requested_duration(plan,cfg.get('requested_target_seconds'))
   # One digest of the authored plan for every use below (status per block, evidence, final state). Nothing in
   # this function mutates the authored plan: timed_voice/paid_preflight/check_duration/opening_review read it and
   # conform_plan deep-copies it (6-00: the old per-block digest re-hashed the whole plan B times).
   plan_id=digest(plan)
   # validate() returns the same cfg['plan'] object; preflight() reuses these checks instead of repeating them.
   checked=editorial_evidence(root/'preflight',plan,plan_id=plan_id);pf=preflight(cfg,checked=checked)
   if not pf['ok']:raise ProductionError('preflight_failed',json.dumps(pf['missing'],ensure_ascii=False),action='repair_environment')
   # Gemini TTS (2026-10-22 · 요청 82): each block's Volcano Kit WAV becomes an external voice in a copy of the plan, so
   # budget and timing below take the existing author-voice path (measured word times). Typecast jobs: the same object.
   from longform_gemini_voice import with_voices
   if cfg.get('voice_engine'):save(root/'status.json',{'engine':VERSION,'state':'running','phase':'voice','block':None,'completed':0,'total':len(plan['blocks']),'plan_id':plan_id})
   voiced=with_voices(plan,cfg,root)
   budget=paid_preflight(root,voiced,cfg);save(root/'cost-plan.json',budget)
   layout=Layout(cfg['fonts'],styles=plan.get('styles'),headline=plan['subject']['headline'],lang=cfg.get('screen_language','ko'));stages=Stages(root);voices=[];scenes=[];fonts=[Path(cfg['fonts'])/n for n in FONT_NAMES]+layout.font_dependencies();implementation=code_id()
   for index,block in enumerate(voiced['blocks']):
    save(root/'status.json',{'engine':VERSION,'state':'running','phase':'voice','block':block['id'],'completed':index,'total':len(plan['blocks']),'plan_id':plan_id})
    voices.append(timed_voice(block,cfg,root,layout))
   save(root/'duration-check.json',check_duration(plan,voices))
   save(root/'opening-review.json',opening_review(plan,voices))
   from longform_timing import conform_plan,validate_source_capacity
   execution_plan=conform_plan(plan,voices)
   # The authored plan was judged above before paid voice; re-judging unique-v1 on the conformed at/duration would
   # repeat the check and could flip it after TTS (B2). Structural checks still run on the execution plan.
   validate(execution_plan,execution=True)
   validate_source_capacity(execution_plan,voices)
   save(root/'execution-plan.json',execution_plan)
   # One digest of the execution plan, shared with its editorial audit (6-00); everything after reads it only.
   execution_id=digest(execution_plan)
   editorial=editorial_evidence(root,execution_plan,voices,source_plan=plan,plan_id=execution_id,source_plan_id=plan_id)
   timed_review=timed_media_review(stages,execution_plan,voices)
   save(root/'timed-media-review.json',timed_review)
   import inspect
   audio_inputs={'code':digest({'build':inspect.getsource(build_audio),'audio':file_digest(Path(__file__).with_name('longform_audio.py')),'source_audio':file_digest(Path(__file__).with_name('longform_source_audio.py'))}),
     'voices':[{key:v[key] for key in ('path','sha256','frames','samples')} for v in voices],
     'repairs':[b.get('audio_repair') for b in plan['blocks']],
     'source_audio':[b.get('source_audio',[]) for b in execution_plan['blocks']],'source_media':{c['media']:plan['media'][c['media']] for b in execution_plan['blocks'] for c in b.get('source_audio',[])},
     'sfx':[b.get('sfx',[]) for b in execution_plan['blocks']],'sound_assets':plan.get('sound_assets',{}),'music':execution_plan.get('music')}
   audio=stages.run('audio-master',audio_inputs,[v['path'] for v in voices]+[a['path'] for a in plan.get('sound_assets',{}).values()]+longform_source_audio.dependencies(execution_plan),lambda folder:build_audio(folder,voices,execution_plan))
   # 2026-10-17 사장님 결정: 렌더가 끝난 뒤에는 agy 를 부르지 않는다 — B3 그래픽 실화면 검수(렌더한 그래픽을 agy 가 보기)를
   # 지웠다. 그래픽 다양성은 굽기 전 제작표 계약(longform_contract · unique-v1 조합·이웃 유일 규칙)이 잰다.
   scenes,endcard=render_joined(stages,execution_plan,voices,fonts,layout,cfg)
   result=stages.run('assemble',{'code':assembly_code_id(),'render_epoch':cfg.get('render_epoch'),'plan':execution_plan,'scenes':scenes,'endcard':endcard,'voices':voices,'audio':audio},[s['path'] for s in scenes]+[endcard['path'],audio['path']]+fonts,lambda folder:assemble(folder,scenes,endcard,voices,execution_plan,layout,audio))
   verified=validate_output(root,result);save(root/'verification.json',verified)
   # 렌더 뒤 사람(호스트 AI) 눈 검수도 지웠다(같은 결정) — 결과물은 프로그램 측정(validate_output: 규격·길이·음량·파일)을
   # 통과하면 곧바로 완료(passed)로 넘어가 전달(deliver)만 남는다.
   state={'engine':VERSION,'state':'passed','delivery_verified':False,'result':result,'verification':str(root/'verification.json'),'opening_review':str(root/'opening-review.json'),'editorial_review':editorial,'events':stages.events,'plan_id':plan_id,'execution_plan_id':execution_id,'code_id':implementation,'render_id':digest(verified['files'])}
   state['source_boundary_reviews']=[{'block':b['id'],'reports':s.get('source_boundary_reports',[])} for b,s in zip(execution_plan['blocks'],scenes) if s.get('source_boundary_reports')]
   state['timed_media_review']=timed_review
   from longform_video import boundary_review_page
   state['source_boundary_review_page']=boundary_review_page(root,state['source_boundary_reviews'])
   save(root/'status.json',state);return state
  except Exception as error:
   fault=error.record() if isinstance(error,ProductionError) else {'code':'paid_request_uncertain' if isinstance(error,PaidUncertain) else 'production_failed','message':str(error),'retryable':False,'action':'reconcile_request' if isinstance(error,PaidUncertain) else 'repair'}
   state={'engine':VERSION,'state':'blocked','error':fault};save(root/'status.json',state);return state

def alive(run):
 import psutil
 try:
  p=psutil.Process(run['pid'])
  return p.is_running() and abs(p.create_time()-run['created'])<.1 and p.status()!=psutil.STATUS_ZOMBIE
 except (KeyError,psutil.Error):return False

def frozen_runtime(root,source=None):
 # A running job must not import a mixture of pre/post-update runner modules.
 from film_editor import atomic_bytes
 source=Path(source) if source else Path(__file__).resolve().parent
 bodies={p.name:p.read_bytes() for p in source.glob('*.py')}
 manifest={name:__import__('hashlib').sha256(body).hexdigest() for name,body in bodies.items()}
 if 'longform_engine.py' not in bodies:raise ProductionError('runtime_missing','실행기 원본이 없습니다.')
 folder=Path(root)/'runtime'/digest(manifest);folder.mkdir(parents=True,exist_ok=True)
 for name,body in bodies.items():
  target=folder/name
  if target.exists():
   if file_digest(target)!=manifest[name]:raise ProductionError('runtime_changed','보존된 실행기 파일이 변경됐습니다: '+str(target),action='repair_environment')
  else:atomic_bytes(target,body)
 save(folder/'manifest.json',manifest)
 return folder/'longform_engine.py'

def launch(cfg):
 import psutil
 root=Path(cfg['workdir'])/'geumbit';root.mkdir(parents=True,exist_ok=True)
 with file_lock(root/'launch.lock'):
  previous=read(root/'run.json') if (root/'run.json').exists() else {}
  if alive(previous):
   if previous.get('plan_id')!=digest(cfg['plan']):raise ProductionError('job_running','작업이 실행 중입니다. 완료 후 새 편집표를 적용하세요.',action='wait')
   return {'ok':True,'engine':VERSION,**previous,'reused':True}
  run_id=uuid.uuid4().hex
  epoch_file=root/'render-epoch.json'
  if cfg.get('restart_local') is True:save(epoch_file,{'epoch':run_id,'paid_records_preserved':True})
  epoch=read(epoch_file).get('epoch') if epoch_file.exists() else None
  config=root/('run-'+run_id+'.json');save(config,{**cfg,'mode':'run','render_epoch':epoch})
  log=root/('run-'+run_id+'.log')
  runtime=frozen_runtime(root)
  state_file=root/'status.json'
  if state_file.exists():save(root/('status-before-'+run_id+'.json'),read(state_file))
  save(state_file,{'engine':VERSION,'state':'running','phase':'launch','run_id':run_id,'plan_id':digest(cfg['plan'])})
  with log.open('wb') as stream:
   # Windows: a hidden console of its own (CREATE_NO_WINDOW), not DETACHED_PROCESS. A detached (console-less) engine gives every console
   # child it starts (ffmpeg, node, python) a new console window (win-01: GetConsoleWindow != 0 under a DETACHED parent; 0 with
   # CREATE_NO_WINDOW -- docs/2026-10-05_조교-윈도우OCR_w2b-I.md), one conhost per child for the whole production; closing one ends that
   # child (0xC000013A). 0xC0000142 is NOT caused by many consoles: win-main 2026-10-23 ran 600 concurrent conhosts with none; it is a
   # child that inherits a console which has already gone (10/10 fail, own hidden console 10/10 ok -- docs/solutions/integration-issues/
   # windows-0xC0000142-dead-console-2026-10-23.md). That is another reason the engine gets its own hidden console here.
   # Children inherit the one hidden console. Same choice as the movie runner (_detach/_group). CREATE_NO_WINDOW is ignored together
   # with DETACHED_PROCESS (Microsoft Process Creation Flags), so the two are not mixed.
   options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | subprocess.CREATE_BREAKAWAY_FROM_JOB} if os.name=='nt' else {'start_new_session':True}
   try:
    proc=subprocess.Popen([sys.executable,str(runtime),str(config)],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,close_fds=True,env={**scratch_environment(cfg),'HYPERFRAMES_RENDER_DETACHED':'1'},**options)
   except OSError as error:
    fault=ProductionError('background_launch_unavailable','독립 제작 프로세스를 시작하지 못했습니다. 기존 결과와 요청 기록은 보존했습니다. 실행 파일 권한과 실행 앱의 프로세스 분리 제한을 확인한 뒤 같은 작업폴더에서 재개하세요: '+str(error),action='repair_environment')
    save(state_file,{'engine':VERSION,'state':'blocked','error':fault.record(),'run_id':run_id})
    raise fault from error
  record={'pid':proc.pid,'created':psutil.Process(proc.pid).create_time(),'run_id':run_id,'plan_id':digest(cfg['plan']),'log':str(log)}
  save(root/'run.json',record)
  return {'ok':True,'engine':VERSION,**record,'reused':False}

def _log_tail(path,limit=1200):
 """Last characters of the job log (bounded read: only the final 64 KiB), or '' when unreadable."""
 try:
  with open(native_path(path),'rb') as stream:
   stream.seek(0,os.SEEK_END);size=stream.tell();stream.seek(max(0,size-65536))
   text=stream.read().decode('utf-8',errors='replace')
 except (OSError,TypeError,ValueError):return ''
 lines=[x.strip() for x in text.replace('\r','\n').split('\n') if x.strip()]
 return ' | '.join(lines)[-limit:]

def status(cfg):
 root=Path(cfg['workdir'])/'geumbit';deadline=time.monotonic()+min(1800,float(cfg.get('wait_seconds',30)))
 while True:
  run=read(root/'run.json') if (root/'run.json').exists() else {}
  state=read(root/'status.json') if (root/'status.json').exists() else {'engine':VERSION,'state':'not_started'}
  if alive(run):
   if time.monotonic()>=deadline:return {**state,'engine':VERSION,'state':'running','run_id':run['run_id'],'pid':run['pid']}
   time.sleep(.5);continue
  if state.get('state')=='running':
   # The job's own log is the only witness of why it died (killed, crashed outside produce(), PC slept…).
   # 2026-10-14: 41 blocked jobs/24h said only «종료됐습니다» — the cause stayed on the student PC. Carry the tail.
   tail=_log_tail(run.get('log'))
   return {'engine':VERSION,'state':'blocked','error':{'code':'process_interrupted','retryable':False,'action':'resume','message':'작업 프로세스가 종료됐습니다. 결과와 요청 기록은 보존했습니다. 사전 검사 후 미완료 부분부터 재개하세요.'+(' 마지막 실행 기록: '+tail if tail else ' (실행 기록이 비어 있습니다 — 프로세스가 기록을 남기기 전에 끝났습니다)'),'log':run.get('log'),'log_tail':tail}}
  if cfg.get('plan') and state.get('plan_id') and state['plan_id']!=digest(cfg['plan']):return {'engine':VERSION,'state':'blocked','error':{'code':'plan_changed','retryable':False,'action':'resume','message':'현재 제작표와 이전 결과가 다릅니다. 새 제작표로 부분 재개하세요.'}}
  return state

def accept(cfg):
 """옛 판이 «review_required» 로 남긴 작업을 잇는다(2026-10-17 렌더 뒤 사람·agy 검수 삭제). 검수 기록을 받지 않고, 결과 파일이
 렌더 때와 같은지(프로그램 측정 validate_output 의 지문)만 보고 완료로 넘긴다. 새 작업은 렌더가 곧바로 passed 다."""
 root=Path(cfg['workdir'])/'geumbit'
 with file_lock(root/'production.lock'):
  state=status({**cfg,'wait_seconds':0})
  if state.get('state')=='passed':return state
  if state.get('state')!='review_required':raise ProductionError('review_state','완료할 영상이 없습니다.')
  verified=validate_output(root,state['result'])
  if digest(verified['files'])!=state['render_id']:raise ProductionError('output_changed','렌더 이후 결과 파일이 변경됐습니다.',action='review')
  state.pop('graphic_review',None)
  state.update(state='passed',delivery_verified=False);save(root/'status.json',state);return state

def deliver(cfg):
 root=Path(cfg['workdir'])/'geumbit'
 with file_lock(root/'production.lock'):
  state=status({**cfg,'wait_seconds':0})
  if state.get('state')!='passed':raise ProductionError('not_passed','아직 완료 판정이 없습니다.')
  verified=validate_output(root,state['result'])
  if digest(verified['files'])!=state['render_id']:raise ProductionError('output_changed','전달할 파일이 검수한 파일과 다릅니다.',action='review')
  return {**state,'delivery_verified':True}

def main():
 # Windows redirected stderr otherwise uses the local code page (e.g. CP949),
 # while the public runner consumes UTF-8 JSON and logs on both platforms.
 for stream in (sys.stdout,sys.stderr):
  if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
 # 2026-10-17 신고 #132: the engine ended with a non-zero code and an empty stderr (5 students · Windows) — a death outside
 # Python's exception handling (a native crash in an extension module), which the JSON fault below cannot report. Python's
 # own fault handler writes the crashing thread's Python stack to stderr on such a crash; the runner already puts the exit
 # code and the stderr tail into its «실행 실패» message (volcano_run.failure_text). One thread keeps it inside that tail.
 # It needs a real file descriptor; a stderr without one (an embedding host or a test double) has nowhere to write a
 # native crash, so the handler is simply not armed there.
 try:stderr_fd=sys.stderr.fileno()
 except (AttributeError,OSError,ValueError):stderr_fd=None
 if stderr_fd is not None:faulthandler.enable(file=sys.stderr,all_threads=False)
 cfg=read(sys.argv[1]);mode=cfg.get('mode','run')
 try:
  if mode in ('preflight','run','start'):
   # B3: the agy graphic review keeps its temporary workspace OUTSIDE the student workdir. Remember the original
   # system temp folder before TMPDIR/TEMP/TMP point into the workdir (a child started by «start» inherits it, so
   # setdefault keeps the first one). tempfile's cache is restored so later Python temp files follow the override as before.
   cached=tempfile.tempdir;os.environ.setdefault('VOLCANO_SYSTEM_TMP',tempfile.gettempdir());tempfile.tempdir=cached
   selected=('TMPDIR','TEMP','TMP','NPM_CONFIG_CACHE','NPM_CONFIG_PREFER_OFFLINE')
   environment=scratch_environment(cfg)
   for name in tuple(os.environ):
    if name.upper() in selected:del os.environ[name]
   for name in selected:os.environ[name]=environment[name]
  handler={'preflight':preflight,'start':launch,'run':produce,'status':status,'accept':accept,'deliver':deliver}[mode]
  result=handler(cfg)
 except Exception as error:
  fault=error.record() if isinstance(error,ProductionError) else {'code':'runtime_failed','message':str(error),'retryable':False,'action':'repair'}
  result={'ok':False,'engine':VERSION,'state':'blocked','error':fault}
 sys.stdout.buffer.write((json.dumps(result,ensure_ascii=False)+"\n").encode("utf-8"))
if __name__=='__main__':main()
