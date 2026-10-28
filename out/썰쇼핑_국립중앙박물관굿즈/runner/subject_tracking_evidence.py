"""Typed tracking evidence; new questions explicitly distinguish target identity.

No new tolerance or automatic approval. Legacy answers take the old path.
"""
from contextlib import nullcontext
import copy
import hashlib
import json
from pathlib import Path

CONTRACT = 'anchor-relations-v1'
INSTRUCTION = (
    '\n추적 계약 anchor-relations-v1: 연속한 두 sample에서 선택한 대상의 관계를 '
    'anchor_relations에 빠짐없이 답하라. 같은 위치/같은 종류라는 이유로 같은 대상이라고 추측하지 마라. '
    '실제 첨부와 문맥으로 동일한 개별 대상(그룹이면 구성원 모두)임을 확인한 경우에만 same_target, '
    '다른 대상이면 changed_target, 확인할 수 없으면 uncertain이다. 원래 decisions 및 '
    'refine_intervals도 그대로 답한다. 관계 JSON: "anchor_relations":['
    '{"left":0,"right":1,"relation":"same_target|changed_target|uncertain"}]. '
    'left/right는 원래 sample 번호이며 시간순 인접 쌍만 쓴다. 표본 하나면 빈 배열이다.'
)


def relations(answer, metadata):
    if not isinstance(answer,dict) or not isinstance(answer.get('anchor_relations'),list):
        return None
    ids=[m['sample'] for m in metadata]
    expected=set(zip(ids,ids[1:]));result={}
    for row in answer['anchor_relations']:
        if (not isinstance(row,dict) or set(row)!={'left','right','relation'}
                or type(row['left']) is not int or type(row['right']) is not int
                or row['relation'] not in ('same_target','changed_target','uncertain')):
            return None
        pair=(row['left'],row['right'])
        if pair not in expected or pair in result:return None
        result[pair]=row['relation']
    return result if set(result)==expected else None


def question_contract(F, config):
    """A new prompt is opt-in once, before its first request is published.

    Any old whole/split/client receipt, including unknown state, keeps the old
    question. The choice itself is durable before the new transport runs.
    """
    original=Path(config['out']);marker=Path(str(original)+'.question-contract.json')
    with F.R.review_receipt_lock(str(marker)):
        if marker.exists():
            try: saved=json.loads(marker.read_text(encoding='utf-8'))
            except (OSError,ValueError) as exc:raise F.R.StepError('선택 질문 계약 기록을 읽지 못했습니다. 기존 검수를 보존합니다.') from exc
            if (not isinstance(saved,dict) or set(saved)!={'version','contract','binding'}
                    or saved['version']!=1 or saved['binding']!=config['binding']
                    or saved['contract'] not in ('legacy',CONTRACT)):
                raise F.R.StepError('선택 질문 계약이 원래 질문과 다릅니다. 다시 보내지 않습니다.')
            chosen=saved['contract']
        else:
            ignored={marker,Path(str(marker)+'.lock')}
            prior=[p for p in original.parent.glob(original.name+'*') if p not in ignored]
            if any(p.name.startswith(original.name+'.'+CONTRACT+'.json') for p in prior):
                raise F.R.StepError('새 선택 질문 기록은 있지만 계약 선택 영수증이 없습니다. 기존 질문을 다시 발급하지 않습니다.')
            chosen='legacy' if prior else CONTRACT
            F.R._photo_write_state(str(marker),dict(version=1,contract=chosen,binding=config['binding']))
    if chosen=='legacy':return config,False
    marker_text='\nMeasured sample metadata: '
    prompt=(config['prompt'].replace(marker_text,INSTRUCTION+marker_text,1)
            if marker_text in config['prompt'] else INSTRUCTION+'\n'+config['prompt'])
    upgraded=dict(config,prompt=prompt,
                  binding=dict(config['binding'],tracking_relation_contract=CONTRACT),
                  out=str(original)+'.'+CONTRACT+'.json')
    return upgraded,True


def relation_frames(answer, indices):
    if not isinstance(answer,dict) or answer.get('_tracking_relation_contract') != CONTRACT:
        return set()
    rel=relations(answer,[dict(sample=n) for n in range(len(indices))])
    if rel is None:return set()
    return {i for (left,right),value in rel.items() if value!='same_target'
            for i in range(indices[left]+1,indices[right])}


def classify(indices, decisions, cuts, refine, answer):
    """Keep geometric disagreement distinct from a selected-target transition."""
    if not isinstance(answer,dict) or answer.get('_tracking_relation_contract') != CONTRACT:
        return []
    meta=[dict(sample=n) for n in range(len(indices))]
    rel=relations(answer,meta)
    if rel is None:return []
    result=[]
    for n,(left,right) in enumerate(zip(indices,indices[1:])):
        pending=sorted(set(range(left,right+1)) & refine)
        if not pending:continue
        relation=rel[(n,n+1)];before,after=decisions[n:n+2]
        reason=('scene_boundary' if any(left<c<=right for c in cuts) else
                'target_change' if relation=='changed_target' else
                'target_uncertain' if relation!='same_target' else
                'selection_kind_or_speaker_changed' if any(before.get(k)!=after.get(k) for k in ('kind','speaker')) else
                'coordinate_or_motion_uncertain')
        result.append(dict(left=left,right=right,left_sample=n,right_sample=n+1,
                           target_relation=relation,reason=reason,frames=pending))
    return result


def static_candidates(F, paths, issues):
    """Identical canonical PNG bytes prove equal pixels at EVERY frame.

    Reuse the source-bound hashes already observed during dense tracking. No
    second decode is needed for the normal complete object track. Comparing
    cached endpoint hashes first also avoids reading moving intervals again.
    """
    def digest(index):
        return paths.png_sha_at(index) if hasattr(paths,'png_sha_at') else F._sha(paths[index])
    eligible=[r for r in issues if r['reason']=='coordinate_or_motion_uncertain']
    result=[]
    with paths.tracking() if hasattr(paths,'tracking') else nullcontext():
        for issue in eligible:
            first=digest(issue['left'])
            if digest(issue['right']) != first:continue
            if all(digest(index)==first for index in range(issue['left']+1,issue['right'])):
                result.append(dict(issue,png_sha256=first))
    return result


def resolve_static(F, track, refine, decisions, candidates, *, objects_verified):
    """Preserve BOTH independently verified selected regions, never erase a target."""
    result=copy.deepcopy(track);pending=set(refine);proof=[]
    for issue in candidates:
        left,right=issue['left_sample'],issue['right_sample']
        a,b=decisions[left],decisions[right]
        if a.get('kind')!='object' or b.get('kind')!='object' or not objects_verified:
            continue
        required=F._union([a['bbox'],b['bbox']])
        # Missing tracks are a distinct problem. Static evidence cannot silently
        # overwrite unmeasured or structurally invalid input with a made-up track.
        rows=result[issue['left']:issue['right']+1]
        if any(row.get('bbox') is None for row in rows):continue
        for row in rows:row['bbox']=F._union([row['bbox'],required])
        pending.difference_update(issue['frames'])
        proof.append(dict(contract=CONTRACT,kind='identical_pixels_verified_same_target',
                          left=issue['left'],right=issue['right'],left_sample=left,right_sample=right,
                          original_boxes=[list(a['bbox']),list(b['bbox'])],required_box=required,
                          png_sha256=issue['png_sha256'],
                          pixels_checked=issue['right']-issue['left']+1))
    return result,pending,proof
