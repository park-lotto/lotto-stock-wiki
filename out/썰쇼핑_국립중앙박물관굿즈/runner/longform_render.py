"""Fixed local layouts from the approved pilot. No factual or media selection here."""
from pathlib import Path
import html
import json
import math
import shutil
import subprocess
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageOps,ImageColor
from film_editor import command
from longform_state import ProductionError
from longform_photo import render as photo_render

W,H,FPS=1920,1080,60

#: Fixed on-screen words the engine draws itself (not the author's text) — per episode language. 2026-10-23 인물형 롱폼 영어:
#: an English episode must not carry Korean provenance/end-card words. Korean is the default and keeps its exact pixels.
SCREEN_WORDS={
 'ko':{'record_illustration':'자료사진·삽화 합성','illustration':'설명용 삽화','cutout':'자료사진 합성',
       'similar':'비슷한 영상','recommended':'추천 영상','thanks':'시청해 주셔서 감사합니다',
       'music':'사용 음악','reading_order':'기록을\n읽는 순서'},
 'en':{'record_illustration':'Archival photo + illustration','illustration':'Illustration','cutout':'Archival photo composite',
       'similar':'Related videos','recommended':'Recommended','thanks':'Thanks for watching',
       'music':'Music','reading_order':'Reading\norder'}}

def screen_words(lang):
 if lang not in SCREEN_WORDS:raise ProductionError('screen_language','이 엔진이 화면 고정 문구를 가진 언어가 아닙니다: '+str(lang),action='repair_environment')
 return SCREEN_WORDS[lang]

def provenance_label(visual,media,lang='ko'):
 words=screen_words(lang)
 origins={media[mid]['origin'] for mid in visual['media']}
 if 'illustration' in origins:
  return words['record_illustration'] if 'record' in origins else words['illustration']
 if visual['kind']=='cutout':return words['cutout']
 return ''

def source_label(visual,media,lang='ko'):
 # A historical painting is neither a camera record nor an unlabeled AI scene.
 # Preserve the mandatory provenance prefix when adding a specific attribution.
 prefix=provenance_label(visual,media,lang);detail=visual.get('source_label','')
 return ' · '.join(x for x in (prefix,detail) if x)

def photo_source(visual,media,folder):
 source=Path(media[visual['media'][0]]['path'])
 if visual.get('crop') is not None:
  with Image.open(source) as image:
   a,b,c,d=visual['crop']
   if not (0<=a<c<=image.width and 0<=b<d<=image.height):
    raise ProductionError('photo_crop','사진 자르기 범위가 원본 밖입니다.',action='edit_plan')
   output=Path(folder)/'source-crop.png';image.crop((a,b,c,d)).convert('RGB').save(output)
  return output
 return source

class Layout:
 # 2026-10-05 (누락 점검 M3): 왼쪽 위에 늘 «금빛폭발» 채널 배지(남색 정사각형 + 금색 두 줄)를 그렸다 — 인물형 롱폼(이 엔진을
 # 쓰는 유일한 프리셋)의 모든 완성본에 다른 채널 이름이 박혔다(10-04 23:50 «납품 보류» 신고). 08-11 사장님 결정 «워터마크는
 # 모든 프리셋에 없어야 한다»·08-20 어랍숏 크레딧 제거와 같은 부류라 배지를 통째로 걷었다(금빛폭발은 서버의 프리셋이 아니고
 # 원본 채널 이름이다 — volcano_spec 에 그 이름의 프리셋이 없다). 인물 이름·상단 문구 알약은 배지 자리(왼쪽 35px)에서 시작하고
 # 글자 앞뒤 여백을 같게(26px) 둔다. 채널 이름 인자(branding)도 없앴다 — 받아 두면 다음 사람이 다시 그린다.
 BRAND_LEFT=35;BRAND_PAD=26
 def __init__(self,fonts,styles=None,headline='',lang='ko'):
  from longform_contract import validate_styles,FONT_NAMES
  self.fonts=Path(fonts);self.styles=validate_styles(styles or {});self.headline=headline
  self.lang=lang;screen_words(lang)
  self.caption_style=self.styles.get('caption',{})
  self.overlay_lock=self.styles.get('overlay_lock',False)
  if self.overlay_lock:
   self.caption_style={**self.caption_style,'x':W/2,'y':905,'background_opacity':1.0,'background_color':'#000000'}
  self.caption_file=self.caption_style.get('font_file','ROKAFSansMedium.ttf')
  if self.caption_style.get('font') and not self.caption_style.get('font_file'):
   requested=self.caption_style['font'].casefold();matches=[]
   for name in FONT_NAMES:
    font=self.font(name,20)
    if requested in (name.casefold(),font.getname()[0].casefold()):matches.append(name)
   if not matches:raise ProductionError('caption_font_missing','요청한 자막 글꼴의 실제 font_file을 지정하세요. 다른 글꼴로 대체하지 않습니다.',action='edit_plan')
   self.caption_file=matches[0]
 def font(self,name,size):
  # Fixed Korean/Latin raster layouts must not depend on optional RAQM.
  # Pillow otherwise selects RAQM on some hosts and BASIC on others,
  # changing fractional advances and per-character caption positions.
  return ImageFont.truetype(str(self.fonts/name),size,layout_engine=ImageFont.Layout.BASIC)
 def caption_font(self):return self.font(self.caption_file,round(self.caption_style.get('font_size',55)))
 def font_dependencies(self):return [self.fonts/self.caption_file]
 def brand(self,subject,headline=None):
  im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im);left=self.BRAND_LEFT;x=left+self.BRAND_PAD
  f=self.font('JalnanGothic.ttf',41);box=d.textbbox((0,0),subject,font=f);width=d.textlength(subject,font=f)
  if x+width+self.BRAND_PAD>W-35:raise ProductionError('brand_overflow','화면에 표시할 인물 이름을 줄이세요.',action='edit_plan')
  d.rounded_rectangle((left,85,x+width+self.BRAND_PAD,155),35,fill='#FDFDFD');d.text((x,104-box[1]),subject,font=f,fill='#141844')
  text=self.headline if headline is None else headline
  if text:
   f=self.font('ROKAFSansMedium.ttf',25);b=d.textbbox((0,0),text,font=f);right=x+d.textlength(text,font=f)+24
   if right>W-35:raise ProductionError('headline_overflow','인물/장면에 맞는 상단 문구를 줄이세요.',action='edit_plan')
   d.rounded_rectangle((left,49,right,92),21,fill='#EDCA63')
   d.text((x,58-b[1]),text,font=f,fill='#141844')
  return im
 def caption(self,text,highlights=(),style=None):
  # The contract matched these terms against the displayed caption (period-free); draw them the same way (#119).
  from longform_contract import display_highlights
  highlights=display_highlights(list(highlights))
  if style:
   # A card override must not leak to following narration cards or voices.
   merged={**self.caption_style,**style}
   if style.get('font') and 'font_file' not in style:merged.pop('font_file',None)
   card_layout=Layout(self.fonts,{'caption':merged,'overlay_lock':self.overlay_lock},self.headline,self.lang)
   return card_layout.caption(text,highlights)
  if any(isinstance(item,dict) and 'font_size' in item and item['text'] in text for item in highlights):
   return self.caption_sized(text,highlights)
  im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im);f=self.caption_font();style=self.caption_style
  width=d.textlength(text,font=f)
  if width>1780:raise ProductionError('caption_overflow','자막을 나누세요: '+text,action='edit_plan')
  b=d.textbbox((0,0),text,font=f);scale=style.get('font_size',55)/55
  x=style.get('x',W/2)-width/2;top=style.get('y',905);y=top-b[1]
  background=(x-22.45*scale,top-24.2*scale,x+width+22.45*scale,top+74.7*scale)
  stroke=round(style.get('outline_width',0))
  if min(background[:2])<0 or background[2]>W or background[3]>H or x-stroke<0 or x+width+stroke>W or top-stroke<0 or top+b[3]-b[1]+stroke>H:
   raise ProductionError('caption_overflow','자막 글꼴 크기나 위치 때문에 화면을 벗어납니다.',action='edit_plan')
  from PIL import ImageColor
  color=ImageColor.getrgb(style.get('background_color','#000000'))
  d.rounded_rectangle(background,17.92*scale,fill=(*color,round(style.get('background_opacity',151/255)*255)))
  shadow=Image.new('RGBA',(W,H));ImageDraw.Draw(shadow).text((x+3,y+8),text,font=f,fill=(0,0,0,56))
  im=Image.alpha_composite(im,shadow.filter(ImageFilter.GaussianBlur(3.9)));d=ImageDraw.Draw(im)
  colors={}
  for item in highlights:
   term=item['text'] if isinstance(item,dict) else item
   color=item.get('color','#00FCA6') if isinstance(item,dict) else '#00FCA6'
   at=text.find(term)
   while at>=0:
    colors.update({i:color for i in range(at,at+len(term))})
    at=text.find(term,at+len(term))
  # Prefix widths keep the font's kerning (a sum of single-glyph widths would move glyphs): O(L^2) in one
  # caption card's length only — cards are a few dozen characters (Layout.caption wraps them).
  for i,ch in enumerate(text):d.text((x+d.textlength(text[:i],font=f),y),ch,font=f,fill=colors.get(i,style.get('color','#FEFEFE')),stroke_width=stroke,stroke_fill=style.get('outline_color','#000000'))
  return im
 def caption_sized(self,text,highlights):
  """Measure mixed-size runs on a common baseline before creating final PNGs."""
  style=self.caption_style;base=self.caption_font();base_size=round(style.get('font_size',55))
  specs=[(style.get('color','#FEFEFE'),base_size) for _ in text]
  for item in highlights:
   term=item['text'] if isinstance(item,dict) else item
   color=item.get('color','#00FCA6') if isinstance(item,dict) else '#00FCA6'
   size=item.get('font_size',base_size) if isinstance(item,dict) else base_size
   if type(size) is not int or not 1<=size<=500:
    raise ProductionError('caption_highlight','강조 글자 크기는 1~500 정수여야 합니다.',action='edit_plan')
   at=text.find(term)
   while at>=0:
    specs[at:at+len(term)]=[(color,size)]*len(term);at=text.find(term,at+len(term))
  runs=[]
  for ch,spec in zip(text,specs):
   if runs and runs[-1][1]==spec:runs[-1][0]+=ch
   else:runs.append([ch,spec])
  im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im);stroke=round(style.get('outline_width',0))
  placed=[];advance=0.;bounds=[]
  for word,(color,size) in runs:
   font=base if size==base_size else base.font_variant(size=size)
   box=d.textbbox((advance,0),word,font=font,anchor='ls',stroke_width=stroke)
   bounds.append(box);placed.append((word,color,font,advance));advance+=d.textlength(word,font=font)
  left=min(b[0] for b in bounds);right=max(b[2] for b in bounds)
  upper=min(b[1] for b in bounds);lower=max(b[3] for b in bounds)
  width=right-left;top=style.get('y',905);x=style.get('x',W/2)-(left+right)/2;baseline=top-upper
  scale=max(size for _,size in specs)/55
  background=(x+left-22.45*scale,top-24.2*scale,x+right+22.45*scale,top+lower-upper+24.2*scale)
  if width>1780 or min(background[:2])<0 or background[2]>W or background[3]>H:
   raise ProductionError('caption_overflow','강조 크기를 포함한 자막을 나누거나 위치를 조정하세요: '+text,action='edit_plan')
  bg=ImageColor.getrgb(style.get('background_color','#000000'))
  d.rounded_rectangle(background,17.92*scale,fill=(*bg,round(style.get('background_opacity',151/255)*255)))
  shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow)
  for word,color,font,offset in placed:sd.text((x+offset+3,baseline+8),word,font=font,anchor='ls',fill=(0,0,0,56))
  im=Image.alpha_composite(im,shadow.filter(ImageFilter.GaussianBlur(3.9)));d=ImageDraw.Draw(im)
  for word,color,font,offset in placed:d.text((x+offset,baseline),word,font=font,anchor='ls',fill=color,stroke_width=stroke,stroke_fill=style.get('outline_color','#000000'))
  return im
 def overlay(self,subject,visual,provenance=''):
  im=self.brand(subject,visual.get('headline',self.headline))
  if 'brand_position' in visual and not getattr(self,'overlay_lock',False):
   from longform_contract import validate_brand_position
   x,y=validate_brand_position(visual['brand_position']);box=im.getbbox()
   if box:
    brand=im.crop(box)
    if x+brand.width>W or y+brand.height>H:
     raise ProductionError('brand_overflow','브랜드 표시 전체가 화면 안에 들어오게 위치를 조정하세요.',action='edit_plan')
    im=Image.new('RGBA',(W,H));im.alpha_composite(brand,(x,y))
  d=ImageDraw.Draw(im)
  if provenance:
   style=visual.get('source_style',{});size=style.get('font_size',20)
   f=self.font(style.get('font_file','Paperlogy-3Light.ttf'),size);box=d.textbbox((0,0),provenance,font=f)
   if d.textlength(provenance,font=f)>W-94:raise ProductionError('source_label_overflow','화면 자료 설명을 줄이세요.',action='edit_plan')
   top=1054-size-15
   d.rounded_rectangle((35,top-8,59+d.textlength(provenance,font=f),1054),6,fill=(0,0,0,style.get('background_alpha',100)))
   d.text((47,top-box[1]),provenance,font=f,fill='#FFFFFF')
  if visual.get('reaction'):
   f=self.font('BMYEONSUNG.ttf',118);box=d.textbbox((1240,455),visual['reaction'],font=f,anchor='mm',stroke_width=14)
   if box[0]<0 or box[1]<0 or box[2]>W or box[3]>H:raise ProductionError('reaction_overflow','효과 문구를 화면 안에 들어오게 줄이세요.',action='edit_plan')
   d.text((1240,455),visual['reaction'],font=f,anchor='mm',fill='#FAC02D',stroke_width=14,stroke_fill='#1E1929')
  if visual.get('work'):im.alpha_composite(self.work_layer(subject,visual))
  return im

 def work_layer(self,subject,visual):
  im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im)
  work=visual['work'];f=self.font('JalnanGothic.ttf',62);width=d.textlength(work['title'],font=f);left=1848-width
  headline_right=212+d.textlength(visual.get('headline',self.headline),font=self.font('ROKAFSansMedium.ttf',25))
  if left<max(550,headline_right,214+d.textlength(subject,font=self.font('JalnanGothic.ttf',41)))+24:raise ProductionError('work_chip_overflow','작품칩 문구가 인물/상단 표시와 겹칩니다.',action='edit_plan')
  d.rounded_rectangle((left,56,1895,148),7,fill='#252627',outline='#F4FB04',width=5)
  b=d.textbbox((0,0),work['title'],font=f);d.text((left+25,72-b[1]),work['title'],font=f,fill='#F5FC01')
  d.text((left+7,19),str(work['year']),font=self.font('ROKAFSansMedium.ttf',25),fill='white',stroke_width=1,stroke_fill='#272627')
  return im

def image_layout(visual,media):
 kind=visual['kind'];paths=[Path(media[x]['path']) for x in visual['media']]
 if kind=='split':
  im=Image.new('RGB',(W,H))
  im=split_frame(split_bases(visual,media),0,2,max_scale=visual.get('max_scale'))
  ImageDraw.Draw(im).line((960,0,960,H),fill='white',width=4)
 elif kind=='cutout':
  im=ImageOps.fit(Image.open(paths[0]).convert('RGB'),(W,H),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(45)).convert('RGBA')
  fg=Image.open(paths[1]).convert('RGBA')
  if fg.getchannel('A').getextrema()[0]==255:raise ProductionError('cutout_alpha_missing','누끼 소재에 투명 영역이 없습니다.',action='repair_asset')
  fg=ImageOps.contain(fg,(900,850),Image.Resampling.LANCZOS);x=(W-fg.width)//2;y=H-fg.height
  mask=Image.new('L',(W,H));mask.paste(fg.getchannel('A'),(x,y));outline=Image.new('RGBA',(W,H),'white');outline.putalpha(mask.filter(ImageFilter.MaxFilter(21)))
  im=Image.alpha_composite(im,outline);im.alpha_composite(fg,(x,y));im=im.convert('RGB')
 else:raise ProductionError('unsupported_layout',kind)
 return im

def cutout_layers(visual,media,size=(W,H)):
 """Keep the background and outlined subject separate until each video frame."""
 width,height=size
 with Image.open(media[visual['media'][0]]['path']) as source:
  background=ImageOps.fit(source.convert('RGB'),size,Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(width*visual.get('background_blur',45)/W)).convert('RGBA')
 with Image.open(media[visual['media'][1]]['path']) as source:
  foreground=source.convert('RGBA')
 if foreground.getchannel('A').getextrema()[0]==255:
  raise ProductionError('cutout_alpha_missing','누끼 소재에 투명 영역이 없습니다.',action='repair_asset')
 # 2x fixed original canvas; sample it using floating-point transforms instead
 # of repeatedly rounding resized widths/positions, which made the old pan shake.
 subject=Image.new('RGBA',(width*2,height*2))
 foreground=ImageOps.contain(foreground,(round(width*900/W*2),round(height*850/H*2)),Image.Resampling.LANCZOS)
 x=(width*2-foreground.width)//2;y=height*2-foreground.height
 mask=Image.new('L',subject.size);mask.paste(foreground.getchannel('A'),(x,y))
 outline=Image.new('RGBA',subject.size,'white')
 kernel=max(3,round(width*42/W)//2*2+1)
 outline.putalpha(mask.filter(ImageFilter.MaxFilter(kernel)))
 subject=Image.alpha_composite(subject,outline);subject.alpha_composite(foreground,(x,y))
 return background,subject

def cutout_frame(background,subject,frame,frames,entrance='left'):
 width,height=background.size;t=frame/FPS
 entrance_progress=min(1.,t/.4);ease=1-(1-entrance_progress)**3
 progress=frame/max(1,frames-1)
 scale=.95+.05*ease+.035*progress
 dx=(-1 if entrance=='left' else 1)*width*.065*(1-ease) if entrance!='rise' else 0.
 dy=height*.075*(1-ease) if entrance=='rise' else 0.
 dx+=width*.012*progress
 # Fixed bottom-centre anchor. No frame depends on the previous frame.
 cx=width/2;cy=height
 transform=(2/scale,0,2*cx-2*(cx+dx)/scale,0,2/scale,2*cy-2*(cy+dy)/scale)
 layer=subject.transform(background.size,Image.Transform.AFFINE,transform,Image.Resampling.BICUBIC)
 opacity=min(1.,t/.18)
 if opacity<1:layer.putalpha(layer.getchannel('A').point(lambda a:round(a*opacity)))
 return Image.alpha_composite(background,layer).convert('RGB')

def animated_cutout(visual,media,target,frames):
 from longform_photo import encode_frames,Frames
 background,subject=cutout_layers(visual,media)
 encode_frames(Frames(lambda:(cutout_frame(background,subject,i,frames,visual.get('entrance','left')).tobytes() for i in range(frames))),target)

def hyperframes_launcher():
 # Volta supplies a native npx.exe; execute it directly, without cmd.exe.
 if __import__('os').name=='nt':
  native=shutil.which('npx.exe')
  if native:return [native]
  npx=shutil.which('npx.cmd');node=shutil.which('node')
  if npx and node:
   cli=Path(npx).resolve().parent/'node_modules/npm/bin/npx-cli.js'
   if cli.is_file():return [node,str(cli)]
 else:
  npx=shutil.which('npx')
  if npx:return [npx]
 raise ProductionError('runtime_missing','Node.js/npm 실행 경로 확인이 필요합니다.',action='repair_environment')

def graphic(folder,visual,seconds,layout,media,*,handle_seconds=0):
 from longform_graphic import document
 folder=Path(folder)
 document(folder,visual,seconds,layout.fonts,media,handle_seconds=handle_seconds,lang=layout.lang)
 if visual.get('renderer')=='hyperframes':
  from longform_hyperframes import render_document
 else:
  from longform_native import render_document
 return render_document(folder,max(1,math.ceil((seconds+handle_seconds)*FPS-1e-7)))

def still_command(photo,frames,source):
 """A still photo held for `frames` (picture.mp4 — decoded again by its scene, not joined with `-c copy`).

 The old argv had no -c:v, so FFmpeg picked libx264 at its defaults (preset medium, crf 23). The encoder slot names
 that explicitly: on CPU `-c:v libx264 -crf 23` (same encode), else this PC's GPU pick at the same size
 (runner/video_encoder.py · BPP medium23 measured 10-19). No colour tags, like every longform piece.
 film_editor.command runs it: the GPU try, then CPU once."""
 import video_encoder
 return ['ffmpeg','-y','-v','error','-loop','1','-i',photo,'-vf','scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080',
         '-frames:v',frames,'-r',FPS,*video_encoder.x264(None,23,W,H,FPS,program='ffmpeg',color=False),'-pix_fmt','yuv420p',source]

def prepare_picture(folder,block,media,voice,layout,*,handle_frames=0):
 folder=Path(folder);visual=block['visual'];frames=voice['frames'];seconds=frames/FPS;kind=visual['kind']
 treated=None
 if handle_frames and (kind!='graphic' or visual.get('template')!='authored'):
  raise ProductionError('scene_handoff_kind','전환용 추가 프레임은 맞춤 그래픽에서 생성합니다.',action='edit_plan')
 if kind=='photo':
  photo=photo_source(visual,media,folder)
  source=folder/'picture.mp4';motion=visual.get('motion','in')
  if motion=='still' and visual.get('fit','auto')=='auto':
   command(folder,still_command(photo,frames,source),'still')
  else:photo_render(photo,source,frames,motion,fit=visual.get('fit','auto'),max_scale=visual.get('max_scale'),min_scale=visual.get('min_scale',1))
  start=0
 elif kind=='cutout':
  source=folder/'picture.mp4';animated_cutout(visual,media,source,frames);start=0
 elif kind=='split':
  source=folder/'picture.mp4';animated_split(visual,media,source,frames);start=0
 elif kind=='montage':
  from longform_montage import build
  source=build(folder/'montage',visual,media,frames,assets=Path(layout.fonts).parent if any(s.get('video_treatment') for s in visual['shots']) else None);start=0
 elif kind=='graphic':
  if visual.get('template')=='authored':
   from longform_graphic import aligned_visual
   visual=aligned_visual(visual,voice)
  source=graphic(folder,visual,seconds,layout,media,handle_seconds=handle_frames/FPS);start=0
 else:
  source=Path(media[visual['media'][0]]['path']);start=visual['in']
  from longform_video import inspect_cuts
  inspect_cuts(folder,source,start,seconds,cut_review=visual.get('cut_review'))
  if seconds>visual['out']-start+1/FPS:raise ProductionError('source_too_short','나레이션보다 영상 구간이 짧습니다: '+block['id'],action='edit_plan')
 if kind=='video' and visual.get('video_treatment'):
  from longform_video_treatment import prepare
  treated=prepare(folder/'source-treatment',source,start,frames,visual['video_treatment'],Path(layout.fonts).parent)
  source=Path(treated['path']);start=0
 # Preserve the clean source and its clock before brand/caption composition.
 # No extra encode: video remains the original source with an explicit offset.
 from longform_state import save
 picture={'path':str(source),'start':start,'kind':kind,'visual':visual,
          'frames':frames+handle_frames,'seconds':seconds+handle_frames/FPS,'visible_frames':frames}
 if treated is not None:picture.update(source_treated=True,treatment_proof=treated['proof'])
 if kind=='montage':picture['montage_proof']=str(folder/'montage/montage.json')
 # Only reports under this content-addressed picture stage belong to this scene.
 reports=sorted(folder.rglob('source-cuts.json'))
 picture['source_boundary_reports']=[str(p) for p in reports]
 save(folder/'picture.json',picture)
 outputs=[folder/'picture.json',source]
 for report in reports:
  outputs.append(report)
  evidence=json.loads(report.read_text(encoding='utf-8')).get('boundary_evidence',{})
  outputs.extend(Path(evidence[k]) for k in ('head','tail','head_context','tail_context') if k in evidence)
 if kind=='montage':outputs.append(Path(picture['montage_proof']))
 return picture,outputs

def render_scene(folder,block,media,voice,subject,layout,*,picture=None,picture_only=False):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 if picture is None:picture,_=prepare_picture(folder,block,media,voice,layout)
 frames=voice['frames'];seconds=frames/FPS
 if picture['frames']<frames:
  raise ProductionError('picture_clock_mismatch','화면과 나레이션의 프레임 수가 다릅니다.',action='edit_plan')
 visual=picture['visual'];kind=picture['kind'];source=Path(picture['path']);start=picture['start']
 content_glitch=visual.get('glitch',{}).get('scope','picture')=='content'
 layers=[];brand_views=[];animated_captions={};work_runs=[];work_layers=[]
 group_zoom=visual.get('group_zoom') if kind=='montage' and not picture_only else None
 work_motion=visual.get('work_motion') if kind=='montage' else None
 group_zoom_boundary=None
 if not picture_only:
  view=dict(visual)
  if content_glitch and visual.get('work'):
   view.pop('work')
   work_runs.append({'start':0,'end':frames,'work':visual['work']})
  layers=[(folder/'brand.png',0,seconds)];layout.overlay(subject,view,source_label(visual,media,layout.lang)).save(layers[0][0]);brand_views.append(view)
 if group_zoom:
  proof=json.loads(Path(picture['montage_proof']).read_text(encoding='utf-8'))
  at=group_zoom['after_shot'];timings=proof['shots']
  group_zoom_boundary=timings[at+1]['timeline_start_frame']
  if group_zoom['out_frames']>timings[at]['visible_frames'] or group_zoom['in_frames']>timings[at+1]['visible_frames']:
   raise ProductionError('group_zoom_length','공동 확대 전환이 실제 컷 길이를 넘습니다.',action='edit_plan')
 if not picture_only and kind=='montage' and any('work' in shot or 'source_label' in shot or 'brand_position' in shot for shot in visual['shots']):
  # Use the encoded montage's actual frame allocation, never a second timing estimate.
  proof=json.loads(Path(picture['montage_proof']).read_text(encoding='utf-8'))
  layers=[];brand_views=[]
  for i,(shot,timing) in enumerate(zip(visual['shots'],proof['shots'])):
   view=dict(visual);view.pop('work',None)
   view['media']=[shot['media']]+([shot['paired_photo']['media']] if shot.get('paired_photo') else [])
   if 'brand_position' in shot:view['brand_position']=shot['brand_position']
   if 'source_label' in shot:view['source_label']=shot['source_label']
   if shot.get('work') and not (work_motion or group_zoom or content_glitch):view['work']=shot['work']
   p=folder/f'brand-shot-{i}.png'
   layout.overlay(subject,view,source_label(view,media,layout.lang)).save(p)
   a=timing['timeline_start_frame'];b=a+timing['visible_frames']
   layers.append((p,a/FPS,b/FPS));brand_views.append(view)
   if (work_motion or group_zoom or content_glitch) and shot.get('work'):
    if work_runs and work_runs[-1]['end']==a and work_runs[-1]['work']==shot['work']:work_runs[-1]['end']=b
    else:work_runs.append({'start':a,'end':b,'work':shot['work']})
 if not picture_only and picture.get('handoff_source_visual'):
  boundary=picture['handoff_frames']/FPS;combined=[]
  previous_label=source_label(picture['handoff_source_visual'],media,layout.lang)
  current_label=source_label(visual,media,layout.lang)
  label=' → '.join(dict.fromkeys(x for x in (previous_label,current_label) if x))
  for i,((p,a,b),view) in enumerate(zip(layers,brand_views)):
   if a<boundary and previous_label and previous_label!=current_label:
    mixed=folder/f'brand-handoff-{i}.png';layout.overlay(subject,view,label).save(mixed)
    combined.append((mixed,a,min(b,boundary)))
    if b>boundary:combined.append((p,boundary,b))
   else:combined.append((p,a,b))
  layers=combined
 fixed_layers=set(range(len(layers)))
 if not picture_only and work_runs:
  from longform_caption_motion import work_entrance_frames
  for i,run in enumerate(work_runs):
   view={**visual,'work':run['work']};p=folder/f'work-{i}.png'
   layer=layout.work_layer(subject,view);layer.save(p)
   first=run['start'];stop=run['end']
   if work_motion:
    motion=work_entrance_frames(layer,folder/f'work-motion-{i}',work_motion,stop-first,FPS)
    animated_captions[len(layers)]={**motion,'first':first}
   work_layers.append(len(layers))
   layers.append((p,first/FPS,stop/FPS))
 for i,caption in enumerate([] if picture_only else voice['captions']):
  p=folder/f'caption-{i}.png';layout.caption(caption['text'],block.get('highlights',[]),style=caption.get('style')).save(p);layers.append((p,caption['start'],caption['end']))
  if caption.get('motion') and not getattr(layout,'overlay_lock',False):
   import math
   from longform_caption_motion import entrance_frames
   first=max(0,math.ceil(caption['start']*FPS-1e-7));stop=min(frames,math.ceil(caption['end']*FPS-1e-7))
   if stop<=first:raise ProductionError('caption_empty','자막 모션의 표시 프레임이 없습니다.')
   with Image.open(p) as caption_image:
    animated_captions[len(layers)-1]={**entrance_frames(caption_image,folder/f'caption-motion-{i}',caption['motion'],stop-first,FPS),'first':first}
 # Keep process termination messages in the saved log; at error verbosity
 # FFmpeg can handle a signal and exit 255 without explaining it.
 args=['ffmpeg','-y','-v','info','-filter_complex_threads','1','-ss',start,'-i',source]
 # Decode each static overlay once; overlay repeatlast keeps its pixels.
 # Looping every PNG at 60fps needlessly re-decodes every inactive caption.
 for index,(p,_,_) in enumerate(layers):
  if index in animated_captions:args+=['-framerate',FPS,'-i',animated_captions[index]['pattern']]
  else:args+=['-i',p]
 effects={} if picture.get('normalized') else visual
 if picture_only and picture.get('visible_frames',frames)!=frames:
  import copy
  effects=copy.deepcopy(effects);ratio=max(1,picture['visible_frames']-1)/max(1,frames-1)
  for name in ('ink_cover','tear_cover','brush_cover','light_leak','negative_splatter','grain_wipe','glitch'):
   if name in effects:
    for key in ('at','duration'):
     if key in effects[name]:effects[name][key]*=ratio
 ink=effects.get('ink_cover')
 if ink:
  from longform_ink import render_mask
  args+=['-i',render_mask(folder/'ink',frames,ink)]
 tear=effects.get('tear_cover')
 if tear:
  from longform_tear import render_layers
  for path in render_layers(folder/'tear',frames,tear):args+=['-i',path]
 brush=effects.get('brush_cover')
 if brush:
  from longform_transitions import render_brush
  for path in render_brush(folder/'brush',frames,brush):args+=['-i',path]
 light=effects.get('light_leak')
 # Assign actual input offsets alongside the input list, independently of
 # whether an optional effect is enabled. No placeholder stream is added.
 light_index=len(layers)+1+(1 if ink else 2 if tear or brush else 0)
 if light:
  from longform_transitions import render_light
  args+=['-i',render_light(folder/'light',frames,light)]
 next_input=len(layers)+1+(1 if ink else 2 if tear or brush else 0)+(1 if light else 0)
 splatter=effects.get('negative_splatter')
 splatter_index=next_input
 if splatter:
  from longform_transitions import render_splatter
  next_input+=1
  args+=['-i',render_splatter(folder/'splatter',frames,splatter)]
 grain=effects.get('grain_wipe')
 grain_index=next_input
 if grain:
  from longform_transitions import render_grain
  for path in render_grain(folder/'grain',frames,grain,media[grain['media']]['path']):args+=['-i',path]
 graph='[0:v]setpts=PTS-STARTPTS,fps=60,setsar=1[v0];'
 if kind=='video' and not picture.get('normalized') and not picture.get('source_treated'):
  graph=direct_video_graph(source,visual)
 if ink:
  graph=graph.replace('[v0];','[inkbase0];')
  graph+=f'[inkbase0]format=gbrp[inkbase];[{len(layers)+1}:v]scale=1920:1080,format=gbrp[inkmask];[inkbase][inkmask]blend=all_mode=multiply,format=yuv420p[v0];'
 if tear:
  graph=graph.replace('[v0];','[tearbase0];')
  index=len(layers)+1
  graph+=f'[tearbase0]format=gbrp[tearbase];[{index}:v]scale=1920:1080,format=gbrp[tearmask];[{index+1}:v]scale=1920:1080,format=gbrp[tearfold];[tearbase][tearmask]blend=all_mode=multiply[remaining];[remaining][tearfold]blend=all_mode=addition,format=yuv420p[v0];'
 if brush:
  graph=graph.replace('[v0];','[brushbase0];');index=len(layers)+1
  graph+=f'[brushbase0]format=gbrp[brushbase];[{index}:v]scale=1920:1080,format=gbrp[brushkeep];[{index+1}:v]scale=1920:1080,format=gbrp[brushpaint];[brushbase][brushkeep]blend=all_mode=multiply[brushremaining];[brushremaining][brushpaint]blend=all_mode=addition,format=yuv420p[v0];'
 if light:
  graph=graph.replace('[v0];','[lightbase0];')
  graph+=f'[lightbase0]format=gbrp[lightbase];[{light_index}:v]scale=1920:1080,format=gbrp[lightwash];[lightbase][lightwash]blend=all_mode=screen,format=yuv420p[v0];'
 if effects.get('glitch') and not content_glitch:
  from longform_transitions import glitch_filter
  graph=graph.replace('[v0];','[glitchbase];')
  graph+=glitch_filter(frames,effects['glitch'],(W,H))
 if splatter:
  from longform_transitions import splatter_filter
  graph=graph.replace('[v0];','[splatterbase];');graph+=splatter_filter(splatter_index)
 if grain:
  graph=graph.replace('[v0];','[grainbase0];')
  graph+=f'[grainbase0]format=gbrp[grainbase];[{grain_index}:v]scale=1920:1080,format=gbrp[grainkeep];[{grain_index+1}:v]scale=1920:1080,format=gbrp[grainpaint];[grainbase][grainkeep]blend=all_mode=multiply[grainremaining];[grainremaining][grainpaint]blend=all_mode=addition,format=yuv420p[v0];'
 if effects.get('edge_strobe'):
  from longform_transitions import edge_strobe_filter
  graph=graph.replace('[v0];','[edgebase];')
  graph+=edge_strobe_filter(frames,effects['edge_strobe'])
 from longform_video import overlay_enable
 # Only the picture and work labels enter the shared moving surface.
 # Set membership for the work-layer list (same order; fixed_layers is already a set) instead of a list scan per layer.
 work_set=set(work_layers)
 order=work_layers+[i for i in range(len(layers)) if i not in work_set] if group_zoom else list(range(len(layers)))
 if content_glitch:
  order=[i for i in order if i not in fixed_layers]+[i for i in order if i in fixed_layers]
 current='v0'
 for position,i in enumerate(order):
  if group_zoom and position==len(work_layers):
   from longform_transitions import group_zoom_filter
   graph+=group_zoom_filter(current,'groupzoom',group_zoom,group_zoom_boundary,canvas=(W,H,FPS));current='groupzoom'
  if content_glitch and not picture_only and position==len(order)-len(fixed_layers):
   # Deferred even for normalized picture caches: apply exactly once, after
   # moving labels/captions and before the fixed logo/source overlays.
   from longform_transitions import glitch_filter
   graph+=glitch_filter(frames,visual['glitch'],(W,H),input_label=current,output_label='contentglitch');current='contentglitch'
  _,a,b=layers[i]
  enabled=overlay_enable(a,b,frames)
  next_label=f'v{position+1}'
  if i in animated_captions:
   motion=animated_captions[i]
   graph+=f"[{i+1}:v]settb=expr=1/{FPS},setpts=N+{motion['first']}[captionmotion{i}];"
   graph+=f"[{current}][captionmotion{i}]overlay={motion['x']}:{motion['y']}:enable='{enabled}'[{next_label}];"
  else:graph+=f"[{current}][{i+1}:v]overlay=0:0:enable='{enabled}'[{next_label}];"
  current=next_label
 output=folder/('clean.mkv' if picture_only else 'scene.mp4')
 # picture_only: lossless normalized frame surface; never an extra lossy delivery encode.
 result={'path':str(output),'frames':frames,'seconds':seconds,
         'source_boundary_reports':picture.get('source_boundary_reports',[])}
 tail=['-filter_complex',graph.rstrip(';'),'-map',f'[{current}]','-an','-frames:v',frames]
 if picture_only:
  command(folder,args+tail+['-c:v','ffv1','-pix_fmt','yuv420p',output],'picture-normalize',timeout=1800)
  return result,[output]
 # scene.mp4 is joined with `-c copy` (longform_engine.assemble): this PC's pick only, no per-scene CPU retry —
 # a GPU failure raises EncoderFailed and render_joined renders every joined piece again on CPU.
 from longform_photo import encoder_slot,joined_encode,joined_failed
 argv,gpu,name=joined_encode(args+tail+[*encoder_slot(19),'-pix_fmt','yuv420p',output])
 try:command(folder,argv,'scene',timeout=1800)
 except ValueError as error:
  if gpu is None or 'time limit' in str(error):raise
  raise joined_failed(gpu,str(error)) from error
 result['encoder']=name
 return result,[output]

def thumbnail(plan,layout,path):
 if plan['thumbnail'].get('elements'):
  return composed_thumbnail(plan,layout,path)
 canvas=Image.new('RGB',(1280,720),'black');source=Path(plan['media'][plan['thumbnail']['media']]['path'])
 photo=Image.open(source).convert('RGB')
 if plan['thumbnail'].get('crop'):
  box=plan['thumbnail']['crop']
  if not (0<=box[0]<box[2]<=photo.width and 0<=box[1]<box[3]<=photo.height):raise ProductionError('thumbnail_crop','썸네일 자르기 범위가 원본 밖입니다.')
  photo=photo.crop(tuple(box))
 photo=ImageOps.fit(photo,(590,720),Image.Resampling.LANCZOS);canvas.paste(photo,(0,0))
 if plan['thumbnail'].get('secondary_media'):
  secondary=Image.open(plan['media'][plan['thumbnail']['secondary_media']]['path']).convert('RGB')
  canvas.paste(ImageOps.fit(secondary,(370,210),Image.Resampling.LANCZOS,centering=(.2,.5)),(810,35))
 layer=Image.new('RGBA',(720,420));d=ImageDraw.Draw(layer);f=layout.font('Paperlogy-8ExtraBold.ttf',98)
 for i,line in enumerate(plan['thumbnail']['lines']):
  if d.textlength(line,font=f)>665:raise ProductionError('thumbnail_overflow','썸네일 문구를 줄이세요.',action='edit_plan')
  d.text((25,25+i*157),line,font=f,fill='#99ff00' if i==0 else 'white',stroke_width=7,stroke_fill='black')
 layer=layer.transform(layer.size,Image.Transform.AFFINE,(1,.09,-22,0,1,0),Image.Resampling.BICUBIC);canvas.paste(layer,(557,290),layer);canvas.save(path)


def composed_thumbnail(plan,layout,path):
 """Explicit editorial geometry: no automatic small inset or fixed two-line box."""
 canvas=Image.new('RGBA',(1280,720),'black')
 for element in plan['thumbnail']['elements']:
  x,y,w,h=element['box']
  if element['kind']=='image':
   with Image.open(plan['media'][element['media']]['path']) as source:
    picture=source.convert('RGBA')
   if element.get('crop'):
    a,b,c,d=element['crop']
    if not (0<=a<c<=picture.width and 0<=b<d<=picture.height):
     raise ProductionError('thumbnail_crop','썸네일 자르기 범위가 원본 밖입니다.')
    picture=picture.crop((a,b,c,d))
   picture=ImageOps.fit(picture,(w,h),Image.Resampling.LANCZOS)
   canvas.alpha_composite(picture,(x,y))
  else:
   face=layout.font(element.get('font','Paperlogy-8ExtraBold.ttf'),element['size'])
   draw=ImageDraw.Draw(canvas);stroke=element.get('stroke',7)
   bbox=draw.textbbox((0,0),element['text'],font=face,stroke_width=stroke)
   tw,th=bbox[2]-bbox[0],bbox[3]-bbox[1]
   shear=element.get('shear',0)
   extra=math.ceil(abs(shear)*th)
   if tw+extra>w or th>h:
    raise ProductionError('thumbnail_overflow','썸네일 기울기를 포함한 글자가 지정한 영역을 넘습니다: '+element['text'],action='edit_plan')
   layer=Image.new('RGBA',(tw+extra,th));draw=ImageDraw.Draw(layer)
   draw.text((-bbox[0],-bbox[1]),element['text'],font=face,fill=element['color'],stroke_width=stroke,stroke_fill='black')
   if element.get('gradient'):
    # Color only the glyph interior; keep the original black outline and alpha.
    mask=Image.new('L',layer.size)
    ImageDraw.Draw(mask).text((-bbox[0],-bbox[1]),element['text'],font=face,fill=255)
    ink=mask.getbbox()
    if ink:
     colors=[ImageColor.getrgb(c) for c in element['gradient']['colors']]
     vertical=element['gradient'].get('direction','vertical')=='vertical'
     start,end=(ink[1],ink[3]) if vertical else (ink[0],ink[2])
     gradient=Image.new('RGBA',layer.size);paint=ImageDraw.Draw(gradient)
     length=layer.height if vertical else layer.width
     for pos in range(length):
      u=max(0,min(1,(pos-start)/max(1,end-start-1)))*(len(colors)-1)
      segment=min(len(colors)-2,int(u));fraction=u-segment
      color=tuple(round(a+(b-a)*fraction) for a,b in zip(colors[segment],colors[segment+1]))+(255,)
      paint.line((0,pos,layer.width-1,pos) if vertical else (pos,0,pos,layer.height-1),fill=color)
     layer.paste(gradient,(0,0),mask)
   if shear:
    # Inverse mapping keeps both the upper and lower stroked corners in frame.
    offset=-shear*max(0,th-1) if shear>0 else 0
    layer=layer.transform(layer.size,Image.Transform.AFFINE,(1,shear,offset,0,1,0),Image.Resampling.BICUBIC)
   canvas.alpha_composite(layer,(x,y))
 canvas.convert('RGB').save(path)


def split_frame(bases,index,frames,size=(W,H),max_scale=None):
 """Independent opposing camera moves, sampled from immutable 2x originals."""
 from longform_photo import coefficients
 width,height=size;half=width//2;canvas=Image.new('RGB',size)
 for i,base in enumerate(bases):
  panel=base.transform((half,height),Image.Transform.AFFINE,
      coefficients(index,frames,half,height,'in' if i==0 else 'out',max_scale=max_scale),Image.Resampling.BICUBIC)
  canvas.paste(panel,(i*half,0))
 ImageDraw.Draw(canvas).line((half,0,half,height),fill='white',width=max(2,width//480))
 return canvas


def animated_split(visual,media,target,frames):
 from longform_photo import encode_frames,Frames
 bases=split_bases(visual,media)
 encode_frames(Frames(lambda:(split_frame(bases,i,frames,max_scale=visual.get('max_scale')).tobytes() for i in range(frames))),target)

def split_bases(visual,media):
 bases=[]
 for i,mid in enumerate(visual['media']):
  panel=visual.get('panels',[{},{}])[i]
  with Image.open(media[mid]['path']) as original:
   source=original.convert('RGB')
  if panel.get('crop'):
   a,b,c,d=panel['crop']
   if not (0<=a<c<=source.width and 0<=b<d<=source.height):raise ProductionError('split_crop','분할 사진 자르기 범위가 원본 밖입니다.',action='edit_plan')
   source=source.crop((a,b,c,d))
  size=(W,H*2)
  base=ImageOps.fit(source,size,Image.Resampling.LANCZOS)
  if panel.get('fit','cover')=='contain':
   base=base.filter(ImageFilter.GaussianBlur(70));inset=round(panel.get('inset_top',0)*2)
   foreground=ImageOps.contain(source,(size[0],size[1]-inset),Image.Resampling.LANCZOS)
   base.paste(foreground,((size[0]-foreground.width)//2,inset+(size[1]-inset-foreground.height)//2))
  bases.append(base)
 return bases

def direct_video_graph(source,visual):
 """Honor explicit mattes; retain legacy blur only when background is omitted."""
 prefix=video_crop_filter(source,visual.get('crop'))
 if visual.get('fit','contain')!='contain':
  from longform_montage import video_filter
  # Validate the source crop above, then use the same explicit cover contract.
  return '[0:v]setpts=PTS-STARTPTS,'+video_filter(visual)+'[v0];'
 top=visual.get('inset_top',0);bottom=visual.get('inset_bottom',0)
 if not all(isinstance(n,(int,float)) and 0<=n<=400 for n in (top,bottom)):
  raise ProductionError('video_inset_range','영상 여백은 0~400px입니다.',action='edit_plan')
 height=H-top-bottom
 background=visual.get('background','blur')
 if background not in ('black','blur'):
  raise ProductionError('video_background','영상 배경은 black 또는 blur입니다.',action='edit_plan')
 if background=='black':
  return '[0:v]'+prefix+f'setpts=PTS-STARTPTS,fps=60,setsar=1,scale=1920:{height}:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:{top}+({height}-ih)/2:color=black,setsar=1[v0];'
 return '[0:v]'+prefix+f'setpts=PTS-STARTPTS,fps=60,setsar=1,split[b][f];[b]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,gblur=sigma=45,eq=brightness=-0.16[bg];[f]scale=1920:{height}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:{top}+({height}-h)/2,setsar=1[v0];'

def video_crop_filter(source,crop):
 if crop is None:return ''
 raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(source)],timeout=30)
 stream=json.loads(raw)['streams'][0];a,b,c,d=crop
 if not (0<=a<c<=stream['width'] and 0<=b<d<=stream['height']):raise ProductionError('video_crop','영상 자르기 범위가 원본 밖입니다.',action='edit_plan')
 return f'crop={c-a}:{d-b}:{a}:{b},'
