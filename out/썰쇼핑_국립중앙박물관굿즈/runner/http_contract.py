"""Proposed HTTP adapter; production entry registers these exact routes.

No public asset-grant fallback. No redirects, retries, provider calls or refresh.
"""
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import integration_contract as C

STREAM_PREFIX='/originals/v1/'
ADMIT_PATH=STREAM_PREFIX+'admit'




class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise urllib.error.HTTPError(req.full_url,code,'Original import redirects are forbidden',headers,fp)


def _url(client,path):
    base=urllib.parse.urlsplit(client.url)
    if base.scheme!='https' or not base.netloc or base.username or base.password:
        raise ValueError('trusted HTTPS runner origin required')
    return urllib.parse.urlunsplit((base.scheme,base.netloc,path,'',''))


def _open(client,request):
    client._rpc_wait()
    try:return urllib.request.build_opener(NoRedirect()).open(request,timeout=client.timeout)
    except urllib.error.HTTPError as error:
        error.close()
        raise
    finally:client._rpc_record()


def fetch(client,preset,sha):
    if not isinstance(sha,str) or not C.SHA.fullmatch(sha):raise ValueError('invalid SHA')
    url=_url(client,STREAM_PREFIX+sha)+'?'+urllib.parse.urlencode({'preset':preset})
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+client.token,
        'User-Agent':'volcano-local-original/1','Accept':'application/json'})
    response=_open(client,request)
    try:
        headers=response.headers
        # ReadableStream responses need not have HTTP Content-Length. Storage size
        # comes from the owner-authorized R2 lookup, independent of HTTP framing.
        declared=headers.get('x-volcano-original-size')
        if not isinstance(declared,str) or not declared.isascii() or not declared.isdecimal() or int(declared)<=0:
            raise ValueError('authenticated original size is missing or invalid')
        size=int(declared)
        content_length=headers.get('content-length')
        if content_length is not None and (not content_length.isascii() or not content_length.isdecimal() or int(content_length)!=size):
            raise ValueError('HTTP Content-Length disagrees with authenticated original size')
        metadata=dict(version=int(headers['x-volcano-original-version']),owner=headers['x-volcano-original-owner'],
                      sha=headers['x-volcano-original-sha'],size=size,preset=preset)
        if metadata['sha']!=sha:raise ValueError('response original SHA mismatch')
        def chunks():
            try:
                while True:
                    chunk=response.read(io.DEFAULT_BUFFER_SIZE)
                    if not chunk:break
                    yield chunk
            finally:response.close()
        return dict(metadata,body=chunks(),close=response.close)
    except BaseException:
        response.close();raise


def admit(client,args,*,max_request_bytes):
    raw=json.dumps(args,ensure_ascii=True,separators=(',',':')).encode()
    if type(max_request_bytes) is not int or len(raw)>max_request_bytes:
        raise ValueError('compact admission exceeds negotiated request budget')
    request=urllib.request.Request(_url(client,ADMIT_PATH),data=raw,headers={
        'Authorization':'Bearer '+client.token,'Content-Type':'application/json','User-Agent':'volcano-local-original/1'})
    with _open(client,request) as response:
        data=response.read(max_request_bytes+1)
        if len(data)>max_request_bytes:raise ValueError('admission response exceeds negotiated budget')
        result=json.loads(data)
    if not isinstance(result,dict) or result.get('status')!='admitted':raise ValueError('original admission failed')
    return result
