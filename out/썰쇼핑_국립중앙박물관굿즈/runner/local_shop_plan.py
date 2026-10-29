"""Shop geometry, filters and editable original motion remain on the user's PC."""
import copy
import hashlib
import json
from pathlib import Path
import local_render_plan as T

def _validate(task):
 import shop_kernel as K,focus_kernel as F,volcano_run as R
 if (task.get('kernel_id')!=K.KERNEL_ID or task.get('focus_kernel_id')!=F.KERNEL_ID
     or task.get('shop_kernel_sha256')!=hashlib.sha256(Path(K.__file__).read_bytes()).hexdigest()
     or hashlib.sha256(T._bytes(T._semantic(task))).hexdigest()!=task.get('contract_key')):
  raise R.StepError('쇼핑 로컬 계산 규격 또는 코드가 다릅니다.')
 folder=task['workdir']+'/local-shop/'+task['contract_key']
 files={str(c['card']):folder+'/cut-'+str(c['card'])+'.filter' for c in task['cuts']}
 files.update(raw_cuts=folder+'/original_cuts.json',receipt=folder+'/planner_receipt.json')
 if task['out_dir']!=folder or task['files']!=files:raise R.StepError('쇼핑 로컬 파일 경로가 계약과 다릅니다.')

class GeometryRejected(ValueError):
 def __init__(self,diagnostics):
  self.diagnostics=diagnostics
  super().__init__('쇼핑 컷 기하 검증 실패')

def _build(task,rows):
 import shop_kernel as K,volcano_run as R
 args=task['inputs'];spec=task['spec']
 framed=K.audit_frames(args['cuts'],rows,spec,src_crop=args['src_crop'])
 if framed['reject']:
  diagnostics={}
  bound={str(c['card']):c for c in task['cuts']}
  for cut in args['cuts']:
   card=str(cut['order']);one=K.audit_frames([cut],rows,spec,src_crop=args['src_crop'])
   if one['reject']:
    diagnostics[card]=dict(code='shop_geometry_invalid',stage='framing',
      reasons=one['reject'],automatic_retry=False,focus_key=bound[card]['focus_key'],
      source=bound[card]['src'],source_identity=rows[card]['source_identity'])
  raise GeometryRejected(diagnostics)
 jobs=K.cut_jobs(args['cuts'],args['times'],args['shots'],args['sources'],task['workdir'],spec,plan=framed['plan'])
 raw=K.deliver_cuts(args['cuts'],args['times'],args['shots'],args['sources'],framed['plan'],spec)
 blobs={str(job['index']):('[0:v]'+job['argv'][job['argv'].index('-vf')+1]+'[filtered_video]').encode() for job in jobs}
 blobs['raw_cuts']=(json.dumps(raw,ensure_ascii=False,indent=2)+'\n').encode()
 return blobs,framed['warn']

def _changed(current):
 e=T._source_changed(current);e.execution_next_step='shop_cuts';return e

# ★온화면 컷(2026-10-08 · 쇼핑 수리): 서버가 `shop_full_frame` 을 붙인 컷은 원본 알맹이가 이미 출력과 같은 세로 9:16 이라
#   피사체를 어디로 고르든 화면이 바뀌지 않는다 — 피사체 초점(물체 고르기·추적·AGY 검수)을 부르지 않고, 수급이 잰 알맹이
#   상자를 그대로 행으로 쓴다(audit_frames 의 기본 갈래 frame_crop · 2026-10-04 이전 쇼핑과 같은 자).
#   실측(10-08 E2E 줄눈펜): 21컷 모두 세로 원본인데 초점이 22분 걸리고 14컷이 «selection_unresolved» 로 막혔다.
#   원본 바이트 묶기(source_identity · _source_versions)는 다른 컷과 똑같이 건다.
def _full_frame(cut):
 v=cut.get('shop_full_frame')
 return v if isinstance(v,dict) and isinstance(v.get('content'),list) and isinstance(v.get('size'),list) else None

def _full_row(cut,identity):
 v=_full_frame(cut)
 return dict(size=[int(x) for x in v['size']],content=[int(x) for x in v['content']],source_identity=identity)

def prepare(task,headers=None):
 import local_focus as F,volcano_run as R
 from longform_state import native_path,save
 from film_editor import atomic_bytes,file_digest
 _validate(task);current=T._source_versions(task)
 if task.get('source_versions')!=current:raise _changed(current)
 root=native_path(task['out_dir']);root.mkdir(parents=True,exist_ok=True)
 with R.review_receipt_lock(str(root/'execution')):
  identities={}   # 뿌리마다 지금 검출 환경 지문 한 번(local_focus.runtime_stale)
  if T.reusable_receipt(native_path(task['files']['receipt']),identities):return verify(task,identities)
  focus_cuts=[c for c in task['cuts'] if _full_frame(c) is None]
  focus=(F.prepare_local_focus(dict(version=1,kernel_id=task['focus_kernel_id'],contract_key=task['contract_key'],cuts=focus_cuts,selection=task['selection'],text_review=task['text_review'],out_dir=task['out_dir']+'/focus',legacy_dir=task['workdir']+'/local-shop/evidence'),headers=headers)
         if focus_cuts else dict(status='complete',receipts={},review_requests=[],diagnostics={}))
  result=dict(version=1,contract_key=task['contract_key'],status=focus['status'],files={},counts={},warnings=[],source_sizes={},review_requests=focus.get('review_requests',[]),diagnostics=focus.get('diagnostics',{}))
  if focus['status']!='complete':return result
  rows={card:T._read(native_path(meta['path'])) for card,meta in focus['receipts'].items()}
  # Preserve accepted source-bound selection before geometry can reject. A
  # changed crop/peer cut receives a new overall contract but reuses exact
  # unchanged focus keys through the existing validated legacy importer.
  if rows:F.preserve_wire_evidence({'frames':rows},out_dir=task['workdir']+'/local-shop/evidence')
  rows.update({str(c['card']):_full_row(c,current[c['src']]) for c in task['cuts'] if _full_frame(c) is not None})
  try:blobs,warnings=_build(task,rows)
  except GeometryRejected as exc:
   result.update(status='blocked',diagnostics=exc.diagnostics)
   save(root/'geometry_failure.json',dict(task=task,focus=focus,sources=current,result=result))
   return result
  latest=T._source_versions(task)
  if latest!=current:raise _changed(latest)
  for key,blob in blobs.items():atomic_bytes(native_path(task['files'][key]),blob)
  result.update(files={key:dict(path=task['files'][key],sha256=hashlib.sha256(blob).hexdigest()) for key,blob in blobs.items()},counts={'frames':sum(round(c['duration']*c['fps']) for c in task['cuts']),'parts':len(task['cuts']),'runs':len(task['cuts'])},warnings=warnings,source_sizes={card:row['size'] for card,row in rows.items()})
  save(native_path(task['files']['receipt']),dict(task=task,focus=focus,sources=current,result=result))
  result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
  return result

def verify(task,identities=None):
 import local_focus as F,focus_kernel as K,volcano_run as R
 from film_editor import file_digest
 from longform_state import native_path
 _validate(task);saved=T._read(native_path(task['files']['receipt']))
 if T._semantic(saved['task'])!=T._semantic(task) or saved['sources']!=task['source_versions']:raise R.StepError('쇼핑 저장 계약 또는 원본 목록이 변경됐습니다.')
 current=T._source_versions(task);rows={}
 for cut in task['cuts']:
  if _full_frame(cut) is not None:
   rows[str(cut['card'])]=_full_row(cut,saved['sources'][cut['src']]);continue
  meta=saved['focus']['receipts'][str(cut['card'])];path=native_path(meta['path'])
  if meta['path']!=task['out_dir']+'/focus/'+cut['focus_key']+'.'+saved['sources'][cut['src']]+'.json' or file_digest(path)!=meta['sha256']:raise R.StepError('쇼핑 검수 증거가 변경됐습니다.')
  row=T._read(path)
  if K.validate(cut,row) or row['source_identity']!=saved['sources'][cut['src']]:raise R.StepError('쇼핑 검수 증거가 현재 계약과 다릅니다.')
  rows[str(cut['card'])]=row
 F.verify_selection_runtime([rows[str(c['card'])] for c in task['cuts'] if _full_frame(c) is None],identities);blobs,warnings=_build(task,rows);result=copy.deepcopy(saved['result'])
 expected={key:dict(path=task['files'][key],sha256=hashlib.sha256(blob).hexdigest()) for key,blob in blobs.items()}
 if (result['files']!=expected or any(native_path(task['files'][key]).read_bytes()!=blob for key,blob in blobs.items())
     or result['warnings']!=warnings or result['source_sizes']!={card:row['size'] for card,row in rows.items()}
     or result['counts']!={'frames':sum(round(c['duration']*c['fps']) for c in task['cuts']),'parts':len(task['cuts']),'runs':len(task['cuts'])}):raise R.StepError('쇼핑 로컬 계획 또는 요약이 변경됐습니다.')
 latest=T._source_versions(task)
 if latest!=current:raise _changed(latest)
 if current!=saved['sources']:raise _changed(current)
 result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
 return result

def verify_proof(proof):
 from longform_state import native_path
 from film_editor import file_digest
 import volcano_run as R
 path=native_path(proof['files']['receipt']['path'])
 if file_digest(path)!=proof['files']['receipt']['sha256']:raise R.StepError('쇼핑 실행 증명이 변경됐습니다.')
 identities=T.runtime_checked(path,proof['files']['receipt'],'shop_cuts')
 saved=T._read(path);task=saved['task'];result=verify(task,identities)
 if proof!={'version':1,'kernel_id':task['kernel_id'],'contract_key':task['contract_key'],'files':result['files']}:raise R.StepError('쇼핑 실행 증명과 로컬 파일이 다릅니다.')
 return [dict(path=path,sha256=sha) for path,sha in saved['sources'].items()]

def delivery_files(item):
 """Generate original-source editor files after revalidating the local proof."""
 import shop_export_kernel as E,volcano_run as R
 from longform_state import native_path
 verify_proof(item['proof'])
 saved=T._read(native_path(item['proof']['files']['receipt']['path']));task=saved['task']
 if hashlib.sha256(Path(E.__file__).read_bytes()).hexdigest()!=task['shop_export_sha256']:raise R.StepError('쇼핑 편집 내보내기 코드가 계약과 다릅니다.')
 raw=T._read(native_path(task['files']['raw_cuts']));spec=task['spec']
 xml=E.fcp7_xml(item['name'],raw,item['audio'],item['total_frames'],item['markers'],spec,spec['FPS'])
 if item.get('text_records'):xml=E.editable_text_xml(xml,item['text_records'],spec['FPS'],spec['W'],spec['H'])
 return [dict(path=item['directory']+'/프리미어_원본편집.xml',content=xml),dict(path=item['directory']+'/원본소재.json',content=json.dumps(raw,ensure_ascii=False,indent=2)+'\n')]
