# -*- coding: utf-8 -*-
"""실험실 편집(편성·트림·늘려채우기)을 **라이브 잡의 edit_plan에 반영**한다 — 2026-08-15
사장님 "거기서 어떻게 되는지를 보고 판단해야해"(실제 렌더에 반영해 봐야 판단이 선다).

원리(retts.py와 같은 통로 — 새 방식 발명 없음):
    ① 브라우저(서버에 반영 버튼)가 payload를 로컬 서버(serve.py /apply)로 보낸다
    ② 이 파일이 SSH로 서버에 올려, **라이브와 같은 코드**(edit_plan.apply_scene_lab)로
       edit_plan에 얹는다 — 원본 primary/alternates는 안 건드린다(scene_override로 얹기만)
    ③ 다음 렌더(미리보기/완성)부터 그 편성이 그대로 나온다
되돌리기: py tools/scene_lab/apply.py <job_id> --revert   (얹은 것만 걷어냄 → 원래 편집안)

쓰는 법(보통은 실험실의 '서버에 반영' 버튼이 대신 부른다):
    py tools/scene_lab/apply.py <job_id> <payload.json>
    py tools/scene_lab/apply.py <job_id> --revert
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from fetch import HOST, OUT, REPO, _key, ssh  # noqa: E402  (같은 SSH 설정을 쓴다)

DB = f"{REPO}/shopping_shorts/data/reference.db"


def _py_on_server(code):
    """서버 venv 파이썬으로 실행 — 인라인 -c는 따옴표가 겹쳐 깨지므로(retts 실측)
    파일로 올려 돌린다."""
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "_sl_apply_code.py"
    tmp.write_text(code, encoding="utf-8")
    up = subprocess.run(["scp", "-q", "-i", _key(), str(tmp), HOST + ":/tmp/sl_apply_code.py"],
                        capture_output=True, text=True)
    if up.returncode != 0:
        sys.exit("[중단] 코드 업로드 실패: " + (up.stderr or "")[-200:])
    return ssh(f"cd {REPO} && sudo /home/ubuntu/venv/bin/python /tmp/sl_apply_code.py")


def apply(job_id, payload=None, revert=False):
    """payload = {"beats":[{"beat_idx","list","stretch"}...], "trims":{sid:[a,b]}}"""
    if not revert:
        if not payload or not isinstance(payload.get("beats"), list):
            sys.exit("[중단] payload에 beats가 없다")
        # 적용본을 로컬에도 남긴다(무엇을 보냈는지 근거 — 사장님 saved/*.json은 안 덮는다).
        rec = BASE / "saved" / f"{job_id}.apply.json"
        rec.parent.mkdir(exist_ok=True)
        rec.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        up = subprocess.run(["scp", "-q", "-i", _key(), str(rec),
                             HOST + f":/tmp/sl_apply_{job_id}.json"],
                            capture_output=True, text=True)
        if up.returncode != 0:
            sys.exit("[중단] payload 업로드 실패: " + (up.stderr or "")[-200:])

    action = "revert" if revert else "apply"
    code = f"""
import json, sys
sys.path.insert(0, '/home/ubuntu/lotto-stock-wiki')
from shopping_shorts import edit_plan as ep
from shopping_shorts.store import Store
store = Store('{DB}')
job = store.get_mix_job('{job_id}')
if not job: raise SystemExit('그런 job_id 없음')
if job.get('status') in ('rendering', 'removing_subtitles'):
    raise SystemExit('렌더 중에는 반영할 수 없다(상태: %s) — 끝난 뒤 다시' % job['status'])
plan = job.get('edit_plan')
if not plan: raise SystemExit('편집안이 아직 없다(상태: %s)' % job.get('status'))
if '{action}' == 'revert':
    ep.revert_scene_lab(plan)
    print('   되돌림: 실험실 편성 제거 — 원래 편집안으로')
else:
    edits = json.load(open('/tmp/sl_apply_{job_id}.json'))
    extract = job.get('extract') or {{}}
    seg_map, _ = ep._build_inventory(list(extract.values()))
    ep.apply_scene_lab(plan, seg_map, edits)
    n = plan.get('scene_lab', {{}}).get('applied', 0)
    print('   반영: 칸 %d개 편성 적용(scene_override) — 다음 렌더부터' % n)
store.update_mix_job('{job_id}', edit_plan=plan)
print('   저장 완료(edit_plan)')
"""
    print(f"[1/1] 서버 edit_plan에 {'되돌리기' if revert else '반영'} 중… ({job_id})")
    out = _py_on_server(code)
    print(out)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    jid = sys.argv[1]
    if sys.argv[2] == "--revert":
        apply(jid, revert=True)
    else:
        apply(jid, json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
