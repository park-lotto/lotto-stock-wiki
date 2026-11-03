"""Local Chrome/CDP capture; streamed PNG frames and atomic output publication."""
from pathlib import Path
import contextlib,json,os,shutil,subprocess,tempfile,signal,time
from longform_state import ProductionError,save,replace as publish

def svg_path_matches(actual, expected):
    import re,math
    token=re.compile(r'[MmZzLlHhVvCcSsQqTtAa]|[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?')
    def parse(value):
        if not isinstance(value,str) or re.sub(r'[\s,]','',token.sub('',value)):return None
        return token.findall(value)
    a,b=parse(actual),parse(expected)
    if not a or not b or len(a)!=len(b):return False
    command=None;coordinate=0
    for left,right in zip(a,b):
        if right.isalpha():
            if left!=right:return False
            command=right;coordinate=0;continue
        if command is None:return False
        try:x,y=float(left),float(right)
        except ValueError:return False
        if not math.isfinite(x) or not math.isfinite(y):return False
        # Arc flags are discrete, never approximate. Coordinates use the same
        # .001 local tolerance as scalar motion checks. GSAP rounds seeks and
        # SVG numeric strings; literal string equality rejected .0005px at end.
        if command in ('A','a') and coordinate%7 in (3,4):
            if x!=y or x not in (0,1):return False
        elif abs(x-y)>.001:return False
        coordinate+=1
    return True


def css_inset_matches(actual,expected):
    import re
    def parse(value):
        if not isinstance(value,str):return None
        match=re.fullmatch(r'inset\(([^()]*)\)',value.strip())
        if not match:return None
        parts=match[1].split()
        if not 1<=len(parts)<=4:return None
        values=[]
        for part in parts:
            m=re.fullmatch(r'([-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))(px|%)?',part)
            if not m:return None
            n=float(m[1]);unit=m[2] or ''
            if not unit and n!=0:return None
            values.append((n,unit))
        if len(values)==1:return values*4
        if len(values)==2:return values*2
        if len(values)==3:return [*values,values[1]]
        return values
    a,b=parse(actual),parse(expected)
    if a is None or b is None:return actual==expected
    # % values are percentage points: .001% is <.02px on this 1920px canvas.
    # Compare expanded CSS sides, not serialization/rounding of the string.
    return all((u==v or x==y==0) and abs(x-y)<=.001 for (x,u),(y,v) in zip(a,b))


def motion_state_matches(actual,expected,path=()):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and motion_state_matches(actual[k],v,path+(k,)) for k,v in expected.items())
    if path[-2:]==('attr','d'):return svg_path_matches(actual,expected)
    if path and path[-1]=='clipPath':return css_inset_matches(actual,expected)
    if path and path[-1]=='--wipe-edge':
        # This authored CSS variable is a percentage, not literal caption text.
        # Preserve units and the existing .001 percentage-point motion tolerance.
        import re
        pattern=r'[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)%'
        if not all(isinstance(v,str) and re.fullmatch(pattern,v) for v in (actual,expected)):return False
        return abs(float(actual[:-1])-float(expected[:-1]))<=.001
    if isinstance(expected,(int,float)):
        try:return abs(float(str(actual).removesuffix('px'))-expected)<=.001
        except (TypeError,ValueError):return False
    return actual==expected

def runtime():
    found={k:shutil.which(k) for k in ('node','ffmpeg','ffprobe')}
    candidates=[os.environ.get('VOLCANO_CHROME',''),shutil.which('google-chrome') or '',shutil.which('chromium') or '', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    for key in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
        if os.environ.get(key):candidates.append(str(Path(os.environ[key])/'Google/Chrome/Application/chrome.exe'))
    found['chrome']=next((p for p in candidates if p and Path(p).is_file()),None)
    if not all(found.values()):raise ProductionError('graphic_runtime_missing','Node.js, Chrome, FFmpeg, ffprobe 설치를 확인하세요.',action='repair_environment')
    try:
        p=subprocess.run([found['node'],'-p',"JSON.stringify({node:process.version})"],capture_output=True,timeout=15,check=True)
        info=json.loads(p.stdout)
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        raise ProductionError('graphic_runtime_invalid','Node.js 실행을 확인하세요.',action='repair_environment') from exc
    return {**found,'node_version':info['node'],'transport':'cdp_pipe'}

def render_document(folder,frames,*,target=None):
    from film_editor import command
    folder=Path(folder).resolve();target=Path(target or folder/'graphic.mp4').resolve()
    if type(frames) is not int or frames<1:raise ValueError('Positive integer frame count required')
    info=runtime()
    import video_encoder
    from longform_render import W,H,FPS
    # graphic.mp4 is decoded again by its scene (not joined with `-c copy`). Node only spawns ffmpeg with the encoder
    # argv picked here (runner/video_encoder.py — the one picker): this PC's choice, then CPU once if the GPU encoder
    # fails during the capture. The CPU argv is the old `-c:v libx264 -preset fast -crf 18` exactly.
    slot=video_encoder.x264('fast',18,W,H,FPS,program=info['ffmpeg'],color=False)
    for gpu,encode in video_encoder.attempts(slot):
        job=Path(tempfile.mkdtemp(prefix='native-render-',dir=folder));script=job/'capture.cjs';script.write_text(CAPTURE,encoding='utf-8');partial=job/'capture.mp4'
        with video_encoder.gpu_slots if gpu else contextlib.nullcontext():
            code=_browser_job(folder,job,script,partial,frames,info,encode=encode)
        failed=_encoder_failure(partial) if code and gpu else None
        if failed is None:break
        video_encoder.failed(gpu,failed)
    else:
        # attempts() always ends with the CPU try (gpu None → failed None → break) — reaching here means that contract broke.
        raise ProductionError('graphic_capture_failed','인코더 시도 목록이 CPU 시도로 끝나지 않았습니다(video_encoder.attempts 계약).',action='repair_environment')

    if code:raise ProductionError('graphic_capture_failed','그래픽 캡처 실패. 진단 보존: '+str(job),action='repair_environment')
    report=json.loads(command(job,[info['ffprobe'],'-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',partial],'probe').decode('utf-8'))['streams'][0]
    if (report.get('width'),report.get('height'),report.get('r_frame_rate'),int(report.get('nb_frames',0)))!=(1920,1080,'60/1',frames):raise ProductionError('graphic_capture_invalid','그래픽 프레임 규격 오류. 기존 출력 보존.')
    command(job,[info['ffmpeg'],'-v','error','-xerror','-i',partial,'-f','null','-'],'decode',timeout=max(120,frames))
    with partial.open('r+b') as stream:os.fsync(stream.fileno())
    publish(partial,target)
    save(folder/'native-render.json',dict(runtime=info,frames=frames,output=str(target),evidence=str(job),decode='passed',
                                          encoder=encode[encode.index('-c:v')+1]))
    return target

def _encoder_failure(partial):
    """The capture report's encoder failure (ffmpeg exit + stderr tail), or None when the encoder did not fail
    (Chrome, page or seek failures are not retried on another encoder)."""
    try:report=json.loads(Path(str(partial)+'.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    exit_code=report.get('encoderExit') if isinstance(report,dict) else None
    if exit_code is None:return None
    return f'ffmpeg exit {exit_code}: '+str(report.get('encoderErrors') or '')[-400:]

def _wait_layout_progress(proc,job,idle_timeout=120):
    """Bound lack of progress, not the length of a finite evidence capture list.

    6-00 (2026-10-09): this loop ends — progress counts only NEW png names and the capture list is finite
    (overlap candidates x 9 + contrast samples); a total cap was tried in B4 and removed after review: it could cut a
    legitimate long check (the 120 s total limit was removed for the same reason on 2026-09-2x).

    Each new PNG belongs to this unique job and is preserved as diagnostic evidence.
    Rewriting an existing file is not progress. CDP calls retain their own20s timeout.
    """
    last_progress=time.monotonic();seen=set()
    while True:
        try:return proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            now=time.monotonic()
            current={p.name for p in Path(job).glob('*.png') if p.is_file() and p.stat().st_size>0}
            if current-seen:last_progress=now;seen.update(current)
            if now-last_progress>=idle_timeout:
                raise subprocess.TimeoutExpired(proc.args,idle_timeout)

def _browser_job(folder,job,script,partial,frames,info,mode='capture',encode=None):
    from film_editor import process_directory
    env={**os.environ,'VOLCANO_NATIVE_CHROME':info['chrome'],'VOLCANO_NATIVE_FFMPEG':info['ffmpeg']}
    # Capture mode: the encoder argv chosen in Python (render_document). Node has no encoder of its own.
    if encode is not None:env['VOLCANO_NATIVE_ENCODE']=json.dumps([str(a) for a in encode])
    logs=job/'logs';logs.mkdir()
    # Keep the whole browser workspace addressable below Windows MAX_PATH.
    # Preserve the main-module alias: Node otherwise realpaths it back to the
    # long target before Chrome can start. Python receipts retain original paths.
    with process_directory(folder, force_alias=True) as child_root,(logs/'stdout.log').open('wb') as out,(logs/'stderr.log').open('wb') as err:
        child_root=Path(child_root);child_job=child_root/job.relative_to(folder)
        proc=subprocess.Popen([info['node'],'--preserve-symlinks-main',str(child_job/script.name),str(child_root/'index.html'),str(child_job/partial.name),'0',str(frames),mode],cwd=str(child_root),stdout=out,stderr=err,env=env,start_new_session=os.name!='nt')
        try:code=_wait_layout_progress(proc,job) if mode in ("layout","motion") else proc.wait(timeout=max(120,frames*3))
        except BaseException:
            # Windows terminate() kills Node before it can clean up Chrome.
            # Terminate its owned process tree while the parent PID still exists.
            if os.name=='nt':
                subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=15)
                proc.wait(timeout=8)
            else:
                # The dedicated session includes Node wrappers, Chrome and FFmpeg.
                # Killing just the immediate Node PID can leave these children alive.
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    proc.poll()
                    try:os.killpg(proc.pid,0)
                    except ProcessLookupError:break
                    time.sleep(.05)
                else:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                proc.wait(timeout=8)
            raise
        finally:
            # Snapshot/evidence filenames must still work after the temporary
            # Windows junction is removed. Keep failed reports as diagnostics too.
            report=Path(str(partial)+'.json')
            try:data=json.loads(report.read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
            else:
                prefix=str(child_job)
                def original_paths(value):
                    if isinstance(value,str) and value.startswith(prefix+os.sep):return str(job)+value[len(prefix):]
                    if isinstance(value,list):return [original_paths(item) for item in value]
                    if isinstance(value,dict):return {key:original_paths(item) for key,item in value.items()}
                    return value
                save(report,original_paths(data))

    return code

def check_document(folder,*,motion_only=False):
    """Inspect actual browser text geometry; retain findings for the layout gate.

    This supplements the existing checker while motion/contrast parity is audited.
    Geometry candidates are evidence, not a claim of final visual approval.
    """
    folder=Path(folder).resolve();info=runtime()
    job=Path(tempfile.mkdtemp(prefix='native-layout-',dir=folder))
    script=job/'capture.cjs';script.write_text(CAPTURE,encoding='utf-8')
    output=job/'layout'
    code=_browser_job(folder,job,script,output,1,info,mode='motion' if motion_only else 'layout')
    if code:
        # CDP transport timeouts do not establish a defect in the authored plan.
        # Preserve content failures if they were observed before the timeout.
        try:failure=json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):failure={}
        try:stderr=(job/'logs/stderr.log').read_text(encoding='utf-8',errors='replace')
        except OSError:stderr=''
        transport_timeout=any(line.startswith(('Error: CDP timeout ', 'Error: CDP pipe ', 'Error: Chrome exited', 'Error: Chrome launch: ')) for line in stderr.splitlines())
        content_failure=bool(failure.get('runtimeErrors') or failure.get('resourceErrors'))
        action='repair_environment' if transport_timeout and not content_failure else 'edit_plan'
        message='브라우저 연결이 종료됐거나 응답 시간이 초과됐습니다. 실행 환경을 확인하세요. 기존 제작표와 결과는 보존했습니다. ' if action=='repair_environment' else '브라우저 화면 검사 실패. '
        raise ProductionError('graphic_layout_failed',message+'진단 보존: '+str(job),action=action)
    report=json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
    if not report.get('success') or not report.get('layout'):
        raise ProductionError('graphic_layout_invalid','브라우저 화면 검사 결과가 없습니다.',action='edit_plan')
    from PIL import Image
    import numpy as np
    for evidence in report['layout'].get('inkEvidence',[]):
        if 'files' not in evidence:
            evidence['status']='unresolved';continue
        def pixels(name):
            with Image.open(evidence['files'][name]) as image:
                return np.asarray(image.convert('RGB'),dtype=np.int16)
        original,wrapped=pixels('original'),pixels('wrapped')
        # Wrapping must not change rendering; otherwise the isolation is invalid.
        if original.shape!=wrapped.shape or np.any(original!=wrapped):
            evidence['status']='unresolved_wrapper_changed_render';continue
        if 'restored' not in evidence['files']:
            evidence['status']='unresolved_restoration_not_verified';continue
        restored=pixels('restored')
        if original.shape!=restored.shape or np.any(original!=restored):
            evidence['status']='unresolved_restoration_changed_render';continue
        background=pixels('background')
        if 'prepaint' in evidence['files']:
            prepaint=pixels('prepaint')
            if prepaint.shape!=original.shape:
                evidence['status']='unresolved_prepaint_shape_changed';continue
            evidence['prepaint_changed_pixels']=int(np.count_nonzero(np.any(prepaint!=original,axis=2)))
            evidence['prepaint_max_channel_delta']=int(np.max(np.abs(prepaint-original)))
            # Same existing ink-mask heuristic; preparation must not move/add/remove ink.
            before=np.max(np.abs(prepaint-background),axis=2)>8
            after=np.max(np.abs(original-background),axis=2)>8
            evidence['prepaint_support_changed_pixels']=int(np.count_nonzero(before!=after))
            if evidence['prepaint_support_changed_pixels']:
                evidence['status']='unresolved_prepaint_ink_changed';continue
        a,b=pixels('a'),pixels('b')
        if a.shape!=background.shape or b.shape!=background.shape:
            evidence['status']='unresolved_shape_changed';continue
        # Ignore <=8/255 raster noise; threshold is an explicit local heuristic,
        # not an external standard or perceptual-equivalence guarantee.
        mask_a=np.max(np.abs(a-background),axis=2)>8
        mask_b=np.max(np.abs(b-background),axis=2)>8
        evidence['overlap_pixels']=int(np.count_nonzero(mask_a & mask_b))
        evidence['a_pixels']=int(np.count_nonzero(mask_a));evidence['b_pixels']=int(np.count_nonzero(mask_b))
        evidence['exact_a_pixels']=int(np.count_nonzero(np.any(a!=background,axis=2)))
        evidence['exact_b_pixels']=int(np.count_nonzero(np.any(b!=background,axis=2)))
        if ((evidence['exact_a_pixels']==0 and evidence['b_pixels']>0) or
                (evidence['exact_b_pixels']==0 and evidence['a_pixels']>0)):
            evidence['status']='one_text_not_painted_at_sample'
        elif not evidence['a_pixels'] or not evidence['b_pixels']:
            # Faint fade-in ink can fall below the noise heuristic. Prove
            # separation with every changed pixel instead, but only when the
            # unprepared frame is exactly preserved (not merely threshold-equal).
            exact_a=np.any(a!=background,axis=2)
            exact_b=np.any(b!=background,axis=2)
            evidence['exact_overlap_pixels']=int(np.count_nonzero(exact_a & exact_b))
            exact_proof=('prepaint' in evidence['files'] and
                         evidence.get('prepaint_changed_pixels')==0 and
                         evidence['exact_a_pixels']>0 and evidence['exact_b_pixels']>0 and
                         evidence['exact_overlap_pixels']==0)
            evidence['status']='exact_disjoint_faint_ink' if exact_proof else 'unresolved_no_visible_ink'
        else:
            evidence['status']='ink_overlap_candidate' if evidence['overlap_pixels'] else 'no_painted_overlap_at_sample'
    for row in report['layout'].get('motion',[]):
        if 'samples' not in row:continue
        row['mismatches']=[{'phase':v['phase'],'t':v['t'],'expected':v['expected'],'actual':v['actual']} for v in row['samples'] if not all(motion_state_matches(a,v['expected']) for a in v['actual'])]
        row['status']='state_mismatch' if row['mismatches'] else 'states_verified'
    assess_contrast(report)
    save(folder/'native-layout.json',report)
    failures=[row for row in report['layout'].get('motion',[]) if row.get('status') in ('target_missing','state_mismatch')]
    if failures:
        raise ProductionError('graphic_motion_failed','선언한 모션과 실제 화면 값이 다릅니다. 진단 보존: '+str(folder/'native-layout.json'),action='edit_plan')
    return report



def assess_contrast(report):
    """Conservative diagnostics from hidden-text background pixels and CSS paint.

    WCAG math/thresholds: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
    Sampling and unsupported paint handling are local diagnostics, not certification.
    """
    import re
    import numpy as np
    from PIL import Image
    def luminance(rgb):
        v=rgb/255.0
        v=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
        return v@np.array([.2126,.7152,.0722])
    for evidence in report.get('layout',{}).get('contrastEvidence',[]):
        files=evidence['files']
        images={}
        for k in ('original','wrapped','background'):
            with Image.open(files[k]) as image:images[k]=np.asarray(image.convert('RGB'),dtype=np.float64)
        invariant=images['original'].shape==images['wrapped'].shape and np.array_equal(images['original'],images['wrapped'])
        restored=None
        if 'restored' in files:
            with Image.open(files['restored']) as image:restored=np.asarray(image.convert('RGB'),dtype=np.float64)
        restoration_invariant=restored is not None and restored.shape==images['original'].shape and np.array_equal(restored,images['original'])
        bg=images['background'];height,width=bg.shape[:2]
        for item in evidence['candidates']:
            item['status']='unresolved'
            if not invariant:item['reason']='wrapper_changed_render';continue
            if restored is None:item['reason']='restoration_not_verified';continue
            if not restoration_invariant:item['reason']='restoration_changed_render';continue
            if item.get('unsupported'):item['reason']='unsupported_paint';continue
            if abs(item.get('opacity',0)-1)>1e-6:item['reason']='transitional_opacity';continue
            match=re.fullmatch(r'rgba?\(([^)]+)\)',item.get('foreground',''))
            if not match:item['reason']='unsupported_color';continue
            try:color=[float(v.strip()) for v in match[1].split(',')]
            except ValueError:item['reason']='unsupported_color';continue
            if len(color) not in (3,4) or not all(np.isfinite(color)):item['reason']='unsupported_color';continue
            alpha=(color[3] if len(color)==4 else 1)*item['opacity'];parts=[];visible_pixels=0
            for box in item.get('boxes',[]):
                x0=max(0,int(np.floor(box['left'])));x1=min(width,int(np.ceil(box['right'])))
                y0=max(0,int(np.floor(box['top'])));y1=min(height,int(np.ceil(box['bottom'])))
                if x1>x0 and y1>y0:
                    parts.append(bg[y0:y1,x0:x1].reshape(-1,3))
                    visible_pixels+=int(np.count_nonzero(np.max(np.abs(images['original'][y0:y1,x0:x1]-bg[y0:y1,x0:x1]),axis=2)>8))
            if not parts:item['reason']='outside_canvas';continue
            item['visible_difference_pixels']=visible_pixels
            if not visible_pixels:item['reason']='no_visible_ink';continue
            pixels=np.concatenate(parts);paint=np.array(color[:3])*alpha+pixels*(1-alpha)
            lb,lf=luminance(pixels),luminance(paint)
            ratios=(np.maximum(lb,lf)+.05)/(np.minimum(lb,lf)+.05)
            # 18pt regular or14pt bold at96 CSS px/in. Never round ratios to pass.
            weight=item.get('font_weight','400');bold=weight=='bold' or (weight.isdigit() and int(weight)>=700)
            threshold=3 if item['font_size']>=24 or (bold and item['font_size']>=14*96/72) else 4.5
            item.update(min_ratio=float(ratios.min()),median_ratio=float(np.median(ratios)),threshold=threshold,
                        sampled_pixels=len(ratios),below_threshold_fraction=float(np.mean(ratios<threshold)))
            item['status']='low_contrast_candidate' if item['min_ratio']<threshold else 'sampled_background_contrast_passed'
    return report

def require_resolved_layout(folder,report):
    """Do not turn recorded, unresolved layout findings into a successful receipt.

    Range intersections alone are not proven collisions. Only the corresponding
    isolated-pixel evidence may clear an overlap; clipping still needs correction
    or better evidence. This is a geometry gate, not contrast/style approval.
    """
    layout=report.get('layout',{})
    if not report.get('success') or not layout.get('samples') or not isinstance(layout.get('issues'),list):
        raise ProductionError('graphic_layout_invalid','글자 배치 검사 표본이나 판정 목록이 없습니다.',action='edit_plan')
    pending=[];cleared=[]
    for issue_index,issue in enumerate(layout['issues']):
        matches=[e for e in layout.get('inkEvidence',[]) if
                 e.get('t')==issue.get('t') and e.get('node_keys')==issue.get('node_keys')]
        # Match the exact pair and timestamp; a clean result elsewhere is irrelevant.
        proven=(issue.get('type')=='text_overlap_candidate' and
                len(issue.get('node_keys',[]))==2 and len(matches)==1 and
                matches[0].get('status')=='no_painted_overlap_at_sample' and
                matches[0].get('overlap_pixels')==0 and
                matches[0].get('a_pixels',0)>0 and matches[0].get('b_pixels',0)>0)
        # Exact pixel equality only: a faint text below the noise heuristic is
        # not sufficient. This clears collision, never readability/contrast.
        proven=proven or (issue.get('type')=='text_overlap_candidate' and
                len(issue.get('node_keys',[]))==2 and len(matches)==1 and
                matches[0].get('status')=='one_text_not_painted_at_sample' and
                matches[0].get('overlap_pixels')==0 and
                ((matches[0].get('exact_a_pixels')==0 and matches[0].get('b_pixels',0)>0) or
                 (matches[0].get('exact_b_pixels')==0 and matches[0].get('a_pixels',0)>0)))
        proven=proven or (issue.get('type')=='text_overlap_candidate' and
                len(issue.get('node_keys',[]))==2 and len(matches)==1 and
                matches[0].get('status')=='exact_disjoint_faint_ink' and
                matches[0].get('prepaint_changed_pixels')==0 and
                matches[0].get('exact_overlap_pixels')==0 and
                matches[0].get('exact_a_pixels',0)>0 and matches[0].get('exact_b_pixels',0)>0)
        proven=proven or (issue.get('type')=='text_paint_overlap' and issue.get('paint',{}).get('verified') is True)
        transitions=[e for e in layout.get('viewportTransitions',[]) if e.get('issue_index')==issue_index]
        proven=proven or (issue.get('type') in ('text_outside_canvas','text_clipped') and
                         len(transitions)==1 and transitions[0].get('verified') is True)
        focus=[e for e in layout.get('focusTransitions',[]) if e.get('issue_index')==issue_index and e.get('verified') is True]
        if issue.get('type')=='text_overlap_candidate' and len(focus)==1:
            f=focus[0]
            ends=[e for e in layout.get('inkEvidence',[]) if abs(e.get('t',-1)-f['end'])<1e-6 and e.get('node_keys')==issue.get('node_keys')]
            end_clear=(len(ends)==1 and ends[0].get('status')=='no_painted_overlap_at_sample' and ends[0].get('overlap_pixels')==0 and ends[0].get('a_pixels',0)>0 and ends[0].get('b_pixels',0)>0)
            proven=proven or bool(f.get('range_separated_at_end') or end_clear)
        (cleared if proven else pending).append(issue)
    layout['geometryGate']={'status':'review_required' if pending else 'passed',
                            'pending':pending,'cleared_overlap_candidates':cleared,
                            'scope':'Sampled text geometry only; not contrast, whole-video or style approval'}
    path=Path(folder)/'native-layout.json';save(path,report)
    if pending:
        raise ProductionError('graphic_layout_review_required',
                              '글자 잘림·겹침 검사에서 확인이 필요한 항목이 남았습니다. 제작 전 수정·재검사하세요. 진단: '+str(path),
                              action='edit_plan')
    return layout['geometryGate']

# GSAP child.startTime() rounds to seven decimals. Viewport eligibility uses
# that same start clock; measured poses and settled canvas bounds remain mandatory.
CAPTURE = 'const fs=require(\'fs\'),path=require(\'path\'),os=require(\'os\'),{spawn}=require(\'child_process\'),{pathToFileURL}=require(\'url\'),{once}=require(\'events\');\nconst sleep=ms=>new Promise(r=>setTimeout(r,ms));\n(async()=>{\n const [html,out,startArg=\'0\',framesArg=\'30\',mode=\'capture\']=process.argv.slice(2),start=Number(startArg),frames=Number(framesArg);\n if(!html||!out||!Number.isFinite(start)||!Number.isInteger(frames)||frames<1)throw Error(\'html output start frames required\');\n const profile=fs.mkdtempSync(path.join(path.dirname(out),\'native-chrome-\'));\n const chrome=process.env.VOLCANO_NATIVE_CHROME;\n const started=performance.now();let browser,encoder,sessionId,transportError,closing=false,errors=\'\',encoderExit=null,pending=new Map(),seq=0,rows=[],success=false,layout=null,runtimeErrors=[],resourceErrors=[],resourceNotes=[],requests=new Map();\n process.once(\'SIGTERM\',()=>{if(encoder)encoder.kill();if(browser)browser.kill();process.exit(143);});\n try{\n  browser=spawn(chrome,[\'--headless=new\',\'--disable-background-networking\',\'--no-first-run\',\'--no-default-browser-check\',\'--allow-file-access-from-files\',\'--hide-scrollbars\',\'--mute-audio\',\'--force-device-scale-factor=1\',\'--remote-debugging-pipe\',\'--user-data-dir=\'+profile,\'about:blank\'],{stdio:[\'ignore\',\'ignore\',\'ignore\',\'pipe\',\'pipe\']});\n  // Chrome CDP pipe: fd3 commands, fd4 NUL-delimited responses.\n  // https://github.com/GoogleChrome/chrome-launcher/blob/main/src/chrome-launcher.ts\n  // Avoid Node22 Undici\'s 4MiB permessage-deflate decompression limit.\n  const failTransport=error=>{if(closing)return;transportError=error;for(const p of pending.values()){clearTimeout(p.timer);p.reject(error);}pending.clear();};\n  const receive=data=>{const p=pending.get(data.id);\n   if(data.method===\'Network.requestWillBeSent\')requests.set(data.params.requestId,{url:data.params.request.url,type:data.params.type});\n   if(data.method===\'Network.loadingFailed\'){\n    const request=requests.get(data.params.requestId)||{},finding={...request,error:data.params.errorText,canceled:!!data.params.canceled};\n    // Chromium may cancel an obsolete media range when seeking. Decoded-frame\n    // checks still require the active source/time; other missing resources fail.\n    if(finding.canceled&&request.type===\'Media\')resourceNotes.push(finding);else resourceErrors.push(finding);\n   }\n   if(data.method===\'Network.responseReceived\'&&data.params.response.status>=400)resourceErrors.push({url:data.params.response.url,type:data.params.type,status:data.params.response.status});\n   if(data.method===\'Runtime.exceptionThrown\')runtimeErrors.push({type:\'page_exception\',details:data.params.exceptionDetails});\n   if(data.method===\'Runtime.consoleAPICalled\'&&data.params.type===\'error\')runtimeErrors.push({type:\'console_error\',args:data.params.args,stackTrace:data.params.stackTrace});\n   if(p){clearTimeout(p.timer);pending.delete(data.id);data.error?p.reject(Error(JSON.stringify(data.error))):p.resolve(data.result);}};\n  let pieces=[];\n  browser.stdio[4].on(\'data\',chunk=>{try{let start=0,end;while((end=chunk.indexOf(0,start))!==-1){pieces.push(chunk.subarray(start,end));const message=Buffer.concat(pieces).toString(\'utf8\');pieces=[];if(message)receive(JSON.parse(message));start=end+1;}if(start<chunk.length)pieces.push(chunk.subarray(start));}catch(error){failTransport(error);}});\n  browser.stdio[3].on(\'error\',error=>failTransport(Error(\'CDP pipe write: \'+error.message)));\n  browser.stdio[4].on(\'error\',error=>failTransport(Error(\'CDP pipe read: \'+error.message)));\n  browser.stdio[4].on(\'end\',()=>failTransport(Error(\'CDP pipe closed\')));\n  browser.on(\'error\',error=>failTransport(Error(\'Chrome launch: \'+error.message)));\n  browser.on(\'exit\',()=>failTransport(Error(\'Chrome exited\')));\n  const assertRuntime=()=>{if(runtimeErrors.length||resourceErrors.length)throw Error(\'Composition runtime/resource error: \'+JSON.stringify({runtimeErrors,resourceErrors}));};\n  const call=(method,params={})=>new Promise((resolve,reject)=>{if(transportError){reject(transportError);return;}const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error(\'CDP timeout \'+method));},20000);pending.set(id,{resolve,reject,timer});browser.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+\'\\0\');});\n  // https://github.com/ChromeDevTools/devtools-protocol/blob/master/pdl/domains/Page.pdl\n  // Every PNG screenshot (frames, layout evidence) goes through this one call. optimizeForSpeed: official Page.pdl\n  // captureScreenshot «Optimize image encoding for speed, not for resulting size» — still lossless PNG. 2026-10-22\n  // measured 1920x1080: encoding was 75-95% of each frame (Windows 584→119 ms, macOS 398→95 ms); a slower PC\n  // took 3-4 s per frame and crossed the 20 s CDP call limit below.\n  const screenshot=clip=>call(\'Page.captureScreenshot\',{format:\'png\',clip,captureBeyondViewport:false,optimizeForSpeed:true});\n  const FULL_FRAME={x:0,y:0,width:1920,height:1080,scale:1};\n  const evaluate=async expression=>{const r=await call(\'Runtime.evaluate\',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails){runtimeErrors.push({type:\'evaluation_exception\',details:r.exceptionDetails});throw Error(JSON.stringify(r.exceptionDetails));}assertRuntime();return r.result.value;};\n  const target=await call(\'Target.createTarget\',{url:\'about:blank\'});\n  sessionId=(await call(\'Target.attachToTarget\',{targetId:target.targetId,flatten:true})).sessionId;\n  await call(\'Page.enable\');await call(\'Runtime.enable\');await call(\'Network.enable\');await call(\'Emulation.setDeviceMetricsOverride\',{width:1920,height:1080,deviceScaleFactor:1,mobile:false});await call(\'Page.navigate\',{url:pathToFileURL(path.resolve(html)).href});\n  let ready=false;for(let i=0;i<200;i++){ready=await evaluate(\'!!window.__timelines?.graphic\');if(ready)break;await sleep(50);}if(!ready)throw Error(\'Timeline missing\');\n  await evaluate(`(async()=>{document.documentElement.style.cssText+=\';width:1920px;height:1080px;overflow:hidden\';document.body.style.cssText+=\';margin:0;width:1920px;height:1080px;overflow:hidden\';await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()));return true})()`);\n  // Use the same decoded-frame seek for production capture and pixel evidence.\n  await evaluate(`(()=>{window.__nativeSeekFrame=async(t)=>{window.__timelines.graphic.seek(t,false);let states=[];for(const v of document.querySelectorAll(\'video\')){const a=+v.dataset.start,d=+v.dataset.duration,on=t>=a&&t<a+d;v.pause();v.style.visibility=on?\'visible\':\'hidden\';if(!on)continue;// Metadata alone does not mean the first image is decoded, including at currentTime=0.\nawait new Promise((resolve,reject)=>{\n const clean=()=>{clearTimeout(timer);v.removeEventListener(\'loadeddata\',ready);v.removeEventListener(\'canplay\',ready);v.removeEventListener(\'error\',failed);};\n const ready=()=>{if(v.readyState>=2){clean();resolve();}};\n const failed=()=>{clean();reject(Error(\'video load: \'+(v.error?.message||v.id)));};\n const timer=setTimeout(()=>{clean();reject(Error(\'video data timeout: \'+v.id));},10000);\n v.addEventListener(\'loadeddata\',ready);v.addEventListener(\'canplay\',ready);v.addEventListener(\'error\',failed);\n if(v.error)failed();else ready();\n});const target=+v.dataset.mediaStart+t-a;if(Math.abs(v.currentTime-target)>0.00001){await new Promise((res,rej)=>{let seek=false,frame=false;const timer=setTimeout(()=>rej(Error(\'video frame timeout\')),10000);const done=()=>{if(seek&&frame){clearTimeout(timer);res();}};v.requestVideoFrameCallback(()=>{frame=true;done();});v.addEventListener(\'seeked\',()=>{seek=true;done();},{once:true});v.currentTime=target;});}if(v.readyState<2||Math.abs(v.currentTime-target)>.04)throw Error(\'Video time mismatch\');states.push({id:v.id,actual:v.currentTime,expected:target});}await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));return states;};return true})()`);\n  if(mode===\'layout\'||mode===\'motion\'){\n   layout=mode===\'motion\'?{samples:[],issues:[]}:await evaluate(`(async()=>{\n    const duration=Number(document.querySelector(\'[data-composition-id]\')?.dataset.duration);\n    if(!Number.isFinite(duration)||duration<=0)throw Error(\'Invalid composition duration\');\n    const timeline=window.__timelines.graphic,times=new Set([0,Math.max(0,duration-1/60)]);\n    for(let t=0;t<duration;t+=1/8)times.add(t);\n    for(const child of timeline.getChildren(true,true,true))for(const t of [child.startTime(),child.endTime()])\n     for(const delta of [-1/60,0,1/60])if(t+delta>=0&&t+delta<duration)times.add(t+delta);\n    const samples=[],issues=[],nodeIds=new WeakMap();let nextNodeId=0;window.__nativeTextNodes=new Map();\n    const rect=r=>({left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height});\n    const visible=e=>{let opacity=1;for(let p=e;p;p=p.parentElement){const c=getComputedStyle(p);if(c.display===\'none\'||c.visibility===\'hidden\')return false;opacity*=Number(c.opacity);}return opacity>.01;};\n    const paintPair=(a,b)=>{\n     const x=document.getElementById(a.object_id),y=document.getElementById(b.object_id);\n     if(!x||!y)return null;\n     const depth=x.dataset.textPaintOwner===y.id?x:y.dataset.textPaintOwner===x.id?y:null;\n     if(!depth)return null;const front=depth===x?y:x;\n     if(depth.parentElement!==front.parentElement||depth.textContent!==front.textContent)return null;\n     const an=window.__nativeTextNodes.get(a.node_key),bn=window.__nativeTextNodes.get(b.node_key);\n     if(!an?.isConnected||!bn?.isConnected)return null;\n     for(const [n,owner] of [[an,x],[bn,y]])for(let p=n.parentElement;p&&p!==owner;p=p.parentElement)if(getComputedStyle(p).transform!==\'none\')return null;\n     const ds=getComputedStyle(depth),fs=getComputedStyle(front),as=getComputedStyle(an.parentElement),bs=getComputedStyle(bn.parentElement);\n     if([\'fontFamily\',\'fontSize\',\'fontWeight\',\'fontStyle\',\'letterSpacing\',\'lineHeight\',\'whiteSpace\'].some(k=>as[k]!==bs[k]))return null;\n     if([\'fontFamily\',\'fontSize\',\'fontWeight\',\'fontStyle\',\'letterSpacing\',\'lineHeight\',\'textAlign\',\'whiteSpace\',\'opacity\',\'transform\'].some(k=>ds[k]!==fs[k])||ds.transform!==\'none\')return null;\n     let dx=Number(depth.dataset.textPaintDx),dy=Number(depth.dataset.textPaintDy);\n     if(!Number.isFinite(dx)||!Number.isFinite(dy))return null;\n     for(let p=front.parentElement;p;p=p.parentElement){const c=getComputedStyle(p);if(c.transform!==\'none\'){const m=new DOMMatrixReadOnly(c.transform);if(!m.is2D)return null;[dx,dy]=[m.a*dx+m.c*dy,m.b*dx+m.d*dy];}}\n     const d=depth.getBoundingClientRect(),f=front.getBoundingClientRect();\n     if(Math.abs(d.width-f.width)>.1||Math.abs(d.height-f.height)>.1||Math.abs(d.left-f.left-dx)>.1||Math.abs(d.top-f.top-dy)>.1)return null;\n     if(!(depth.compareDocumentPosition(front)&Node.DOCUMENT_POSITION_FOLLOWING))return null;\n     return {front:front.id,depth:depth.id,expected_offset:[dx,dy],actual_offset:[d.left-f.left,d.top-f.top],verified:true};\n    };\n    for(const t of [...times].sort((a,b)=>a-b)){\n     timeline.seek(t,false);await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));\n     const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),texts=[];let n;\n     while(n=walker.nextNode()){\n      const e=n.parentElement;if(!n.textContent.trim()||!e||[\'SCRIPT\',\'STYLE\'].includes(e.tagName)||!visible(e))continue;\n      const range=document.createRange();range.selectNodeContents(n);\n      const boxes=[...range.getClientRects()].filter(r=>r.width>0&&r.height>0).map(rect);\n      if(!boxes.length)continue;\n      const id=e.closest(\'[id]\')?.id||e.tagName;\n      if(!nodeIds.has(n)){nodeIds.set(n,++nextNodeId);window.__nativeTextNodes.set(nextNodeId,n);}\n      const row={id,object_id:e.closest(\'.scene-object\')?.id,node_key:nodeIds.get(n),text:n.textContent,boxes};texts.push(row);\n      if(!e.closest(\'[data-layout-allow-overflow="true"]\'))for(const b of boxes){\n       if(b.left< -2||b.top< -2||b.right>1922||b.bottom>1082)issues.push({type:\'text_outside_canvas\',t,id,node_key:row.node_key,box:b});\n       for(let p=e;p&&p!==document.body;p=p.parentElement){const c=getComputedStyle(p),q=p.getBoundingClientRect();\n        if(([\'hidden\',\'clip\'].includes(c.overflowX)&&(b.left<q.left-2||b.right>q.right+2))||([\'hidden\',\'clip\'].includes(c.overflowY)&&(b.top<q.top-2||b.bottom>q.bottom+2))){issues.push({type:\'text_clipped\',t,id,node_key:row.node_key,clip:p.id||p.tagName,box:b});break;}\n       }\n      }\n     }\n     for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){\n      const a=texts[i],b=texts[j];\n      if(a.boxes.some(x=>b.boxes.some(y=>Math.min(x.right,y.right)-Math.max(x.left,y.left)>2&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>2))){const paint=paintPair(a,b);issues.push({type:paint?\'text_paint_overlap\':\'text_overlap_candidate\',t,ids:[a.id,b.id],node_keys:[a.node_key,b.node_key],...(paint?{paint}: {})});}\n     }\n     samples.push({t,texts});\n    }\n    const failedFonts=[...document.fonts].filter(f=>f.status===\'error\').map(f=>f.family);\n    if(failedFonts.length)throw Error(\'Font load failed: \'+failedFonts.join(\',\'));\n    return {duration,samples,issues,scope:\'Text range geometry candidates, not contrast/motion/style approval\'};\n   })()`);\n   await evaluate(`(()=>{\n    window.__nativeIsolateText=nodes=>nodes.map(n=>{\n     const p=n.parentElement,c=p&&getComputedStyle(p);\n     const textClip=c&&(c.backgroundClip===\'text\'||c.webkitBackgroundClip===\'text\');\n     const noBoxPaint=c&&(textClip||(c.backgroundColor===\'rgba(0, 0, 0, 0)\'&&c.backgroundImage===\'none\'))&&c.boxShadow===\'none\'&&[\'Top\',\'Right\',\'Bottom\',\'Left\'].every(side=>parseFloat(c[\'border\'+side+\'Width\'])===0)&&[\'::before\',\'::after\'].every(pseudo=>[\'none\',\'normal\',\'""\'].includes(getComputedStyle(p,pseudo).content));\n     const existing=p&&p.childNodes.length===1&&p.firstChild===n&&noBoxPaint;\n     const e=existing?p:document.createElement(\'span\');\n     if(!existing){e.style.display=\'contents\';n.replaceWith(e);e.appendChild(n);}\n     // A created wrapper is display:contents (no box, so layout and pixels stay identical) — opacity does not apply\n     // to an element without a box (CSS Display 3 «display: contents»), so it hides the text with inherited\n     // transparent text paints instead. An existing paint-free parent keeps opacity, which also covers its decorations.\n     const paints=existing?[[\'opacity\',\'0\']]:[[\'color\',\'transparent\'],[\'-webkit-text-fill-color\',\'transparent\'],[\'-webkit-text-stroke-color\',\'transparent\'],[\'text-decoration-color\',\'transparent\'],[\'text-emphasis-color\',\'transparent\'],[\'text-shadow\',\'none\']];\n     return {e,created:!existing,paints:paints.map(([k,v])=>[k,v,e.style.getPropertyValue(k),e.style.getPropertyPriority(k)])};\n    });\n    window.__nativeHideText=(h,hidden)=>{for(const [k,v,old,priority] of h.paints){if(hidden)h.e.style.setProperty(k,v,\'important\');else if(old)h.e.style.setProperty(k,old,priority);else h.e.style.removeProperty(k);}};\n    window.__nativeRestoreText=handles=>handles?.forEach(h=>{window.__nativeHideText(h,false);if(h.created)h.e.replaceWith(...h.e.childNodes);});\n    return true;\n   })()`);\n   layout.inkEvidence=[];\n   const candidates=layout.issues.filter(i=>i.type===\'text_overlap_candidate\');\n   for(let index=0;index<candidates.length;index++){\n    const issue=candidates[index],prefix=out+\'.ink-\'+index;\n    await evaluate(`window.__nativeSeekFrame(${issue.t})`);\n    const setup=await evaluate(`(()=>{\n     const nodes=${JSON.stringify(issue.node_keys)}.map(k=>window.__nativeTextNodes.get(k));\n     if(nodes.some(n=>!n?.isConnected))return {unavailable:\'text node changed during seek\'};\n     const rects=nodes.map(n=>{const r=document.createRange();r.selectNodeContents(n);return r.getBoundingClientRect();});\n     // Include both complete text rectangles; permit strokes/shadows around them.\n     const x=Math.max(0,Math.floor(Math.min(...rects.map(r=>r.left))-32)),y=Math.max(0,Math.floor(Math.min(...rects.map(r=>r.top))-32));\n     const right=Math.min(1920,Math.ceil(Math.max(...rects.map(r=>r.right))+32)),bottom=Math.min(1080,Math.ceil(Math.max(...rects.map(r=>r.bottom))+32));\n     if(right<=x||bottom<=y)return {unavailable:\'outside canvas\'};\n     window.__nativeInkNodes=nodes;\n     // Keep screenshot viewport constant: region clips changed glyph RGB in\n     // saved career03 controls despite unchanged DOM. Preserve exact equality gates.\n     return {clip:{x:0,y:0,width:1920,height:1080,scale:1}};\n    })()`);\n    if(setup.unavailable){layout.inkEvidence.push({t:issue.t,node_keys:issue.node_keys,unavailable:setup.unavailable});continue;}\n    const files={};\n    const snap=async name=>{const shot=await screenshot(setup.clip);files[name]=prefix+\'.\'+name+\'.png\';fs.writeFileSync(files[name],Buffer.from(shot.data,\'base64\'));};\n    await snap(\'prepaint\');\n    await evaluate(`(async()=>{window.__nativeInkSpans=window.__nativeIsolateText(window.__nativeInkNodes);window.__nativeInkSpans.forEach(h=>window.__nativeHideText(h,true));await new Promise(r=>requestAnimationFrame(r));return true})()`);\n    await snap(\'prepaint_hidden\');\n    await evaluate(`(async()=>{window.__nativeRestoreText(window.__nativeInkSpans);await new Promise(r=>requestAnimationFrame(r));return true})()`);\n    await snap(\'original\');\n    try{\n     await evaluate(`(()=>{window.__nativeInkSpans=window.__nativeIsolateText(window.__nativeInkNodes);return true})()`);\n     await snap(\'wrapped\');\n     for(const [name,hidden] of [[\'background\',[true,true]],[\'a\',[false,true]],[\'b\',[true,false]]]){\n      await evaluate(`(async()=>{window.__nativeInkSpans.forEach((h,i)=>window.__nativeHideText(h,${JSON.stringify(hidden)}[i]));await new Promise(r=>requestAnimationFrame(r));return true})()`);\n      await snap(name);\n     }\n     layout.inkEvidence.push({t:issue.t,node_keys:issue.node_keys,clip:setup.clip,files});\n    }finally{await evaluate(`(async()=>{window.__nativeRestoreText(window.__nativeInkSpans);await new Promise(r=>requestAnimationFrame(r));return true})()`);await snap(\'restored\');}\n   }\n   layout.contrastEvidence=[];\n   if(mode===\'layout\'){\n    // Five local diagnostic samples; not a full-timeline readability approval.\n    const sampleIndices=[...new Set([0,.25,.5,.75,1].map(q=>Math.round(q*(layout.samples.length-1))))];\n    for(const sampleIndex of sampleIndices){\n     const sample=layout.samples[sampleIndex];if(!sample?.texts.length)continue;\n     const prefix=out+\'.contrast-\'+sampleIndex,files={};\n     const videoStates=await evaluate(`window.__nativeSeekFrame(${sample.t})`);\n     const candidates=await evaluate(`(async()=>{\n      const keys=${JSON.stringify(sample.texts.map(n=>n.node_key))};window.__nativeContrastNodes=keys.map(k=>window.__nativeTextNodes.get(k));\n      return window.__nativeContrastNodes.map((n,i)=>{\n       if(!n?.isConnected)return {node_key:keys[i],unsupported:[\'text_node_changed\']};\n       const e=n.parentElement,c=getComputedStyle(e),range=document.createRange();range.selectNodeContents(n);\n       let opacity=1,unsupported=[];for(let p=e;p;p=p.parentElement){const s=getComputedStyle(p);opacity*=Number(s.opacity);if(s.filter!==\'none\'||s.mixBlendMode!==\'normal\')unsupported.push(\'filter_or_blend\');if(s.transform!==\'none\'){const m=new DOMMatrixReadOnly(s.transform);if(!m.is2D||Math.abs(m.a*m.d-m.b*m.c-1)>1e-6)unsupported.push(\'scaled_or_3d_text\');}}\n       if(e.ownerSVGElement)unsupported.push(\'svg_text\');const object=e.closest(\'.scene-object\');if(object&&(object.dataset.textPaintOwner||[...document.querySelectorAll(\'[data-text-paint-owner]\')].some(p=>p.dataset.textPaintOwner===object.id)))unsupported.push(\'composite_text_paint\');\n       if(c.textShadow!==\'none\'||parseFloat(c.webkitTextStrokeWidth)>0)unsupported.push(\'text_outline_or_shadow\');\n       if(c.backgroundClip===\'text\'||c.webkitBackgroundClip===\'text\')unsupported.push(\'gradient_text\');\n       const fill=c.webkitTextFillColor||c.color;\n       return {node_key:keys[i],text:n.textContent,foreground:fill,font_size:parseFloat(c.fontSize),font_weight:c.fontWeight,opacity,unsupported,boxes:[...range.getClientRects()].map(b=>({left:b.left,top:b.top,right:b.right,bottom:b.bottom}))};\n      });})()`);\n     const snap=async name=>{const shot=await screenshot(FULL_FRAME);files[name]=prefix+\'.\'+name+\'.png\';fs.writeFileSync(files[name],Buffer.from(shot.data,\'base64\'));};\n     await snap(\'original\');\n     try{\n      await evaluate(`(()=>{window.__nativeContrastSpans=window.__nativeIsolateText(window.__nativeContrastNodes.filter(n=>n?.isConnected));return true})()`);\n      await snap(\'wrapped\');\n      await evaluate(`(async()=>{window.__nativeContrastSpans.forEach(h=>window.__nativeHideText(h,true));await new Promise(r=>requestAnimationFrame(r));return true})()`);\n      await snap(\'background\');\n      layout.contrastEvidence.push({t:sample.t,candidates,files,videoStates});\n     }finally{await evaluate(`(async()=>{window.__nativeRestoreText(window.__nativeContrastSpans);await new Promise(r=>requestAnimationFrame(r));return true})()`);await snap(\'restored\');}\n    }\n   }\n   const motionPath=path.join(path.dirname(path.resolve(html)),\'motion.json\');\n   const motionSpec=JSON.parse(fs.readFileSync(motionPath,\'utf8\'));\n   if(motionSpec.schema!==\'geumbit-motion-v1\'||!Array.isArray(motionSpec.cues))throw Error(\'Invalid native motion plan\');\n   layout.motion=await evaluate(`(async()=>{\n    const cues=${JSON.stringify(motionSpec.cues)}.flatMap((cue,parent_index)=>(cue.checks||[cue]).map(c=>({...c,technique:cue.technique,parent_index}))),rows=[];\n    const canonical=expected=>Object.fromEntries(Object.entries(expected).map(([k,v])=>{if(typeof v!==\'string\'||k===\'textContent\')return [k,v];const s=document.createElement(\'span\').style;if(k.startsWith(\'--\')){s.setProperty(k,v);return [k,s.getPropertyValue(k)];}if(k in s){s[k]=v;return [k,s[k]||v];}return [k,v];}));\n    const state=(e,expected)=>Object.fromEntries(Object.entries(expected).map(([k,v])=>[k,k===\'attr\'?Object.fromEntries(Object.keys(v).map(a=>[a,e.getAttribute(a)])):k===\'textContent\'?e.textContent:typeof v===\'string\'&&k.startsWith(\'--\')?getComputedStyle(e).getPropertyValue(k).trim():typeof v===\'string\'&&k in e.style?getComputedStyle(e)[k]:gsap.getProperty(e,k)]));\n    for(let index=0;index<cues.length;index++){\n     const cue=cues[index];\n     if(!cue.expected_start||!cue.expected_end){rows.push({index,target:cue.target,technique:cue.technique,status:\'unverified_technique\'});continue;}\n     if(!Number.isFinite(cue.start)||!Number.isFinite(cue.end)||cue.start<0||cue.end<=cue.start)throw Error(\'Invalid motion cue clock\');\n     const nodes=[...document.querySelectorAll(cue.target)];\n     if(!nodes.length){rows.push({index,target:cue.target,status:\'target_missing\'});continue;}\n     const samples=[];\n     for(const [phase,t,expected] of [[\'start\',cue.start,cue.expected_start],[\'end\',cue.end,cue.expected_end],[\'reverse\',cue.start,cue.expected_start]]){\n      window.__timelines.graphic.seek(t,false);await new Promise(r=>requestAnimationFrame(r));\n      samples.push({phase,t,expected:canonical(expected),actual:nodes.map(e=>state(e,expected))});\n     }\n     rows.push({index,target:cue.target,technique:cue.technique,samples});\n    }\n    return rows;\n   })()`);\n   layout.viewportTransitions=await evaluate(`(async()=>{\n    const allCues=${JSON.stringify(motionSpec.cues)},declarations=allCues.filter(c=>c.viewport_transition),issues=${JSON.stringify(layout.issues)},out=[];\n    const visible=e=>{let a=1;for(let p=e;p;p=p.parentElement){const c=getComputedStyle(p);if(c.display===\'none\'||c.visibility===\'hidden\')return false;a*=Number(c.opacity);}return a>.01;};\n    const read=n=>{const r=document.createRange();r.selectNodeContents(n);return [...r.getClientRects()].filter(b=>b.width>0&&b.height>0);};\n    const inside=bs=>bs.length>0&&bs.every(b=>b.left>=-2&&b.top>=-2&&b.right<=1922&&b.bottom<=1082);\n    const outside=bs=>bs.length>0&&bs.every(b=>b.right<=0||b.left>=1920||b.bottom<=0||b.top>=1080);\n    for(let index=0;index<issues.length;index++){\n     const issue=issues[index];\n     if(![\'text_outside_canvas\',\'text_clipped\'].includes(issue.type)||(issue.type===\'text_clipped\'&&issue.clip!==\'graphic-scene\'))continue;\n     const n=window.__nativeTextNodes.get(issue.node_key);if(!n?.isConnected)continue;\n     const options=declarations.filter(c=>[\'pan\',\'zoom\'].includes(c.technique)&&Math.round(c.start*1e7)/1e7<=issue.t&&(issue.t<c.end||c.viewport_transition.phase===\'exit\')&&document.querySelector(c.target)?.contains(n));\n     if(options.length!==1)continue;\n     const c=options[0],target=document.querySelector(c.target),phase=c.viewport_transition.phase;\n     if(![\'enter\',\'exit\'].includes(phase))continue;\n     const axes=Object.keys(c.expected_start||{});\n     if(!axes.length||axes.some(k=>!(c.technique===\'pan\'?[\'x\',\'y\']:[\'scale\']).includes(k)||!Number.isFinite(c.expected_start[k])||!Number.isFinite(c.expected_end[k])))continue;\n     const ease=gsap.parseEase(c.ease);if(typeof ease!==\'function\')continue;\n     const poses=[];let valid=true;\n     for(const t of [c.start,issue.t,c.end]){\n      window.__timelines.graphic.seek(t,false);await new Promise(r=>requestAnimationFrame(r));\n      const q=ease(Math.max(0,Math.min(1,(t-c.start)/(c.end-c.start))));\n      const actual=Object.fromEntries(axes.map(k=>[k,Number(gsap.getProperty(target,k))]));\n      const expected=Object.fromEntries(axes.map(k=>[k,c.expected_start[k]+(c.expected_end[k]-c.expected_start[k])*q]));\n      if(axes.some(k=>!Number.isFinite(actual[k])||Math.abs(actual[k]-expected[k])>.1))valid=false;\n      poses.push({t,actual,expected,inside:inside(read(n)),outside:outside(read(n)),visible:visible(n.parentElement)});\n     }\n     const settled=phase===\'enter\'?poses[2]:poses[0],departed=phase===\'enter\'?poses[0]:poses[2];\n     const fade=allCues.find(f=>f.target===c.target&&f.technique===\'fade\'&&f.expected_end?.opacity===0&&f.start>=c.start&&(f.end<=c.end+1e-6||(f.expected_start?.opacity===0&&f.start<=c.end+1e-6)));\n     const hiddenExit=!!fade&&!departed.visible;\n     valid=valid&&settled.inside&&settled.visible&&(phase===\'exit\'?(departed.outside||hiddenExit):!departed.inside);\n     if(phase===\'exit\'&&issue.t>=c.end)valid=valid&&(poses[1].outside||(hiddenExit&&!poses[1].visible));\n     out.push({issue_index:index,target:c.target,phase,reason:c.viewport_transition.reason,start:c.start,end:c.end,poses,verified:valid});\n    }\n    return out;\n   })()`);\n   layout.focusTransitions=await evaluate(`(async()=>{\n    const cues=${JSON.stringify(motionSpec.cues.filter(c=>c.focus_transition))},issues=${JSON.stringify(layout.issues)},out=[];\n    const number=s=>{const m=/^blur\\\\(([0-9.]+)px\\\\)$/.exec(s);return m?Number(m[1]):NaN;};\n    const rects=n=>{const r=document.createRange();r.selectNodeContents(n);return [...r.getClientRects()].filter(b=>b.width>0&&b.height>0);};\n    const visible=e=>{let a=1;for(let p=e;p;p=p.parentElement){const c=getComputedStyle(p);if(c.display===\'none\'||c.visibility===\'hidden\')return false;a*=Number(c.opacity);}return a>.01;};\n    const inside=bs=>bs.length&&bs.every(b=>b.left>=-2&&b.top>=-2&&b.right<=1922&&b.bottom<=1082);\n    for(let index=0;index<issues.length;index++){\n     const issue=issues[index];if(issue.type!==\'text_overlap_candidate\'||issue.node_keys?.length!==2)continue;\n     const ns=issue.node_keys.map(k=>window.__nativeTextNodes.get(k));if(ns.some(n=>!n?.isConnected))continue;\n     const options=cues.filter(c=>c.technique===\'focus\'&&c.start<=issue.t+1e-6&&issue.t<c.end&&ns.every(n=>document.querySelector(c.target)?.contains(n)));\n     if(options.length!==1)continue;\n     const c=options[0],target=document.querySelector(c.target),from=number(c.expected_start?.filter),to=number(c.expected_end?.filter),ease=gsap.parseEase(c.ease);\n     if(!(from>0)||to!==0||typeof ease!==\'function\')continue;\n     const samples=[];let valid=true;\n     for(const t of [c.start,issue.t,c.end]){\n      window.__timelines.graphic.seek(t,false);await new Promise(r=>requestAnimationFrame(r));\n      const expected=from*(1-ease(Math.max(0,Math.min(1,(t-c.start)/(c.end-c.start))))),actual=number(getComputedStyle(target).filter);\n      if(!Number.isFinite(actual)||Math.abs(actual-expected)>.001)valid=false;\n      const bs=ns.map(rects),separated=bs[0].every(a=>bs[1].every(b=>a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top));\n      samples.push({t,expected,actual,visible:ns.every(n=>visible(n.parentElement)),inside:bs.every(inside),range_separated:separated});\n     }\n     valid=valid&&samples[1].actual>0&&samples[2].visible&&samples[2].inside;\n     out.push({issue_index:index,target:c.target,start:c.start,end:c.end,node_keys:issue.node_keys,reason:c.focus_transition.reason,samples,verified:valid,range_separated_at_end:samples[2].range_separated});\n    }\n    return out;\n   })()`);\n   layout.snapshots=[];\n   // Store the first candidate and final sampled state for direct review.\n   // These show text geometry; they are not a full timed-video render.\n   const views=[...new Set([layout.issues[0]?.t,layout.samples.at(-1)?.t].filter(t=>t!==undefined))];\n   for(const t of views){\n    await evaluate(`window.__nativeSeekFrame(${t})`);\n    const shot=await screenshot(FULL_FRAME);\n    const filename=out+\'.review-\'+layout.snapshots.length+\'.png\';fs.writeFileSync(filename,Buffer.from(shot.data,\'base64\'));\n    layout.snapshots.push({t,path:filename,scope:\'Text layout evidence with decoded video seek; not full-video approval\'});\n   }\n   assertRuntime();success=true;return;\n  }\n  encoder=spawn(process.env.VOLCANO_NATIVE_FFMPEG,[\'-y\',\'-v\',\'error\',\'-f\',\'image2pipe\',\'-framerate\',\'60\',\'-vcodec\',\'png\',\'-i\',\'pipe:0\',\'-an\',\'-frames:v\',String(frames),...JSON.parse(process.env.VOLCANO_NATIVE_ENCODE),\'-pix_fmt\',\'yuv420p\',out],{stdio:[\'pipe\',\'ignore\',\'pipe\']});encoder.stderr.on(\'data\',b=>errors+=b.toString());encoder.stdin.on(\'error\',()=>{});const encoded=once(encoder,\'close\');\n  for(let i=0;i<frames;i++){\n   const t=start+i/60;\n   const videos=await evaluate(`window.__nativeSeekFrame(${t})`);\n   const shot=await screenshot(FULL_FRAME);\n   if(!encoder.stdin.write(Buffer.from(shot.data,\'base64\'))){\n    // An encoder that exits early never drains: stop capturing and report its exit below.\n    await Promise.race([once(encoder.stdin,\'drain\'),encoded]);if(encoder.exitCode!==null||encoder.signalCode!==null)break\n   };rows.push({frame:i,t,videos});\n  }\n  encoder.stdin.end();const [code]=await encoded;if(code!==0){encoderExit=String(code);throw Error(\'ffmpeg \'+errors)};assertRuntime();success=true;\n }finally{\n  closing=true;for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error(\'Closed\'));}pending.clear();if(browser?.stdio[3])browser.stdio[3].end();\n  if(encoder&&!success){\n   // FFmpeg may still be waiting for the next PNG packet when a page seek fails.\n   // Close its input before signalling, then bound cleanup of the owned process.\n   encoder.stdin.destroy();encoder.kill();\n   if(encoder.exitCode===null&&encoder.signalCode===null){await Promise.race([once(encoder,\'close\'),sleep(1000)]);}\n   if(encoder.exitCode===null&&encoder.signalCode===null){encoder.kill(\'SIGKILL\');await Promise.race([once(encoder,\'close\'),sleep(1000)]);}\n  }if(browser&&browser.exitCode===null){browser.kill();await Promise.race([once(browser,\'close\'),sleep(3000)]);}\n  fs.writeFileSync(out+\'.json\',JSON.stringify({success,encoderExit,encoderErrors:encoderExit===null?\'\':errors,actualOS:process.platform,captureFormat:\'png\',elapsedSeconds:(performance.now()-started)/1000,start,frames,rows,layout,runtimeErrors,resourceErrors,resourceNotes,scope:\'Native CDP capture or layout evidence; not whole-video/audio approval\'},null,2));\n }\n console.log(\'Captured\',frames,\'frames on\',process.platform);\n})().catch(e=>{console.error(e);process.exitCode=1;});\n'
