"""Scene hierarchy shared by validation, visibility and HTML composition."""
from longform_state import ProductionError


def chain(groups, gid):
    # Scene-local: groups <= 8 (validate_authored), so the list «in» and the per-call dict stay tiny.
    definitions = {g['id']: g for g in groups}
    result = []
    while gid is not None:
        if not isinstance(gid, str) or gid not in definitions or gid in result:
            raise ProductionError('graphic_group_hierarchy', '묶음 부모가 없거나 순환합니다.', action='edit_plan')
        result.append(gid)
        gid = definitions[gid].get('parent')
    return list(reversed(result))


def members(visual, gid):
    # objects <= 30 x chain depth <= 8 per call (validate_authored caps).
    groups = visual.get('groups', [])
    return [n for n in visual['objects'] if gid in chain(groups, n.get('group'))]


def validate_order(visual):
    groups = visual.get('groups', [])
    for group in groups:
        chain(groups, group['id'])
    active = []; closed = set(); used = set()
    for node in visual['objects']:
        wanted = chain(groups, node.get('group'))
        common = 0
        while common < min(len(active), len(wanted)) and active[common] == wanted[common]:
            common += 1
        closed.update(active[common:])
        if any(g in closed for g in wanted[common:]):
            raise ProductionError('graphic_group_hierarchy', '묶음 객체는 겹침 순서대로 연속 배치하세요.', action='edit_plan')
        used.update(wanted); active = wanted
    if used != {g['id'] for g in groups}:
        raise ProductionError('graphic_group_hierarchy', '빈 모션 묶음이 있습니다.', action='edit_plan')


def wrap(visual, markup, bounds):
    import html
    esc=lambda value:html.escape(str(value),quote=True)
    definitions={g['id']:g for g in visual['groups']};result=[];active=[]
    def close(gid):
        return '</div></div>' if definitions[gid].get('clip') in ('rounded','gear') else '</div>'
    for node,body in zip(visual['objects'],markup):
        wanted=chain(visual['groups'],node.get('group'));common=0
        while common<min(len(active),len(wanted)) and active[common]==wanted[common]:common+=1
        for gid in reversed(active[common:]):result.append(close(gid))
        for gid in wanted[common:]:
            group=definitions[gid];ox,oy=group.get('origin',[.5,.5]);gx,gy,gw,gh=bounds[gid]
            parent=group.get('parent');px,py=bounds[parent][:2] if parent else (0,0)
            result.append(f'<div id="obj-{esc(gid)}" class="scene-group" style="position:absolute;left:{gx-px}px;top:{gy-py}px;width:{gw}px;height:{gh}px;transform-origin:{ox*1920-gx}px {oy*1080-gy}px">')
            if group.get('clip')=='rounded':
                result.append(f'<div id="frame-{esc(gid)}" class="scene-frame" style="position:absolute;inset:0;overflow:hidden;border-radius:0%">')
            elif group.get('clip')=='gear':
                result.append(f'<div id="frame-{esc(gid)}" class="scene-frame" style="position:absolute;inset:0;clip-path:url(#gear-clip-{esc(gid)})">')
        active=wanted;result.append(body)
    for gid in reversed(active):result.append(close(gid))
    return result
