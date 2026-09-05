# -*- coding: utf-8 -*-
"""HTML 틀을 여러 개 찍어낸다.

사장님이 코덱스로 만드실 틀들과 같은 모양이다 — 이 파일은 '이렇게 늘어나면
화면이 어떻게 되나'를 보여주려고 견본을 만드는 것뿐이고, 실제로는 tpl/ 폴더에
HTML을 넣기만 하면 된다(등록 절차 없음).
"""
import io, os

TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tpl')
FONT = '../../../shopping_shorts/static/fonts'

BASE = """<!doctype html>
<!--설명: {desc}-->
<html><head><meta charset="utf-8">
<style>
@font-face{{font-family:BHS;src:url('{font}/BlackHanSans.ttf')}}
@font-face{{font-family:PT;src:url('{font}/Pretendard-ExtraBold.otf')}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;background:transparent}}
.wrap{{position:relative;width:1080px;height:1920px;font-family:BHS,PT,sans-serif}}
.head{{position:absolute;left:0;top:0;width:100%;padding:{pad_t}px 0 34px;background:{head_bg};text-align:center}}
.ad{{position:absolute;right:40px;top:34px;color:{ad_c};font-family:PT;font-size:32px;font-weight:700;opacity:.85;z-index:3}}
{chbar}
.l1,.l2{{display:block;padding:0 3%;line-height:1.02;letter-spacing:-5px;white-space:nowrap;
  -webkit-text-stroke:{ol}px {ol_c};paint-order:stroke fill;text-shadow:0 {sh}px 0 {ol_c};
  transform:scaleX({{{{SCALEX}}}}) skewX({{{{SKEW}}}}deg)}}
.l1{{color:{{{{COLOR1}}}};font-size:{sz}px}}
.l2{{color:{{{{COLOR2}}}};font-size:{sz}px;margin-top:14px}}
.bar{{position:absolute;left:0;width:100%;background:{bar_bg};display:flex;align-items:center;justify-content:center}}
.bar span{{font-family:PT;font-weight:900;color:{bar_c};letter-spacing:-2px;font-size:46px;white-space:nowrap;padding:0 4%}}
{extra}
</style></head><body>
<div class="wrap">
  <div class="ad">[광고]</div>
  {chhtml}
  <div class="head" id="h"><span class="l1">{{{{LINE1}}}}</span><span class="l2">{{{{LINE2}}}}</span></div>
  <div class="bar" id="b"><span>{{{{SUB}}}}</span></div>
</div>
<script>
var h=document.getElementById('h'), b=document.getElementById('b');
var els=document.querySelectorAll('.l1,.l2');
for(var i=0;i<els.length;i++){{
  var s=parseInt(getComputedStyle(els[i]).fontSize);
  while(els[i].scrollWidth>1080 && s>40){{ s-=2; els[i].style.fontSize=s+'px'; }}
}}
b.style.top=h.offsetHeight+'px'; b.style.height='{bar_h}px';
</script></body></html>
"""

def CHBAR(h, bg, fg):
    """채널명 띠 CSS. %서식은 CSS의 %와 부딪히니 문자열 조립으로 만든다."""
    return (".chb{position:absolute;left:0;top:0;width:100%;height:" + str(h) + "px;background:" + bg
            + ";z-index:2;display:flex;align-items:center;justify-content:center;font-family:PT;"
              "font-weight:900;font-size:44px;color:" + fg + "}")
CHHTML = '<div class="chb">숏템메이커</div>'

# (파일명, 설명, 머리 배경, 외곽선 색, 외곽선, 그림자, 글자, 흰바 배경, 흰바 글자, 흰바 높이, 위여백, 채널띠)
SPECS = [
 ('썰채널_검정띠',   '검정 띠 · 굵은 외곽선',      '#000',    '#000', 14, 10, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_검정얇은띠','검정 띠 · 얇은 외곽선',      '#000',    '#000',  6,  5, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_파랑띠',   '파란 띠 · 흰 바',            '#1B4A8B', '#000', 12,  8, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_초록띠',   '초록 띠 · 흰 바',            '#14663C', '#000', 12,  8, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_보라띠',   '보라 띠 · 흰 바',            '#3F2A73', '#000', 12,  8, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_빨강띠',   '빨간 띠 · 흰 바',            '#B4181F', '#000', 12,  8, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_남색띠',   '남색 띠 · 흰 바',            '#12233F', '#000', 12,  8, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_회색띠',   '회색 띠 · 흰 바',            '#3A3F45', '#000', 12,  8, 126, '#fff',    '#111', 128, 96,  None),
 ('썰채널_흰바탕',   '흰 바탕 · 검정 글씨',        '#F4F4F4', '#fff',  8,  6, 118, '#E9E9E9', '#111', 120, 96,  None),
 ('썰채널_크림바탕', '크림 바탕 · 검정 글씨',       '#F7EFD9', '#fff',  8,  6, 118, '#EFE3C4', '#111', 120, 96,  None),
 ('썰채널_검정띠_큰글씨','검정 띠 · 아주 큰 글씨',   '#000',    '#000', 16, 12, 150, '#fff',    '#111', 128, 80,  None),
 ('썰채널_검정띠_작은바','검정 띠 · 얇은 흰 바',     '#000',    '#000', 14, 10, 126, '#fff',    '#111',  92, 96,  None),
 ('채널형_분홍띠',   '채널명 띠 · 분홍',           '#000',    '#000', 12,  8, 118, '#fff',    '#111', 128, 200, ('#EE7481', '#fff')),
 ('채널형_검정띠',   '채널명 띠 · 검정',           '#000',    '#000', 12,  8, 118, '#fff',    '#111', 128, 200, ('#141414', '#fff')),
 ('채널형_청록띠',   '채널명 띠 · 청록',           '#000',    '#000', 12,  8, 118, '#fff',    '#111', 128, 200, ('#0E6B72', '#fff')),
 ('채널형_노랑띠',   '채널명 띠 · 노랑',           '#000',    '#000', 12,  8, 118, '#fff',    '#111', 128, 200, ('#F2C94C', '#111')),
]


def main():
    os.makedirs(TPL_DIR, exist_ok=True)
    for (name, desc, head_bg, ol_c, ol, sh, sz, bar_bg, bar_c, bar_h, pad_t, ch) in SPECS:
        chbar = CHBAR(170, ch[0], ch[1]) if ch else ''
        html = BASE.format(desc=desc, font=FONT, head_bg=head_bg, ol_c=ol_c, ol=ol, sh=sh,
                           sz=sz, bar_bg=bar_bg, bar_c=bar_c, bar_h=bar_h, pad_t=pad_t,
                           ad_c='#fff' if head_bg not in ('#F4F4F4', '#F7EFD9') else '#111',
                           chbar=chbar, chhtml=(CHHTML if ch else ''), extra='')
        io.open(os.path.join(TPL_DIR, name + '.html'), 'w', encoding='utf-8').write(html)
        print('만듦:', name, '·', desc)
    print('총', len(SPECS), '개')


if __name__ == '__main__':
    main()
