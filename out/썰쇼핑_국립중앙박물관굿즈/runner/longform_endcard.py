"""Seek-safe nine-second recommendation card; credits come from the authored plan."""
import math
from bisect import bisect_right
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from longform_photo import encode_frames,Frames

# udJmxrlVn_w, 1835.833333–1839.166667; measured at native 640x360.
# Evidence: docs/2026-09-19_금빛폭발-롱폼/2026-09-24-endcard-arrow-measurement.json.
# Offsets are measured bounding-box left/top; stroke is a drawn approximation.
_ARROW_PATH=((0,274,76),(5,265,82),(10,262,85),(15,262,84),
 (20,266,82),(25,270,78),(30,274,76),(35,266,82),(40,262,85),
 (45,262,84),(50,268,80),(55,272,76),(60,269,80),(65,262,84),
 (70,262,86),(75,264,84),(80,268,80),(85,272,78),(90,272,78),
 (95,264,84),(100,262,85))

def draw_recommendation_arrow(im,t):
 # Absolute-time interpolation allows backward seeks and 60 fps output.
 if not 0<=t<100/30:return
 f=t*30;index=min(len(_ARROW_PATH)-2,max(0,bisect_right([p[0] for p in _ARROW_PATH],f)-1))
 a,b=_ARROW_PATH[index:index+2];q=(f-a[0])/(b[0]-a[0])
 x=(a[1]+(b[1]-a[1])*q)*3;y=(a[2]+(b[2]-a[2])*q)*3
 alpha=min(1,max(0,(100-f)/13))
 layer=Image.new('RGBA',(280,205));d=ImageDraw.Draw(layer)
 color=(255,0,0,round(255*alpha));width=33
 # Rounded three-stroke down-left arrow, fitted to the measured 75x56 box.
 points=[(207,17),(17,148),(40,40),(17,148),(100,164)]
 for a,b in ((points[0],points[1]),(points[2],points[3]),(points[3],points[4])):
  d.line((a,b),fill=color,width=width)
  for px,py in (a,b):d.ellipse((px-16,py-16,px+16,py+16),fill=color)
 im.alpha_composite(layer,(round(x),round(y)))

# 0opgOhMJ2Ks2187.3333 onward:265 decoded30fpsframes, white-star ROI energy.
# Measured timing/energy; drawn star contours are authored, not recovered vectors.
_REFERENCE_STAR_LEVELS=(
 bytes.fromhex('000208162c4e7698c5e1fcfefff9f3e8ddd2c6baaea59f9a97979797979797969696969696968c837a7065655851453c32281a28323c454f58646d78828d969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696966464584f423c3229202b343e47515b656e79838e9696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696'),
 bytes.fromhex('000000000000030d234b77aadfeffffbf6eaddd0c2b9afaaa4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a3a39790897d7066564e443c322a1d28333d454e55616c757d85919ba4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a3a3a09e9b90857b6f675d544941372d232d353e4650586169747e89939ca3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3'),
 bytes.fromhex('0000000000000000000000000000000000000101000000000000000000050b2035608db8e2f1fffdfbf5ede6ded7cfc8c0c0c0c0c0bfbfbfbfbfbfbfbfb7aea59b8e7f7362544536263645546272808f9caebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebebee7e7e7ded5ccc2c2c2c2c2c2c2c2c2c2c1c1c1c1c0b2a2928272624e41312031415262728292a2b2c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0'),
 bytes.fromhex('0000000000000000000000000000000000000000000000030e254a79aedafbfdfff8f0e6dbcfc3b8adadadacacacacabababababababababa396897f75695d52453a2e262d3a46525e6b7784909eaaaaaaaaabababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababacacacacacabababababababababa0978c81756a5d52463a2e262d3b44525f6d7a8793a0aaaaaaababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababab'),
 bytes.fromhex('000408172e4f7799c5e1fdfefff9f2e8ddd2c6baaea59f9797979797969797979797979797978d847b7065655751453d33291f29333d455057646d78828d969697979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797979797976464584f423c3229202a343e47525b646e78828c9495969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696969696'),
 bytes.fromhex('000000000000041526507dabdeeffffdfaeedfd2c3bab0aaa4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a3a39790897f756a5f564b40352a1d29343d454e56606a747d88919ba4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a3a3a1a09e94887e72695f554a41372d222b343d454f586068727c858e99a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3'),
 bytes.fromhex('000000000000000000000000000000000001010101010101010104142e5271889ab6d3e7f9fdfff7efede0e0d6c9c8c2bababababababababab8b3b0abb1b6a99b8c7d6f61534433263645536172818f9daab6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6ddddddd3c8c6c2c0bbbbbbbabababab9b9b8b8b8b7aa9b8d7e7162534133223341536272808f9dabb8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8b8'),
 bytes.fromhex('0000000000000000000000000000000000000000000000030f284d7daedbfcfffff9f0e5d7ccc0b7adacb2b2b2b1b1b1b0b0b0b0b0afafafa79c9084776c6054473c3126303d495662707d8b97a4adaeafafb0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b1b1b1b0b0b0b0b0afafafafafafa59c8f84786e6055493d3125303d4956626f7c8a97a4afafafb0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0'),
)

_REFERENCE_STAR_PEAKS=(
 bytes.fromhex('2c5ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff5e6d1bbbba29882716451434f64738292a2bbcadef0ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffb5b5aca7a09d97928c9399a0a6adb4bccaddeeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('000000000000e0fffffffffffbfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffaefe5d0baa98d7f74685d4b33465d68747f8da0b3c1cddaeefefffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffeecd8c5b2a494857668594a3b495664707e8b98a6b9cbdeeffcffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('000000000000000000000000000000000000050606060606060606040354a2d8fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff5ebe0cbb6a18c7864513d5064788ca1b6cbe0f6fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff4dec9b39e8a71644b314b64778ba1b6cce1f7ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('0000000000000000000000000000000000000202010101fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff0d9cac4bcb3a9a0928374655f70859db0c4d8edfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff3e2d0cdcdcdbdac9a897766646f859ab2c8dbeeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('279efffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff5e6d6c5c5a6a686766866666666768699a6bdcbdff2ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffb9b9a59b8c847b746d77828c96a0a9bacbdbeeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('00000000000086cdfffffefaf9fefffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff5ebe0d0beae9d8c7b6b59433d435764707d8b9babbac9d9e9fafffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff5e5d4c4b3a08d7d6e5f503f4c596774828f9da9b9c9daebfbffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('00000000000000000000000000000000000909090909090908064ba5fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffcf9f4fbfff2e2cdb9a48f7a654f3c50657a8fa4b9cde2f4fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff2decbb7a5917d674f344f677d91a5b7cbdef2ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
 bytes.fromhex('0000000000000000000000000000000000020202030303fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff9e6d3c0ad9d91847a6e625761758ca2b4c6ddf3ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe9d4bebb9d9184776b5f526274899db5cde0f2ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'),
)

def draw_reference_stars(im,t,side):
 positions=(((191,128,52),(166,194,21),(758,176,21),(787,234,52)),
            ((1232,128,52),(1210,194,21),(1713,176,21),(1742,234,52)))[side]
 d=ImageDraw.Draw(im)
 for j,(x,y,radius) in enumerate(positions):
  levels=_REFERENCE_STAR_LEVELS[side*4+j];frame=max(0,min(len(levels)-1,t*30));a=int(frame);b=min(a+1,len(levels)-1);q=frame-a
  energy=(levels[a]*(1-q)+levels[b]*q)/255
  peaks=_REFERENCE_STAR_PEAKS[side*4+j];value=round(peaks[a]*(1-q)+peaks[b]*q)
  if not value or not energy:continue
  radius*=math.sqrt(min(1,energy/(value/255)))
  # Long cardinal rays and shorter diagonal rays, with no overlap into title ink.
  points=[]
  for k in range(16):
   angle=k*math.pi/8;length=radius if k%4==0 else radius*.45 if k%2==0 else radius*.075
   points.append((x+math.cos(angle)*length,y+math.sin(angle)*length))
  d.polygon(points,fill=(value,value,value,255))

def gold_depth_title(layout,text,size,font_file="BMYEONSUNG.ttf"):
 # Bounds measured from0opgOhMJ2Ks2188s,854x480 gold mask scaled to1920x1080.
 # Layer treatment is authored: original font, shear and glow parameters remain unverified.
 w,h=size;mask=Image.new('L',(900,260))
 ImageDraw.Draw(mask).text((60,20),text,font=layout.font(font_file,120),fill=255)
 mask=mask.transform(mask.size,Image.Transform.AFFINE,(1,.18,-30,0,1,0),resample=Image.Resampling.BICUBIC)
 mask=mask.crop(mask.getbbox()).resize((w,h),Image.Resampling.LANCZOS)
 base=Image.new('L',(w+80,h+80));base.paste(mask,(30,30))
 outer=base.filter(ImageFilter.MaxFilter(9));layer=Image.new('RGBA',base.size)
 glow=Image.new('RGBA',base.size,'#ECD85C');glow.putalpha(outer.filter(ImageFilter.GaussianBlur(9)).point(lambda a:round(a*.7)));layer.alpha_composite(glow)
 shadow=Image.new('RGBA',base.size,'#181405');shadow.putalpha(outer);layer.alpha_composite(shadow,(7,8))
 edge=Image.new('RGBA',base.size,'white');edge.putalpha(base.filter(ImageFilter.MaxFilter(5)));layer.alpha_composite(edge)
 fill=Image.new('RGBA',base.size,'#F4D849');fill.putalpha(base);layer.alpha_composite(fill)
 return layer

class Endcard:
 def __init__(self,layout,credits=(),*,recommendation_arrow=True,title_reveal=None,title_treatment="classic",title_font="BMYEONSUNG.ttf"):
  if type(recommendation_arrow) is not bool:raise ValueError("recommendation_arrow must be boolean")
  if title_reveal is not None and (not isinstance(title_reveal,(list,tuple)) or len(title_reveal)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in title_reveal) or title_reveal[0]<0 or title_reveal[1]<=0 or sum(title_reveal)>9):raise ValueError("title_reveal requires [start,duration] within nine seconds")
  if title_treatment not in ("classic","gold_depth"):raise ValueError("Unknown endcard title treatment")
  from longform_contract import FONT_NAMES
  if title_font not in FONT_NAMES:raise ValueError("Unknown endcard title font")
  self.title_treatment=title_treatment
  self.title_reveal=title_reveal
  self.recommendation_arrow=recommendation_arrow
  self.titles=[]
  self.title_positions=[]
  from longform_render import screen_words
  words=screen_words(getattr(layout,'lang','ko'))
  for i,text in enumerate((words['similar'],words['recommended'])):
   if title_treatment=='gold_depth':
    x,y,w,h=((247,144,468,99),(1286,144,382,104))[i]
    self.titles.append(gold_depth_title(layout,text,(w,h),title_font));self.title_positions.append((x-30,y-30));continue
   layer=Image.new('RGBA',(660,155));d=ImageDraw.Draw(layer)
   face=layout.font(title_font,83)
   d.text((27,20),text,font=face,fill='#DDB147',stroke_width=3,stroke_fill='white')
   self.titles.append(layer);self.title_positions.append((180+i*1010,80))
  self.credit=Image.new('RGBA',(1800,130));d=ImageDraw.Draw(self.credit)
  for i,text in enumerate(credits):
   face=layout.font('Paperlogy-3Light.ttf',29)
   if d.textlength(text,font=face)>1780:raise ValueError('Endcard credit exceeds safe width')
   d.text((0,i*40),text,font=face,fill='white')
  self.thanks=Image.new('RGBA',(1800,130));d=ImageDraw.Draw(self.thanks)
  d.text((0,0),words['thanks'],font=layout.font('BMYEONSUNG.ttf',55),fill='#D2FF00')
 def frame(self,t):
  im=Image.new('RGBA',(1920,1080),'black')
  if self.recommendation_arrow:draw_recommendation_arrow(im,t)
  for i,layer in enumerate(self.titles):
   start,duration=self.title_reveal or (17/30,11/30)
   progress=max(0,min(1,(t-start)/duration))
   # Reveal the title along its baseline; no frame-to-frame accumulated transform.
   if self.title_reveal is None:width=round(layer.width*progress)
   else:
    left,_,right,_=layer.getbbox();width=round(left+(right-left)*progress) if progress>0 else 0
   if width:im.alpha_composite(layer.crop((0,0,width,layer.height)),self.title_positions[i])
   if self.title_treatment=='gold_depth':
    draw_reference_stars(im,t,i);continue
   d=ImageDraw.Draw(im)
   for j,(dx,dy,r) in enumerate(((0,18,22),(32,-9,12),(430,95,17))):
    brightness=max(0,math.sin(t*3.4+j*1.8+i))**4
    if t<13/30:continue
    radius=r*(.45+.55*brightness);x=190+i*1010+dx;y=103+dy
    color=tuple([round(85+170*brightness)]*3)+ (255,)
    d.polygon([(x,y-radius),(x+radius*.17,y-radius*.17),(x+radius*.65,y),(x+radius*.17,y+radius*.17),(x,y+radius),(x-radius*.17,y+radius*.17),(x-radius*.65,y),(x-radius*.17,y-radius*.17)],fill=color)
  for layer,alpha in ((self.credit,min(1,max(0,(t-1.4)/.35))*min(1,max(0,(4.4-t)/.35))),
                       (self.thanks,min(1,max(0,(t-4.6)/.45)))):
   if alpha>0:
    shown=layer.copy();shown.putalpha(shown.getchannel('A').point(lambda v:round(v*alpha)))
    im.alpha_composite(shown,(55,945))
  return im.convert('RGB')

def render(folder,layout,plan):
 root=Path(folder);settings=plan.get('endcard',{});card=Endcard(layout,settings.get('credits',[]),recommendation_arrow=settings.get('recommendation_arrow',True),title_reveal=settings.get('title_reveal'),title_treatment=settings.get('title_treatment','classic'),title_font=settings.get('title_font','BMYEONSUNG.ttf'))
 card.frame(6).save(root/'endcard.png')
 # Joined after the scenes with `-c copy`: same encoder as the scenes, a GPU failure raises EncoderFailed (render_joined).
 path=root/'endcard.mp4';encoder=encode_frames(Frames(lambda:(card.frame(i/60).tobytes() for i in range(540))),path,joined=True)
 return path,encoder
