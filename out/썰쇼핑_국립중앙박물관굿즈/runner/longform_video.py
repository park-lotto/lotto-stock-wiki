"""Inspect source edit boundaries before narration-length trims become flash cuts."""
from pathlib import Path
import re
import math
import uuid
from film_editor import command
from longform_state import save, ProductionError

def boundary_review_page(root, scenes):
    """Publish current selected boundaries, without inventing a review verdict."""
    import html
    import json
    import os
    from urllib.parse import quote
    from film_editor import atomic_bytes
    root=Path(root).resolve()
    def link(path):
        path=Path(path).resolve()
        try:
            return quote(Path(os.path.relpath(path,root)).as_posix(),safe='/')
        except ValueError:  # Different Windows drives cannot form relative paths.
            # W2-17: a `\\?\` long-path prefix must not become `file://%3F/…`; one shared converter.
            from volcano_run import _file_uri
            return _file_uri(path)
    sections=[]
    for scene in scenes:
        cards=[]
        for number, report_path in enumerate(scene['reports'],1):
            report=json.loads(Path(report_path).read_text(encoding='utf-8'))
            evidence=report.get('boundary_evidence',{})
            images=[]
            for key,label in (('head','앞쪽 상세'),('tail','뒤쪽 상세'),('head_context','앞쪽 1초 연속'),('tail_context','뒤쪽 1초 연속')):
                if key.endswith('_context') and key not in evidence:continue
                path=Path(evidence.get(key,''))
                if not path.is_file():
                    raise ProductionError('boundary_frames_missing','장면 경계 검수 이미지가 없습니다.',action='repair')
                indices=evidence[key+'_frame_indices']
                images.append(f'<figure><figcaption>{label} · 출력 프레임 {indices[0]}–{indices[-1]}</figcaption>'
                              f'<a href="{html.escape(link(path),quote=True)}"><img loading="lazy" '
                              f'src="{html.escape(link(path),quote=True)}" alt="{label} 연속 프레임"></a></figure>')
            status='짧은 컷 후보 있음' if report.get('short_shot_candidates') else '자동 검사에서 짧은 컷 후보 없음 — 육안 확인 필요'
            cards.append(f'<article><h3>자료 {number} · {status}</h3>'
                         f'<p>{html.escape(str(report.get("source","")))}</p>'
                         f'<p>원본 시작 {evidence["source_start"]}초 · 표시 길이 {evidence["visible_seconds"]}초 · '
                         f'<a href="{html.escape(link(report_path),quote=True)}">검사 기록</a></p>'+''.join(images)+'</article>')
        sections.append('<section><h2>'+html.escape(str(scene['block']))+'</h2>'+''.join(cards)+'</section>')
    body='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>장면 경계 검수</title><style>body{font:16px sans-serif;background:#16191f;color:#eee;margin:24px auto;padding:0 20px;max-width:1700px}a{color:#92caff}section{border-top:2px solid #59616d;margin-top:32px}article{padding:12px;background:#222730;margin:16px 0}p{overflow-wrap:anywhere}figure{margin:16px 0}img{display:block;width:100%;height:auto}figcaption{padding:8px 0}</style>
<h1>장면 경계 검수 · 확인 대기</h1><p>각 그림은 왼쪽에서 오른쪽, 위에서 아래 순서입니다. 원본의 실제 표시 구간 앞뒤 최대 20프레임 상세와 최대 1초(60프레임) 연속 그림을 60fps 출력 기준으로 보여줍니다. 이전 기록에는 1초 그림이 없을 수 있습니다. 짧은 구간의 남은 칸은 빈칸입니다. 원본 프레임이 반복될 수 있습니다.</p>
<p>자동 통과는 화면의 연속성을 보증하지 않습니다. 이 자료는 자막·크롭·전환이 합성되기 전 원본입니다. 최종 화면과 실제 재생 속도도 별도로 확인해야 합니다.</p>'''
    body+=''.join(sections) if sections else '<p>현재 장면에 영상 경계 검수 자료가 없습니다. 검수 통과를 뜻하지 않습니다.</p>'
    path=root/'source-boundary-review.html'
    atomic_bytes(path,(body+'</html>').encode('utf-8'))
    return str(path)

def boundary_evidence(root, source, start, visible):
    """Keep detailed edges and one-second context even when scene detection passes.

    These are review evidence, not an automatic visual pass. A unique directory
    preserves earlier selections and avoids replacing an image open on Windows.
    """
    folder=Path(root)/'boundary-frames'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    frames=max(1,math.ceil(visible*60-1e-7));count=min(20,frames)
    head=folder/'head.png';tail=folder/'tail.png'
    context_count=min(60,frames)
    head_context=folder/'head-context.png';tail_context=folder/'tail-context.png'
    # Resample before trimming on the output clock. Trimming the input first
    # drops the frame needed to produce the last 60fps sample for fractional
    # durations (e.g. 29.97fps -> 4.101333s needs 247 output samples, not 246).
    # end_frame still bounds decoding; do not pad a genuinely short source.
    graph=('[0:v]setpts=PTS-STARTPTS,fps=60,'
           f'trim=end_frame={frames},scale=320:180:force_original_aspect_ratio=decrease,'
           'pad=320:180:(ow-iw)/2:(oh-ih)/2,setsar=1,split=4[a][z][ac][zc];'
           f'[a]trim=end_frame={count},showinfo@head,tile=5x4:nb_frames={count}[head];'
           f'[z]trim=start_frame={frames-count}:end_frame={frames},'
           f'showinfo@tail,tile=5x4:nb_frames={count}[tail];'
           f'[ac]trim=end_frame={context_count},showinfo@head_context,tile=6x10:nb_frames={context_count}[head_context];'
           f'[zc]trim=start_frame={frames-context_count}:end_frame={frames},'
           f'showinfo@tail_context,tile=6x10:nb_frames={context_count}[tail_context]')
    command(folder,['ffmpeg','-hide_banner','-nostats','-v','info','-ss',start,'-i',source,
                    '-filter_complex',graph,'-map','[head]','-frames:v','1',head,
                    '-map','[tail]','-frames:v','1',tail,
                    '-map','[head_context]','-frames:v','1',head_context,
                    '-map','[tail_context]','-frames:v','1',tail_context],
            'boundary-frames',timeout=1800)
    log=(folder/'logs/boundary-frames.log').read_text(encoding='utf-8',errors='replace')
    actual={name:len(re.findall(r'showinfo@'+name+r'\b[^\n]*\bn:\s*\d+\s+pts:',log)) for name in ('head','tail')}
    if not head.is_file() or not tail.is_file() or any(n!=count for n in actual.values()):
        raise ProductionError('boundary_frames_missing','영상 앞뒤 프레임 검수 자료를 만들지 못했습니다.',action='edit_plan')
    context_actual={name:len(re.findall(r'showinfo@'+name+r'\b[^\n]*\bn:\s*\d+\s+pts:',log)) for name in ('head_context','tail_context')}
    if not head_context.is_file() or not tail_context.is_file() or any(n!=context_count for n in context_actual.values()):
        raise ProductionError('boundary_frames_missing','영상 앞뒤 1초 연속 검수 자료를 만들지 못했습니다.',action='edit_plan')
    return {'context_frames_per_sheet':context_count,'context_decoded_counts':context_actual,
            'head_context':str(head_context),'tail_context':str(tail_context),
            'head_context_frame_indices':list(range(context_count)),
            'tail_context_frame_indices':list(range(frames-context_count,frames)),
            'status':'review_required','fps':60,'frames_per_sheet':count,'decoded_counts':actual,
            'head':str(head),'tail':str(tail),'visible_frames':frames,
            'head_frame_indices':list(range(count)),
            'tail_frame_indices':list(range(frames-count,frames)),
            'source_start':start,'visible_seconds':visible,
            'scope':'Uncropped source on the 60fps output clock; not final composition or full-speed review'}

def inspect_cuts(root, source, start, seconds, minimum_shot=.5, *, visible_seconds=None, cut_review=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    # Dark-source cut measured 0.240780: the former 0.25 threshold missed an 8-frame head.
    # This remains candidate detection; fades and subtler cuts still require visual review.
    # Scene score uses differences from the preceding frame pair. Starting it
    # at a selection boundary misclassifies continuous motion as a tiny shot.
    # Feed bounded context first; only then restrict detections to the selection.
    # Keep the threshold and the first selected frames: genuine head slivers
    # must remain detectable (tests/test_geumbit_video.py).
    context_start=max(0.,float(start)-2.)
    context_seconds=float(start)-context_start
    command(root,['ffmpeg','-hide_banner','-nostats','-ss',context_start,'-i',source,
                  '-vf',f"trim=duration={context_seconds+seconds},setpts=PTS-STARTPTS,scale=320:-2,"
                        f"select='gt(scene,0.20)',setpts=PTS-{context_seconds}/TB,"
                        f"trim=start=0:end={seconds},showinfo",
                  '-an','-f','null','-'],'source-cuts',timeout=1800)
    log=(root/'logs/source-cuts.log').read_text(encoding='utf-8',errors='replace')
    cuts=[float(x) for x in re.findall(r'\bpts_time:([0-9.]+)',log)]
    cuts=sorted(set(x for x in cuts if 0<x<seconds))
    # The outgoing transition handle must not make a tiny visible tail look safe.
    visible=float(seconds if visible_seconds is None else visible_seconds)
    if not 0<visible<=seconds:
        raise ProductionError('source_cut_window','표시 구간이 검사 범위 밖입니다.',action='edit_plan')
    raw_cuts=list(cuts)
    adjudication=None
    if cut_review is not None:
        from longform_cut_review import apply_cut_review
        cuts,adjudication=apply_cut_review(source,start,seconds,cuts,cut_review)
    short=[]
    windows=[('decoded',float(seconds))]
    if visible<seconds:windows.append(('visible',visible))
    for scope,end in windows:
        edges=[0.,*[x for x in cuts if x<end],end]
        short.extend({'start':a,'end':b,'duration':b-a,'scope':scope,
                      'output_frames_60fps':round((b-a)*60)}
                     for a,b in zip(edges,edges[1:]) if b-a<minimum_shot-1e-7)
    raw_short=[]
    for scope,end in windows:
        edges=[0.,*[x for x in raw_cuts if x<end],end]
        raw_short.extend({'start':a,'end':b,'duration':b-a,'scope':scope}
                         for a,b in zip(edges,edges[1:]) if b-a<minimum_shot-1e-7)
    report={'source':str(source),'source_start':start,'duration':seconds,'detected_cuts':raw_cuts,'effective_cuts':cuts,'cut_review':adjudication,
            'visible_seconds':visible,'detector_context_seconds':context_seconds,'detection_scope':'scene score >0.20; candidates require source review, not proof of all cuts',
            'minimum_shot_seconds':minimum_shot,'short_shot_candidates':short,'raw_short_shot_candidates':raw_short,
            'automatic_pass':not raw_short,'passed':not short}
    report['boundary_evidence']=boundary_evidence(root,source,start,visible)
    save(root/'source-cuts.json',report)
    if short:
        # Say where (2026-10-17 #128): the source file and every short span in source seconds, so the author can move
        # in/out without opening source-cuts.json. Callers prefix the block/shot and gather every block's report.
        spans=', '.join(f"{float(start)+row['start']:.2f}–{float(start)+row['end']:.2f}초({row['duration']:.2f}초)" for row in short if row['scope']=='decoded') \
              or ', '.join(f"{float(start)+row['start']:.2f}–{float(start)+row['end']:.2f}초" for row in short)
        raise ProductionError('short_source_shot',
            f'실사 구간에 0.5초 미만의 짧은 컷 후보가 있습니다 — 원본 {Path(str(source)).name} {spans}. '
            '그 장면 전환을 피하도록 in/out 을 옮기거나 다른 구간을 고르세요(자세한 판정: '+str(root/'source-cuts.json')+').',action='edit_plan')
    return report


def overlay_enable(start, end, frames, fps=60):
    """Evaluate on the rendered frame index, independent of source timestamp offsets."""
    import math
    first=max(0,math.ceil(start*fps-1e-7))
    stop=min(frames,math.ceil(end*fps-1e-7))
    return f'gte(n,{first})*lt(n,{stop})'
