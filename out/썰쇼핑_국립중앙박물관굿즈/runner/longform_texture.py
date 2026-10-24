"""Authored, seek-safe texture holds on an inner bitmap, never the whole scene."""
import json
import math
from longform_state import ProductionError


def validate(node):
    spec = node['texture_cadence']
    def require(ok, message):
        if not ok:
            raise ProductionError('texture_cadence_invalid', message, action='edit_plan')
    require(node.get('kind') == 'image' and node.get('fit') == 'cover',
            '종이 무늬 교체는 cover 이미지에 지정하세요.')
    require(isinstance(spec, dict) and set(spec) == {'hold_seconds', 'start_seconds', 'states', 'reference'},
            '무늬 유지 시간·시작·상태·관찰 근거가 필요합니다.')
    for name in ('hold_seconds', 'start_seconds'):
        value = spec[name]
        require(type(value) in (int, float) and math.isfinite(value), '질감 시간은 유한수여야 합니다.')
    require(spec['hold_seconds'] >= 1 / 60 and spec['start_seconds'] >= 0, '질감 시간 범위 오류')
    require(isinstance(spec['reference'], str) and bool(spec['reference'].strip()), '질감 관찰 근거 누락')
    require(isinstance(spec['states'], list) and 2 <= len(spec['states']) <= 60, '질감 상태는 2~60개입니다.')
    for state in spec['states']:
        require(isinstance(state, dict) and set(state) == {'scaleX', 'scaleY', 'x', 'y', 'rotation'}, '질감 상태 형식 오류')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in state.values()), '질감 상태는 유한수여야 합니다.')
        require(all(1 <= abs(state[k]) <= 4 for k in ('scaleX', 'scaleY')), '질감 크기 범위 오류')


def motion(node, seconds):
    validate(node)
    spec = node['texture_cadence']; target = '#texture-obj-' + node['id']
    states = spec['states']; hold = spec['hold_seconds']; start = spec['start_seconds']
    # State zero is explicitly in the timeline so reverse seeks reset it too.
    events = [(0, states[0])]
    i = 0
    # Ends after < seconds/hold + 1 steps: hold >= 1/60 s is validated (longform_texture.validate).
    while start + i * hold < seconds:
        events.append((start + i * hold, states[(i + 1) % len(states)]))
        i += 1
    script = 'gsap.set(' + json.dumps(target) + ',' + json.dumps(states[0]) + ');'
    checks = []
    for index, (at, state) in enumerate(events):
        script += 'tl.set(' + json.dumps(target) + ',' + json.dumps(state) + ',' + repr(at) + ');'
        end = events[index + 1][0] if index + 1 < len(events) else seconds
        if end > at:
            checks.append(dict(target=target, start=at, end=max(at, end - 1 / 6000),
                               technique='texture_hold', expected_start=state, expected_end=state))
    return script, checks
