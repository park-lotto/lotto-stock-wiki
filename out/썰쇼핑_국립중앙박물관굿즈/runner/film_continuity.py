"""Pure source-time picture and camera planning; no decoding or paid operations.

Picture intervals are half open. Audio source_in/audio_in and output frame counts
are immutable here. Scene windows must already have been measured by the caller;
an unmeasured gap never establishes shot continuity.
"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math

_EPS = Fraction(1, 10**8)


def _number(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError, TypeError):
        raise ValueError(f"{label} must be a finite number") from None
    return result


def _rate(tl):
    fps = _number(tl["fps"], "fps")
    if fps <= 0:
        raise ValueError("fps must be positive")
    return fps


def _frames(clip):
    frames = clip["frames"]
    if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
        raise ValueError("Each clip must have a positive integer frame count")
    return frames


def resolve_picture_intervals(tl, source_duration):
    """Copy timeline onto one absolute output-frame grid; preserve all audio.

    D picture starts round to the nearest global frame (at most half a frame of
    visual shift). N pictures first round identically, then fit backward using
    integer frames. Output lengths never change. Only complete source frame
    intervals are available; the final partial frame is not extended or frozen.
    An authored nonblank intentional_jumpback_reason starts a separate sequence.
    """
    result = deepcopy(tl)
    fps = _rate(result)
    limit = _number(source_duration, "source duration")
    if limit <= 0:
        raise ValueError("Source duration must be positive")
    capacity = (limit * fps + _EPS).__floor__()
    clips = result["clips"]
    indices = [c["index"] for c in clips]
    if len(set(indices)) != len(indices):
        raise ValueError("Clip indices must be unique")
    segments = [[]]
    for c in clips:
        reason = c.get("intentional_jumpback_reason")
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError(f"Clip {c['index']}: intentional_jumpback_reason needs an authored explanation")
        if reason and segments[-1]:
            segments.append([])
        if c["kind"] not in ("N", "D"):
            raise ValueError(f"Clip {c['index']}: unsupported kind")
        requested = _number(c["source_in"], "source_in")
        count = _frames(c)
        if requested < 0 or requested >= limit:
            raise ValueError(f"Clip {c['index']}: source_in is outside the source")
        segments[-1].append((c, requested, math.floor(requested * fps + Fraction(1, 2) + Fraction(1, 100000000)), count))
    adjustments = []
    for segment in segments:
        upper = capacity
        for c, requested, quantized, count in reversed(segment):
            start = min(quantized, upper - count) if c["kind"] == "N" else quantized
            if start < 0 or start + count > upper:
                raise ValueError(
                    f"Clip {c['index']}: cannot fit {count} frames "
                    f"({float(Fraction(count, 1) / fps):.6f}s) of picture before source "
                    f"frame {upper} ({float(Fraction(upper, 1) / fps):.6f}s) without "
                    "replaying an earlier interval. Choose an earlier narration source "
                    "with enough space or revise the selected dialogue/story; audio will "
                    "not be trimmed or frozen. For an intentional flashback, author "
                    "intentional_jumpback_reason on its first clip.")
            picture_in = Fraction(start, 1) / fps
            picture_out = Fraction(start + count, 1) / fps
            c.update(source_frame_in=start, source_frame_out=start + count,
                     picture_in=float(picture_in), picture_out=float(picture_out))
            quantization = Fraction(quantized, 1) / fps - requested
            if quantization or start != quantized:
                adjustments.append({"clip_index": c["index"], "requested_in": float(requested),
                                    "quantized_frame_in": quantized,
                                    "source_frame_in": start, "source_frame_out": start + count,
                                    "quantization_seconds": float(quantization),
                                    "backfit_frames": quantized - start,
                                    "picture_in": float(picture_in), "picture_out": float(picture_out),
                                    "shift_seconds": float(picture_in - requested),
                                    "reason": ("fit_narration_before_next_selected_picture_or_source_end"
                                               if start != quantized else "global_source_frame_quantization")})
            upper = start
    result["picture_adjustments"] = sorted(adjustments, key=lambda a: indices.index(a["clip_index"]))
    return result


def _picture_start(clip, fps):
    """Use exact canonical frame identity; tolerate old second-only fragments."""
    if "source_frame_in" not in clip:
        return _number(clip["picture_in"], "picture_in")
    start, end = clip["source_frame_in"], clip.get("source_frame_out")
    if (isinstance(start, bool) or not isinstance(start, int) or start < 0
            or isinstance(end, bool) or not isinstance(end, int)
            or end != start + _frames(clip)):
        raise ValueError("Canonical source frame interval must match the clip frame count")
    seconds = Fraction(start, 1) / fps
    if abs(seconds - _number(clip["picture_in"], "picture_in")) > _EPS:
        raise ValueError("picture_in differs from the canonical source frame grid")
    return seconds


def build_source_shots(windows, cuts, source_duration):
    """Return canonical shots from measured absolute windows and absolute cuts.

    windows=[[start,end],...], cuts=[source_seconds,...]. Only overlapping or
    touching measured windows merge. A real shot keeps its identity when the
    surrounding measurement handles change. Truncated edges remain explicit.
    """
    limit = _number(source_duration, "source duration")
    ranges = []
    for pair in windows:
        if len(pair) != 2:
            raise ValueError("A measured window needs [start, end]")
        a, b = (_number(v, "window boundary") for v in pair)
        if a < 0 or b <= a or b > limit + _EPS:
            raise ValueError("Measured window is outside the source or empty")
        ranges.append((a, min(b, limit)))
    merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    boundaries = sorted(set(_number(c, "cut") for c in cuts))
    if any(not any(a <= c <= b for a, b in merged) for c in boundaries):
        raise ValueError("A source cut lies outside all measured windows")
    shots = []
    for a, b in merged:
        points = [a] + [c for c in boundaries if a < c < b] + [b]
        for left, right in zip(points, points[1:]):
            start_is_cut, end_is_cut = left in boundaries, right in boundaries
            identity = json.dumps([str(left), str(right), start_is_cut, end_is_cut], separators=(",", ":"))
            shots.append({"id": "shot-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                          "source_in": float(left), "source_out": float(right),
                          "window_in": float(a), "window_out": float(b),
                          "start_is_cut": start_is_cut, "end_is_cut": end_is_cut})
    return shots


#: 나레이션 그림이 이웃 컷과 이만큼(초) 이내로 떨어져 있으면 그 사이도 측정한다 — 엔진이 틈을 닫으려면(bridge_narration_gaps)
#:   옮겨 갈 자리가 측정돼 있어야 한다. 실물 162프레임(5.4초) 틈은 앞뒤 2초 여유만으로 가운데 1.4초가 비었다.
#:   공식 숫자가 아니라 이 엔진의 측정 비용 상한이다(이웃 사이 한 번 · 컷 수만큼 · 전체를 다시 훑지 않는다).
NARRATION_BRIDGE_MEASURE_SECONDS = 10


def picture_measure_intervals(clips):
    """측정할 그림 구간 — 컷마다 자기 구간 + N 컷은 같은 차례의 이웃까지 틈(상한 안)을 붙인다(한 번 훑기)."""
    out = []
    for i, c in enumerate(clips):
        a, b = c['picture_in'], c['picture_out']
        if c.get('kind') == 'N':
            if i and not c.get('intentional_jumpback_reason'):
                gap = a - clips[i - 1]['picture_out']
                if 0 < gap <= NARRATION_BRIDGE_MEASURE_SECONDS:
                    a = clips[i - 1]['picture_out']
            if i + 1 < len(clips) and not clips[i + 1].get('intentional_jumpback_reason'):
                gap = clips[i + 1]['picture_in'] - b
                if 0 < gap <= NARRATION_BRIDGE_MEASURE_SECONDS:
                    b = clips[i + 1]['picture_in']
        out.append((a, b))
    return out


def measurement_windows(intervals, fps, duration, handles):
    """Expand onto the source frame grid, then measure every intervening frame.

    Overlapping handles may connect clips, but an unmeasured gap never does.
    The final partial source frame cannot be promised as a complete frame.
    """
    rate = _number(fps, 'fps')
    limit = math.floor(_number(duration, 'duration') * rate + _EPS)
    padding = math.ceil(_number(handles, 'handles') * rate)
    if rate <= 0 or limit <= 0 or padding < 0:
        raise ValueError('Invalid source measurement limits')
    ranges = []
    for a, b in intervals:
        a, b = _number(a, 'start'), _number(b, 'end')
        if a < 0 or b <= a:
            raise ValueError('Invalid selected source interval')
        left = max(0, math.floor(a * rate + _EPS) - padding)
        right = min(limit, math.ceil(b * rate - _EPS) + padding)
        if right <= left:
            raise ValueError('Selected source interval is outside the source')
        ranges.append((left, right))
    merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1])
        else:
            merged.append([a, b])
    return [[float(Fraction(a, 1) / rate), float(Fraction(b, 1) / rate)] for a, b in merged]


def boundary_issues(tl, shots, min_frames):
    """Distinguish partial shot stubs from genuinely short complete source shots."""
    fps = _rate(tl)
    fragments = build_picture_fragments(tl, shots)
    by_id = {s['id']: s for s in shots}
    issues = []
    for c in tl['clips']:
        parts = fragments[str(c['index'])]
        # A short clip entirely inside a long shot is also a partial shot.
        for edge, part in [('leading', parts[0]), ('trailing', parts[-1])]:
            count = part['end'] - part['start']
            if count > min_frames:
                continue
            # Caption/utterance splits inside a continuous shot do not create
            # a short visual shot. Measure its whole contiguous output run.
            pos = tl['clips'].index(c)
            displayed = count
            for direction in (-1,1):
                current, current_part, at = c, part, pos
                while 0 <= at+direction < len(tl['clips']):
                    if direction<0 and current_part['start']!=0 or direction>0 and current_part['end']!=current['frames']:
                        break
                    other=tl['clips'][at+direction]
                    other_part=fragments[str(other['index'])][-1 if direction<0 else 0]
                    contiguous=(other['source_frame_out']==current['source_frame_in'] if direction<0
                                else current['source_frame_out']==other['source_frame_in'])
                    if abs(other['index']-current['index'])!=1 or not contiguous or other_part['shot_id']!=part['shot_id']:
                        break
                    displayed+=other_part['end']-other_part['start']
                    current,current_part,at=other,other_part,at+direction
            if displayed>min_frames:
                continue
            shot = by_id[part['shot_id']]
            left = math.ceil(_number(shot['source_in'], 'shot') * fps - _EPS)
            right = math.ceil(_number(shot['source_out'], 'shot') * fps - _EPS)
            start = c['source_frame_in'] + part['start']
            end = c['source_frame_in'] + part['end']
            complete = (start == left and end == right and
                        shot.get('start_is_cut') and shot.get('end_is_cut'))
            if complete:
                continue
            issues.append({'clip_index': c['index'], 'kind': c['kind'], 'edge': edge,
                           'frames': count, 'source_in': float(Fraction(start, 1) / fps),
                           'source_out': float(Fraction(end, 1) / fps),
                           'shot_id': part['shot_id'], 'shot_source_in': shot['source_in'],
                           'shot_source_out': shot['source_out']})
    return issues


def clean_narration_boundaries(tl, shots, *, min_frames, max_shift_frames):
    """Select a clean continuous N picture interval; never freeze or retime voice.

    All candidates stay inside measured footage and between neighboring clips.
    Complete short original shots survive. Unresolved dialogue is reported for
    source/word-aware planning, never silently masked with cloned frames.
    """
    result = deepcopy(tl)
    fps = _rate(result)
    adjustments = []
    for pos, c in enumerate(result['clips']):
        if c['kind'] != 'N' or not any(i['clip_index'] == c['index'] for i in boundary_issues(result, shots, min_frames)):
            continue
        original = c['source_frame_in']
        count = c['frames']
        lower, upper = original - max_shift_frames, original + max_shift_frames
        if pos and not c.get('intentional_jumpback_reason'):
            lower = max(lower, result['clips'][pos-1]['source_frame_out'])
        if pos + 1 < len(result['clips']) and not result['clips'][pos+1].get('intentional_jumpback_reason'):
            upper = min(upper, result['clips'][pos+1]['source_frame_in'] - count)
        # Two seconds of candidates is at most 121 intervals at the delivery fps.
        for start in sorted(range(max(0, lower), upper+1), key=lambda n:(abs(n-original), n)):
            candidate = deepcopy(result)
            changed = candidate['clips'][pos]
            changed.update(source_frame_in=start, source_frame_out=start+count,
                           picture_in=float(Fraction(start, 1)/fps),
                           picture_out=float(Fraction(start+count, 1)/fps))
            try:
                issues = boundary_issues(candidate, shots, min_frames)
            except ValueError:  # Unmeasured outside handles is not a valid choice.
                continue
            if any(i['clip_index'] == c['index'] for i in issues):
                continue
            result = candidate
            adjustments.append({'clip_index':c['index'], 'from_frame':original,
                                'to_frame':start, 'frames':count, 'audio_changed':False,
                                'reason':'continuous_picture_window_without_partial_edge_shots'})
            break
    result['boundary_audit'] = {'version':1, 'minimum_partial_shot_frames':min_frames,
                               'adjustments':adjustments, 'issues':boundary_issues(result, shots, min_frames)}
    return result


def bridge_narration_gaps(tl, shots, adjustments):
    """같은 원본 장면 안에서 나레이션(N) 그림이 이웃 컷과 떨어져 생긴 틈을 엔진이 닫는다 (2026-10-10).

    ■ 왜 — 반려가 아니라 엔진이 해야 할 일이다
        N 그림의 길이는 TTS 길이(프레임)로 정해지고 시작은 저자가 고른 초를 프레임으로 반올림한다. 그래서 같은 장면의
        이웃 컷과 1~3프레임(실물: 2·1·3프레임, 큰 것은 162프레임) 떨어진 채 남았고, 엔진은 이를 «same_shot_source_gap»
        으로 돌려보냈다. 호스트는 초 단위 편집으로 프레임 틈을 맞히지 못해 실물 1명이 5시간 1,417회를 돌았다.
        N 그림은 소리와 묶여 있지 않으므로(목소리는 TTS) 같은 장면 안에서 붙여 놓아도 말·자막·길이가 바뀌지 않는다.
    ■ 방법 — 틈마다 **한 번**: 오른쪽이 N 이면 그 시작을 왼쪽 끝으로 당기고, 아니면 왼쪽 N 의 끝을 오른쪽 시작에 붙인다.
        옮긴 그림이 ① 측정된 같은 장면 하나 안에 있고 ② 반대쪽 이웃과의 순서를 넘지 않고 ③ 반대쪽 이웃과 같은 장면이면
        새 틈을 만들지 않을 때만 옮긴다. 조건에 맞지 않으면 그대로 두고 예전처럼 보고한다(지어내지 않는다).
        검사는 그 클립 하나·이웃 하나만 본다 — 틈마다 타임라인 전체를 다시 훑지 않는다(제곱 계산 금지).
    """
    result = deepcopy(tl)
    clips = result['clips']
    fps = _rate(result)
    at = {c['index']: i for i, c in enumerate(clips)}

    def one_shot(c, start):
        test = dict(c, source_frame_in=start, source_frame_out=start + c['frames'],
                    picture_in=float(Fraction(start, 1) / fps), picture_out=float(Fraction(start + c['frames'], 1) / fps))
        try:
            parts = build_picture_fragments({'fps': result['fps'], 'clips': [test]}, shots)[str(c['index'])]
        except ValueError:
            return None
        return parts[0]['shot_id'] if len(parts) == 1 else None

    def place(c, start):
        c.update(source_frame_in=start, source_frame_out=start + c['frames'],
                 picture_in=float(Fraction(start, 1) / fps), picture_out=float(Fraction(start + c['frames'], 1) / fps))

    def linked(a, b):
        """a 바로 뒤 b 가 같은 장면에서 틈 없이 이어져 있는가(옮기면 이 이음을 깨뜨린다)."""
        return (b['index'] - a['index'] == 1 and not b.get('intentional_jumpback_reason')
                and a['source_frame_out'] == b['source_frame_in']
                and one_shot(a, a['source_frame_in']) == one_shot(b, b['source_frame_in']) is not None)

    for gap in same_shot_gaps(result, shots):
        pos = at[gap['clip_index']]
        left, right = clips[pos], clips[pos + 1]
        if left['source_frame_out'] >= right['source_frame_in']:
            continue
        shot = one_shot(left, left['source_frame_in'])
        # 오른쪽 N 을 왼쪽 끝으로 당기거나, 왼쪽 N 을 오른쪽 시작에 붙인다 — 옮기는 클립의 반대쪽 이웃 이음은 지킨다.
        tries = []
        if right['kind'] == 'N':
            nxt = clips[pos + 2] if pos + 2 < len(clips) else None
            tries.append((right, left['source_frame_out'], None if nxt is None else (right, nxt)))
        if left['kind'] == 'N':
            prev = clips[pos - 1] if pos else None
            tries.append((left, right['source_frame_in'] - left['frames'], None if prev is None else (prev, left)))
        for c, start, keep in tries:
            if start < 0 or one_shot(c, start) != shot or (keep and linked(*keep)):
                continue
            old = c['source_frame_in']
            place(c, start)
            adjustments.append({'clip_index': c['index'], 'from_frame': old, 'to_frame': start, 'frames': c['frames'],
                                'audio_changed': False, 'reason': 'bridge_narration_same_shot_gap'})
            break
    return result


def same_shot_gaps(tl, shots, *, include_audio=False):
    parts = build_picture_fragments(tl, shots)
    result = []
    for left, right in zip(tl['clips'], tl['clips'][1:]):
        if right['index'] != left['index'] + 1 or right.get('intentional_jumpback_reason'):
            continue
        a, b = left['source_frame_out'], right['source_frame_in']
        audio_delta=left['source_in']+left['frames']/float(_rate(tl))-right['source_in']
        audio_mismatch=(include_audio and b==a and left['kind']==right['kind']=='D' and abs(audio_delta)>1e-8)
        if (b > a or audio_mismatch) and parts[str(left['index'])][-1]['shot_id'] == parts[str(right['index'])][0]['shot_id']:
            result.append({'clip_index':left['index'], 'next_clip_index':right['index'],
                           'reason':'same_shot_audio_clock' if audio_mismatch else 'same_shot_source_gap', 'from_frame':a, 'to_frame':b,
                           'frames':b-a})
    return result


def picture_timeline(tl):
    """The visual track can use J/L cuts while speech/captions keep their clocks."""
    return {**tl,'clips':tl.get('picture_clips',tl['clips'])}


def plan_picture_transitions(tl, shots, *, max_partial_frames):
    """Replace a partial edge with REAL adjacent-shot pre/post-roll.

    A leading stub may show the previous shot's measured post-roll while the
    incoming dialogue begins; a trailing stub may show the next shot's pre-roll
    while outgoing dialogue finishes. The neighboring picture then continues
    at the exact next source frame. No freeze, repeat, stretch or audio change.
    Preview must review the changed visual meaning before a full render.
    """
    result=deepcopy(tl);fps=float(_rate(tl));changes=[]
    units=deepcopy(tl.get('picture_clips',tl['clips']))
    for c in units:c.setdefault('origin_index',c['index'])

    def stamped(values):
        cursor=0;out=[]
        for index,c in enumerate(values):
            if not c['frames']:continue
            c=deepcopy(c);c.update(index=len(out),timeline_in=cursor/fps,
                timeline_out=(cursor+c['frames'])/fps,duration=c['frames']/fps)
            cursor+=c['frames'];out.append(c)
        return {**tl,'clips':out}

    def piece(c,start,count):
        out=deepcopy(c)
        out.update(source_in=start/fps,source_frame_in=start,source_frame_out=start+count,
                   picture_in=start/fps,picture_out=(start+count)/fps,frames=count)
        return out

    visual=stamped(units)
    for _ in range(2*len(units)):
        issues=boundary_issues(visual,shots,max_partial_frames)
        before_count=len(issues)+len(same_shot_gaps(visual,shots))
        changed=False
        fragments=build_picture_fragments(visual,shots)
        for issue in issues:
            pos=issue['clip_index'];c=visual['clips'][pos];leading=issue['edge']=='leading'
            near=pos-1 if leading else pos+1
            if not 0<=near<len(visual['clips']):continue
            other=visual['clips'][near]
            if c.get('intentional_jumpback_reason') or other.get('intentional_jumpback_reason'):continue
            part=fragments[str(c['index'])][0 if leading else -1]
            neighbor=fragments[str(other['index'])][-1 if leading else 0]
            # Moving to a different time within the SAME physical shot would
            # merely relocate the motion jump. That needs continuous selection.
            if part['shot_id']==neighbor['shot_id']:continue
            count=part['end']-part['start']
            start=other['source_frame_out'] if leading else other['source_frame_in']-count
            if start<0:continue
            borrowed=piece(c,start,count)
            try:
                evidence=build_picture_fragments({'fps':fps,'clips':[borrowed]},shots)[str(c['index'])]
            except ValueError:continue
            if len(evidence)!=1 or evidence[0]['shot_id']!=neighbor['shot_id']:continue
            kept=piece(c,c['source_frame_in']+count if leading else c['source_frame_in'],c['frames']-count)
            replacements=[borrowed,kept] if leading else [kept,borrowed]
            candidate=stamped(visual['clips'][:pos]+replacements+visual['clips'][pos+1:])
            remaining=boundary_issues(candidate,shots,max_partial_frames)
            if len(remaining)+len(same_shot_gaps(candidate,shots))>=before_count:continue
            changes.append({'origin_index':c['origin_index'],'edge':issue['edge'],'frames':count,
                            'borrowed_source_frames':[start,start+count],
                            'neighbor_origin_index':other['origin_index'],
                            'source_shot_id':neighbor['shot_id'],'audio_changed':False,
                            'method':'previous_shot_postroll' if leading else 'next_shot_preroll'})
            visual=candidate;changed=True;break
        if not changed:break
    result['picture_clips']=visual['clips']
    result['picture_transitions']=changes
    result['picture_boundary_issues']=boundary_issues(visual,shots,max_partial_frames)+same_shot_gaps(visual,shots)
    return result


def clean_dialogue_boundaries(tl, shots, *, words, coverage, min_frames, max_shift_frames):
    """Before TTS, jointly trim/extend D picture and audio on measured boundaries.

    No selected word/caption may be cut; no unselected word may be added. A lack
    of words is usable only inside verified transcription coverage. If no safe
    automatic choice exists, return all issues for one source-selection pass.
    """
    from film_word_audio import missing_ranges
    result = deepcopy(tl)
    fps = float(_rate(result))
    originals = {c['index']:deepcopy(c) for c in tl['clips']}
    adjustments = []

    def selected_end(c):
        rendered = c['source_in'] + c['frames']/fps
        authored = c.get('authored_source_out', rendered)
        # Only recover the subframe remainder of the actual authored interval.
        # An arbitrary caller-supplied handle is never permission to add speech.
        return max(rendered, authored) if abs(authored-rendered)<=.5/fps+1e-8 else rendered

    def adds_unselected_speech(ranges, selected):
        allowed = sorted((c['source_in'], selected_end(c)) for c in selected)
        for a,b in ranges:
            for word in words:
                cursor, end = max(a,word['start']), min(b,word['end'])
                if cursor>=end-1e-8:continue
                for left,right in allowed:
                    if left>cursor+1e-8:break
                    if right>cursor:cursor=right
                    if cursor>=end-1e-8:break
                if cursor<end-1e-8:return True
        return False

    def safe(c, start, end):
        original = originals[c['index']]
        a, b = original['source_frame_in'], original['source_frame_out']
        if start < 0 or end <= start or max(abs(a-start),abs(b-end)) > max_shift_frames:
            return False
        # Audio keeps its original subframe offset. Check audio, not just picture.
        oa = original['source_in']; ob = oa + original['frames']/fps
        na = oa + (start-a)/fps; nb = na+(end-start)/fps
        changed = [[min(oa,na),max(oa,na)], [min(ob,nb),max(ob,nb)]]
        if missing_ranges([pair for pair in changed if pair[1]>pair[0]], coverage):
            return False
        if adds_unselected_speech([(na,oa),(ob,nb)], [original]):
            return False
        for word in words:
            wa, wb = word['start'], word['end']
            # A partly audible previous/next word is not permission to add the
            # rest of that utterance. Only measured speech-free handles extend.
            selected = wb > oa+1e-8 and wa < selected_end(original)-1e-8
            included = wb > na+1e-8 and wa < nb-1e-8
            if selected and (na > max(oa,wa)+1e-8 or nb < min(selected_end(original),wb)-1e-8):
                return False
            if included and not selected:
                return False
        for ca, cb, _ in original.get('captions', []):
            if na > oa+ca+1e-8 or nb < oa+cb-1e-8:
                return False
        try:
            test = deepcopy(c)
            test.update(source_frame_in=start,source_frame_out=end,frames=end-start,
                        picture_in=start/fps,picture_out=end/fps)
            build_picture_fragments({'fps':fps,'clips':[test]},shots)
        except ValueError:
            return False
        return True

    def move(c, start, end, reason):
        original = originals[c['index']]
        shift = (start-original['source_frame_in'])/fps
        c.update(source_frame_in=start,source_frame_out=end,frames=end-start,
                 source_in=original['source_in']+shift,picture_in=start/fps,picture_out=end/fps,
                 duration=(end-start)/fps,
                 captions=[[a-shift,b-shift,text] for a,b,text in original.get('captions',[])])
        adjustments.append({'clip_index':c['index'],'from_frames':[
            original['source_frame_in'],original['source_frame_out']], 'to_frames':[start,end],
            'reason':reason, 'audio_and_picture_changed_together':True})

    # Bridging a proven same-shot gap removes the actual motion discontinuity.
    for gap in same_shot_gaps(result,shots,include_audio=True):
        c = next(c for c in result['clips'] if c['index']==gap['clip_index'])
        other = next(c for c in result['clips'] if c['index']==gap['next_clip_index'])
        # Distinct subframe audio offsets cannot be bridged by extending picture
        # frame count: that would repeat/drop audio samples at the join. Such
        # cases need one continuous authored source selection, not a fake pass.
        same_audio_grid=abs((c['source_in']-c['source_frame_in']/fps)-
                            (other['source_in']-other['source_frame_in']/fps))<1e-8
        if c['kind']=='D' and other['kind']=='D' and same_audio_grid and safe(c,c['source_frame_in'],other['source_frame_in']):
            move(c,c['source_frame_in'],other['source_frame_in'],'bridge_measured_same_shot_gap')
        elif c['kind']=='D' and other['kind']=='D' and gap['frames']<=max_shift_frames:
            # Reconcile BOTH clips onto one audio sample clock. Checking only
            # the left clip would reject a word whose first milliseconds move
            # across the join, or duplicate it. Validate the continuous union.
            oa,ob=c['source_in'],c['source_in']+c['frames']/fps
            ra,rb=other['source_in'],other['source_in']+other['frames']/fps
            join=oa+(other['source_frame_in']-c['source_frame_in'])/fps
            for count in (other['frames'],other['frames']+1,other['frames']-1):
                if count<1:continue
                end=join+count/fps
                if missing_ranges([[oa,end]],coverage):
                    continue
                added=[(a,b) for a,b in ((ob,ra),(rb,end)) if b>a]
                if adds_unselected_speech(added,[c,other]):
                    continue
                if any((w['end']>oa+1e-8 and w['start']<end-1e-8) and not
                       (w['end']>oa+1e-8 and w['start']<selected_end(c)-1e-8 or w['end']>ra+1e-8 and w['start']<selected_end(other)-1e-8) for w in words):
                    continue
                if any(w['end']>ra and w['start']<selected_end(other) and end<min(selected_end(other),w['end'])-1e-8 for w in words):
                    continue
                if any(end<ra+cap[1]-1e-8 for cap in other.get('captions',[])):
                    continue
                at=result['clips'].index(other)
                if at+1<len(result['clips']) and not result['clips'][at+1].get('intentional_jumpback_reason') and other['source_frame_in']+count>result['clips'][at+1]['source_frame_in']:
                    continue
                proposed=deepcopy(other)
                proposed.update(frames=count,source_frame_out=other['source_frame_in']+count,
                                picture_out=(other['source_frame_in']+count)/fps)
                try:
                    build_picture_fragments({'fps':fps,'clips':[proposed]},shots)
                except ValueError:
                    continue
                move(c,c['source_frame_in'],other['source_frame_in'],'bridge_measured_same_shot_gap')
                delta=join-ra
                other.update(source_in=join,frames=count,source_frame_out=proposed['source_frame_out'],
                    picture_out=proposed['picture_out'],duration=count/fps,
                    captions=[[max(0,a-delta),b-delta,text] for a,b,text in other.get('captions',[])])
                # Subsequent edge planning must protect the reconciled clock.
                originals[other['index']]=deepcopy(other)
                adjustments.append({'clip_index':other['index'],'audio_start_before':ra,
                    'audio_start_after':join,'frames':count,'reason':'continuous_source_audio_clock',
                    'audio_and_picture_changed_together':True})
                break
        if c['source_frame_out']==other['source_frame_in']:
            originals[c['index']]=deepcopy(c)
    for pos,c in enumerate(result['clips']):
        if c['kind']!='D':
            continue
        for issue in [i for i in boundary_issues(result,shots,min_frames) if i['clip_index']==c['index']]:
            a,b=c['source_frame_in'],c['source_frame_out']
            if issue['edge']=='leading':
                cut=round(issue['source_out']*fps)
                candidates=[(cut,b),(round(issue['shot_source_in']*fps),b)]
            else:
                cut=round(issue['source_in']*fps)
                candidates=[(a,cut),(a,round(issue['shot_source_out']*fps))]
            for start,end in sorted(candidates,key=lambda pair:abs(pair[0]-a)+abs(pair[1]-b)):
                if pos and not c.get('intentional_jumpback_reason') and start<result['clips'][pos-1]['source_frame_out']:
                    continue
                if pos+1<len(result['clips']) and not result['clips'][pos+1].get('intentional_jumpback_reason') and end>result['clips'][pos+1]['source_frame_in']:
                    continue
                if safe(c,start,end):
                    move(c,start,end,'word_safe_'+issue['edge']+'_source_boundary')
                    break
    # Recompute all output clocks only after audio and picture lengths agree.
    cursor=0
    for c in result['clips']:
        if c != originals[c['index']] or 'timeline_in' in c:
            c.update(timeline_in=cursor/fps,timeline_out=(cursor+c['frames'])/fps,duration=c['frames']/fps)
        cursor+=c['frames']
    if 'frames' in result: result['frames']=cursor
    if 'duration' in result: result['duration']=cursor/fps
    result['boundary_audit']={'version':1,'minimum_partial_shot_frames':min_frames,
        'adjustments':adjustments,'issues':boundary_issues(result,shots,min_frames)+same_shot_gaps(result,shots,include_audio=True)}
    return result


def build_picture_fragments(tl, shots):
    """Map clips to sampled-frame fragments in canonical source shots.

    start/end are local output frame indices (end exclusive). A cut between
    frames belongs to the first frame whose source time reaches the cut; fractional
    fractional fps values are evaluated rationally.
    """
    fps = _rate(tl)
    ordered = sorted(shots, key=lambda s: s["source_in"])
    if len({s["id"] for s in ordered}) != len(ordered):
        raise ValueError("Canonical shot IDs must be unique")
    bounds = [(_number(s["source_in"], "shot start"), _number(s["source_out"], "shot end"), s) for s in ordered]
    if any(b <= a for a, b, _ in bounds) or any(bounds[i][1] > bounds[i+1][0] + _EPS for i in range(len(bounds)-1)):
        raise ValueError("Canonical shots must be nonempty and nonoverlapping")
    result = {}
    for c in tl["clips"]:
        start = _picture_start(c, fps)
        count = _frames(c)
        stop = start + Fraction(count, 1) / fps
        # Check the whole picture interval, including portions between sampled frames.
        cursor = start
        for a, b, _ in bounds:
            if b <= cursor:
                continue
            if a > cursor + _EPS:
                break
            cursor = max(cursor, b)
            if cursor >= stop - _EPS:
                break
        if cursor < stop - _EPS:
            raise ValueError(f"Clip {c['index']}: picture interval crosses an unmeasured source gap; measure that interval first")
        fragments = []
        cursor=0
        for a,b,shot in bounds:
            # Solve a-EPS <= start+n/fps < b-EPS on the integer frame grid.
            # This is the same per-frame partition without rescanning every
            # source shot for every frame during each candidate boundary plan.
            if b-_EPS<=start or a-_EPS>=stop:continue
            left=max(0,math.ceil((a-start-_EPS)*fps))
            right=min(count,math.ceil((b-start-_EPS)*fps))
            if right<=left:continue
            if left!=cursor:
                raise ValueError(f"Clip {c['index']} frame {cursor}: canonical source-shot coverage is missing or ambiguous")
            fragments.append({'shot_id':shot['id'],'start':left,'end':right,
                              'source_in':float(start+Fraction(left,1)/fps),
                              'source_out':float(start+Fraction(right,1)/fps),
                              'shot_source_in':float(a),'shot_source_out':float(b)})
            cursor=right
        if cursor!=count:
            raise ValueError(f"Clip {c['index']} frame {cursor}: canonical source-shot coverage is missing or ambiguous")
        key = str(c["index"])
        if key in result:
            raise ValueError("Clip indices must be unique")
        result[key] = fragments
    return result


def _value_at(points, time, axis=1):
    """Linear value of one axis (1 = cx · 2 = cy) at `time` — held outside the authored range."""
    if time <= points[0][0]:
        return points[0][axis]
    for p, q in zip(points, points[1:]):
        if time <= q[0]:
            return p[axis] + (q[axis] - p[axis]) * float((time - p[0]) / (q[0] - p[0]))
    return points[-1][axis]


def project_camera(tl, fragments, trajectories):
    """Compile camera.source_shots to existing camera['clips'] format.

    trajectories={shot_id: {points:[[absolute_source_seconds,cx], ...]}}.
    AGY 구도(사장님 결정 2026-10-07 · shorts_framing.resolve): points 가 [초, cx, cy] 이고 crop [가로 비율, 세로 비율] 이 있으면
    확대한 창의 가로·세로 가운데를 함께 따라간다(한 원본 장면에 창 크기는 하나).
    One canonical trajectory is shared across N/D boundaries and nonadjacent reuse.
    Points hold outside their authored time range; no smoothing crosses a real cut.
    A missing/extra shot or invalid/duplicate time fails instead of guessing centers.
    """
    fps = _rate(tl)
    required = {f["shot_id"] for group in fragments.values() for f in group}
    if set(trajectories) != required:
        raise ValueError(f"Camera source_shots must match measured shots; missing={sorted(required-set(trajectories))}, unexpected={sorted(set(trajectories)-required)}")
    parsed = {}
    for shot_id in sorted(required):
        crop = trajectories[shot_id].get('crop')
        if crop is not None and not (isinstance(crop, (list, tuple)) and len(crop) == 2
                                     and all(0 < _number(v, 'source shot crop') <= 1 for v in crop)):
            raise ValueError('Source shot crop must be [width fraction, height fraction] in (0,1]')
        if crop is not None and 'view_width' in trajectories[shot_id]:
            raise ValueError('Source shot crop and view_width cannot be combined')
        if 'view_width' in trajectories[shot_id]:
            width = _number(trajectories[shot_id]['view_width'], 'source shot view width')
            if not 0 < width <= 1:
                raise ValueError('Source shot view_width must be a fraction in (0,1]')
        points = trajectories[shot_id].get("points")
        if not isinstance(points, list) or not points:
            raise ValueError(f"{shot_id}: author at least one source-time camera point")
        values = []
        shot_fragments = [f for group in fragments.values() for f in group if f["shot_id"] == shot_id]
        lower = _number(shot_fragments[0]["shot_source_in"], "shot start")
        upper = _number(shot_fragments[0]["shot_source_out"], "shot end")
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) != (2 if crop is None else 3):
                raise ValueError(f"{shot_id}: camera point must be [source_seconds, cx]"
                                 + ("" if crop is None else " plus cy when the shot has a crop"))
            t = _number(point[0], "camera source time")
            x = _number(point[1], "camera cx")
            y = None if crop is None else _number(point[2], "camera cy")
            if y is not None and not 0 <= y <= 1:
                raise ValueError(f"{shot_id}: cy is outside [0,1]")
            # Decimal authoring can round an exact boundary outside the shot.
            # Resolve only a sub-half-frame boundary discrepancy to the measured
            # boundary; retain all interior motion anchors without quantizing.
            tolerance = 1 / (2 * fps)
            if not 0 <= x <= 1 or not lower - tolerance <= t <= upper + tolerance:
                raise ValueError(f"{shot_id}: camera point is outside its source shot or cx is outside [0,1]")
            t = min(upper, max(lower, t))
            if values and t <= values[-1][0]:
                raise ValueError(f"{shot_id}: source-time camera points must be strictly increasing; conflicting per-clip anchors are not allowed")
            values.append((t, float(x)) if y is None else (t, float(x), float(y)))
        parsed[shot_id] = values
    if set(fragments) != {str(c["index"]) for c in tl["clips"]}:
        raise ValueError("Picture fragments do not match timeline clips")
    plans = {}
    for c in tl["clips"]:
        start = _picture_start(c, fps)
        shots = []
        cursor = 0
        for f in fragments[str(c["index"])]:
            if f["start"] != cursor or not f["start"] < f["end"] <= _frames(c):
                raise ValueError(f"Clip {c['index']}: picture fragments must cover each output frame exactly once")
            cursor = f["end"]
            sampled = []
            track = parsed[f["shot_id"]]; axes = range(1, len(track[0]))
            for n in range(f["start"], f["end"]):
                when = start + Fraction(n, 1) / fps
                sampled.append([n, *(_value_at(track, when, k) for k in axes)])
                while len(sampled) >= 3:
                    a, b, d = sampled[-3:]
                    if any(abs(b[k] - (a[k] + (d[k] - a[k]) * (b[0] - a[0]) / (d[0] - a[0]))) > 1e-12 for k in axes):
                        break
                    sampled.pop(-2)
            shot = {"start": f["start"], "points": sampled, "source_shot_id": f["shot_id"]}
            if trajectories[f['shot_id']].get('crop') is not None:
                shot['crop'] = [float(v) for v in trajectories[f['shot_id']]['crop']]
            if 'view_width' in trajectories[f['shot_id']]:
                shot['view_width'] = trajectories[f['shot_id']]['view_width']
            shots.append(shot)
        if cursor != _frames(c):
            raise ValueError(f"Clip {c['index']}: picture fragments do not cover all output frames")
        plans[str(c["index"])] = {"shots": shots}
    return {"clips": plans}


def stabilize_picture_edges(tl, camera, max_frames):
    """Clone isolated short edge pictures without changing source/audio timing."""
    import copy
    if type(max_frames) is not int or max_frames < 0:
        raise ValueError("Edge repair frame limit must be a nonnegative integer")
    result = copy.deepcopy(camera)
    clips = tl["clips"]
    fps = _rate(tl)
    for index, clip in enumerate(clips):
        plan = result["clips"][str(clip["index"])]; shots = plan["shots"]
        if len(shots) < 2 or not max_frames:
            continue
        count = _frames(clip)
        leading, trailing = shots[1]["start"], count-shots[-1]["start"]
        previous = clips[index-1] if index else None
        following = clips[index+1] if index+1 < len(clips) else None
        def continues(other, before):
            if other is None:
                return False
            other_shots = camera["clips"][str(other["index"])]["shots"]
            if before:
                return (_picture_start(other,fps)+Fraction(_frames(other),1)/fps == _picture_start(clip,fps)
                        and other_shots[-1]["source_shot_id"] == shots[0]["source_shot_id"])
            return (_picture_start(clip,fps)+Fraction(count,1)/fps == _picture_start(other,fps)
                    and shots[-1]["source_shot_id"] == other_shots[0]["source_shot_id"])
        trim_lead = leading <= max_frames and not continues(previous, True)
        trim_tail = trailing <= max_frames and not continues(following, False)
        if trim_lead and trim_tail and len(shots) == 2:
            continue  # No stable interior picture exists to clone.
        if trim_tail:
            plan["trim_end"] = shots[-1]["start"]
            shots.pop()
        if trim_lead:
            plan["trim_start"] = leading
            shots.pop(0)
            shots[0]["start"] = 0
            shots[0]["points"].insert(0,[0,*shots[0]["points"][0][1:]])
        if trim_lead or trim_tail:
            plan["edge_picture_repair"] = {"leading_cloned_frames": leading if trim_lead else 0,
                "trailing_cloned_frames": trailing if trim_tail else 0,
                "audio_unchanged": True}
    return result
