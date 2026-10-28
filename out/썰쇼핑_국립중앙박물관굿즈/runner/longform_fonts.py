"""Resolve publisher-hosted fonts through the existing audited font installer."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote,urljoin
import json,urllib.request,sys
from contextlib import redirect_stdout
from film_editor import file_digest,file_lock
from longform_state import ProductionError,save
import volcano_run as runner

class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.links.extend(value for key,value in attrs if key=='href' and value)

def resolve_archive(source):
 page=source['page'];parts=urlsplit(page)
 if parts.scheme!='https' or parts.username:raise ProductionError('font_source_invalid','공식 HTTPS 글꼴 배포 페이지가 필요합니다.')
 req=urllib.request.Request(page,headers={'User-Agent':runner._UA})
 with runner._open_retry(req,30,'font-source') as response:raw=response.read(2*1024*1024+1)
 if len(raw)>2*1024*1024:raise ProductionError('font_source_changed','글꼴 안내 페이지 크기가 예상 범위를 넘었습니다.')
 parser=Links();parser.feed(raw.decode('utf-8'))
 urls=set()
 for link in parser.links:
  url=urljoin(page,link);parts=urlsplit(url)
  if parts.scheme=='https' and not parts.username and parts.hostname==source['archive_host'] and unquote(parts.path).rsplit('/',1)[-1]==source['archive_name']:urls.add(url)
 if len(urls)!=1:raise ProductionError('font_source_changed','공식 글꼴 압축 링크를 하나로 확인하지 못했습니다.',action='repair_environment')
 return urls.pop()

def ensure_fonts(fonts):
 fonts=Path(fonts);catalog=fonts.parent/'font-sources.json'
 if not catalog.is_file():return []
 sources=json.loads(catalog.read_text(encoding='utf-8'));fonts.mkdir(parents=True,exist_ok=True);evidence=[]
 with file_lock(fonts/'.publisher-download.lock'):
  for name,source in sources.items():
   if Path(name).name!=name:raise ProductionError('font_source_invalid','글꼴 파일명 형식 오류')
   dest=fonts/name;approved={source['sha256'],*source.get('existing_approved_sha256',[])}
   if dest.is_file():
    have=file_digest(dest)          # 한 번만 잰다(6-00)
    if have not in approved:raise ProductionError('font_version_mismatch','등록된 글꼴과 다릅니다. 기존 파일은 보존했습니다: '+str(dest),action='repair_environment')
    evidence.append({'font':name,'sha256':have,'reused':True});continue
   with redirect_stdout(sys.stderr):
    archive=resolve_archive(source)
    # member_sha256: zip 안 글꼴을 이름이 아니라 내용 지문으로 고른다(2026-10-17 신고 #123 — 공군체 zip 은 안 이름이 CP949 라
    # 이름으로 찾으면 «zip 안에 없다» 로 막혔다. 목록의 글꼴은 전부 zip 안 파일 그대로라 sha256 이 곧 그 파일의 지문이다).
    # 지문 대조는 fetch_font 안에서 한 번만 하고(file_sha256 으로 결과도 대조), 여기서 다시 재지 않는다.
    runner.fetch_font({'url':archive,'kind':'zip','member':source['member'],'member_sha256':source['sha256'],
                       'dest':str(dest),'file_sha256':source['sha256'],'ass_name':name})
   record={'font':name,'sha256':source['sha256'],'publisher_page':source['page'],'license':source['license'],'reused':False}
   save(fonts/(name+'.source.json'),record);evidence.append(record)
 return evidence
