"""Read-only signed repair discovery. No controller resume or provider dispatch."""
import json
from pathlib import Path
import subprocess

_QUERY = r'''
import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';import {createHash} from 'node:crypto';
const [old,current,jobId,runId]=process.argv.slice(2);
const r=await import(pathToFileURL(path.join(current,'tools/lib/repair_release.mjs')));
const j=await import(pathToFileURL(path.join(current,'tools/lib/episode_jobs.mjs')));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const job=read(path.join(old,'work/_episode_jobs',jobId,'job.json'));
if(job.jobId!==jobId||job.runId!==runId)throw Error('Repair discovery job/run changed');
const saved=job.repairManifest??read(path.join(old,'work/_episode_jobs',jobId,'code_manifest.json'));
if(saved.version!==1||saved.codeIdentity!==job.codeIdentity||j.identityOf(saved.files)!==job.codeIdentity)throw Error('Repair discovery manifest changed');
const after=j.productionManifest(current),candidates=[];
for(const id of [r.REPAIR_RELEASE_ID,r.CONTENT_REPAIR_RELEASE_ID,r.NUMERIC_REPAIR_RELEASE_ID].filter(Boolean)){
 if((job.repairHistory||[]).some(h=>h.releaseId===id))continue;
 const name=r.repairReleaseFile(id),file=path.join(current,name);if(!fs.existsSync(file))continue;
 const raw=fs.readFileSync(file);
 try{const proof=r.verifyReleaseEnvelope(JSON.parse(raw.toString('utf8')),{releaseId:id,before:saved.files,after});
 candidates.push({releaseId:id,descriptorSha256:proof.descriptorSha256,envelopeSha256:createHash('sha256').update(raw).digest('hex')});
 }catch(error){if(error.code!=='REPAIR_RELEASE_INVALID')throw error;}
}
process.stdout.write(JSON.stringify({version:1,ok:true,jobId,runId,codeIdentity:job.codeIdentity,candidates,nativeCalls:0,providerCalls:0}));
'''


def discover(cfg, selected, node, child_env, timeout):
    """Pin selection/transaction recovery must complete before this function."""
    from repair_transition import path_for
    from info3d_engine_pin import _json
    wd=Path(cfg['workdir']).resolve();job=cfg['jobId'];txpath=path_for(wd,job)
    if txpath.exists() and _json(txpath).get('phase') in ('prepared','inflight'):
        raise ValueError('Previous repair admission is unresolved; no candidate was selected')
    current=wd/'.volcano-engines'/cfg['pack_revision']/'info3d'
    old=Path(selected['root']).resolve()
    if not old.is_relative_to(wd) or not current.resolve().is_relative_to(wd):raise ValueError('Repair discovery roots outside workspace')
    run=selected.get('runId') or cfg['runId']
    if not (current/'tools/lib/repair_release.mjs').is_file():
        return dict(version=1,ok=False,jobId=job,runId=run,packRevision=cfg['pack_revision'],
                    candidates=[],nativeCalls=0,providerCalls=0,
                    error={'code':'REPAIR_PACK_MISSING'})
    # Node's '-' reads source from stdin (https://nodejs.org/api/cli.html#-).
    # Windows Volta's shim can drop a multiline -e argument while returning 0.
    # Keep the source out of argv; argv[1] is now '-' on both Windows and macOS.
    result=subprocess.run([node,'--input-type=module','-',str(old),str(current),job,run],
        env=child_env,cwd=str(old),input=_QUERY,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        encoding='utf-8',errors='replace',timeout=timeout)
    if result.returncode:raise ValueError('Signed repair discovery could not verify local manifests; original job preserved')
    value=json.loads(result.stdout)
    allowed={'version','ok','jobId','runId','codeIdentity','candidates','nativeCalls','providerCalls'}
    if set(value)!=allowed or value['jobId']!=job or value['runId']!=run or value['nativeCalls']!=0 or value['providerCalls']!=0:
        raise ValueError('Invalid compact repair discovery result')
    return dict(value,packRevision=cfg['pack_revision'])
