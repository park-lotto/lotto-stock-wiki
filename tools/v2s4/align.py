"""S4 필재 음성 → 단어 시각(whisper word_timestamps). 결과 tools/v2s4/align.json {씬키: [[단어,시작,끝],...]}"""
import json, sys, glob, os, whisper
src = sys.argv[1]; out = os.path.join(os.path.dirname(__file__), 'align.json')
res = json.load(open(out, encoding='utf8')) if os.path.exists(out) else {}
m = whisper.load_model('medium')
for f in sorted(glob.glob(os.path.join(src, '*.mp3'))):
    k = os.path.basename(f).split('__')[0]
    if k in res: continue
    r = m.transcribe(f, language='ko', word_timestamps=True)
    res[k] = [[w['word'].strip(), round(w['start'], 3), round(w['end'], 3)] for s in r['segments'] for w in s['words']]
    print(k, len(res[k]), flush=True)
    json.dump(res, open(out, 'w', encoding='utf8'), ensure_ascii=False)
