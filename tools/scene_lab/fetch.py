# -*- coding: utf-8 -*-
"""장면 실험실 — 서버 잡 하나를 로컬로 통째로 빼온다.

왜 필요한가: 제작소(라이브)는 유료게이트가 걸려 있어 로컬 페이지가 API를 직접 못 부른다
(실측 2026-08-13: /api/mix/segments → 401). 그래서 SSH로 데이터·썸네일·소스 mp4를 받아
완전 오프라인 자립 페이지로 만든다. 집·회사 어디서든 job_id만 알면 재현된다.

쓰는 법:
    py tools/scene_lab/fetch.py                 # 최신 잡 자동 선택
    py tools/scene_lab/fetch.py <job_id>        # 특정 잡
    py tools/scene_lab/fetch.py --list          # 최근 잡 목록만 보기

받은 것은 out/<job_id>/ 에 쌓이고(gitignore), 이어서 build.py가 index.html을 만든다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "out"

SSH_KEY = os.environ.get(
    "SCENE_LAB_KEY",
    r"C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem")
HOST = os.environ.get("SCENE_LAB_HOST", "ubuntu@43.200.48.69")
REPO = "/home/ubuntu/lotto-stock-wiki"
DB = f"{REPO}/shopping_shorts/data/reference.db"
JOBS = f"{REPO}/shopping_shorts/data/mix_jobs"


def _key():
    """git-bash/OpenSSH가 둘 다 먹는 경로로 정규화. 키가 없으면 즉시 알려준다."""
    p = Path(SSH_KEY)
    if not p.exists():
        sys.exit(f"[중단] SSH 키가 없다: {p}\n"
                 f"       다른 PC면 환경변수 SCENE_LAB_KEY로 키 경로를 지정해라.")
    return str(p)


def ssh(cmd, capture=True):
    full = ["ssh", "-o", "ConnectTimeout=15", "-i", _key(), HOST, cmd]
    r = subprocess.run(full, capture_output=capture, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        sys.exit(f"[중단] SSH 실패(exit {r.returncode})\n{(r.stderr or '')[-500:]}")
    return (r.stdout or "").strip()


def scp(remote, local):
    r = subprocess.run(["scp", "-q", "-i", _key(), f"{HOST}:{remote}", str(local)],
                       capture_output=True, text=True)
    return r.returncode == 0


def py_on_server(code):
    """서버 venv 파이썬으로 코드 실행(edit_plan 임포트가 필요해 venv여야 한다)."""
    esc = code.replace('"', r'\"')
    return ssh(f'cd {REPO} && sudo /home/ubuntu/venv/bin/python -c "{esc}"')


def list_jobs(n=8):
    out = ssh(f'''sudo python3 -c "
import sqlite3,json
c=sqlite3.connect('{DB}')
for j,s,u,cr in c.execute('select job_id,status,urls_json,created_at from mix_jobs order by created_at desc limit {n}'):
    print(j, s, cr[:19], len(json.loads(u)), '소스')
"''')
    return out


def fetch(job_id):
    work = OUT / job_id
    (work / "thumbs").mkdir(parents=True, exist_ok=True)
    (work / "src").mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 편집안·세그먼트 뽑는 중… ({job_id})")
    print(py_on_server(f"""
import json,sqlite3
from shopping_shorts import edit_plan as ep
c=sqlite3.connect('{DB}')
r=c.execute('select edit_plan_json,extract_json,urls_json,status from mix_jobs where job_id=?',('{job_id}',)).fetchone()
if not r: raise SystemExit('그런 job_id 없음')
if not r[0]: raise SystemExit('편집안이 아직 없다(상태: %s) — 제작소에서 완료된 뒤 다시 받아라' % r[3])
plan=json.loads(r[0]); extract=json.loads(r[1])
seg_map,_=ep._build_inventory(list(extract.values()))
out={{'job_id':'{job_id}','beats':plan['beats'],'urls':json.loads(r[2]),
     'segments':{{k:{{'video_id':v['video_id'],'start':v['start'],'end':v['end'],
                    'scene_desc':v.get('scene_desc',''),'text':v.get('text','')}} for k,v in seg_map.items()}}}}
open('/tmp/sl_data.json','w').write(json.dumps(out,ensure_ascii=False))
print('   세그먼트', len(seg_map), '/ 칸', len(plan['beats']))
"""))

    print("[2/4] 썸네일 뽑는 중…")
    print(py_on_server(f"""
import json,subprocess,glob,os,shutil
d=json.load(open('/tmp/sl_data.json'))
base='{JOBS}/{job_id}'
shutil.rmtree('/tmp/sl_thumbs', ignore_errors=True); os.makedirs('/tmp/sl_thumbs')
src={{}}
for vid in sorted(set(s['video_id'] for s in d['segments'].values())):
    g=glob.glob(base+'/'+vid+'/*.mp4')
    if g: src[vid]=g[0]
n=0
for sid,s in d['segments'].items():
    p=src.get(s['video_id'])
    if not p: continue
    mid=(s['start']+s['end'])/2
    o='/tmp/sl_thumbs/'+sid+'.jpg'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-ss',str(mid),'-i',p,
                    '-frames:v','1','-vf','scale=200:-1',o],check=False)
    if os.path.exists(o): n+=1
json.dump(src, open('/tmp/sl_src.json','w'))
print('   썸네일', n)
"""))

    print("[3/4] 내려받는 중…")
    if not scp("/tmp/sl_data.json", work / "data.json"):
        sys.exit("[중단] data.json 다운로드 실패")
    subprocess.run(["scp", "-q", "-i", _key(), f"{HOST}:/tmp/sl_thumbs/*.jpg",
                    str(work / "thumbs")], check=False)
    src_map = json.loads(ssh("cat /tmp/sl_src.json"))
    for vid, remote in src_map.items():
        scp(remote, work / "src" / f"{vid}.mp4")
    got = len(list((work / "src").glob("*.mp4")))
    print(f"   썸네일 {len(list((work / 'thumbs').glob('*.jpg')))}장 / 소스 {got}개")

    # faststart 리먹스: 브라우저가 구간 탐색(시크)을 하려면 moov가 앞에 있어야 한다.
    for mp4 in (work / "src").glob("*.mp4"):
        tmp = mp4.with_suffix(".fs.mp4")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4),
                            "-c", "copy", "-movflags", "+faststart", str(tmp)],
                           capture_output=True)
        if r.returncode == 0 and tmp.exists():
            mp4.unlink(); tmp.rename(mp4)

    print("[4/4] 페이지 만드는 중…")
    subprocess.run([sys.executable, str(BASE / "build.py"), str(work)], check=True)
    print(f"\n완료 → py tools/scene_lab/serve.py {job_id}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if args and args[0] == "--list":
        print(list_jobs()); sys.exit()
    if args:
        fetch(args[0])
    else:
        rows = list_jobs(1).splitlines()
        if not rows:
            sys.exit("잡이 없다")
        jid = rows[0].split()[0]
        print(f"최신 잡: {rows[0]}\n")
        fetch(jid)
