"""Bind a visual cut adjudication to exact source bytes, range and evidence."""
from pathlib import Path
import hashlib
import json
import math
from longform_state import ProductionError


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def apply_cut_review(source,start,seconds,cuts,review_path):
    """Never suppress an unreviewed candidate or accept a stale review.

    A matching review is evidence of a recorded visual judgment, not proof of
    final composition or listening. Automatic detections remain in the report.
    Relative evidence paths are resolved beside the review on both OSes.
    """
    try:
        path=Path(review_path)
        review=json.loads(path.read_text(encoding='utf-8'))
        if review.get('schema')!='source-cut-review-v1':raise ValueError('schema')
        if digest(source)!=review['source_sha256']:raise ValueError('source changed')
        for key,value in [('source_start',start),('duration',seconds)]:
            number=float(review[key])
            if not math.isfinite(number) or abs(number-float(value))>1e-7:raise ValueError('range changed')
        rows=review['candidates']
        if not isinstance(rows,list) or len(rows)!=len(cuts):raise ValueError('candidate count changed')
        effective=[]
        for actual,row in zip(cuts,rows):
            offset=float(row['relative_seconds'])
            if not math.isfinite(offset) or abs(actual-offset)>1e-5:raise ValueError('candidate changed')
            if not isinstance(row.get('reviewer'),str) or not row['reviewer'].strip():raise ValueError('reviewer missing')
            if not isinstance(row.get('reason'),str) or not row['reason'].strip():raise ValueError('reason missing')
            image=Path(row['image']);image=image if image.is_absolute() else path.parent/image
            if digest(image)!=row['image_sha256']:raise ValueError('evidence changed')
            rate=row['source_frame_rate'].split('/')
            fps=float(rate[0])/float(rate[1])
            first=float(row['capture_start']);count=row['frames']
            if not math.isfinite(fps) or fps<=0 or not math.isfinite(first):raise ValueError('frame timing')
            if not isinstance(count,int) or isinstance(count,bool) or count<6:raise ValueError('insufficient frames')
            # Require evidence before AND after the actual candidate, not merely
            # a picture from somewhere in the same file.
            absolute=float(start)+actual
            if not first<absolute<first+(count-1)/fps:raise ValueError('evidence does not straddle candidate')
            if row['decision']=='scene_cut':effective.append(actual)
            elif row['decision']!='no_scene_cut_observed_in_six_frame_window':raise ValueError('unreviewed decision')
        return effective,{'path':str(path),'sha256':digest(path),'status':'visual_adjudication_applied',
                          'reviewed_candidates':len(rows),'scope':'Candidate windows only; not final playback/audio approval'}
    except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError,IndexError) as exc:
        raise ProductionError('source_cut_review_invalid','원본·검사 구간·검수 증거가 일치하지 않습니다. 컷 검수를 다시 확인하세요.',action='edit_plan') from exc


def review_dependencies(visual):
    """Include nested review files AND evidence in cached picture receipts."""
    paths=[]
    def walk(value):
        if isinstance(value,list):
            for item in value:walk(item)
        elif isinstance(value,dict):
            if value.get('cut_review') is not None:
                path=Path(value['cut_review']);paths.append(str(path))
                try:
                    review=json.loads(path.read_text(encoding='utf-8'))
                    for row in review['candidates']:
                        image=Path(row['image'])
                        paths.append(str(image if image.is_absolute() else path.parent/image))
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    raise ProductionError('source_cut_review_invalid','컷 검수 의존 파일을 읽을 수 없습니다.',action='edit_plan') from exc
            for key,item in value.items():
                if key!='cut_review':walk(item)
    walk(visual)
    return list(dict.fromkeys(paths))
