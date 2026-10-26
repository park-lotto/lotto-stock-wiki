"""Subscription AGY media transport; shares the shipped 3D adapter's machine slots.

Official stream result/error semantics: https://antigravity.google/docs/cli/headless
Official auth: https://antigravity.google/docs/cli/install
Concurrency16 and file100MiB: existing info3d/ref/agy_codes.json (user/tool policy,
not claimed as Google limits). No documented request spacing/retry numeric was
found in official headless/reference/usage pages on2026-10-03. This bridge uses
one adapter invocation, never the higher-level agy_review retry loop.
"""
import hashlib
import json
import os
import re
import math
import uuid
from pathlib import Path
import agy_transport_client as AGY
import agy_transport_pc_env as PC
import agy_transport_refusal as run_refusal

_PROCESS_RUN_ID = uuid.uuid4().hex


def _sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()


def _files(request):
 values=[]
 for field in ('images','video','audio','videos','audios'):
  value=request.get(field) or []
  values.extend(value if isinstance(value,list) else [value])
 return values


def _environment(config):
 env=dict(os.environ)
 env['INFO3D_RUN_ID']=env.get('INFO3D_RUN_ID') or config.get('run_id') or _PROCESS_RUN_ID
 env['INFO3D_REFUSAL_ROOT']=env.get('INFO3D_REFUSAL_ROOT') or config.get('run_root') or str(Path.home()/'.volcano')
 if config.get('bin'):env['INFO3D_AGY_BIN']=str(config['bin'])
 # Installation memory is a path hint only, never a choice of review provider.
 if not env.get('INFO3D_AGY_BIN') and not env.get('INFO3D_TEXT_PROVIDER_FILE'):
  home=Path(env.get('USERPROFILE') or env.get('HOME') or Path.home())
  memory=home/'.volcano/info3d/pc.json'
  if memory.exists():
   data=json.loads(memory.read_text(encoding='utf8'))
   hint=(data.get('agy') or {}).get('path')
   if hint:env['INFO3D_AGY_BIN']=str(hint)
 return env


ANSWER_STRING_TAIL=('\nReturn the complete reply_schema identity envelope, but encode its answer value as a JSON STRING containing '
                    'the original typed answer. Do not change the typed answer inside that string.')
ANSWER_OBJECT_TAIL='\nReturn the complete reply_schema identity envelope; its answer value is the typed answer object itself.'


def transport_schema(expected,answer_schema=None):
 # Google function schema supports string enums and typed arrays, not array-valued enums.
 # https://ai.google.dev/gemini-api/docs/structured-output
 # answer_schema: 질문이 답의 모양을 실었으면 그 객체 스키마 그대로(모델이 JSON 을 글자로 다시 감싸지 않는다 · 510306).
 properties={}
 for key,value in expected.items():
  if isinstance(value,list) and all(isinstance(v,str) for v in value):
   properties[key]={'type':'array','items':{'type':'string'},'minItems':len(value),'maxItems':len(value)}
  elif isinstance(value,str):properties[key]={'type':'string','enum':[value]}
  else:raise ValueError('Unsupported AGY reply identity schema')
 properties['answer']=(answer_schema if answer_schema is not None else
                       {'type':'string','description':'The original typed answer encoded as one complete JSON string.'})
 return {'type':'object','required':list(properties),'additionalProperties':False,'properties':properties}


def _strict_json(text):
 if not isinstance(text,str):raise ValueError('AGY transport answer must be a JSON string')
 def pairs(items):
  result={}
  for key,value in items:
   if key in result:raise ValueError('AGY answer contains duplicate JSON keys')
   result[key]=value
  return result
 def invalid(value):raise ValueError('AGY answer contains non-finite JSON numbers')
 def number(value):
  parsed=float(value)
  if not math.isfinite(parsed):invalid(value)
  return parsed
 return json.loads(text,object_pairs_hook=pairs,parse_constant=invalid,parse_float=number)


def provider_evidence(result,request_sha):
 # Local receipt only: preserve the parsed result, never raw process logs or environment.
 raw=json.dumps(result,sort_keys=True,ensure_ascii=False)
 secret_key=re.compile(r'(?:authorization|password|api[_-]?key|access[_-]?token|refresh[_-]?token|^token$|cookie|credential)',re.I)
 secrets=[v for k,v in os.environ.items() if secret_key.search(k) and isinstance(v,str) and len(v)>=8]
 def clean(value):
  if isinstance(value,dict):return {str(k):('[REDACTED]' if secret_key.search(str(k)) else clean(v)) for k,v in value.items()}
  if isinstance(value,list):return [clean(v) for v in value]
  if isinstance(value,str):
   for secret in secrets:value=value.replace(secret,'[REDACTED]')
   value=re.sub(r'(?i)Bearer\s+[^\s"\']+','Bearer [REDACTED]',value)
   value=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','[REDACTED_EMAIL]',value)
   return value
  return value
 return {'version':1,'request_sha256':request_sha,'original_result_sha256':hashlib.sha256(raw.encode()).hexdigest(),'result':clean(result)}


def failure_reason(result):
 safe=provider_evidence(result,'')['result']
 return 'AGY media review incomplete: code={code}, status={status}, exit={returncode}: {message}; error={error}'.format(**{k:safe.get(k) for k in ('code','status','returncode','message','error')})


def _agy_view(request):
 """agy 에게 보이는 요청 글 — 매체 경로만 AGY.plain_path 글자로. 원래 요청(확인 SHA·증거)은 그대로 둔다."""
 shown=dict(request)
 for field in ('images','video','audio','videos','audios'):
  value=request.get(field)
  if isinstance(value,dict):shown[field]={**value,'path':AGY.plain_path(value['path'])}
  elif isinstance(value,list):shown[field]=[{**v,'path':AGY.plain_path(v['path'])} if isinstance(v,dict) and 'path' in v else v for v in value]
 return shown


def verified_answer(request,result):
 """A model claim alone cannot establish that original media were opened."""
 if (not result.get('ok') or result.get('status') != 'SUCCESS'
     or (result.get('returncode') != 0 and not result.get('closedAfterResult'))   # 답을 다 쓰고 매달려 우리가 끝낸 것만 0 아님을 받는다(#305)
     or result.get('denied')):raise ValueError(failure_reason(result))
 # 도구 기록 판정은 전송 한 자리(AGY.opened_exactly — 1.4.2 view_file · 1.4.3 read_file 같은 표 · 긴 경로 머리 없는 글자로 대조).
 search='web_search' in request.get('capabilities',[])
 why,used=AGY.opened_exactly(result.get('tools'),[m['path'] for m in _files(request)],allowed=('search_web',) if search else ())
 if why:raise ValueError({'shape':'AGY tool evidence has an unknown shape','other_tool':'AGY used an unrequested tool',
  'path_missing':'AGY file read path evidence missing','outside':'AGY opened media outside this request',
  'missing':'AGY did not finish reading every required media file'}[why])
 if search and 'search_web' not in used:raise ValueError('AGY web search evidence missing')
 reply=result.get('json')
 expected={k:v for k,v in request['reply_schema'].items() if k!='answer'}
 if not isinstance(reply,dict) or set(reply)!={*expected,'answer'} or any(reply.get(k)!=v for k,v in expected.items()):
  raise ValueError('AGY reply does not match the original media request')
 for media in _files(request):
  if _sha(media['path'])!=media['sha256']:raise ValueError('AGY review media changed while reading')
 if request.get('answer_schema') is not None:
  if not isinstance(reply['answer'],dict):raise ValueError('AGY typed answer must be a JSON object')
  return reply['answer']
 return _strict_json(reply['answer'])


def review(config,request,*,before_model,on_result=None):
 """Preflight locally, record dispatch, invoke once, verify exact media evidence."""
 import volcano_run as R
 try:
  env=_environment(config)
  settings=PC.agy_settings_path(env)
  saved=json.loads(Path(settings).read_text(encoding='utf8')) if os.path.exists(settings) else {}
  if not isinstance(saved,dict):return None,'AGY settings must be a JSON object; original settings were preserved'
 except (ValueError,TypeError,OSError) as error:
  return None,'AGY configuration could not be read; original settings were preserved: '+str(error)
 R.check_review_running()
 try:
  run_refusal.assert_allowed(env)
 except run_refusal.RunServiceRefused as error:
  refusal=R.ProviderRefusalError('provider.agy',error.code,str(error))
  refusal.request_sent=False
  raise R.remember_review_refusal(refusal) from error
 if saved.get('modelProvider')=='gemini':return None,'AGY is configured for API keys; subscription login required'
 if saved.get('useG1Credits') is True:return None,'AGY paid credit fallback is enabled; subscription-only review requires useG1Credits=false'
 media=_files(request);limit=AGY.table()['fileLimitBytes']
 for item in media:
  if not os.path.isfile(item['path']) or _sha(item['path'])!=item['sha256']:return None,'AGY original media missing or changed'
  if os.path.getsize(item['path'])>limit:return None,'AGY_FILE_TOO_LARGE: media exceeds the declared view_file limit'
 ready,why,code=AGY.status(env)
 if not ready:
  if code in ('AGY_QUOTA','AGY_RATE_LIMIT','AGY_NOT_SIGNED_IN'):
   run_refusal.mark_refusal(env=env)
   raise R.remember_review_refusal(R.ProviderRefusalError('provider.agy',code,why))
  return None,why
 # Official headless contract auto-allows reads in the active workspace.
 # Keep user settings byte-identical; existing adapter adds every media parent.
 # agy 에 가는 경로는 긴 경로 머리 없는 글자로(AGY.plain_path 한 자리) — 붙은 채 가면 read_file 이 거부된다.
 paths=[AGY.plain_path(item['path']) for item in media]
 workspace = os.path.dirname(paths[0]) if paths else None
 expected={k:v for k,v in request['reply_schema'].items() if k!='answer'}
 schema=transport_schema(expected,request.get('answer_schema'))
 head=AGY.preface('view',paths)
 if 'web_search' in request.get('capabilities',[]):
  head='Use only view_file to read every listed original media file and search_web for the required source check. Never run commands or write files. Files: '+json.dumps(paths,ensure_ascii=False)
 prompt=head+'\n'+json.dumps(_agy_view(request),ensure_ascii=False)+(ANSWER_OBJECT_TAIL if request.get('answer_schema') is not None else ANSWER_STRING_TAIL)
 R.check_review_running()
 try:
  import subject_stage_pool as ST
  with ST.model_wait((run_refusal.RunServiceRefused,R.ProviderRefusalError)):
   R.check_review_running();before_model()
   # status_error='per_request' (W2-15 · owner decision 2026-10-05 5-1): an ordinary status ERROR (output limit,
   # invalid request, model stop) fails only this review request — pending, no automatic resend. Refusals still stop
   # the whole run: file-read permission denial, rate-limit/quota wording, and /usage showing quota spent, signed out
   # or unknown. A forbidden tool the model tried (RunCommand) is this request only (AGY.forbidden_tool_only, 2026-10-21).
   # ★'per_request_evidence'(2026-10-21 쇼핑 신고 510306 · 쇼핑 한 패스 10-17·인물형 롱폼 피사체 10-06 과 같은 판정): /usage 를
   #   확인하지 못한 것만으로는 거부가 아니다 — 400 INVALID_ARGUMENT(짧은 영상) 한 건이 /usage 확인 실패로 «서비스 거부» 가 되어
   #   회차 전체(7건)가 멈췄다. 속도·한도 낱말이나 /usage 가 한도 소진·로그인 풀림을 말하면 그대로 전부 멈춘다(6-2).
   result=AGY.invoke(prompt,kind=None,files=paths,schema=schema,env=env,tries=1,status_error='per_request_evidence',
                    model=config.get('model'),cwd=workspace,owner={'purpose':'volcano-client-review','request':request['request_sha256']})
   if on_result:on_result(provider_evidence(result,request['request_sha256']))
 except run_refusal.RunServiceRefused as e:
  evidence=getattr(e,'provider_result',None)
  if evidence is not None and on_result:on_result(provider_evidence(evidence,request['request_sha256']))
  code=(evidence or {}).get('refused_as') or (evidence or {}).get('code') or e.code
  reason=failure_reason(evidence) if evidence is not None else str(e)
  raise R.remember_review_refusal(R.ProviderRefusalError('provider.agy',code,reason)) from e
 # 도구 거부는 한 판정(AGY.forbidden_tool_only)으로 가른다. 파일 읽기 권한 거부(허락 폴더·경로 — 모든 요청에 같다)·모양 모르는
 # 거부는 예전처럼 이 실행을 멈춘다. 모델이 금지 도구(RunCommand 등)를 시도한 것은 그 요청 하나의 실패뿐이다(failure_kind
 # 'forbidden_tool') — verified_answer 가 denied 를 미완료로 돌려 이 요청만 대기(engine_failed)가 된다. 여기서 거부 표식을
 # 남기면 같은 실행의 다른 컷이 전부 멈춘다(2026-10-20 쇼핑 shop_cuts 신고: 1컷 거부 → 23컷 provider_refused).
 # 판정은 전송 한 자리(invoke 가 forbidden_tool_only 로 가른 failure_kind)를 그대로 읽는다 — 여기서 다시 가르지 않는다(갈리면 상충).
 if (result.get('denied') or result.get('code') == 'AGY_TOOL_DENIED') and result.get('failure_kind') != 'forbidden_tool':
  run_refusal.mark_refusal(env=env)
  raise R.remember_review_refusal(R.ProviderRefusalError('provider.agy','AGY_TOOL_DENIED','AGY refused a requested media tool; this run is stopped'))
 try:return verified_answer(request,result),None
 except (ValueError,KeyError,TypeError,OSError) as error:return None,str(error)
