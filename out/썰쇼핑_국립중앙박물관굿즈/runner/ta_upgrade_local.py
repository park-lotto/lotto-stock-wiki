"""Explicit TA code-only installation with immutable original receipts and crash journal.

The caller must obtain the transition from its authenticated server connection.
This module never starts production or retries any provider request.
"""
import contextlib,hashlib,json,ntpath,os,stat,tarfile,tempfile
from pathlib import Path

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def file_sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def native(path):
 value=os.fspath(path)
 if os.name=='nt':
  value=ntpath.abspath(value)
  if not value.startswith('\\\\?\\'):value='\\\\?\\UNC\\'+value[2:] if value.startswith('\\\\') else '\\\\?\\'+value
 return Path(value)
def safe(root,relative):
 parts=relative.split('/')
 if not parts or any(x in ('','.','..') or ':' in x or '\\' in x for x in parts):raise ValueError('Invalid managed path')
 path=root
 for part in parts:
  path=path/part
  try:info=path.lstat()
  except FileNotFoundError:continue
  if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):raise ValueError('Managed path link is forbidden')
 return path

def atomic(path,source):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.upgrade-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as out:
   if isinstance(source,bytes):out.write(source)
   else:
    with source.open('rb') as src:
     for block in iter(lambda:src.read(1024*1024),b''):out.write(block)
   out.flush();os.fsync(out.fileno())
  os.replace(tmp,path)
  if os.name!='nt':
   fd=os.open(path.parent,os.O_RDONLY)
   try:os.fsync(fd)
   finally:os.close(fd)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

@contextlib.contextmanager
def locked(path):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a+b') as f:
  f.seek(0,2)
  if f.tell()==0:f.write(b'0');f.flush();os.fsync(f.fileno())
  f.seek(0)
  if os.name=='nt':
   import msvcrt
   msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  else:
   import fcntl
   fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:
   f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def alive(pid):
 if type(pid) is not int or pid<=0:raise ValueError('Invalid prior process identity')
 if os.name=='nt':
  import ctypes
  from ctypes import wintypes
  k=ctypes.WinDLL('kernel32',use_last_error=True)
  k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
  k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
  k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
  handle=k.OpenProcess(0x100000,False,pid) # SYNCHRONIZE, no process mutation.
  if not handle:
   code=ctypes.get_last_error()
   if code==87:return False # ERROR_INVALID_PARAMETER: process no longer exists.
   raise OSError(code,'Cannot establish prior process state')
  try:
   result=k.WaitForSingleObject(handle,0)
   if result==0:return False
   if result==258:return True
   raise OSError('Cannot establish prior process state')
  finally:k.CloseHandle(handle)
 try:os.kill(pid,0);return True
 except ProcessLookupError:return False

def quiescent(root):
 work=safe(root,'politics/work')
 pid_file=safe(root,'politics/work/_volcano_run.pid')
 manifest=safe(root,'politics/work/_volcano_result.json')
 if pid_file.exists():
  pid=int(pid_file.read_text(encoding='utf-8').splitlines()[0])
  if alive(pid):raise RuntimeError('Prior production process is still running')
 elif manifest.exists():raise RuntimeError('Prior process identity is unknown; existing records preserved')
 # Repaired runs also record individual worker PIDs, including lost parent replies.
 launches=safe(root,'politics/work/_volcano_runs')
 if launches.exists():
  for folder in launches.iterdir():
   for name in ('launch.json','worker.json'):
    p=safe(root,folder.relative_to(root).as_posix()+'/'+name)
    if not p.exists():continue
    record=json.loads(p.read_bytes());pid=record.get('pid')
    if pid is not None and alive(pid):raise RuntimeError('Prior production process is still running')
    if pid is None and record.get('phase') in ('inflight','spawned'):raise RuntimeError('Prior launch acceptance is uncertain')

def install(workdir,archive,receipt,*,quiescent=quiescent,after_replace=None):
 root=native(workdir)
 info=root.lstat()
 if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):raise ValueError('Project link is forbidden')
 if digest(canonical({k:v for k,v in receipt.items() if k!='receipt_sha256'}))!=receipt.get('receipt_sha256'):raise ValueError('Transition receipt digest mismatch')
 identifier=receipt.get('upgrade_id','')
 if len(identifier)!=64 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid upgrade identity')
 original_path=safe(root,'.ta-job-receipt.json');original_raw=original_path.read_bytes();original=json.loads(original_raw)
 if any(original.get(k)!=receipt.get(k) for k in ('job_id','preset','account')) or original.get('receipt_sha256')!=receipt.get('old_receipt_sha256'):raise ValueError('Original job receipt mismatch')
 pin=receipt['pins']['pipeline'];archive=native(archive)
 if archive.stat().st_size!=pin['bytes'] or file_sha(archive)!=pin['sha256']:raise ValueError('Target pack mismatch')
 changes=receipt['files']['changed'];preserved=receipt['files']['preserved']
 if not changes or set(changes)&set(preserved):raise ValueError('Invalid managed file contract')
 for name,row in changes.items():
  if not name.startswith('politics/politics/') and name!=receipt.get('launcher',{}).get('path'):raise ValueError('Upgrade would change non-engine material')
  if not row.get('after'):raise ValueError('Upgrade cannot delete material')
 with locked(safe(root,'.ta-upgrade.lock')),locked(safe(root,'politics/work/_volcano_launch.lock')),locked(safe(root,'politics/work/_volcano_pipeline.lock')):
  quiescent(root)
  home=safe(root,'.ta-upgrades/'+identifier);home.mkdir(parents=True,exist_ok=True)
  journal=safe(root,'.ta-upgrade-journal.json');effective=safe(root,'.ta-effective-upgrade.json')
  if effective.exists():
   if json.loads(effective.read_bytes())!=receipt:raise ValueError('Another effective upgrade exists')
   for p,h in dict(preserved,**{p:r['after'] for p,r in changes.items()}).items():
    if file_sha(safe(root,p))!=h:raise ValueError('Installed upgraded code changed')
   return receipt
  existing=json.loads(journal.read_bytes()) if journal.exists() else None
  if existing is not None and existing!=receipt:raise ValueError('Another installation must be recovered first')
  for p,h in preserved.items():
   if file_sha(safe(root,p))!=h:raise ValueError('Preserved original changed: '+p)
  for p,row in changes.items():
   target=safe(root,p);actual=file_sha(target) if target.exists() else None
   allowed=(row['before'],row['after']) if existing else (row['before'],)
   if actual not in allowed:raise ValueError('Installed original changed: '+p)
  stage=safe(root,'.ta-upgrades/'+identifier+'/staged');stage.mkdir(parents=True,exist_ok=True)
  expected=dict(preserved,**{p:r['after'] for p,r in changes.items()});seen=set()
  with tarfile.open(archive,'r|gz') as packed:
   for member in packed:
    if member.isdir():safe(stage,member.name.rstrip('/'));continue
    if not member.isfile() or member.name not in expected or member.name in seen:raise ValueError('Unexpected target pack member')
    seen.add(member.name);target=safe(stage,member.name)
    if target.exists() and file_sha(target)==expected[member.name]:continue
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.stage-',dir=target.parent)
    with os.fdopen(fd,'wb') as dst,packed.extractfile(member) as src:
     for block in iter(lambda:src.read(1024*1024),b''):dst.write(block)
     dst.flush();os.fsync(dst.fileno())
    if file_sha(Path(tmp))!=expected[member.name]:raise ValueError('Target member digest mismatch')
    os.replace(tmp,target)
  if seen!=set(expected):raise ValueError('Target pack is incomplete')
  for p,row in changes.items():
   if row['before'] is None:continue
   backup=safe(home,'original/'+p)
   if backup.exists():
    if file_sha(backup)!=row['before']:raise ValueError('Original backup changed')
   elif existing:raise ValueError('Interrupted installation lacks original backup')
   else:
    atomic(backup,safe(root,p))
    if file_sha(backup)!=row['before']:raise ValueError('Original changed while preserving backup')
  old_receipt=safe(home,'original-job-receipt.json')
  if old_receipt.exists():
   if old_receipt.read_bytes()!=original_raw:raise ValueError('Original receipt backup changed')
  else:atomic(old_receipt,original_raw)
  if existing is None:atomic(journal,canonical(receipt))
  for i,(p,row) in enumerate(sorted(changes.items())):
   target=safe(root,p)
   if not target.exists() or file_sha(target)!=row['after']:atomic(target,safe(stage,p))
   if after_replace:after_replace(i)
  for p,h in expected.items():
   if file_sha(safe(root,p))!=h:raise ValueError('Installed material changed before commit')
  if original_path.read_bytes()!=original_raw:raise ValueError('Original receipt changed during installation')
  atomic(effective,canonical(receipt))
  return receipt

class UpgradeServiceRefused(RuntimeError):
 def __init__(self,status=None):
  self.status=status
  super().__init__('Service refusal'+(' (HTTP '+str(status)+')' if status is not None else '')+
                   '; all requests in this execution are stopped')

class Transport:
 """One-attempt same-origin authenticated requests; no redirect/retry fallback."""
 def __init__(self,endpoint,token,*,client=None):
  from urllib.parse import urlsplit
  self.origin=urlsplit(endpoint);self.token=token
  self.client=client;self.refused=False
  if self.origin.scheme!='https' or not self.origin.hostname or self.origin.path not in ('','/') or self.origin.username or self.origin.password or self.origin.query or self.origin.fragment:raise ValueError('Use the trusted bare HTTPS server origin')
  if not token or '\r' in token or '\n' in token:raise ValueError('Personal authentication is required')
 def _open(self,method,path,body=None):
  if self.refused or getattr(self.client,'_receipt_execution_refused',False):raise UpgradeServiceRefused()
  import http.client
  from urllib.parse import urlsplit
  parsed=urlsplit(path)
  if parsed.scheme or parsed.netloc or not path.startswith(('/ta-deploy/','/asset/')) or path.startswith('//'):raise ValueError('Unexpected authenticated path')
  conn=http.client.HTTPSConnection(self.origin.hostname,self.origin.port)
  try:
   conn.request(method,path,body=canonical(body) if body is not None else None,headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
   response=conn.getresponse()
   if response.status in (401,403,429):
    # Same refusal statuses as Client.step; keep installer, recovery GET and
    # failure feedback in the original execution's stop scope.
    self.refused=True
    if self.client is not None:self.client._receipt_execution_refused=True
    raise UpgradeServiceRefused(response.status)
   if response.status<200 or response.status>=300:raise RuntimeError('Server returned HTTP '+str(response.status)+'; no retry was sent')
   return conn,response
  except BaseException:conn.close();raise
 def request(self,method,path,body=None):
  conn,response=self._open(method,path,body)
  try:return json.loads(response.read())
  finally:conn.close()
 def download(self,plan,target):
  conn,response=self._open('GET',plan['url'])
  total=0;h=hashlib.sha256()
  try:
   with target.open('xb') as stream:
    while block:=response.read(1024*1024):
     total+=len(block)
     if total>plan['bytes']:raise ValueError('Downloaded pack exceeds authenticated size')
     stream.write(block);h.update(block)
    stream.flush();os.fsync(stream.fileno())
   if total!=plan['bytes'] or h.hexdigest()!=plan['sha256']:raise ValueError('Downloaded pack digest mismatch')
  finally:conn.close()

def upgrade(transport,workdir,target_manifest,*,approved=False):
 """Explicit operation only. Returns follow-up context; never starts production."""
 if approved is not True:raise ValueError('Explicit upgrade-preserving-work approval is required')
 import secrets
 root=native(workdir);original=json.loads(safe(root,'.ta-job-receipt.json').read_bytes())
 if len(target_manifest)!=64 or any(c not in '0123456789abcdef' for c in target_manifest):raise ValueError('Exact published target manifest required')
 request_path=safe(root,'.ta-upgrade-request.json')
 with locked(safe(root,'.ta-upgrade-request.lock')):
  body={'protocol':'pinned-upgrade-v1','action':'upgrade-preserving-work','job_id':original['job_id'],
        'old_receipt_sha256':original['receipt_sha256'],'target_manifest_sha256':target_manifest}
  if request_path.exists():
   saved=json.loads(request_path.read_bytes())
   if {k:v for k,v in saved.items() if k!='nonce'}!=body:raise ValueError('A different upgrade request is already preserved')
   body=saved
  else:
   body['nonce']=secrets.token_hex(32);atomic(request_path,canonical(body))
  receipt=transport.request('POST','/ta-deploy/job-upgrades',body)
  if receipt.get('request')!=body or receipt.get('job_id')!=original['job_id']:raise ValueError('Server upgrade response does not match explicit request')
  identifier=receipt.get('upgrade_id','')
  if not isinstance(identifier,str) or len(identifier)!=64 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid server upgrade identity')
  if digest(canonical({k:v for k,v in receipt.items() if k!='receipt_sha256'}))!=receipt.get('receipt_sha256'):raise ValueError('Invalid server transition receipt')
  home=safe(root,'.ta-upgrades/'+identifier);home.mkdir(parents=True,exist_ok=True)
  archive=safe(home,'target.tar.gz')
  pin=receipt['pins']['pipeline']
  if not archive.exists() or archive.stat().st_size!=pin['bytes'] or file_sha(archive)!=pin['sha256']:
   plan=transport.request('GET','/ta-deploy/job-upgrades/'+receipt['upgrade_id']+'/download')
   if any(plan.get(k)!=pin.get(k) for k in ('sha256','bytes')) or plan.get('upgrade_id')!=receipt['upgrade_id']:raise ValueError('Download plan differs from selected upgrade')
   fd,tmp=tempfile.mkstemp(prefix='.download-',dir=home);os.close(fd);os.unlink(tmp)
   transport.download(plan,Path(tmp))
   os.replace(tmp,archive)
  installed=install(root,archive,receipt)
  return {'ta_job_id':original['job_id'],'ta_upgrade_id':installed['upgrade_id'],
          'workdir':str(workdir),'resume':True,'next_step':'politics_run',
          'production_started':False}

def attach_context(payload,preset,client=None):
 """Restore only a completed local upgrade; server revalidates ownership/pins."""
 if preset not in ('가라사대 정치','우팔롬아 정치','정치롱') or not isinstance(payload,dict) or not payload.get('workdir'):return payload
 root=native(payload['workdir']);journal=safe(root,'.ta-upgrade-journal.json');effective=safe(root,'.ta-effective-upgrade.json')
 if not journal.exists() and not effective.exists():
  if payload.get('ta_upgrade_id') is not None:raise ValueError('Selected upgrade is not installed in this project')
  return payload
 if not journal.exists() or not effective.exists() or journal.read_bytes()!=effective.read_bytes():
  if client is None or not journal.exists():raise RuntimeError('Recover the interrupted code installation before continuing production')
  pending=json.loads(journal.read_bytes());original=json.loads(safe(root,'.ta-job-receipt.json').read_bytes())
  if digest(canonical({k:v for k,v in pending.items() if k!='receipt_sha256'}))!=pending.get('receipt_sha256'):raise ValueError('Interrupted upgrade receipt changed')
  if pending.get('preset')!=preset or any(original.get(k)!=pending.get(k) for k in ('job_id','preset','account')) or original.get('receipt_sha256')!=pending.get('old_receipt_sha256'):raise ValueError('Interrupted upgrade belongs to another job')
  request=json.loads(safe(root,'.ta-upgrade-request.json').read_bytes())
  if request!=pending.get('request'):raise ValueError('Interrupted upgrade lacks its exact authenticated request')
  if any(k in payload and payload[k]!=pending[v] for k,v in (('ta_job_id','job_id'),('ta_upgrade_id','upgrade_id'))):raise ValueError('Requested lineage conflicts with interrupted upgrade')
  upgrade(Transport(client.url,client.token,client=client),str(root),request['target_manifest_sha256'],approved=True)
  return attach_context(payload,preset)

 value=json.loads(effective.read_bytes());original=json.loads(safe(root,'.ta-job-receipt.json').read_bytes())
 if digest(canonical({k:v for k,v in value.items() if k!='receipt_sha256'}))!=value.get('receipt_sha256'):raise ValueError('Installed upgrade receipt changed')
 if value.get('preset')!=preset or any(original.get(k)!=value.get(k) for k in ('job_id','preset','account')) or original.get('receipt_sha256')!=value.get('old_receipt_sha256'):raise ValueError('Installed upgrade belongs to another original job')
 result=dict(payload)
 for key,value in (('ta_job_id',value['job_id']),('ta_upgrade_id',value['upgrade_id'])):
  if key in result and result[key]!=value:raise ValueError('Requested job lineage conflicts with installed upgrade')
  result[key]=value
 return result

def require_installed(workdir,expected):
 root=native(workdir);value=json.loads(safe(root,'.ta-effective-upgrade.json').read_bytes())
 attach_context({'workdir':str(workdir),'ta_job_id':value['job_id'],'ta_upgrade_id':expected['upgrade_id']},value['preset'])
 if any(value.get(k)!=expected.get(k) for k in ('upgrade_id','receipt_sha256')):raise ValueError('Installed upgrade does not match server admission')
 for p,h in dict(value['files']['preserved'],**{p:r['after'] for p,r in value['files']['changed'].items()}).items():
  if file_sha(safe(root,p))!=h:raise ValueError('Installed upgrade code changed')

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--key-file',help='Existing runner JSON credential file; defaults to this project')
 parser.add_argument('--server');parser.add_argument('--token-file',help='Optional explicit plain token file, paired with --server')
 parser.add_argument('--workdir',required=True);parser.add_argument('--target-manifest',required=True)
 parser.add_argument('--approve-preserving-work',action='store_true')
 a=parser.parse_args()
 if a.server or a.token_file:
  if not (a.server and a.token_file) or a.key_file:parser.error('--server/--token-file must be paired and cannot override --key-file')
  endpoint=a.server;token=native(a.token_file).read_text(encoding='utf-8').strip()
 else:
  from volcano_drive import load_runner_key
  key,why=load_runner_key(a.workdir,a.key_file)
  if not key:raise ValueError('작업 출입증을 읽지 못했습니다: '+str(why))
  endpoint=key['url'];token=key['token']
 result=upgrade(Transport(endpoint,token),a.workdir,a.target_manifest,approved=a.approve_preserving_work)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
