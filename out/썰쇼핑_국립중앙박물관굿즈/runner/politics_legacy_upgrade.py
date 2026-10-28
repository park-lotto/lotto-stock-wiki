"""Politics engine upgrade for the 10-04 baseline-repair command — keeps locally edited engine files.

■ 무슨 일이 있었나 (2026-10-04 12:43 배포 · 10-04 하루 148건·23명)
    서버가 이 설치기(`politics_baseline_repair` 칸)를 붙였고, 옛 판은 «갱신이 바꾸지도 않는 22개까지 공식본과
    바이트가 같아야 한다» 며 로컬에서 고친 폴더를 전부 막았다(`Existing baseline material differs: …`).
    사장님 결정(2026-09-15 «커스텀 전부 개방»)과 정반대였다. 서버는 이제 이 설치기를 시키지 않는다
    (→ 서버 src/politics/baseline.py). 그런데 **이미 막힌 폴더의 실행기는 저장해 둔 옛 지시를 서버에 묻지 않고
    다시 실행한다**(응답 영수증) — 그래서 그 옛 지시가 와도 서버와 **같은 판정**으로 맞추도록 이 설치기를 바꿨다.

■ 지금 동작 (조교 고정 작업이 아닌 폴더)
    install        공식 팩을 보관 폴더(`.politics-official/`)에 풀고, 서버가 내리는 맞춤 스크립트와 **같은 코드**
                   (`politics_baseline_core` = 서버 `runner_script.BASELINE` 바이트 그대로)로 맞춘다 —
                   고친 파일은 그대로 · 없거나 공식 옛 판이면 새 판 · 새 실행 방식과 안 맞물리는 커스텀만 보존 폴더로 옮긴 뒤 새 판.
    ready          «중간에 끊긴 맞춤이 없다» 만 본다(서버 관문과 같은 상태 파일). 바이트 대조는 없다.
    require_ready  ready 가 아니면 사람 말로 멈춘다 — 같은 단계를 다시 실행하면 이어서 끝낸다.

■ 조교 고정 작업(`.ta-job-receipt.json` 이 있는 폴더)은 기존 그대로다 — 영수증으로 판을 고정하는 다른 설계다.

이 설치기는 제작을 띄우지 않고, 유료 요청을 하지 않는다.
"""
import json, os, sys, tarfile
from ta_upgrade_local import native, safe, canonical, digest, file_sha  # noqa: F401 — canonical·digest 는 조교 고정 작업 시험이 이 모듈에서 꺼내 쓴다
OLD='58a2db55332dba16591db8187430fbfa5ac5fd6a0e78a3d6022c12b962908861'
NEW='82f780337b8e3cb74589f81958bd8ce9d5f22b2b276b82d3e81873f82892f620'

def validate(c):
 if c.get('protocol')!='politics-baseline-repair-v1' or (c.get('old_sha256'),c.get('sha256'))!=(OLD,NEW):raise ValueError('Unknown baseline repair')
 changes=c['changed'];preserved=c['preserved']
 if not changes or set(changes)&set(preserved):raise ValueError('Invalid baseline file contract')
 for p,row in changes.items():
  if not p.startswith('politics/politics/') or not row.get('after'):raise ValueError('Repair changes non-engine material')
 return dict(preserved,**{p:r['after'] for p,r in changes.items()})

def _pinned(workdir):
 """조교 고정 작업 — 영수증으로 판을 고정한 폴더(기존 엄격 판정을 그대로 쓴다)."""
 return os.path.lexists(native(workdir)/'.ta-job-receipt.json')

def _pinned_ready(workdir,c):
 expected=validate(c);root=native(workdir)
 journal=safe(root,'.politics-baseline-repair.json');done=safe(root,'.politics-baseline-effective.json')
 if journal.exists() and (not done.exists() or done.read_bytes()!=journal.read_bytes()):return False
 return all(safe(root,p).is_file() and file_sha(safe(root,p))==h for p,h in expected.items())

def spec(workdir,c):
 """맞춤 설정 — 이 지시가 맞추라는 판(계약의 NEW = 82f7)으로. 서버 `politics.baseline.sync_spec(workdir)` 과 같은 모양.

 ★맞출 판은 **계약**에서 온다(자료 파일 `politics_baseline_known` 의 지금 판이 아니다 · 2026-10-05 w3-E).
   저장된 이 지시는 10-04 의 82f7 팩을 받아 그 판의 실행 설정으로 제작을 띄운다 — 정치 팩이 그 뒤 새 판(X)이 되어도
   이 지시가 받는 팩·띄우는 실행 설정은 82f7 이다. 예전처럼 «자료의 지금 판 == 82f7» 을 요구하면, 정치 팩을 한 번
   다시 굽는 순간 이 설치기가 `Baseline repair data does not match the contract` 로 영구히 멈춘다(바로 그 폴더들이
   다시 막힌다). 그래서:
     files    계약이 검증한 82f7 의 파일 지문 전부(`validate`)
     known    공식 옛 판 지문(자료의 KNOWN) + 자료의 지금 판(X) 지문 가운데 82f7 과 다른 것 — 공식 파일이면 판이 무엇이든
              82f7 로 맞춘다(뒤이어 실행할 저장 지시가 82f7 이다). 고쳐 쓴 파일(어느 공식 지문과도 다르다)은 그대로다.
     updated  계약의 «바뀐 파일»(58a2 → 82f7) — 고쳐 둔 파일 가운데 공식 수정이 빠졌을 수 있다고 알릴 것.
   그 뒤 서버의 새 지시가 오면 서버 맞춤이 82f7(공식 옛 판)을 X 로 맞춘다(고쳐 둔 파일은 그대로).
 ★자료의 지금 판이 82f7 인 동안(이 파일을 만든 판)은 예전과 같은 값이다 — files·known 이 같고 updated 도 같다(검사가 대조한다)."""
 import politics_baseline_known as K
 expected=validate(c)
 if K.TARGET==NEW and K.FILES!=expected:raise ValueError('Baseline repair data does not match the contract')
 prefix=16
 official=set(K.KNOWN)|{h[:prefix] for p,h in K.FILES.items() if expected.get(p)!=h}
 wd=str(workdir).rstrip('/\\')
 return {'state':wd+'/'+K.STATE,'target':NEW,'version':1,'staged':wd+'/'+K.STAGED,
         'preserve':K.PRESERVE,'files':dict(expected),'known':sorted(official),'updated':sorted(c['changed'])}

def _state(workdir,c):
 try:
  with open(native(spec(workdir,c)['state']),encoding='utf-8') as fh:value=json.load(fh)
  return value if isinstance(value,dict) else None
 except (OSError,ValueError):
  return None

def ready(workdir,c):
 """맞춤이 끝났는가 — 계약의 판(82f7)으로 끝났거나, 그보다 **새 공식 판**(자료의 지금 판)으로 이미 끝났으면 끝난 것이다.
 ★2026-10-05 w3-E: 서버의 새 지시가 이미 새 판으로 맞춘 폴더에서 저장된 10-04 지시가 다시 돌아도 82f7 로 되돌리지 않는다
   (새 판 엔진은 그 지시의 실행 설정과 맞물린다 — 발사 함수 이름·인수가 같다)."""
 validate(c)
 if _pinned(workdir):return _pinned_ready(workdir,c)
 import politics_baseline_known as K
 state=_state(workdir,c)
 return bool(state) and state.get('target') in (NEW,K.TARGET) and state.get('complete') is True

def require_ready(workdir,c):
 if _pinned(workdir):
  if not _pinned_ready(workdir,c):raise RuntimeError('Baseline engine repair is incomplete; preserve existing work and finish the authenticated asset repair before production')
  return
 if not ready(workdir,c):
  why=str((_state(workdir,c) or {}).get('why') or '').strip()
  raise RuntimeError('엔진 준비가 끝나지 않아 제작을 시작하지 않았습니다'+(' — '+why if why else '')
                     +'. 같은 단계를 다시 실행하면 이어서 끝냅니다(작업물과 고쳐 두신 파일은 그대로입니다).')

def _say(result):
 """무엇을 그대로 뒀고 무엇을 옮겼는지 — 사람이 볼 화면(stderr)에 남긴다. 막지 않고 알린다."""
 lines=[]
 short=lambda name:name.split('/',1)[1] if name.startswith('politics/') else name
 if result.get('detached'):
  lines.append('  [정치 엔진] 다른 작업 폴더와 같이 쓰던(연결된) 엔진 폴더를 이 작업 폴더만의 복사본으로 바꾼 뒤 맞췄습니다: '
               +', '.join(result['detached'])+' — 공용 원본은 그대로입니다.')
 if result.get('kept'):
  lines.append('  [정치 엔진] 고쳐 두신 엔진 파일은 그대로 두고 제작합니다: '+', '.join(short(n) for n in result['kept']))
 if result.get('unpatched'):
  lines.append('  [정치 엔진] 이 가운데 '+', '.join(short(n) for n in result['unpatched'])
               +' 은(는) 이번에 공식 판도 바뀐 파일입니다 — 고쳐 두신 판을 그대로 쓰므로 공식 쪽 수정은 들어가 있지 않을 수 있습니다.')
 for row in result.get('replaced') or []:
  lines.append('  [정치 엔진] 새 실행 방식과 맞물려야 해서 공식 새 판으로 바꿨습니다: %s — 고쳐 두신 원래 파일은 작업 폴더의 %s 에 그대로 있습니다'
               %(short(row.get('path','')),row.get('backup','')))
 for line in lines:print(line,file=sys.stderr,flush=True)

def install(workdir,archive,c,*,after_replace=None):
 """공식 팩을 보관 폴더에 풀고 서버와 같은 판정으로 맞춘다. 못 끝내면 사람 말로 멈춘다(같은 명령을 다시 실행하면 이어서 한다).
 after_replace  예전 엄격 설치기의 시험용 칸 — 받기만 한다(맞춤 코드는 서버 스크립트와 같은 것이라 따로 끼어들 자리가 없다)."""
 expected=validate(c);root=native(workdir);archive=native(archive)
 if _pinned(workdir):raise ValueError('Pinned job requires an explicit authenticated pin transition')
 if archive.stat().st_size!=c['bytes'] or file_sha(archive)!=c['sha256']:raise ValueError('Baseline target archive mismatch')
 settings=spec(workdir,c)
 staged=native(settings['staged'])
 from volcano_drive import extract_pack
 with tarfile.open(archive) as packed:
  if sorted(m.name for m in packed.getmembers() if m.isfile())!=sorted(expected):raise ValueError('Unexpected baseline archive members')
  extract_pack(packed,str(staged))
 import politics_baseline_core as core
 result=core.baseline({'workdir':str(workdir),'root':str(workdir).rstrip('/\\')+'/politics','baseline_sync':settings})
 if not result.get('ok'):
  raise RuntimeError('정치 엔진을 아직 맞추지 못했습니다 — '+str(result.get('why') or '사유를 알 수 없습니다')
                     +'. 고쳐 두신 파일과 작업물은 그대로입니다.')
 _say(result)
 return result
