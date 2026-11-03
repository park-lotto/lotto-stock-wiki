"""Create upload copy from authored facts and the music actually assigned to the plan."""
import re

def upload_fields(plan,lang='ko'):
 upload=plan['upload'];body=[];tags=[]
 # Preserve authored tags while avoiding duplicates from both authoring fields.
 for line in upload['description'].splitlines():
  words=line.split()
  if words and all(re.fullmatch(r'#[^\s#]+',word) for word in words):
   tags.extend(words)
  else:body.append(line)
 tags.extend(upload.get('hashtags',[]));tags=list(dict.fromkeys(tags))
 description='\n'.join(body).strip()
 if plan.get('music'):
  music=plan['music'];cues=music.get('segments',[music])
  for aid in dict.fromkeys(cue['asset'] for cue in cues):
   asset=plan['sound_assets'][aid]
   fields=[asset.get('title',aid),asset.get('artist'),asset['source'],asset['license'],asset.get('license_url')]
   from longform_render import screen_words
   description+='\n\n'+screen_words(lang)['music']+'\n'+'\n'.join(str(v) for v in fields if v)
 if tags:description+='\n\n'+' '.join(tags)
 title=upload['title'].strip()
 # YouTube videos.snippet official limits, checked 2026-09-28:
 # https://developers.google.com/youtube/v3/docs/videos#snippet.description
 # Count final UTF-8 bytes including appended music attribution and hashtags.
 from longform_state import ProductionError
 if len(title)>100 or any(c in title for c in '<>'):
  raise ProductionError('upload_title_invalid','유튜브 제목은 100자 이내이며 < >를 사용할 수 없습니다.',action='edit_plan')
 size=len(description.encode('utf-8'))
 if size>5000 or any(c in description for c in '<>'):
  raise ProductionError('upload_description_invalid',f'음악 크레딧·해시태그 포함 영상 설명은 UTF-8 5000바이트 이내이며 < >를 사용할 수 없습니다. 현재 {size}바이트입니다. 출처를 보존해 문구를 수정하세요.',action='edit_plan')
 return {'title':title,'description':description}

def upload_text(plan,lang='ko'):
 fields=upload_fields(plan,lang)
 return fields['title']+'\n\n'+fields['description']+'\n'
