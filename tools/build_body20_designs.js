/* 본문 전용 디자인 원장. 원본 프레임의 헤더/제목/자막/영상 순서를 유지하고
 * 색·재질은 새로 디자인한다. 원본 픽셀 복제본으로 취급하지 않는다.
 * 모든 좌표는 360×640 기준. 미리보기와 썸네일이 같은 frame을 소비한다. */
const fs=require('fs'),path=require('path'),vm=require('vm');
const destination=path.resolve(__dirname,'../out/precision20-data.js');
const context={window:{}};vm.runInNewContext(fs.readFileSync(destination,'utf8'),context);
const window=context.window;
(()=>{
  const profiles={
    s0101:{family:'profile',label:'샴페인 프로필',band:86,caption:192,video:250,end:640,ink:'#29251F',accent:'#B08B48',paper:'#FFFDF7',header:['#F6E7B6','#FFF3CE','#DFC28A']},
    t01:{family:'search',label:'테라코타 검색창',band:90,caption:151,video:215,end:558,ink:'#302827',accent:'#B25D4F',paper:'#FBF5F0',header:['#8D3F36','#C9836B','#A35646']},
    t02:{family:'community',label:'로즈 펄 커뮤니티',band:90,caption:159,video:239,end:584,ink:'#3B2731',accent:'#B85D78',paper:'#FFFAFC',header:['#C88194','#F1BDCA','#BE7790']},
    t03:{family:'search',label:'아이보리 검색창',band:88,caption:148,video:221,end:536,ink:'#35352B',accent:'#9B895B',paper:'#FFFEF8',header:['#D0C798','#F3EDD0','#DBD1A9']},
    t04:{family:'community',label:'코랄 라일락',band:91,caption:155,video:222,end:552,ink:'#372D43',accent:'#B76D7A',paper:'#F8F5FF',header:['#B7586E','#E5A0AE','#CA7B8D']},
    t05:{family:'editorial',label:'로즈 매거진',band:79,caption:161,video:234,end:586,ink:'#38252C',accent:'#AF6378',paper:'#FFF9F7',header:['#E7A3AA','#F8CDD0','#D98D9A']},
    t06:{family:'editorial',label:'세이지 지면',band:78,caption:158,video:225,end:535,ink:'#2D392C',accent:'#69855A',paper:'#F7F9F2',header:['#A6B990','#D4DEC0','#A0B08A']},
    t07:{family:'dark',label:'차콜 실버 정보판',band:59,caption:135,video:195,end:604,ink:'#F3F1ED',accent:'#D4BE98',paper:'#24272C',header:['#292C32','#50555E','#25282E']},
    t08:{family:'community',label:'산호빛 포인트',band:73,caption:152,video:235,end:552,ink:'#272F38',accent:'#AB6169',paper:'#FFF8F5',header:['#BC6872','#EDABB0','#CB7F86']},
    t09:{family:'banner',label:'블루 미스트 배너',band:80,caption:135,video:186,end:545,ink:'#253B53',accent:'#708DAF',paper:'#E9EFF9',header:['#C2D3EA','#EFF4FC','#B1C6E0']},
    t10:{family:'editorial',label:'올리브 노트',band:84,caption:171,video:200,end:593,ink:'#333C2C',accent:'#819563',paper:'#FAFBF3',header:['#D2DDB8','#EFF2DD','#BFCBA5']},
    t11:{family:'dark',label:'스모키 실버',band:58,caption:135,video:195,end:604,ink:'#F3F4F6',accent:'#88CFC7',paper:'#2B2E35',header:['#30343D','#626773','#2B2E36']},
    t12:{family:'community',label:'딥 틸 세라믹',band:98,caption:174,video:245,end:585,ink:'#243E48',accent:'#498D9E',paper:'#F4FAFC',header:['#164B5B','#397D8B','#245A68']},
    t13:{family:'cinema',label:'블랙 골드 시네마',band:42,caption:492,video:151,end:547,ink:'#F8F1D6',accent:'#D5BA70',paper:'#121416',header:['#151719','#2E2B24','#101214']},
    t14:{family:'overlay',label:'청록빛 미니멀',band:40,caption:248,video:104,end:557,ink:'#E5F5F0',accent:'#8CD1C2',paper:'#111C1D',header:['#152829','#294744','#102021']},
    t15:{family:'editorial',label:'민트 프로스트',band:88,caption:161,video:205,end:577,ink:'#29453E',accent:'#6B9A8B',paper:'#F5FAF7',header:['#7CAFA2','#B7DACE','#86B5A8']},
    t16:{family:'editorial',label:'버터 페이퍼',band:82,caption:151,video:224,end:590,ink:'#423828',accent:'#A58A4F',paper:'#FFFCF2',header:['#E8D59A','#FFF0BF','#D9C38A']},
    t17:{family:'browser',label:'흑연 브라우저',band:89,caption:160,video:237,end:610,ink:'#31323B',accent:'#8584A0',paper:'#F9F8FC',header:['#272830','#4C4D58','#292A32']},
    t19:{family:'dark',label:'오닉스 정보판',band:95,caption:163,video:242,end:589,ink:'#F6F1E7',accent:'#B4A386',paper:'#1D2024',header:['#101214','#393C40','#17191C']},
    s0056:{family:'community',label:'허니 브라스',band:72,caption:126,video:184,end:640,ink:'#3D3425',accent:'#9B7E42',paper:'#FFFDF4',header:['#C7AA60','#F1D895','#B79850']}
  };
  const gradient=(colors,angle=125)=>`linear-gradient(${angle}deg,${colors[0]} 0%,${colors[1]} 48%,${colors[2]} 100%)`;
  const makeBody=(p,d)=>{
    const dark=['dark','cinema','overlay'].includes(d.family),overlay=['cinema','overlay'].includes(d.family);
    const frame={width:360,height:640,title_bg:d.paper,font_family:'PretendardXBold',font_weight:400,
      fingerprint:`body-reference-material-v1-${p.id}`,design_label:d.label,
      benchmark:{source:p.body_image,layout:d.family,note:'원본 구성을 바탕으로 색·재질을 새로 디자인한 편집본'},
      caption_slot:{mode:overlay?'overlay':'reserved'},video_from:{y:d.video,pct:d.video/6.4},
      cleanup_regions:[{role:'original-title',x:0,y:0,width:360,height:d.video,background:d.paper},
        ...(d.end<640?[{role:'source-footer',x:0,y:d.end,width:360,height:640-d.end,background:d.paper}]:[])],
      lines:[],surfaces:[],ornaments:[],boxes:[],channel_boxes:[],white_box:null};
    const surface=(x,y,w,h,background,extra={})=>frame.surfaces.push({x,y,width:w,height:h,background,...extra});
    const line=(bind,x,y,w,h,size,color,bg,extra={})=>frame.lines.push({bind,x0:x,x1:x+w,y0:y,y1:y+h,h,font_size:size,
      font_family:'PretendardXBold',font_weight:400,color,background:bg,no_patch:true,max_lines:2,letter_spacing:-.25,...extra});
    const ornament=(type,x,y,w,h,color)=>frame.ornaments.push({type,x,y,width:w,height:h,color});
    // 大面에는 저대비의 빛과 얇은 결만 더한다. 영상 위에는 면을 깔지 않는다.
    surface(0,0,360,d.video,`radial-gradient(ellipse at 90% 15%,${d.accent}19,transparent 65%),linear-gradient(145deg,${d.paper},${d.paper})`);
    surface(0,0,360,d.band,`radial-gradient(ellipse at 25% 0%,#FFFFFF35,transparent 62%),${gradient(d.header)}`,{borderBottom:'#FFFFFF45',shadow:'0 3px 10px #18182016'});
    surface(0,0,360,d.band,'repeating-linear-gradient(115deg,#FFFFFF08 0 1px,transparent 1px 5px)');
    if(d.end<640){surface(0,d.end,360,640-d.end,`linear-gradient(160deg,${d.paper},${d.accent}28)`,{borderTop:dark?'#FFFFFF1C':'#FFFFFFCC'});ornament('rule',148,d.end+Math.min(20,(640-d.end)/2),64,1,d.accent+'66');}
    let channel={x:58,y:22,width:244,height:32,background:d.header[1],color:dark?'#F9F8F2':d.ink,font_size:25,font_family:'GmarketSansBold',font_weight:400,designed:true};
    if(d.family==='search'){
      surface(64,35,232,39,'linear-gradient(180deg,#FFFFFF,#F5F2EE)',{radius:22,border:'#51443845',shadow:'0 3px 7px #3525181B'});
      channel={...channel,x:84,y:40,width:176,height:27,font_size:22,background:'#FFFFFF',color:d.ink};ornament('search',270,46,13,13,d.ink);
    }else if(d.family==='profile'){
      channel.y=24;channel.font_family='JalnanGothic';channel.font_size=27;
      ornament('spark',29,110,15,15,'#E5D5A9');
      ornament('rule',62,114,75,3,d.accent+'AA');ornament('rule',62,123,44,2,d.accent+'55');
    }else if(d.family==='browser'){
      surface(72,38,225,31,'linear-gradient(180deg,#FFFFFF20,#FFFFFF0A)',{radius:16,border:'#FFFFFF40'});
      [0,1,2].forEach((n)=>surface(22+n*13,51,7,7,['#C57D77','#C8B07C','#89AA93'][n],{radius:9}));
      channel={...channel,x:95,y:40,width:182,height:27,font_size:19,color:'#F4F0FA'};
    }else if(d.family==='cinema'){
      channel={...channel,x:25,y:14,width:245,height:20,font_size:13,color:'#C7BA94'};
      ornament('rule',26,42,38,2,d.accent);surface(0,d.video-1,360,1,gradient([d.paper,d.accent,d.paper]));
    }else if(d.family==='overlay'){
      channel={...channel,y:9,height:24,font_size:18,color:'#EDF6F1'};
      ornament('menu',18,14,16,12,'#C8D5CE');ornament('search',325,12,14,14,'#C8D5CE');
      surface(0,41,360,1,'#7FA79D55');
    }else if(d.family==='banner'){
      surface(128,19,104,43,'linear-gradient(135deg,#FFFFFFAF,#F7FBFF4F)',{radius:12,border:'#FFFFFFC0',shadow:'0 4px 12px #36547B18'});
      channel={...channel,x:131,y:27,width:98,height:23,font_size:16,color:d.ink};
    }else if(d.family==='editorial'){
      channel={...channel,y:Math.max(18,(d.band-32)/2),font_family:p.hook?.lines?.[0]?.font_family||'GmarketSansBold',font_size:26};
      ornament('bookmark',27,Math.max(25,d.band/2-9),10,16,d.ink+'A0');ornament('rule',311,d.band/2-4,20,1,d.ink+'99');ornament('rule',317,d.band/2+2,14,1,d.ink+'66');
    }else{
      channel.y=(d.band-30)/2;channel.color=(dark||p.id==='t12')?'#FFFFFF':d.ink;
      ornament('menu',23,d.band/2-7,19,14,channel.color+'BB');ornament('search',317,d.band/2-8,16,16,channel.color+'BB');
    }
    frame.channel_box=channel;
    const titleY=d.family==='profile'?140:d.family==='cinema'?58:d.band+12;
    const titleH=overlay?d.video-titleY-15:d.caption-titleY-12;
    line('bodyTitle',25,titleY,310,Math.max(27,titleH),overlay?29:d.family==='banner'?19:21,d.ink,d.paper,
      {font_family:overlay?'JalnanGothic':(p.hook?.lines?.[0]?.font_family||'GmarketSansBold'),accent_words:overlay?2:0,accent:d.accent});
    if(overlay){
      const isCinema=d.family==='cinema',captionBg=isCinema?'#111714':'#F9FBF4';
      surface(30,d.caption-3,300,isCinema?40:43,isCinema?'linear-gradient(135deg,#121B19F5,#1B2A25EB)':'linear-gradient(120deg,#FFFFFFF5,#F0F5ECEF)',
        {radius:isCinema?4:3,border:isCinema?'#D3C18855':'#FFFFFFB0',shadow:'0 4px 15px #00000028',bind:'caption'});
      line('caption',42,d.caption+3,276,29,19,isCinema?'#EFE5BC':'#26372F',captionBg);
    }else{
      const capH=d.video-d.caption;
      surface(0,d.caption,360,capH,`linear-gradient(110deg,${dark?'#F5F3EE':'#FFFFFF'},${dark?'#E8E6E0':d.paper})`,{borderTop:d.accent+'40',shadow:'inset 0 1px 0 #FFFFFF99'});
      line('caption',34,d.caption+5,292,capH-10,capH<40?17:20,'#30343A','#FFFFFF');
    }
    frame.ornaments=frame.ornaments.filter(o=>!['rule','bookmark','spark'].includes(o.type));
    return frame;
  };
  for(const p of window.PRECISION20||[]){
    const d=profiles[p.id];if(d)p.body=makeBody(p,{...d,end:640});
    const h=p.hook,empty=h.white_box&&!h.white_box.text;
    if(empty){
      const lastTitle=Math.max(0,...h.lines.map(l=>l.y1??l.y0+l.h));
      const next=Math.max(lastTitle+8,h.white_box.y0);
      h.video_from={y:next,pct:next/h.height*100};h.white_box=null;
      h.cleanup_regions=(h.cleanup_regions||[]).map(r=>r.role==='original-title'?{...r,height:Math.max(0,next-r.y)}:r);
    }
    h.cleanup_regions=(h.cleanup_regions||[]).filter(r=>r.role!=='source-footer');
  }
  const even=window.PRECISION20.find(p=>p.id==='t11');
  if(even){
    const line=(bind,x,y,w,h,size,color)=>({bind,x0:x,x1:x+w,y0:y,y1:y+h,h,font_size:size,font_family:'TmonMonsori',font_weight:400,color,background:'#212121',no_patch:true,max_lines:1,letter_spacing:-.6});
    const frame=(width,height,video,label,source)=>({width,height,design_label:label,reference_style:true,title_bg:'#212121',font_family:'TmonMonsori',font_weight:400,
      benchmark:{source,note:'사용자 제공 이븐쇼핑 원본의 배치·색상 재현. 서체는 대조한 후보이며 픽셀 동일성을 보증하지 않음'},
      cleanup_regions:[{role:'original-title',x:0,y:0,width,height:video,background:'#212121'}],video_from:{y:video,pct:video/height*100},
      lines:[],surfaces:[],ornaments:[{type:'menu',x:16,y:14,width:40,height:25,color:'#E6E9E5'},{type:'search',x:width-53,y:9,width:29,height:29,color:'#D9DFDB'}],channel_boxes:[],boxes:[],white_box:null});
    even.sample={...even.sample,channel:'이븐쇼핑',hook1:'건망증 환자를 살려낸',hook2:'일본 천재의 발명품',bodyTitle:'건망증 환자를 살려낸 천재의 발명품?',caption:'전 세계 건망증 환자들의'};
    even.hook_image='template_refs/even-hook-reference.png';even.body_image='template_refs/even-body-reference.png';
    even.hook=frame(425,748,285,'이븐쇼핑 원본형 · 훅',even.hook_image);
    even.hook.media_source='assets/scene-style/even-hook-media.png';
    even.hook.lines=[{...line('hook1',15,103,395,49,43,'#FFFFFF'),stroke:2,shadow_y:2},
      {...line('hook2',13,151,399,62,50,'#00F9ED'),stroke:2,shadow_y:2},
      {...line('bodyTitle',19,231,387,34,25,'#080808'),background:'#FFFFFF'}];
    even.hook.surfaces=[{x:0,y:0,width:425,height:285,background:'linear-gradient(180deg,#202221,#202020 70%,#424441)'},
      {x:0,y:68,width:425,height:1,background:'#727772'},
      {x:5,y:225,width:415,height:51,background:'linear-gradient(180deg,#FFFFFF,#FFFFFF 72%,#ECEEEC)',shadow:'0 0 12px 7px #FFFFFFB0',radius:2}];
    even.body=frame(420,746,229,'이븐쇼핑 원본형 · 본문',even.body_image);
    even.body.media_source='assets/scene-style/even-body-media.png';even.body.caption_slot={mode:'reserved'};
    even.body.channel_box={x:95,y:6,width:230,height:48,font_size:40,font_family:'GmarketSansBold',font_weight:400,letter_spacing:7,color:'#FFFFFF',background:'#404040',designed:true};
    even.body.lines=[{...line('bodyTitle',15,82,390,39,27,'#FFFFFF'),background:'#3F3F3F'},
      {...line('caption',23,173,374,40,27,'#090909'),background:'#FFFFFF'}];
    even.body.surfaces=[{x:0,y:0,width:420,height:156,background:'linear-gradient(180deg,#454545,#3B3B3B)'},
      {x:0,y:67,width:420,height:1,background:'#949494'},{x:0,y:156,width:420,height:73,background:'linear-gradient(180deg,#FFFFFF,#FAFBFA)'}];
    // 원본 조회/댓글 수는 사용자의 영상 수치가 아니므로 복제하지 않는다.
    window.PRECISION20.sort((a,b)=>Number(b.id==='t11')-Number(a.id==='t11'));
  }
  fs.writeFileSync(destination,'window.PRECISION20='+JSON.stringify(window.PRECISION20)+';\n','utf8');
  console.log(`본문 디자인 ${window.PRECISION20.length}종 생성`);
})();
