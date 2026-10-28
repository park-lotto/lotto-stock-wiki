"""Source-only approved texture/color + evidence-bound subject crop.

Never modifies source audio or overlays. Requires a dense accepted subject
receipt from the existing selection system, not a guessed center coordinate.

■ 2026-10-05 (사장님 결정 1) — 화면 처리 Real-ESRGAN → ACNet F8B4 HDN(CPU onnxruntime · longform_video_tools).
  흐름: 원본 → 60fps 격자 · 절반 크기 · yuv444p(원본 Y 그대로) 를 파이프로 → 루마만 ACNet 2배 · 색차는 절반 크기 그대로 →
  피사체 구도 상자로 세 평면을 한 번씩 확대(PIL resize box) → 승인 후처리(POST) → x264 60fps.
  · 프레임 수: 디코더가 정확히 `frames` 장을 내야 하고(모자라면 멈춤) 인코더 출력도 다시 센다(ffprobe count_frames).
  · 30fps 원본을 60fps 격자로 늘린 같은 그림(바이트 동일한 연속 프레임)은 망을 한 번만 돌린다(W2-30 · 결과 바이트 동일).
    구도 상자는 60fps 매 장 다르므로 확대·인코딩은 매 장 한다.
  · 색(w3 검토 major · 10-06): 롱폼의 다른 장면(사진·그래픽·자막·배지·엔드카드)은 전부 «RGB 내용 → ffmpeg 기본 변환 · 색 표식 없음»
    으로 인코딩된다(운영 Real-ESRGAN 처리 영상도 rgb24 파이프라 같았다). 처리 영상만 원본 YUV(BT.709)와 표식을 그대로 두면 장면이
    바뀔 때 같은 겹침 색이 튀고(배지 ΔE 2.96 · 운영 0.13) 몽타주는 첫 컷의 표식이 편 전체를 정했다. 그래서 인코더 입구에서
    원본의 색 행렬(colorspace)로 RGB 로 바꾸고 표식을 지운 뒤(운영의 PNG 추출과 같은 행렬 선택) 승인 후처리(POST)를 건다 →
    출력은 다른 장면과 같은 관례(표식 없음). PQ·HLG 원본도 운영과 같이 톤 매핑 없이 행렬만 쓴다(운영과 같은 동작 · 새 결정 아님).
  · 캐시: 결과는 장면 폴더가 아니라 `geumbit/video-treatment` 공용 자리에 «계산된 처리법» 열쇠로 둔다(원장 §6-2) —
    코드 파일 통째 지문 대신 실제 추출 명령·구도 표본·망 지문·후처리·인코딩 인자·픽셀을 만드는 함수 본문만 열쇠에 든다.
    그래서 다른 파일(피사체 측정·검수 코드)을 고쳐도 같은 처리법이면 다시 처리하지 않는다.
"""
from pathlib import Path
import contextlib
import inspect
import json
import shutil
import subprocess
import uuid
from film_editor import command, digest, file_digest, file_lock
from longform_state import Stages, ProductionError, native_path, read, save, replace as publish
from longform_reframe import from_focus_receipt, fixed_framing
from longform_video_tools import ensure_tools

PROFILE='dramario-subject-v1'
POST='smartblur=2.5:0.9:6,unsharp=5:5:4.0,eq=contrast=1.15:gamma=1.37:saturation=1.9,lutyuv=u=val-4:v=val+1'
RECIPE='acnet-f8b4-hdn-yuv444-v2'
# ■ 2026-10-22 (신고 #81 · 사장님 «바로 고쳐라») — 화면 처리를 컷마다 필요한 만큼만(서버 video_treatment.look·strength).
#   · look 'full'(값 없음 = 옛 판 그대로): 절반 크기 → ACNet 2배 → POST. 처리법 열쇠(pixel_code·decode·encoder argv)가 옛 판과 바이트까지
#     같아 진행 중 작업의 처리 결과를 다시 만들지 않는다.
#   · look 'auto'(서버가 기록 영상 origin=record 에만 준다): 원본이 출력 크기 이상이면 ACNet 을 건너뛰고 원본 크기 그대로
#     디코드해 구도 상자만 확대한다 — 1080p 원본을 절반(960×540)으로 줄였다가 망으로 되키우면 원본에 있던 세부를 버리고 질감만 남는다.
#     그 경로의 POST 기본 세기는 0: smartblur·unsharp 는 ACNet 출력을 다듬던 단계라 원본 화면에는 윤곽 테두리만 남기고(신고 «윤곽 테두리»),
#     색 보정(채도 1.9·감마 1.37·대비 1.15)은 방송 원본에 «색 과함» 으로 보였다. 원본이 출력보다 작으면 'full' 과 같다(저화질 기본값 그대로).
#   · look 'off': ACNet·POST 없이 구도·반전만(원본 크기 디코드).
#   · strength(0~1 · 있으면 어느 경로든 이 값): POST 의 각 값을 «처리 없음(0)» 과 «승인값(1)» 사이에서 선형으로. 1 은 POST 글자 그대로.
LOOKS=('auto','full','off')
RECIPE_NATIVE='native-yuv444-v1'
# 승인값(POST) 의 각 값 — strength 로 0(처리 없음) 과 이 값 사이를 선형으로 잇는다(post_filter).
_POST_AT_FULL={'blur':.9,'sharpen':4.0,'contrast':.15,'gamma':.37,'saturation':.9,'u':-4,'v':1}
# 원본에서 읽는 색 표식은 행렬 하나(swscale 의 YUV→RGB 변환이 고르는 것) — 출력에는 표식을 달지 않는다(위 «색»).
MATRIX_TAG=('color_space','-colorspace')
# RGB 로 부호화된 원본(ffprobe color_space 'gbr' · RGB 화소 형식 — PNG-in-MOV·FFV1 bgr0·H.264 RGB·VP9 gbrp)은 YUV 행렬이 없다.
# 파이프(yuv444p)를 지나는 동안만 쓰는 행렬을 하나로 못박아 디코더(RGB→YUV · out_color_matrix)와 인코더(YUV→RGB · -colorspace)가
# 같은 행렬로 짝을 이루게 한다 — 짝만 맞으면 RGB 가 그대로 되돌아오므로 어느 행렬이든 되지만, 두 기본값이 서로 맞기를 기대하지
# 않고 명시한다(w3 검토 major · 10-06: 원본 표식 'gbr' 을 그대로 -colorspace 에 넘겨 ffmpeg 가 «Unable to parse option value» 로 거부).
RGB_PIPE_MATRIX='bt709'
RGB_PIX_MARKS=('rgb','bgr','gbr','pal8','bayer')
# RGB 로 바꾼 뒤 표식을 지운다: 이 뒤의 RGB→YUV 변환(POST 앞 자동 변환)이 다른 장면과 같은 기본 행렬을 쓰고 출력에 표식이 안 남게.
TO_RGB='format=rgb24,setparams=colorspace=unknown:color_primaries=unknown:color_trc=unknown'
_FFMPEG_SHA={}


def source_frame_command(source,start,frames,half,destination,selected,attempt,source_sha,matrix=None):
    """Decoder argv: exact 60fps grid of the accepted clock → half size → raw planar yuv444p (limited range).

    `matrix` is the pipe matrix for RGB-coded sources (see RGB_PIPE_MATRIX); YUV sources keep their own matrix.
    """
    args=['ffmpeg','-y','-v','error'];grid='fps=60'
    clock=((selected or {}).get('scene_evidence') or {}).get('frame_clock')   # 확대를 끈 컷(reframe_off)은 기록이 없다 — 원본 시계
    if clock is None:args+=['-ss',start]
    else:
        import subject_frame_clock as FC
        import subject_focus as SF
        cut=dict(kind='video',src=str(source),start=start,duration=frames/60,
                 fps=60.,frame_clock=clock,clock_start=selected['scene_evidence']['start'],tracking_probe_argv=['ffprobe'])
        timeline=SF._source_timeline(cut,attempt,source_sha)
        args+=FC.input_options(cut,timeline);grid=FC.grid(cut,timeline)
    out_matrix=f':out_color_matrix={matrix}' if matrix else ''
    return args+['-i',source,'-vf',f'{grid},scale={half[0]}:{half[1]}:flags=lanczos{out_matrix}:out_range=tv,format=yuv444p',
                 '-frames:v',frames,'-f','rawvideo','-pix_fmt','yuv444p',destination]


def _rgb_coded(stream):
    pix=str(stream.get('pix_fmt') or '')
    return stream.get(MATRIX_TAG[0])=='gbr' or any(mark in pix for mark in RGB_PIX_MARKS)


def _probe(source):
    """(size, tags): tags[color_space] is the matrix the pipe is in — the encoder must convert back with exactly it.

    RGB-coded sources get RGB_PIPE_MATRIX (the decoder is told the same through pipe_matrix()); YUV sources their own tag.
    """
    raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
        'stream=width,height,color_space,pix_fmt','-of','json',str(source)],timeout=30)
    stream=json.loads(raw)['streams'][0]
    size=[stream['width'],stream['height']]
    if _rgb_coded(stream):return size,{MATRIX_TAG[0]:RGB_PIPE_MATRIX,'pipe_matrix':RGB_PIPE_MATRIX}
    matrix=stream.get(MATRIX_TAG[0])
    tags={MATRIX_TAG[0]:matrix} if isinstance(matrix,str) and matrix not in ('','unknown','unspecified','reserved') else {}
    return size,tags


def plan_look(settings,size,output):
    """(native, strength) for this cut: native = decode at source size without the ACNet upscale; strength = POST weight.

    'auto' turns native only when the source frame is at least the output size in both directions (measured by ffprobe ·
    _probe) — the server sends 'auto' only for recorded footage (plan media origin 'record'), so drawn material keeps 'full'."""
    look=settings.get('look','full')
    native=look=='off' or (look=='auto' and size[0]>=output[0] and size[1]>=output[1])
    strength=settings['strength'] if 'strength' in settings else (0 if native else 1)
    return native,strength


def post_filter(strength):
    """POST at `strength` (0..1): 1 is the approved string byte for byte (cache keys of running jobs), 0 is no filter."""
    if strength>=1:return POST
    if strength<=0:return ''
    s=strength;k={key:value*s for key,value in _POST_AT_FULL.items()}
    return (f"smartblur=2.5:{k['blur']:.4f}:6,unsharp=5:5:{k['sharpen']:.4f},"
            f"eq=contrast={1+k['contrast']:.4f}:gamma={1+k['gamma']:.4f}:saturation={1+k['saturation']:.4f},"
            f"lutyuv=u=val{k['u']:+.4f}:v=val{k['v']:+.4f}")


def encoder_command(width,height,tags,mirror=False,post=POST):
    """Encoder argv (without output path): planar yuv444p in the source matrix → RGB → untagged → POST → x264 60fps.

    The rest of the long-form (photos, graphics, captions, badge, end card) is RGB content encoded with ffmpeg's
    default conversion and no colour tags; the treated clip leaves the same way so scenes and montage cuts agree.
    """
    matrix=[MATRIX_TAG[1],tags[MATRIX_TAG[0]]] if MATRIX_TAG[0] in tags else []
    return ['ffmpeg','-y','-v','error','-f','rawvideo','-pixel_format','yuv444p','-color_range','tv',*matrix,
            '-video_size',f'{width}x{height}','-framerate','60','-i','pipe:0',
            # 좌우 반전(사장님 결정 2026-10-07 · 서버 video_treatment.mirror): 처리한 원본 화면만 뒤집는다 — 자막·그래픽·사진은 그대로.
            '-vf',TO_RGB+(','+post if post else '')+(',hflip' if mirror else ''),*encode_args(width,height)]


def encode_args(width,height):
    """Encoder argv after the filter: an encoder slot (runner/video_encoder.py — this PC's GPU pick at the same size as
    libx264 `-preset fast -crf 16`, no colour tags) · no audio · yuv420p · 4 threads · faststart.

    Its CPU form is the old argv byte for byte (`cpu_recipe` keys the cache with it — treated clips made before the GPU
    change stay valid). `-threads` stays outside the slot to keep that order; GPU encoders accept it (10-19: VideoToolbox
    on 맥미니24g, AMF on win-main — 1080p60 encodes exit 0).
    The treated clip is decoded again by its scene (never joined with `-c copy`)."""
    import video_encoder
    return ['-an',*video_encoder.x264('fast',16,width,height,60,program='ffmpeg',color=False),
            '-pix_fmt','yuv420p','-threads','4','-movflags','+faststart']


def pipe_commands(source,start,frames,half,selected,attempt,source_sha,tags,width,height,mirror=False,post=POST):
    """(decoder argv, encoder argv without output) for one pipe — both from the same probe tags, so the
    YUV matrix the decoder writes is exactly the one the encoder reads back (RGB-coded sources included)."""
    decode=source_frame_command(source,start,frames,half,'pipe:1',selected,attempt,source_sha,matrix=tags.get('pipe_matrix'))
    return decode,encoder_command(width,height,tags,mirror,post)


def _ffmpeg_identity():
    path=shutil.which('ffmpeg')
    if not path:raise ProductionError('video_tools_missing','ffmpeg가 없습니다.',action='repair_environment')
    path=str(Path(path).resolve());stat=Path(path).stat();key=(path,stat.st_size,stat.st_mtime_ns)
    if key not in _FFMPEG_SHA:_FFMPEG_SHA.clear();_FFMPEG_SHA[key]=file_digest(path)
    return _FFMPEG_SHA[key]


def treat_frames(decoder,encoder,frames,half,size,samples,tools,output):
    """Read `frames` planar yuv444p half frames, write the same number of treated output frames.

    One output frame per input frame (no drop/insert). Byte-identical consecutive inputs (60fps duplicates of a
    30fps source) reuse the previous luma inference — same bytes as running it again.
    """
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    plane=half[0]*half[1];frame=plane*3
    sx,sy=half[0]/size[0],half[1]/size[1];width,height=output
    resample=Image.Resampling.BICUBIC
    # Pillow and onnxruntime release the GIL: the three plane resamples of frame n run while frame n+1 is read and
    # inferred. Writes stay in frame order; every plane is its own deterministic resample (same bytes as serial).
    with ThreadPoolExecutor(max_workers=3) as pool:
        inferred=_treat(pool,decoder,encoder,frames,half,size,samples,tools,width,height,plane,frame,sx,sy,resample)
    if decoder.read(1):raise ProductionError('video_treatment_frames','원본 디코더가 요청보다 많은 프레임을 냈습니다.')
    return inferred


def _treat(pool,decoder,encoder,frames,half,size,samples,tools,width,height,plane,frame,sx,sy,resample):
    import numpy as np
    from PIL import Image
    from longform_video_tools import upscale_luma
    last=None;luma=u=v=None;inferred=0;pending=None
    for index in range(frames):
        raw=_read_exact(decoder,frame)
        if raw is None:raise ProductionError('video_treatment_frames',f'원본 프레임이 {index}장에서 끝났습니다({frames}장 필요).',action='edit_plan')
        if raw!=last:
            y=np.frombuffer(raw,np.uint8,plane).reshape(half[1],half[0])
            # Round once to 8-bit like the shipped shader's unorm output, then crop.
            luma=Image.fromarray(np.rint(upscale_luma(tools,y)*255).astype(np.uint8),'L')
            u=Image.frombuffer('L',(half[0],half[1]),raw[plane:2*plane],'raw','L',0,1)
            v=Image.frombuffer('L',(half[0],half[1]),raw[2*plane:],'raw','L',0,1)
            last=raw;inferred+=1
        x,y0,w,h=samples[index]['crop']
        box=(x*sx,y0*sy,(x+w)*sx,(y0+h)*sy)
        luma_box=tuple(c*2 for c in box)
        jobs=[pool.submit(image.resize,(width,height),resample,box=b) for image,b in ((luma,luma_box),(u,box),(v,box))]
        if pending:
            for job in pending:encoder.write(job.result().tobytes())
        pending=jobs
    for job in pending or []:encoder.write(job.result().tobytes())
    return inferred


def treat_native(decoder,encoder,frames,size,samples,output):
    """Native path (plan_look): `frames` planar yuv444p frames at the source size → the framing box of each, resized to the
    output. No network. Kept apart from treat_frames/_treat so the ACNet recipe (pixel_code) of running jobs stays the same."""
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    plane=size[0]*size[1];frame=plane*3;width,height=output
    resample=Image.Resampling.BICUBIC;pending=None
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index in range(frames):
            raw=_read_exact(decoder,frame)
            if raw is None:raise ProductionError('video_treatment_frames',f'원본 프레임이 {index}장에서 끝났습니다({frames}장 필요).',action='edit_plan')
            x,y0,w,h=samples[index]['crop'];box=(x,y0,x+w,y0+h)
            planes=[Image.frombuffer('L',tuple(size),raw[i*plane:(i+1)*plane],'raw','L',0,1) for i in range(3)]
            jobs=[pool.submit(image.resize,(width,height),resample,box=box) for image in planes]
            for job in pending or []:encoder.write(job.result().tobytes())
            pending=jobs
        for job in pending or []:encoder.write(job.result().tobytes())
    if decoder.read(1):raise ProductionError('video_treatment_frames','원본 디코더가 요청보다 많은 프레임을 냈습니다.')
    return 0


def _pipe_closed(error):
    """The write/close error of a pipe whose reader is gone: BrokenPipeError (EPIPE) on POSIX, OSError EINVAL on Windows.

    Same two shapes CPython's subprocess treats as «the child exited or closed the pipe» when it writes to a child's
    stdin (Lib/subprocess.py Popen._stdin_write · bpo-19612 · bpo-30418).
    """
    import errno
    return isinstance(error,BrokenPipeError) or getattr(error,'errno',None) in (errno.EPIPE,errno.EINVAL)


def _ended(process,timeout):
    """Exit code, or None when the process is still running after `timeout` seconds (then it did not end — not judged)."""
    try:return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:return None


def _encode_failed(code):
    """The encoder's own failure, named with its exit code; its stderr stays in the attempt folder (encode.log)."""
    how='실패로 끝났습니다' if code else '입력 프레임을 다 받기 전에 끝났습니다'
    return ProductionError('video_treatment_encode',
        f'영상처리 인코더(ffmpeg)가 {how}(종료 코드 {code}) — 처리 캐시 시도 폴더의 encode.log 를 보존했습니다.')


def _read_exact(stream,size):
    """One whole raw frame, None at a clean end; a torn frame is an error (never padded)."""
    chunks=[];left=size
    while left:
        data=stream.read(left)
        if not data:
            if left==size:return None
            raise ProductionError('video_treatment_frames',f'원본 프레임이 중간에 끊겼습니다({size-left}/{size} 바이트).')
        chunks.append(data);left-=len(data)
    return b''.join(chunks)


def pixel_code(native=False):
    """Sources that decide pixels (not whole-file fingerprints): edits elsewhere keep the cache."""
    if native:
        return digest({name:inspect.getsource(fn) for name,fn in (
            ('treat_native',treat_native),('read',_read_exact),('decode',source_frame_command))})
    import longform_video_tools as T
    return digest({name:inspect.getsource(fn) for name,fn in (
        ('treat_frames',treat_frames),('treat',_treat),('read',_read_exact),('decode',source_frame_command),
        ('parse',T.parse_shader),('onnx',T.onnx_model),('upscale',T.upscale_luma),('session',T.session))})


def _windows():
    import os
    return os.name=='nt'


def io_path(value):
    r"""The path Python opens on this PC. Windows: absolute + extended prefix (\\?\) without asking the file system — the
    runner's receipt contract volcano_run._review_receipt_io_path. Elsewhere: native_path (resolve), unchanged.

    Why not native_path on Windows (w3 3차 검토 minor · 10-06): native_path first calls Path.resolve() (ntpath.realpath →
    _getfinalpathname), which sends the un-prefixed long path to the file system; with long paths disabled Windows answers
    [WinError 206] and realpath re-raises it (206 is not in _getfinalpathname_nonstrict's allowed list — CPython Lib/ntpath.py).
    The subject receipt <workdir>/geumbit/focus/<64hex>.<64hex>.json is ~150 characters past the work folder, so a work folder
    of ~110+ characters died here (C2 3a28ef51 fixed the same thing in local_focus.verify_render_receipt).
    """
    if _windows():
        from volcano_run import _review_receipt_io_path
        return Path(_review_receipt_io_path(value))
    return native_path(value)


def absolute(value):
    """Absolute path for ffmpeg arguments and records — on Windows without a file-system query (see io_path)."""
    import os
    return Path(os.path.abspath(value)) if _windows() else Path(value).resolve()


def prepare(root, source, start, frames, settings, assets):
    """Treat one source window. `root` is the caller's scene folder; the result lives in the shared recipe cache.

    GPU(DirectML) 가 처리 도중 실패하면 그 장면 전체를 CPU 로 한 번 다시 한다 — 처리법 열쇠(network.provider)가 CPU 로 바뀌어
    GPU 로 반쯤 만든 결과와 섞이지 않는다(onnx_providers.with_cpu_fallback · 재시도는 그 한 번뿐)."""
    from onnx_providers import with_cpu_fallback
    return with_cpu_fallback(lambda: _prepare(root, source, start, frames, settings, assets))


def _prepare(root, source, start, frames, settings, assets):
    from longform_render import W as output_width, H as output_height
    source=absolute(source)
    try:validate_settings(settings)
    except ValueError as error:
        raise ProductionError('video_treatment_contract','영상처리에 승인된 프로필과 피사체 측정 기록이 필요합니다: '+str(error),action='edit_plan') from error
    off=reframe_off(settings)
    # 피사체 영수증·원본은 파이썬이 io_path 로 연다(윈도우 긴 경로 — io_path 머리말 · w3 3차 검토 minor). ffmpeg 인자·기록은 source(absolute).
    evidence=None if off else io_path(settings['focus_receipt'])
    source_io=io_path(source)
    selected=None
    if not off:
        selected=read(evidence)
        from local_focus import verify_render_receipt
        verify_render_receipt(settings,selected)
        if selected.get('focus_key')!=settings['focus_key']:
            raise ProductionError('video_subject_context','현재 장면 문맥과 피사체 선택 키가 다릅니다.',action='edit_plan')
    size,tags=_probe(source)
    native,strength=plan_look(settings,size,(output_width,output_height))
    post=post_filter(strength)
    # 원본 크기 그대로 쓰는 경로(native)는 망을 안 쓴다 — 망 도구를 준비·검증하지 않는다(처리법 열쇠에도 안 든다).
    tools=None if native else ensure_tools(assets)
    # film_editor.file_digest(Path.open 그대로)는 커널·영화 편집기 파일이라 고치지 않고 여는 경로를 여기서 준다.
    source_sha=file_digest(source_io);evidence_sha=None if off else file_digest(evidence)
    identity=digest({'source':source_sha,'start':start,'frames':frames,'evidence':evidence_sha,'profile':PROFILE})
    bounds=settings.get('source_crop') if off else render_bounds(selected,settings.get('source_crop'),size)
    try:framing=(fixed_framing(source_sha,start,frames,60,size,bounds) if off else
                 from_focus_receipt(selected,source_sha,start,frames,60,size,identity,bounds=bounds))
    except (ValueError,KeyError,TypeError) as exc:
        raise ProductionError('video_subject_evidence','피사체 측정 기록이 현재 영상 구간과 맞지 않습니다: '+str(exc),action='edit_plan') from exc
    half=list(size) if native else [max(2,round(n/4)*2) for n in size]
    # ★작업 폴더 아래 긴 경로(원본 시간축 영수증 <64hex>.json 등)가 윈도우 MAX_PATH 를 넘지 않게 확장 경로로(검토 minor · 옛 Frames 와 같다).
    cache=native_path(Path(assets).parent/'geumbit'/'video-treatment')
    remove_legacy_frame_cache(Path(assets).parent/'geumbit')
    probe=cache/'probe'/('decode-'+uuid.uuid4().hex)
    probe.mkdir(parents=True,exist_ok=True)
    # 인코더 argv 전체(출력 경로만 뺀 것)가 처리법 열쇠에 든다 — 입력 형식(-f rawvideo·화소 형식·크기·60fps)을 고쳐도 옛 결과를 쓰지 않게(검토 minor).
    # 인코더는 CPU 형태(예전 인자 그대로)로 든다: 처리 결과는 장면이 다시 디코드하는 중간 파일이라(-c copy 로 잇지 않음) 같은 크기
    # 같은 용량의 GPU 인코딩은 같은 처리법이다 — 이 PC 가 GPU 로 굽든 GPU 실패 뒤 CPU 로 굽든 같은 열쇠로 다시 쓰고, GPU 로 바뀐 판이
    # 나가도 예전에 처리한 영상을 망으로 다시 돌리지 않는다(2026-10-19 GPU 인코딩).
    import video_encoder
    decode,encoder_argv=pipe_commands(source,start,frames,half,selected,probe,source_sha,tags,output_width,output_height,
                                      settings.get('mirror') is True,post)
    # ACNet 경로의 열쇠는 옛 판과 같은 칸·같은 값이다(진행 중 작업의 처리 결과를 다시 만들지 않는다 · strength 1 = POST 그대로).
    recipe={'schema':RECIPE_NATIVE if native else RECIPE,'network':None if native else tools['identity'],
            'code':pixel_code(native),'ffmpeg':_ffmpeg_identity(),
            'decode':digest([str(a) for a in decode]),'framing':digest(framing['samples']),'half':half,
            'output':[output_width,output_height],'encoder':video_encoder.expand(encoder_argv,'cpu')[0]}
    sources=[p for p in ([source_io,evidence] if native else [source_io,evidence,tools['shader']]) if p is not None]

    def produce(folder):
        # This PC's encoder, then CPU once if the GPU encoder fails (video_encoder.attempts — at most two tries). The frames
        # come from the network inside the pipe, so the CPU try runs the whole pipe again in its own attempt folder.
        for gpu,encode in video_encoder.attempts(encoder_argv):
            attempt=folder/('attempt-'+uuid.uuid4().hex);attempt.mkdir()
            dest=attempt/'picture.mp4'
            try:
                with video_encoder.gpu_slots if gpu else contextlib.nullcontext():
                    inferred,count=pipe(attempt,[*encode,str(dest)])
                break
            except ProductionError as error:
                if gpu is None or error.code not in ('video_treatment_encode','video_treatment_output'):raise
                video_encoder.failed(gpu,str(error)+' · '+_log_tail(attempt/'encode.log'))
        else:
            # attempts() always ends with the CPU try (gpu None), which breaks or raises above — reaching here means that contract broke.
            raise ProductionError('video_treatment_encode','인코더 시도 목록이 CPU 시도로 끝나지 않았습니다(video_encoder.attempts 계약).',action='repair_environment')
        # Source mutation during local processing cannot publish a receipt.
        if file_digest(source_io)!=source_sha or (evidence is not None and file_digest(evidence)!=evidence_sha):
            raise ProductionError('video_treatment_changed','처리 중 원본 또는 피사체 기록이 바뀌었습니다.',action='edit_plan')
        proof=attempt/'framing.json'
        save(proof,dict(framing,profile=PROFILE,post=post,recipe=recipe['schema'],network=recipe['network'],
                        inferred_frames=inferred,verification=count,review_status='review_required'))
        result={'path':str(dest),'start':0,'frames':frames,'source_start':start,'source':str(source),
                'proof':str(proof),'profile':PROFILE,'review_status':'review_required'}
        return result,[dest,proof,attempt/'encode.log',attempt/'logs/full-decode.log']

    def pipe(attempt,args):
        """One decoder → network → encoder pipe into `args` (output path last), then the output checks.
        Returns (inferred frames, ffprobe count). Logs stay in `attempt`."""
        dest=args[-1]
        with (attempt/'decode.log').open('wb') as dlog,(attempt/'encode.log').open('wb') as elog:
            decoder=subprocess.Popen([str(a) for a in decode],stdout=subprocess.PIPE,stderr=dlog)
            encoder=subprocess.Popen(args,stdin=subprocess.PIPE,stderr=elog)
            try:
                try:
                    inferred=(treat_native(decoder.stdout,encoder.stdin,frames,size,framing['samples'],(output_width,output_height)) if native else
                              treat_frames(decoder.stdout,encoder.stdin,frames,half,size,framing['samples'],tools,(output_width,output_height)))
                    encoder.stdin.close()
                except ProductionError as short:
                    # 프레임이 모자라면 먼저 디코더가 실패로 끝났는지 본다 — 디코더 실패(코덱 미지원·손상 파일)를 «제작표 구간이
                    # 짧다(edit_plan)» 로 잘못 안내하지 않는다(w3 검토 minor). 깨끗하게 끝났는데 모자랄 때만 원래 판정 그대로.
                    if short.code=='video_treatment_frames' and decoder.wait(timeout=60):
                        raise ProductionError('video_treatment_decode',
                            f'원본 디코더가 실패로 끝났습니다(종료 코드 {decoder.returncode}) — 원본 파일을 읽지 못했습니다. '
                            '처리 캐시 시도 폴더의 decode.log 를 보존했습니다.') from short
                    raise
                except OSError as pipe:
                    # 인코더가 입력을 다 받기 전에 끝나면(인자 거부·코덱 오류) 파이프 쓰기·닫기가 실패한다(w3 3차 검토 minor ·
                    # 고치기 전에는 '[Errno 32] Broken pipe' 가 그대로 엔진의 production_failed 가 됐다). 끊긴 파이프 모양이고
                    # 인코더가 실제로 끝났을 때만 인코더 실패로 바꾼다 — 살아 있는 인코더 옆의 다른 OSError 는 이름을 바꾸지 않는다.
                    code=_ended(encoder,30) if _pipe_closed(pipe) else None
                    if code is None:raise
                    raise _encode_failed(code) from pipe
                if decoder.wait(timeout=300):raise ProductionError('video_treatment_decode','원본 프레임 읽기 실패; 로그를 보존했습니다.')
                code=encoder.wait(timeout=600)
                if code:raise _encode_failed(code)
            except BaseException:
                for p in (decoder,encoder):
                    p.kill();p.wait()
                raise
            finally:
                decoder.stdout.close()
        command(attempt,['ffmpeg','-v','error','-xerror','-i',dest,'-f','null','-'],'full-decode',timeout=1800)
        count=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=nb_read_frames,width,height','-of','json',str(dest)],timeout=180))['streams'][0]
        if int(count['nb_read_frames'])!=frames or [count['width'],count['height']]!=[output_width,output_height]:
            raise ProductionError('video_treatment_output','완성 프레임 수 또는 크기가 다릅니다.')
        return inferred,count
    try:
        with file_lock(cache/'treatment.lock'):
            return Stages(cache).run('video-treatment',{'identity':identity,'recipe':recipe},
                                     sources,produce)
    finally:
        shutil.rmtree(probe,ignore_errors=True)


def _log_tail(path):
    try:return Path(path).read_text(encoding='utf-8',errors='replace')[-400:]
    except OSError:return ''


def place_in(result, root):
    """처리 결과(공용 캐시)를 장면 폴더 `root` 안 `picture.mp4` 로 둔다 — 그래픽 장면 문서처럼 «장면 폴더 안 상대 경로» 만 쓸 수 있는 곳용.

    근거(w3 검토 blocker): 그래픽 장면의 HTML 렌더러(native·hyperframes)는 장면 폴더를 뿌리로 미디어를 찾고, 윈도우에서는 그 폴더를
    별칭(process_directory)으로 열어 '..' 로 나갈 수 없다. 처리 결과를 공용 캐시로 옮긴 뒤(원장 §6-2) 그래픽 영상 객체가
    relative_to 에서 ValueError 로 죽었다(유료 TTS 다음 단계).
    같은 볼륨이면 하드링크(디스크 추가 0) · 안 되면(exFAT·다른 볼륨 등) 복사하고 바이트 지문을 대조한다. 이미 같은 파일이면 그대로.
    임시 이름에 쓰고 os.replace 로 바꿔 끼우므로 도중에 끊겨도 반쪽 파일이 picture.mp4 로 남지 않는다.
    돌려주는 값: `result` 사본(path 만 장면 폴더 안으로).
    """
    import os
    src=native_path(result['path'])
    folder=native_path(root);folder.mkdir(parents=True,exist_ok=True)
    dest=folder/'picture.mp4'
    want=file_digest(src)
    if dest.is_file() and (os.path.samefile(src,dest) or file_digest(dest)==want):
        return dict(result,path=str(Path(root)/'picture.mp4'),cache_path=result['path'])
    tmp=folder/('picture-'+uuid.uuid4().hex+'.tmp')
    try:
        try:os.link(src,tmp)
        except OSError:
            shutil.copyfile(src,tmp)
            if file_digest(tmp)!=want:
                raise ProductionError('video_treatment_place','처리 결과를 장면 폴더로 옮긴 사본의 지문이 다릅니다(디스크를 확인하세요).')
        publish(tmp,dest)
    finally:
        if tmp.exists():tmp.unlink()
    return dict(result,path=str(Path(root)/'picture.mp4'),cache_path=result['path'])


LEGACY_FRAME_CACHE='video-frame-cache'


def remove_legacy_frame_cache(geumbit_root):
    """옛 Real-ESRGAN 프레임 캐시(<작업폴더>/geumbit/video-frame-cache · 컷당 수 GB PNG)를 지운다 — 오케스트레이터 결정 1(10-05 22:5x).

    근거: 새 처리법(ACNet)은 그 캐시를 영원히 읽지 않는다(재계산 가능한 파생물) · 학생 디스크에 수십 GB 가 남는다 ·
    작업 폴더당 실행기 하나(production.lock)라 옛 프로세스가 같은 폴더를 쓰는 경우가 없다.
    조건: 그 작업 폴더의 그 경로만 · 링크(심볼릭·윈도우 정션)면 따라가지 않고 손대지 않는다 · 지운 크기를 진행 로그(stderr)와
    geumbit/video-treatment/legacy-frame-cache.json 에 남긴다 · 실패해도 작업은 계속하되 이유를 같은 두 곳에 남긴다(삼키지 않는다).
    돌려주는 값: 그 기록(지울 것이 없으면 None).
    """
    import os
    import sys
    target=Path(geumbit_root)/LEGACY_FRAME_CACHE
    try:
        info=os.lstat(target)
    except FileNotFoundError:
        return None
    import stat as st
    linked=(st.S_ISLNK(info.st_mode) or getattr(os.path,'isjunction',lambda p:False)(target)
            or bool(getattr(info,'st_file_attributes',0)&getattr(st,'FILE_ATTRIBUTE_REPARSE_POINT',0)))
    record={'path':str(target),'removed':False}
    if linked or not st.S_ISDIR(info.st_mode):
        record['reason']='링크이거나 폴더가 아니어서 손대지 않았다'
    else:
        size=0;count=0;errors=[]
        for parent,dirs,files in os.walk(native_path(target),followlinks=False):
            for name in files:
                try:size+=os.lstat(os.path.join(parent,name)).st_size;count+=1
                except OSError:pass
        def failed(function,path,error):
            errors.append(f'{type(error[1] if isinstance(error,tuple) else error).__name__}: {path}')
        try:
            if sys.version_info>=(3,12):shutil.rmtree(native_path(target),onexc=failed)
            else:shutil.rmtree(native_path(target),onerror=failed)
        except OSError as error:
            errors.append(f'{type(error).__name__}: {error}')
        record.update(removed=not os.path.lexists(target),bytes=size,files=count,errors=errors[:20])
    note=('[영상처리] 옛 Real-ESRGAN 프레임 캐시 '+('삭제 ' if record['removed'] else '삭제 못 함 ')
          +(f"{record.get('bytes',0)/1e9:.2f}GB·{record.get('files',0)}개 " if 'bytes' in record else '')
          +(record.get('reason') or '; '.join(record.get('errors') or [])))
    print(note,file=sys.stderr,flush=True)
    try:save(Path(geumbit_root)/'video-treatment'/'legacy-frame-cache.json',record)
    except OSError as error:print('[영상처리] 기록 저장 실패: '+str(error),file=sys.stderr,flush=True)
    return record


def preflight_evidence(plan):
    """Validate source/context/clock and feasible crop before any paid narration."""
    results=[]
    def walk(value):
        if isinstance(value,list):
            for child in value:walk(child)
        elif isinstance(value,dict):
            if 'video_treatment' in value:
                settings=value['video_treatment'];validate_settings(settings)
                mid=value.get('media');mid=mid[0] if isinstance(mid,list) and mid else mid
                if reframe_off(settings):
                    # 확대를 끈 컷: 피사체 기록이 없다 — 잴 것은 원본 구도뿐이고 그것은 렌더가 고정 창으로 푼다.
                    results.append({'media':mid,'reframe':False})
                    for key,child in value.items():
                        if key!='video_treatment':walk(child)
                    return
                asset=plan['media'][mid];source=Path(asset['path'])
                receipt=read(io_path(settings['focus_receipt']))
                from local_focus import verify_render_receipt
                verify_render_receipt(settings,receipt)
                if receipt.get('focus_key')!=settings['focus_key']:
                    raise ValueError('피사체 기록의 문맥 키가 현재 장면과 다릅니다')
                start=float(value['in']);frames=round((float(value['out'])-start)*60)
                stream=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
                    '-show_entries','stream=width,height','-of','json',str(source)],timeout=30))['streams'][0]
                source_sha=file_digest(io_path(source))
                if source_sha!=asset['sha256']:raise ValueError('피사체 측정 원본이 변경되었습니다')
                size=[stream['width'],stream['height']];crop=settings.get('source_crop')
                framing=from_focus_receipt(receipt,source_sha,start,frames,60,size,settings['focus_key'],
                                           bounds=render_bounds(receipt,crop,size))
                row={'media':mid,'frames':frames,'focus_key':settings['focus_key'],'fallback':framing.get('fallback')}
                # 서버 알림 재료(src/longform/treatment.crop_notice·bystander_notice) — 영수증은 이 PC 에만 있다.
                if crop is not None:
                    row.update(source_crop=crop,crop_planned=crop_planned(receipt,crop,size))
                if bystanders_cut(receipt):
                    row['bystanders_cut']=bystanders_cut(receipt)
                results.append(row)
            for key,child in value.items():
                if key!='video_treatment':walk(child)
    walk([b['visual'] for b in plan['blocks']])
    return results


def _selection_evidence(receipt):
    subject=receipt.get('framing_subject') if isinstance(receipt,dict) else None
    evidence=subject.get('selection_evidence') if isinstance(subject,dict) else None
    return evidence if isinstance(evidence,dict) else {}


def _bounds_shape(value):
    return (isinstance(value,list) and len(value)==4
            and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in value))


def crop_planned(receipt,crop,size):
    """Was this crop cut's subject plan made inside the author's crop? (W2-21 · C2 contract, 2026-10-06)

    The renderer always re-solves the window inside the crop (from_focus_receipt(bounds=)). The two guarantees made by
    the subject plan — bystander half faces kept off the edges (owner decision 5-3) and the AGY crop re-check — hold in
    that window only when the plan itself was made in the crop. C2 (subject_agy.run_cut · impl/w2b-C-1005 d6175b1d)
    plans there and records the region in the receipt: framing_subject.selection_evidence.planned_bounds = the crop's
    whole-pixel interior (ceil/floor). True when that region is this crop (inward rounding, under one pixel per side), or
    when the crop is the whole picture to within a pixel (plan and render then see the same frame). Anything else — no
    mark (a receipt planned before C2), another region, a malformed mark — is False: the server then names the cut.
    """
    w,h=size
    if crop[0]<1 and crop[1]<1 and crop[2]>w-1 and crop[3]>h-1:return True
    return _interior(_selection_evidence(receipt).get('planned_bounds'),crop)


def _interior(planned,crop):
    """`planned` is `crop`'s whole-pixel interior (each side moved inward by under one pixel)."""
    if not _bounds_shape(planned):
        return False
    eps=1e-6
    return (crop[0]-eps<=planned[0]<crop[0]+1 and crop[1]-eps<=planned[1]<crop[1]+1
            and crop[2]-1<planned[2]<=crop[2]+eps and crop[3]-1<planned[3]<=crop[3]+eps)


def render_bounds(receipt,crop,size):
    """The source region the render window is solved in (W2-21): the author's crop — or, when the subject plan was made
    inside it (crop_planned) and names its region, exactly that region (selection_evidence.planned_bounds · C2 contract
    10-06). A fractional crop is planned in its whole-pixel interior; solving the render in the same region keeps the
    plan's guarantees (5-3 bystander heads, crop re-check) exact instead of within a pixel. Integer crops: the same numbers.
    """
    if crop is None:return None
    planned=_selection_evidence(receipt).get('planned_bounds')
    return list(planned) if _interior(planned,crop) else crop


def bystanders_cut(receipt):
    """Bystander heads the subject plan could not keep whole at the edge of a non-16:9 full-frame window — C2 contract
    10-06 (fbc05112): selection_evidence.bystanders.cut_in_full_frame (sample·person pairs). 0 when absent or malformed."""
    bystanders=_selection_evidence(receipt).get('bystanders')
    value=bystanders.get('cut_in_full_frame') if isinstance(bystanders,dict) else None
    return value if type(value) is int and value>0 else 0


def dependencies(value):
    paths=[]
    def walk(item):
        if isinstance(item,list):
            for child in item:walk(child)
        elif isinstance(item,dict):
            treatment=item.get('video_treatment')
            if treatment and not reframe_off(treatment):
                if not isinstance(treatment,dict) or not isinstance(treatment.get('focus_receipt'),str):
                    raise ProductionError('video_treatment_contract','피사체 기록 경로가 없습니다.',action='edit_plan')
                # 엔진 장면 단계가 이 경로를 Stages 원천(files → native_path)으로 쓴다 — 윈도우 긴 경로가 그 resolve 에서 죽지 않게
                # 확장 경로로 준다(같은 파일이면 native_path 결과 글자가 같아 단계 열쇠는 그대로).
                paths.append(str(io_path(treatment['focus_receipt'])))
            for key,child in item.items():
                if key!='video_treatment':walk(child)
    walk(value)
    return list(dict.fromkeys(paths))


def reframe_off(settings):
    """사용자가 이 컷의 피사체 확대·추적을 끈 처리(2026-10-23 · 사장님 결정 09-15 «요청하면 그대로»): video_treatment.reframe 가 False.
    그 컷은 피사체 기록 없이 원본 구도(작성자 crop 안의 가장 큰 16:9 창 · 배율 1.0 · 고정)로 처리한다 — 반전·화면 처리는 그대로."""
    return isinstance(settings,dict) and settings.get('reframe') is False


def validate_settings(settings):
    if not isinstance(settings,dict) or settings.get('profile')!=PROFILE:
        raise ValueError('video_treatment requires profile dramario-subject-v1')
    if 'reframe' in settings and settings['reframe'] is not False:
        raise ValueError('video_treatment.reframe 는 끌 때만 false 로 적는다')
    if reframe_off(settings):
        if 'focus_receipt' in settings or 'focus_key' in settings:
            raise ValueError('video_treatment.reframe false 컷에는 피사체 기록을 싣지 않는다')
    else:
        if not isinstance(settings.get('focus_receipt'),str) or not settings['focus_receipt'].strip():
            raise ValueError('video_treatment requires profile dramario-subject-v1 and a focus_receipt path')
        key=settings.get('focus_key')
        if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('video_treatment requires the source/context-bound focus_key')
    crop=settings.get('source_crop')
    if crop is not None and not valid_crop(crop):
        raise ValueError('video_treatment.source_crop must be [left,top,right,bottom] source pixels')
    if 'mirror' in settings and not isinstance(settings['mirror'],bool):
        raise ValueError('video_treatment.mirror must be true or false')
    if 'look' in settings and settings['look'] not in LOOKS:
        raise ValueError('video_treatment.look must be one of '+', '.join(LOOKS))
    if 'strength' in settings:
        import math
        value=settings['strength']
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError('video_treatment.strength must be a number from 0 to 1')


def valid_crop(crop):
    import math
    return (isinstance(crop,list) and len(crop)==4
            and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in crop)
            and 0<=crop[0]<crop[2] and 0<=crop[1]<crop[3])


def validate_tree(value):
    if isinstance(value,list):
        for child in value:validate_tree(child)
    elif isinstance(value,dict):
        if 'video_treatment' in value:
            validate_settings(value['video_treatment'])
            if value.get('kind')!='video':raise ValueError('video_treatment is only valid on source video')
            # W2-21: an authored crop is the source region the subject framing must stay inside. It is applied by
            # the treatment (source_crop), so the node's own crop must be exactly that region — never a second crop.
            if value.get('crop') is not None and value.get('crop')!=value['video_treatment'].get('source_crop'):
                raise ValueError('source crop must be carried into video_treatment.source_crop (one crop, applied before subject framing)')
            if value.get('camera'):raise ValueError('post-treatment camera zoom can clip verified subjects')
        for key,child in value.items():
            if key!='video_treatment':validate_tree(child)
