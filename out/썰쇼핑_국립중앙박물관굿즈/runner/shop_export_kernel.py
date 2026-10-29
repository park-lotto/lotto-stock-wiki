import math,re,types,json
from urllib.parse import quote
class GateError(ValueError):
    pass
volcano_path=types.SimpleNamespace(GateError=GateError)
_XML_ESC = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}

def xesc(s):
    return ''.join((_XML_ESC.get(c, c) for c in str(s)))

def pathurl(p):
    s = str(p)
    if s and s[0] != '/':
        s = '/' + s
    from urllib.parse import quote
    return 'file://localhost' + quote(s, safe='/')

def _uuid_from(seed):
    import hashlib
    h = hashlib.sha256(seed.encode('utf-8')).hexdigest()
    return f'{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}'

def _rate(fps):
    return f'<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>'

def _tc_string(frames, fps):
    f = max(0, int(frames))
    s, ff = divmod(f, int(fps))
    m, ss = divmod(s, 60)
    h, mm = divmod(m, 60)
    return f'{h % 24:02d}:{mm:02d}:{ss:02d}:{ff:02d}'

def _file_def(fid, path, frames, fps, w=None, h=None, audio=False, tc_frame=0):
    L = [f'<file id="{fid}">', f"<name>{xesc(path.rsplit('/', 1)[-1])}</name>", f'<pathurl>{xesc(pathurl(path))}</pathurl>', _rate(fps), f'<duration>{frames}</duration>', f'<timecode>{_rate(fps)}<string>{_tc_string(tc_frame, fps)}</string><frame>{int(tc_frame)}</frame><displayformat>NDF</displayformat></timecode>', '<media>']
    if w:
        L += ['<video><samplecharacteristics>', _rate(fps), f'<width>{w}</width><height>{h}</height>', '<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio>', '<fielddominance>none</fielddominance>', '</samplecharacteristics></video>']
    if audio:
        L += ['<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>2</channelcount></audio>']
    L += ['</media>', '</file>']
    return ''.join(L)

def _motion_filter(scale_pct, center, keys=None):
    if keys:
        root = _motion_filter(scale_pct, center)
        import xml.etree.ElementTree as ET
        node = ET.fromstring(root)
        for parameter in node.findall('./effect/parameter'):
            field = {'scale': 'scale_pct', 'center': 'center'}.get(parameter.findtext('parameterid'))
            if not field:
                continue
            value = parameter.find('value')
            if value is not None:
                parameter.remove(value)
            ET.SubElement(ET.SubElement(parameter, 'interpolation'), 'name').text = 'FCPCurve'
            for key in keys:
                k = ET.SubElement(parameter, 'keyframe')
                ET.SubElement(k, 'when').text = str(key['when'])
                v = ET.SubElement(k, 'value')
                if field == 'center':
                    ET.SubElement(v, 'horiz').text = f'{key[field][0]:.9f}'
                    ET.SubElement(v, 'vert').text = f'{key[field][1]:.9f}'
                else:
                    v.text = f'{key[field]:.9f}'
        return ET.tostring(node, encoding='unicode')
    h, v = center
    P = '<parameter><parameterid>{i}</parameterid><name>{n}</name><valuemin>{lo}</valuemin><valuemax>{hi}</valuemax><value>{val}</value></parameter>'
    return '<filter><enabled>TRUE</enabled><start>-1</start><end>-1</end><effect id="basicmotion"><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory><effecttype>motion</effecttype><mediatype>video</mediatype>' + P.format(i='scale', n='Scale', lo=0, hi=1000, val=f'{scale_pct:g}') + P.format(i='rotation', n='Rotation', lo=-8640, hi=8640, val=0) + f'<parameter><parameterid>center</parameterid><name>Center</name><value><horiz>{h:g}</horiz><vert>{v:g}</vert></value></parameter>' + '<parameter><parameterid>anchorpoint</parameterid><name>Anchor Point</name><value><horiz>0</horiz><vert>0</vert></value></parameter>' + '</effect></filter>'

def fcp7_xml(name, cuts, audio, total_f, markers, S, fps, frame=None):
    W, H = (S['W'], S['H'])
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE xmeml>', '<xmeml version="5">', '<sequence id="sequence-1">', f'<uuid>{_uuid_from(name + str(total_f) + str(len(cuts)))}</uuid>', f'<duration>{total_f}</duration>', _rate(fps), f'<name>{xesc(name)}</name>', '<media>', '<video>', '<format><samplecharacteristics>', _rate(fps), f'<width>{W}</width><height>{H}</height>', '<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio>', '<fielddominance>none</fielddominance><colordepth>24</colordepth>', '</samplecharacteristics></format>']
    fid_of, nfile = ({}, [0])

    def file_ref(path, frames_, w, h, tc=0):
        if path in fid_of:
            return f'<file id="{fid_of[path]}"/>'
        nfile[0] += 1
        fid_of[path] = f'file-{nfile[0]}'
        return _file_def(fid_of[path], path, frames_, fps, w, h, tc_frame=tc)
    _master = {}

    def master_of(path):
        if path not in _master:
            _master[path] = f'masterclip-{len(_master) + 1}'
        return _master[path]
    L += ['<track>']
    t = 0
    for i, c in enumerate(cuts):
        n = int(c['frames'])
        for k in ('in_f', 'media_frames', 'src', 'scale_pct', 'center'):
            if k not in c:
                raise KeyError(f'cuts[{i}] 에 {k} 가 없다 — deliver_cuts() 가 준 것을 그대로 넘겨라. 채워 넣으면 편집이 안 되는 타임라인이 조용히 나간다.')
        h, mf = (int(c['in_f']), int(c['media_frames']))
        if not (0 <= h and h + n <= mf):
            raise volcano_path.GateError(f'cuts[{i}] 의 in/out({h}~{h + n})이 소재({mf})를 벗어난다.')
        L += [f'<clipitem id="clipitem-{i + 1}">', f"<masterclipid>{master_of(c['src'])}</masterclipid>", f"<name>{xesc(c.get('name') or c['src'].rsplit('/', 1)[-1])}</name>", '<enabled>TRUE</enabled>', f'<duration>{mf}</duration>', _rate(fps), f'<start>{t}</start><end>{t + n}</end><in>{h}</in><out>{h + n}</out>', file_ref(c['src'], mf, int(c['w']), int(c['h'])), _motion_filter(float(c['scale_pct']), c['center'], c.get('motion_keys')), '</clipitem>']
        t += n
    L += ['<enabled>TRUE</enabled><locked>FALSE</locked>', '</track>']
    if frame:
        L += ['<track>', '<clipitem id="clipitem-frame">', f"<masterclipid>{master_of(frame['path'])}</masterclipid>", f"<name>{xesc(frame['path'].rsplit('/', 1)[-1])}</name>", '<enabled>TRUE</enabled>', f'<duration>{total_f}</duration>', _rate(fps), f'<start>0</start><end>{total_f}</end><in>0</in><out>{total_f}</out>', file_ref(frame['path'], total_f, W, H), '</clipitem>', '<enabled>TRUE</enabled><locked>FALSE</locked>', '</track>']
    L += ['</video>']
    if isinstance(audio, list):
        L += ['<audio>', '<numOutputChannels>2</numOutputChannels>', '<format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>', '<outputs>', '<group><index>1</index><numchannels>2</numchannels><downmix>0</downmix><channel><index>1</index></channel><channel><index>2</index></channel></group>', '</outputs>']
        _ci = len(cuts) + 2
        for tr in audio:
            L += ['<track>']
            for cl in tr.get('clips') or []:
                fn_ = int(cl['frames'])
                t0 = int(cl.get('frame') or 0)
                nfile[0] += 1
                _af = f'file-{nfile[0]}'
                L += [f'<clipitem id="clipitem-{_ci}" premiereChannelType="stereo">', f"<masterclipid>{master_of(cl['path'])}</masterclipid>", f"<name>{xesc(str(cl['path']).rsplit('/', 1)[-1])}</name>", '<enabled>TRUE</enabled>', f'<duration>{fn_}</duration>', _rate(fps), f'<start>{t0}</start><end>{min(t0 + fn_, total_f)}</end><in>0</in><out>{min(fn_, max(total_f - t0, 1))}</out>', _file_def(_af, cl['path'], fn_, fps, audio=True), '</clipitem>']
                _ci += 1
            L += ['<enabled>TRUE</enabled><locked>FALSE</locked>', '</track>']
        L += ['</audio>', '</media>', f'<timecode>{_rate(fps)}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>']
        for m in markers:
            L += ['<marker>', f"<comment>{xesc(m['comment'])}</comment>", f"<name>{xesc(m['name'])}</name>", f"<in>{int(m['frame'])}</in><out>-1</out>", '</marker>']
        L += ['</sequence>', '</xmeml>', '']
        return '\n'.join(L)
    an = int(audio['frames'])
    nfile[0] += 1
    af = f'file-{nfile[0]}'
    L += ['<audio>', '<numOutputChannels>2</numOutputChannels>', '<format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>', '<outputs>', '<group><index>1</index><numchannels>2</numchannels><downmix>0</downmix><channel><index>1</index></channel><channel><index>2</index></channel></group>', '</outputs>', '<track>', f'<clipitem id="clipitem-{len(cuts) + 2}" premiereChannelType="stereo">', f"<masterclipid>{master_of(audio['path'])}</masterclipid>", f"<name>{xesc(audio['path'].rsplit('/', 1)[-1])}</name>", '<enabled>TRUE</enabled>', f'<duration>{an}</duration>', _rate(fps), f'<start>0</start><end>{min(an, total_f)}</end><in>0</in><out>{min(an, total_f)}</out>', _file_def(af, audio['path'], an, fps, audio=True), '</clipitem>', '<enabled>TRUE</enabled><locked>FALSE</locked>', '</track>']
    L += ['</audio>', '</media>', f'<timecode>{_rate(fps)}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>']
    for m in markers:
        L += ['<marker>', f"<comment>{xesc(m['comment'])}</comment>", f"<name>{xesc(m['name'])}</name>", f"<in>{int(m['frame'])}</in><out>-1</out>", '</marker>']
    L += ['</sequence>', '</xmeml>', '']
    return '\n'.join(L)

def editable_text_xml(xml, records, fps, W, H):
    from xml.etree import ElementTree as ET
    root = ET.fromstring(xml)
    video = root.find('./sequence/media/video')
    lanes = []

    def put(parent, name, value):
        node = ET.SubElement(parent, name)
        node.text = str(value)
        return node
    for i, row in enumerate(records):
        start = round(row['t'] * fps)
        end = max(start + 1, round(row['end'] * fps))
        lane = next((x for x in lanes if x['role'] == row['role'] and x['end'] <= start), None)
        if lane is None:
            lane = dict(role=row['role'], end=0, node=ET.SubElement(video, 'track'))
            lanes.append(lane)
        lane['end'] = end
        item = ET.SubElement(lane['node'], 'generatoritem', id=f'volcano-text-{i}')
        for k, v in (('name', row['role']), ('duration', end - start), ('in', 0), ('out', end - start), ('start', start), ('end', end), ('enabled', 'TRUE'), ('anamorphic', 'FALSE'), ('alphatype', 'black')):
            put(item, k, v)
        rate = ET.SubElement(item, 'rate')
        put(rate, 'timebase', round(fps))
        put(rate, 'ntsc', 'FALSE')
        effect = ET.SubElement(item, 'effect', id=f'volcano-text-effect-{i}')
        for k, v in (('name', 'Text'), ('effectid', 'Text'), ('effectcategory', 'Text'), ('effecttype', 'generator'), ('mediatype', 'video')):
            put(effect, k, v)

        def param(key, name, value):
            p = ET.SubElement(effect, 'parameter')
            put(p, 'parameterid', key)
            put(p, 'name', name)
            if isinstance(value, dict):
                node = ET.SubElement(p, 'value')
                for k, v in value.items():
                    put(node, k, v)
            else:
                put(p, 'value', value)
        ps_name = row.get('font_postscript_name')
        metric_keys = ('font_units_per_em', 'font_ass_height', 'font_ascender', 'font_descender')
        if not ps_name or any((not isinstance(row.get(k), (int, float)) or isinstance(row.get(k), bool) or (not math.isfinite(row[k])) for k in metric_keys)):
            raise ValueError('편집기 글꼴의 실제 PostScript 이름과 메트릭이 필요합니다. subtitle을 다시 실행하세요.')
        em = row['font_units_per_em']
        height = row['font_ass_height']
        if em <= 0 or height <= 0:
            raise ValueError('편집기 글꼴의 실제 em/높이가 올바르지 않습니다.')
        legacy_size = max(1, round(row['font_size'] * em / height * 480 / H))
        native_size = legacy_size * H / 480
        param('str', 'Text', row['text'])
        param('fontname', 'Font', ps_name)
        param('fontsize', 'Size', legacy_size)
        param('fontstyle', 'Style', 0)
        param('alignment', 'Alignment', 2)
        color = row['color'].lstrip('#')
        param('fontcolor', 'Font Color', dict(alpha=255, red=int(color[:2], 16), green=int(color[2:4], 16), blue=int(color[4:], 16)))
        alignment = int(row.get('alignment', 8))
        anchor = 0 if alignment >= 7 else 0.5 if alignment >= 4 else 1
        baseline = row['y'] + row['font_size'] * (row['font_ascender'] / height - anchor)
        origin_y = baseline - native_size * row['font_descender'] / em
        param('origin', 'Origin', dict(horiz=(row['x'] - W / 2) / W, vert=(origin_y - H / 2) / H))
        source = ET.SubElement(item, 'sourcetrack')
        put(source, 'mediatype', 'video')
        log = ET.SubElement(item, 'logginginfo')
        put(log, 'lognote', json.dumps(row, ensure_ascii=False, sort_keys=True))
    for lane in lanes:
        put(lane['node'], 'enabled', 'TRUE')
        put(lane['node'], 'locked', 'FALSE')
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding='unicode') + '\n'
