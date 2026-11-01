"""Local compute admission separated from subscription model waiting.

Continuation threads do not grant CPU or provider capacity. Local work keeps
server-declared CPU width; the existing AGY process-wide file slots grant model
capacity. Anonymous parking files are scoped to this execution only.
"""
import contextvars
from contextlib import contextmanager
import hashlib
import json
import tempfile
import sys
import threading

_CURRENT = contextvars.ContextVar('subject_stage_pool', default=None)


class Stages:
    def __init__(self, local_width, *, check_running):
        self.width = local_width
        self.check_running = check_running
        self.condition = threading.Condition()
        self.local = 0
        self.stop = None

    def _enter(self):
        with self.condition:
            self.condition.wait_for(lambda:self.local < self.width or self.stop is not None)
            if self.stop is not None:
                self._cancel()
            self.check_running()
            self.local += 1

    def _cancel(self):
        import volcano_run as R
        # A peer's result belongs to its own request. Never propagate its
        # provider_result object into this cut's evidence receipt.
        raise R.ProviderRefusalError('provider.agy','RUN_SERVICE_REFUSED',
            'Another request in this execution was refused; this cut was stopped')

    def _leave(self):
        with self.condition:
            self.local -= 1
            self.condition.notify_all()

    def run(self, function, *args):
        self._enter()
        context={'stages':self,'local':True,'park':[]}
        token=_CURRENT.set(context)
        try:
            return function(*args)
        finally:
            _CURRENT.reset(token)
            if context['local']:self._leave()

    def refuse(self, error):
        with self.condition:
            if self.stop is None:self.stop=error
            self.condition.notify_all()


@contextmanager
def park_track(track):
    """Only the unshared dense track is parked; media/receipt files are untouched."""
    context=_CURRENT.get()
    if context is None or not track:
        yield
        return
    def suspend():
        stream=tempfile.TemporaryFile(mode='w+b',prefix='volcano-track-wait-')
        try:
            raw=json.dumps(track,ensure_ascii=False,allow_nan=False).encode('utf8')
            digest=hashlib.sha256(raw).digest()
            if stream.write(raw)!=len(raw):raise OSError('Incomplete temporary track snapshot')
            stream.flush()
            track.clear()
            def restore(cancelled=False):
                try:
                    if cancelled:return
                    stream.seek(0);raw=stream.read()
                    if hashlib.sha256(raw).digest()!=digest:raise ValueError('Track snapshot changed')
                    track.extend(json.loads(raw))
                finally:stream.close()
            return restore
        except BaseException:
            stream.close();raise
    context['park'].append(suspend)
    try:yield
    finally:context['park'].remove(suspend)


@contextmanager
def model_wait(refusal_type):
    context=_CURRENT.get()
    if context is None:
        yield
        return
    stages=context['stages'];restores=[]
    try:
        for suspend in context['park']:restores.append(suspend())
        stages.check_running()
        stages._leave();context['local']=False
        try:
            yield
            if stages.stop is not None:stages._cancel()
        except refusal_type as error:
            stages.refuse(error)
            raise
        finally:
            # Resume parsing/tracking only with a local compute permit.
            # On stopped runs the continuation unwinds without new local work.
            if stages.stop is None:
                stages._enter();context['local']=True
    finally:
        active_error=sys.exc_info()[1]
        first_error=None
        for restore in reversed(restores):
            try:restore(not context['local'])
            except BaseException as error:
                if first_error is None:first_error=error
        if first_error is not None:
            if active_error is not None:
                if hasattr(active_error,'add_note'):active_error.add_note('Temporary stage cleanup also failed: '+str(first_error))
            else:raise first_error


def active():
    return _CURRENT.get() is not None


@contextmanager
def preserve(suspend):
    context=_CURRENT.get()
    if context is None:
        yield
        return
    context['park'].append(suspend)
    try:yield
    finally:context['park'].remove(suspend)


def review(track,function,*args,**kwargs):
    with park_track(track):return function(*args,**kwargs)
