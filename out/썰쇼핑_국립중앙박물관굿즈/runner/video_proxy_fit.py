"""Bounded local proxy sizing. Never truncates media or submits a paid request."""
import hashlib
import json
import math
import os
from pathlib import Path


def fit_proxy(item, *, runner):
    policy = item['size_fit']
    if policy.get('version') != 1:
        raise runner.StepError('지원하지 않는 영상 크기 조정 계약입니다.')
    source = item['out']
    original = item['prepared_proxy']
    if not runner.video_proxy_valid(item, original):
        raise runner.StepError('크기 조정 전에 원본 또는 proxy가 변경됐습니다.')

    def probe(path):
        result = runner.run_argv([policy['ffprobe'], '-v', 'error', '-count_frames',
            '-show_entries', 'stream=codec_type,nb_read_frames,duration,bit_rate:format=duration',
            '-of', 'json', path], capture=True)
        if result.returncode:
            raise runner.StepError('검수 영상의 길이·프레임 수를 확인하지 못했습니다. API를 호출하지 않았습니다.')
        try:
            data = json.loads(result.stdout)
            video = next(s for s in data['streams'] if s['codec_type'] == 'video')
            sound = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
            return (int(video['nb_read_frames']), float(video.get('duration') or data['format']['duration']),
                    sound is not None, int(sound['bit_rate']) if sound else 0)
        except (ValueError, TypeError, KeyError, StopIteration) as exc:
            raise runner.StepError('검수 영상의 실제 프레임·음성 측정값이 부족합니다. API를 호출하지 않았습니다.') from exc

    frames, duration, audio, audio_rate = probe(source)
    if not math.isfinite(duration) or duration <= 0 or frames < 1:
        raise runner.StepError('검수 영상의 실제 길이가 잘못되었습니다.')
    media, request = runner.video_request_sizes(item, source)
    size = os.path.getsize(source)
    attachment_bytes = media-size
    overhead = request - 4*((size+2)//3)
    target = min(int(item['max_media_bytes'])-attachment_bytes,
                 ((int(item['max_request_bytes'])-overhead)//4)*3-2)
    available = target*float(policy['safety'])*8/duration - audio_rate
    if available < int(policy['min_video_bps']):
        raise runner.StepError('영상 전체와 소리를 유지할 수 있는 검수 첨부 용량이 부족합니다. '
                               'API를 호출하지 않았습니다. '+str(item.get('size_recovery') or ''))
    identity = hashlib.sha256(json.dumps(dict(proxy=original, policy=policy, target=target), sort_keys=True).encode()).hexdigest()[:24]
    for attempt in range(int(policy['attempts'])):
        rate = int(available * float(policy['safety'])**attempt)
        if rate < int(policy['min_video_bps']):
            break
        output = str(Path(source).with_name(f'fit-{identity}-{attempt}.mp4'))
        argv = [item['shrink_argv'][0], '-y', '-v', 'error', '-i', source,
                '-map', '0:v:0', '-map', '0:a:0?', '-c:v', policy['codec'],
                '-preset', policy['preset'], '-b:v', str(rate), '-maxrate', str(rate),
                '-bufsize', str(rate*2), '-c:a', policy['audio_codec'],
                '-fps_mode', 'passthrough', '-movflags', '+faststart', output]
        config = dict(item, out=output, shrink_argv=argv)
        config.pop('prepared_proxy', None)
        config.pop('size_fit', None)  # bounded here, never recurse into another sizing loop
        record = output+'.analysis-proxy.json'
        with runner.review_receipt_lock(record):
            try: receipt = json.loads(Path(record).read_text(encoding='utf8'))
            except (OSError, ValueError): receipt = {}
            if not runner.video_proxy_valid(config, receipt):
                receipt = runner.prepare_video_proxy(config)
            measured = probe(output)
            if measured[0] != frames or measured[2] != audio or abs(measured[1]-duration) > 0.001:
                raise runner.StepError('크기 조정 후 영상 프레임·길이·소리가 달라졌습니다. API를 호출하지 않았습니다.')
            if not runner.video_proxy_valid(item, original):
                raise runner.StepError('크기 조정 중 원본 또는 이전 proxy가 변경됐습니다.')
            receipt['size_fit'] = dict(version=1, parent=original, target_bytes=target,
                                       frames=frames, duration=duration, audio=audio)
            runner._photo_write_state(record, receipt)
        config['prepared_proxy'] = receipt
        try:
            runner._video_size_preflight(config, output)
        except runner.StepError as exc:
            if getattr(exc, 'code', '') != 'video_preflight_size':
                raise
            continue
        return config
    raise runner.StepError('제한된 로컬 압축으로 검수 크기를 맞추지 못했습니다. 원본·기록을 보존하며 API를 호출하지 않았습니다.')
