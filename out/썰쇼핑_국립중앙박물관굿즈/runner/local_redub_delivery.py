"""Verify the actual saved redub plan, then build clean media/editor files locally."""
import hashlib,json,os,types
from pathlib import Path
import local_redub_plan as P
import local_render_plan as T


def _scope(item):
    import redub_export_kernel as E,source_export_kernel as S,redub_kernel as K
    import volcano_run as R
    from longform_state import native_path
    expected={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
              for name in ('redub_export_kernel.py','source_export_kernel.py','redub_kernel.py')}
    if item.get('runtime')!=expected or item.get('kernel_id')!=hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest():
        raise R.StepError('재더빙 편집 인계 코드가 서버 계약과 다릅니다.')
    if item.get('version')!=1 or item.get('contract_key')!=hashlib.sha256(json.dumps({k:v for k,v in item.items() if k!='contract_key'},sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest():
        raise R.StepError('재더빙 인계 계약이 변경됐습니다.')
    checks=P.verify_proof(item['proof'])
    saved=T._read(native_path(item['proof']['files']['receipt']['path']));task=saved['task'];context=item['context'];pl=context['payload']
    # The server constructs this task through the exact master planning route.
    # Independently bind its public source/timing fields before consuming rows.
    segments=pl.get('segments') or [{'from':0,'to':pl['source_dur']}]
    edges=[[float(f"{float(s.get('from',s.get('t0',s.get('start')))):.3f}"),float(f"{float(s.get('to',s.get('t1',s.get('end')))):.3f}")] for s in segments]
    if edges!=task['segments'] or pl['source_size']!=task['size'] or any(c['src']!=pl['source'] for c in task['cuts']) or pl['workdir']!=task['workdir']:
        raise R.StepError('재더빙 인계 원본 또는 구간이 검증된 계획과 다릅니다.')
    if round(float(context['spec']['MATTE_PCT_H'])/100*context['spec']['H'])!=task['matte']:
        raise R.StepError('재더빙 매트 규격이 검증된 렌더와 다릅니다.')
    if [context['spec']['W'],context['spec']['H']]!=task['canvas'] or context['spec']['FPS']!=task['cuts'][0]['fps'] or (context['rhythm'] or {}).get('ZOOM')!=task['zoom']:
        raise R.StepError('재더빙 편집 규격이 검증된 렌더와 다릅니다.')
    rows={card:T._read(native_path(meta['path'])) for card,meta in saved['focus']['receipts'].items()}
    modules=S.build_modules(context['policy'])
    spec=types.SimpleNamespace(person_spec=lambda preset:context['person'],channel_rhythm=lambda preset:context['rhythm'])
    modules['volcano_deliver'].volcano_spec=spec
    custom=types.SimpleNamespace(editor_files=lambda payload,preset,directory:(context['text_records'],context['custom_files']))
    services=dict(build_kit=modules['volcano_deliver'].build_kit,volcano_spec=spec,
        custom_native=custom,volcano_framing=K._modules['volcano_framing'],volcano_urab=K._modules['volcano_urab'],
        volcano_color=types.SimpleNamespace(ARGS=context['color_args']))
    services.update(context['policy']['volcano_deliver'])
    services.update(context['canonical_defaults'])
    return E.build_context(services),dict(pl,focus_measurements=rows,focus_render_key=item['proof']['contract_key']),checks


#: 이 프로세스에서 고른 필터 파일 옵션 — {ffmpeg 실경로: 옵션}. ffmpeg 을 바꾸면 실경로가 달라 다시 묻는다.
_FILTER_FILE_OPTION = {}


def _filter_file_option(R, tool):
    """필터 그래프 파일을 넘기는 옵션 — **실제로 돌 ffmpeg 에** 묻는다(서버 `volcano_stitch.FILTER_FILE_RUNNER_SCRIPT` 와 같은 판단).

    FFmpeg 7.0(2024)이 `-/filter_complex <파일>` 을 냈고 옛 `-filter_complex_script` 는 2026-06 판에서 지웠다(9.x — win-main
    gyan 9.0.2 실측 «Unrecognized option 'filter_complex_script'»). 예전에는 옛 옵션을 박아 새 ffmpeg 수강생의 로컬 재더빙이
    굽기 전에 죽었다(10-21 전체 시험 훑기 · tests/test_camera_stability 와 같은 오류). 새 옵션을 먼저 묻고, 그 옵션을 모르는
    옛 판(7.0 전)만 옛 옵션으로 간다. 그 밖의 실패는 그대로 말한다(조용히 옛 옵션으로 넘기지 않는다)."""
    R._prefer_full_ffmpeg()
    head = R._resolve_tool(tool)
    if not head:
        raise R.StepError(f'ffmpeg 을 찾지 못했습니다: {tool}')
    key = tuple(head)
    if key in _FILTER_FILE_OPTION:
        return _FILTER_FILE_OPTION[key]
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as td:
        graph = os.path.join(td, 'probe.filter')
        with open(graph, 'w', encoding='utf-8') as fh:
            fh.write('anull')
        for option in ('-/filter_complex', '-filter_complex_script'):
            check = subprocess.run([*head, '-nostdin', '-hide_banner', option, graph, '-version'],
                                   capture_output=True, encoding='utf-8', errors='replace', timeout=60)
            if check.returncode == 0:
                _FILTER_FILE_OPTION[key] = option
                return option
            if option == '-/filter_complex' and "Unrecognized option '/filter_complex'." in check.stderr.splitlines():
                continue
            raise R.StepError('ffmpeg 이 필터 파일 옵션을 받지 않습니다: ' + (check.stderr or '').strip()[-400:])
    raise R.StepError('ffmpeg 이 필터 파일 옵션(-/filter_complex · -filter_complex_script)을 둘 다 모릅니다')


def prepare_execution(item):
    import volcano_run as R
    from film_editor import atomic_bytes
    from longform_state import native_path
    scope,pl,checks=_scope(item);context=item['context'];directory=item['directory']
    clean=scope['redub_clean_job'](context['preset'],pl,context['spec'])
    files=scope['redub_kit'](context['preset'],pl,context['spec'],directory)
    # Same filter text; script transport avoids command-line length limits on Windows.
    argv=clean['argv'];i=argv.index('-filter_complex');graph=argv[i+1]
    filter_path=native_path(pl['workdir'])/'local-redub'/item['contract_key']/'clean.filter'
    atomic_bytes(filter_path,graph.encode('utf-8'))
    argv[i:i+2]=[_filter_file_option(R,argv[0]),str(filter_path)]
    clean['argv']=argv
    return dict(jobs_kind='argv',jobs=[clean],write_files=files,source_checks=checks)
