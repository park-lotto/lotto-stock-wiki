"""Generated canonical shop geometry closure; server spec supplied at runtime."""
KERNEL_ID = 'cb0eace77cecc92bdbd9fdfa3df945f604ee21a792451079807ebcd7df670ccb'
import math
import re
def window_vf(S):
    w = S['VIDEO_RECT'][2] - S['VIDEO_RECT'][0]
    h = S['VIDEO_RECT'][3] - S['VIDEO_RECT'][1]
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={S['FPS']}"

def frame_vf(crop, S):
    if isinstance(crop, dict):
        if crop.get('needs_replacement') or not crop.get('vf'):
            raise ValueError('확인한 상품을 중앙에 배치할 수 없습니다: ' + str(crop.get('framing_reason')))
        return crop['vf'] + f",fps={S['FPS']}"
    vw = S['VIDEO_RECT'][2] - S['VIDEO_RECT'][0]
    vh = S['VIDEO_RECT'][3] - S['VIDEO_RECT'][1]
    cx, cy, cw, ch = crop
    return f"crop={cw}:{ch}:{cx}:{cy},scale={vw}:{vh}:force_original_aspect_ratio=decrease:flags=lanczos,pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={S['FPS']}"

def frame_crop(meas, S):
    if 'framing_subject' in meas:
        import focus_kernel as volcano_framing
        rect = S['VIDEO_RECT']
        texts = meas.get('text_boxes_source')
        if texts is None:
            _, texts = volcano_framing.source_boxes(meas)
        p = volcano_framing.center_plan(meas['size'], meas['content'], meas['framing_subject'], [rect[2] - rect[0], rect[3] - rect[1]], texts=texts, contain_selected=True, text_frames=volcano_framing.source_text_frames(meas), frame_grid=meas.get('scene_evidence'))
        return dict(p, scene_guard_plan=meas.get('scene_guard_plan'), pad_ratio=p.get('pad_ratio', 0.0), band=[meas['content'][2] < meas['size'][0], meas['content'][3] < meas['size'][1]], motion=meas.get('motion'), by=meas.get('by'))
    F = S['FRAME']
    x0, y0, x1, y1 = S['VIDEO_RECT']
    a = (x1 - x0) / (y1 - y0)
    cx0, cy0, cw0, ch0 = [int(v) for v in meas['content']]
    cw = cw0
    want_h = int(round(cw / a))
    if ch0 > want_h:
        ch = want_h
        top = cy0 + int(round(F['CY'] * ch0 - F['CY'] * ch))
        top = max(cy0, min(top, cy0 + ch0 - ch))
    else:
        ch = ch0
        top = cy0
    return {'crop': [cx0, top, max(2, cw), max(2, ch)], 'pad_ratio': round(max(0.0, 1.0 - ch / cw * a) if cw else 0.0, 4), 'band': [cw0 < int(meas['size'][0]), ch0 < int(meas['size'][1])], 'motion': meas.get('motion'), 'by': meas.get('by')}

def _isect(content, crop):
    cx, cy, cw, chh = [int(v) for v in content[:4]]
    kx, ky = (int(crop.get('x') or 0), int(crop.get('y') or 0))
    kw, kh = (int(crop.get('keep_w') or cw), int(crop.get('keep_h') or chh))
    x0, y0 = (max(cx, kx), max(cy, ky))
    x1, y1 = (min(cx + cw, kx + kw), min(cy + chh, ky + kh))
    if x1 - x0 < 16 or y1 - y0 < 16:
        raise ValueError('source_crop_intersection_invalid')
    return [x0, y0, x1 - x0, y1 - y0]

def audit_frames(cuts, frames, S, src_crop=None):
    reject, warn, plan = ([], [], [])
    for c in cuts:
        i = int(c['order'])
        m = (frames or {}).get(str(i)) or (frames or {}).get(i)
        cr = (src_crop or {}).get(c.get('source_id'))
        if cr and isinstance(m, dict) and m.get('content'):
            import focus_kernel as volcano_framing
            _, texts = volcano_framing.source_boxes(m)
            try:
                content = _isect(m['content'], cr)
            except (ValueError, TypeError, OverflowError):
                reject.append(f'컷 {i}의 소재 크롭과 실측 알맹이가 유효하게 겹치지 않습니다: source_crop_intersection_invalid')
                continue
            m = dict(m, content=content, text_boxes_source=texts)
        if not isinstance(m, dict) or not m.get('content') or (not m.get('size')):
            reject.append(f'컷 {i}의 화면을 재지 않았습니다 — `shop_frame` 이 준 `measure_frame` 을 그대로 돌리고 그 결과를 payload.frames 에 넣으세요.')
            continue
        pl = frame_crop(m, S)
        if pl.get('needs_replacement'):
            reject.append(f'컷 {i}의 선택된 상품/피사체를 중앙에 배치할 수 없습니다: ' + str(pl.get('framing_reason')))
            continue
        if cr:
            warn.append(f"컷 {i}의 소재는 원작자 글자를 잘라내고 씁니다 ({cr.get('side')}쪽 {int(float(cr.get('frac') or 0) * 100)}%).")
        if any(pl['band']):
            warn.append(f'컷 {i}의 소재에 검은 띠가 있어 알맹이만 잘라 씁니다 (그 띠는 화면에 안 나갑니다).')
        if pl['pad_ratio'] > 0.02:
            warn.append(f"컷 {i}은 가로 소재라 위아래에 검은 띠가 {pl['pad_ratio'] * 100:.0f}% 생깁니다 — **세로로 찍은 소재**를 쓰면 화면이 꽉 찹니다. 좌우를 잘라내지는 않습니다(잘라내면 물건이 화면 밖으로 나갑니다).")
        plan.append(dict(pl, order=i))
    return {'reject': reject, 'warn': warn, 'plan': plan}

def usable_span(sh, S):
    return tuple((v / 100.0 for v in usable_ci(sh, S)))

def usable_ci(sh, S):
    import math
    ins = S['SHOT']['INSET_SEC']
    lo = math.ceil(round((float(sh['start']) + ins) * 100.0, 6))
    hi = math.floor(round((float(sh['end']) - ins) * 100.0, 6))
    return (lo, max(lo, hi))

def source_span(cut, shots, S):
    sh = shots[cut['shot_id']]
    lo, hi = usable_span(sh, S)
    a = lo + float(cut.get('in_off') or 0.0)
    b = lo + float(cut['out_off']) if cut.get('out_off') is not None else hi
    return (max(lo, a), min(hi, b))

def cut_jobs(cuts, times, shots, sources, wd, S, plan=None):
    jobs = []
    by_order = {t['order']: t for t in times}
    by_plan = {int(p['order']): p for p in plan or []}
    for c in cuts:
        t = by_order[c.get('order')]
        a, b = source_span(c, shots, S)
        src = sources[c['source_id']]
        i = int(c.get('order'))
        lo_u, hi_u = usable_span(shots[c['shot_id']], S)
        span = max(b - a, 0.0)
        if span > t['d'] + 0.001:
            a = b - t['d']
        elif span < t['d'] - 0.001:
            need = t['d'] - span
            grow_b = min(need, max(hi_u - b, 0.0))
            b += grow_b
            grow_a = min(need - grow_b, max(a - lo_u, 0.0))
            a -= grow_a
        keep = str(c.get('mode') or 'N').upper() == 'S'
        pl = by_plan.get(i)
        vf = frame_vf(pl if pl.get('vf') or pl.get('needs_replacement') else pl['crop'], S) if pl else window_vf(S)
        avail = max(b - a, 1.0 / float(S['FPS']))
        use = min(t['d'], avail)
        nframes = max(1, int(round(use * float(S['FPS']))))
        tsec = f"{use + 1.0 / float(S['FPS']):.6f}"
        if pl and pl.get('scene_guard_plan'):
            import focus_kernel as volcano_scene_guard
            guard = pl['scene_guard_plan']
            if abs(guard['requested_start'] - float(f'{a:.3f}')) > 1e-06 or guard['nframes'] != nframes or guard['fps'] != S['FPS']:
                raise ValueError('상품 측정의 시각이 실제 굽는 컷과 다릅니다.')
            protected = volcano_scene_guard.plan_filter(guard)
            vf = f"fps={S['FPS']}," + (protected + ',' if protected else '') + vf
        argv = ['ffmpeg', '-y', '-ss', f'{a:.3f}', '-t', tsec, '-i', src['path']]
        use_src_audio = bool(keep and src.get('has_audio'))
        if not use_src_audio:
            argv += ['-f', 'lavfi', '-t', tsec, '-i', 'anullsrc=r=48000:cl=stereo']
        argv += ['-map', '0:v:0', '-map', '0:a:0' if use_src_audio else '1:a:0', '-vf', vf, '-frames:v', str(nframes)]
        argv += ['-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2', '-shortest', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(S['CRF']), '-pix_fmt', 'yuv420p', '-r', str(S['FPS'])]
        jobs.append({'index': i, 'out': f'{wd}/cut/{i:03d}.mp4', 'seconds': round(t['d'], 3), 'argv': argv + [f'{wd}/cut/{i:03d}.mp4', '-loglevel', 'error']})
    return jobs

def focus_cuts(cuts, times, shots, sources, wd, S):
    by_order = {int(c['order']): c for c in cuts}
    requests = []
    for job in cut_jobs(cuts, times, shots, sources, wd, S):
        c = by_order[job['index']]
        argv = job['argv']
        requests.append(dict(card=job['index'], src=argv[argv.index('-i') + 1], kind='video', start=float(argv[argv.index('-ss') + 1]), duration=int(argv[argv.index('-frames:v') + 1]) / float(S['FPS']), fps=float(S['FPS']), source_duration=sources[c['source_id']].get('dur'), source_crop=sources[c['source_id']].get('crop'), focus_role='product', context=str(c.get('caption') or c.get('shows') or c)))
    return requests

def concat_txt(jobs):
    return ''.join((f"file '{j['out']}'\n" for j in jobs))

def deliver_cuts(cuts, times, shots, sources, plan, S):
    fps = float(S['FPS'])
    vw = S['VIDEO_RECT'][2] - S['VIDEO_RECT'][0]
    vh = S['VIDEO_RECT'][3] - S['VIDEO_RECT'][1]
    by_plan = {int(p['order']): p for p in plan or []}
    actual = {c['card']: c for c in focus_cuts(cuts, times, shots, sources, '', S)}
    out = []
    for c in cuts:
        i = int(c['order'])
        src = sources[c['source_id']]
        a = actual[i]['start']
        pl = by_plan.get(i)
        sw, sh = (float(src['w']), float(src['h']))
        if pl:
            cx, cy, cw, ch = [float(v) for v in (pl.get('placement') or {}).get('viewport') or pl['crop']]
            sc = vw / cw
            ccx, ccy = (cx + cw / 2.0, cy + ch / 2.0)
        else:
            sc = max(vw / sw, vh / sh)
            ccx, ccy = (sw / 2.0, sh / 2.0)
        dx = S['VIDEO_RECT'][0] + vw / 2.0 - S['W'] / 2.0 - sc * (ccx - sw / 2.0)
        dy = S['VIDEO_RECT'][1] + vh / 2.0 - S['H'] / 2.0 - sc * (ccy - sh / 2.0)
        in_f = int(round(a * fps))
        n_f = max(1, int(round(actual[i]['duration'] * fps)))
        media_f = int(round(float(src.get('dur') or 0.0) * fps))
        out.append({'index': i, 'src': src['path'], 'kind': 'video', 'src_in': a, 'in_f': in_f, 'frames': n_f, 'media_frames': media_f, 'w': int(sw), 'h': int(sh), 'scale_pct': round(sc * 100.0, 4), 'center': (round(dx / float(S['W']), 6), round(dy / float(S['W']), 6)), 'head_f': in_f, 'tail_f': max(0, media_f - in_f - n_f), 'name': src.get('title') or src['id']})
        if pl and pl.get('placement'):
            out[-1]['placement'] = pl['placement']
        if pl and pl.get('tracking_keys'):
            import focus_kernel as volcano_framing
            out[-1]['motion_keys'] = [dict(when=in_f + frame, **volcano_framing.editor_transform(pl, [sw, sh], S['VIDEO_RECT'], [S['W'], S['H']], frame / fps)) for frame in range(n_f)]
    return out

def rendered_delivery_cuts(cuts, wd, S):
    out = []
    for raw in cuts:
        c = {k: v for k, v in raw.items() if k != 'motion_keys'}
        c.update(src=f"{wd}/cut/{raw['index']:03d}.mp4", src_in=0, in_f=0, media_frames=raw['frames'], w=S['W'], h=S['H'], scale_pct=100, center=(0, 0), head_f=0, tail_f=0, original_source={'path': raw['src'], 'start': raw['src_in']})
        out.append(c)
    return out

__all__ = ['audit_frames', 'cut_jobs', 'deliver_cuts', 'rendered_delivery_cuts', 'focus_cuts', 'concat_txt']
