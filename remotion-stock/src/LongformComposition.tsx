import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from 'remotion';
import { FONT } from './theme';

const C = {
  bg:'#0F112A', white:'#FFFFFF', mint:'#00FFD4', orange:'#FFC000',
  bull:'#FF4336', dim:'rgba(255,255,255,0.45)', card:'rgba(255,255,255,0.07)',
  news:'rgba(255,255,255,0.72)',
};
const SDUR = 540;
const HOOK_DUR = 150;
const N = 34;

// ─── 애니메이션 헬퍼 ──────────────────────────────────
const fi = (f:number,s:number,d=20) =>
  interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
const su = (f:number,s:number,d=20,dist=30) =>
  interpolate(f,[s,s+d],[dist,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
const spr = (f:number,s:number,d=24) => {
  const t=interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return t>=1?1:1-Math.pow(2,-9*t)*Math.cos(t*Math.PI*2.4);
};
const spry = (f:number,s:number,d=24,dist=40) => dist*(1-spr(f,s,d));
const osc = (f:number,sp=.05,base=.7,amp=.2) => base+Math.sin(f*sp)*amp;
const countUp = (f:number,s:number,end:number,d=70) =>
  Math.floor(interpolate(f,[s,s+d],[0,end],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}));

// ─── 공통 컴포넌트 ────────────────────────────────────
const Arrow:React.FC<{color?:string;w?:number;h?:number;t?:number}> = ({color=C.mint,w=70,h=44,t=5}) => {
  const mid=`am${w}${h}${color.replace('#','')}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{display:'block',flexShrink:0,margin:'0 10px'}}>
      <defs><marker id={mid} markerWidth="12" markerHeight="12" refX="11" refY={h/2} orient="auto">
        <polygon points={`0 0,12 ${h/2},0 ${h}`} fill={color}/>
      </marker></defs>
      <line x1="6" y1={h/2} x2={w-12} y2={h/2} stroke={color} strokeWidth={t} markerEnd={`url(#${mid})`}/>
    </svg>
  );
};

const Particles:React.FC<{f:number;color?:string}> = ({f,color=C.mint}) => (
  <div style={{position:'absolute',inset:0,pointerEvents:'none',overflow:'hidden'}}>
    {Array.from({length:18},(_,i)=>(
      <div key={i} style={{
        position:'absolute',
        left:`${(i*13+7)%100}%`,
        top:`${((i*11+5)%100)+Math.sin(f*.01+i*.65)*3}%`,
        width:1+(i%3)*.5,height:1+(i%3)*.5,
        borderRadius:'50%',backgroundColor:color,
        opacity:0.06+Math.sin(f*.018+i*.65)*.03,
      }}/>
    ))}
  </div>
);

const GlowBg:React.FC<{f:number;color?:string}> = ({f,color=C.mint}) => (
  <div style={{
    position:'absolute',inset:0,pointerEvents:'none',
    background:`radial-gradient(ellipse at 50% ${50+Math.sin(f*.012)*8}%, ${color}0C 0%, transparent 60%)`,
  }}/>
);

const Wrap:React.FC<{children:React.ReactNode;no:number;accent?:string;label?:string}> = ({children,no,accent=C.mint,label}) => {
  const f=useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor:C.bg,fontFamily:FONT.main,opacity:fi(f,0,8)}}>
      <Particles f={f} color={accent}/>
      <GlowBg f={f} color={accent}/>
      <div style={{position:'absolute',top:0,left:0,right:0,height:6,backgroundColor:accent}}/>
      <div style={{position:'absolute',top:0,left:`${(f*.7)%120-15}%`,width:'6%',height:6,
        background:`linear-gradient(90deg,transparent,${accent}CC,transparent)`,opacity:.8}}/>
      {label&&<div style={{position:'absolute',top:28,left:60,color:accent,fontFamily:FONT.mono,fontSize:17,letterSpacing:4,fontWeight:600,opacity:fi(f,3)}}>{label}</div>}
      <div style={{position:'absolute',top:28,right:60,color:accent,fontFamily:FONT.mono,fontSize:17,opacity:.5}}>{String(no).padStart(2,'0')} / {N}</div>
      <div style={{position:'absolute',bottom:24,left:0,right:0,textAlign:'center',color:C.dim,fontFamily:FONT.mono,fontSize:16,opacity:.5}}>로또의 주식 — AI 지식 자동화 시스템</div>
      {children}
    </AbsoluteFill>
  );
};

const Ctr:React.FC<{children:React.ReactNode;gap?:number;maxW?:number}> = ({children,gap=28,maxW=940}) => (
  <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',textAlign:'center',padding:'90px 140px',gap}}>
    <div style={{maxWidth:maxW,width:'100%'}}>{children}</div>
  </AbsoluteFill>
);

// ─── 텍스트 헬퍼 (폰트 최대화) ────────────────────────
const Title = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:64,fontWeight:800,lineHeight:1.18,letterSpacing:'-1px',marginBottom:18,...ex}}>{txt}</div>
);
const TitleXL = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:80,fontWeight:900,lineHeight:1.1,letterSpacing:'-2px',marginBottom:18,...ex}}>{txt}</div>
);
const Sub = (txt:React.ReactNode,color=C.mint,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:46,fontWeight:700,lineHeight:1.3,marginBottom:14,...ex}}>{txt}</div>
);
const Body = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:28,fontWeight:500,lineHeight:1.65,letterSpacing:'0.2px',...ex}}>{txt}</div>
);
const Lbl = (txt:React.ReactNode,color=C.dim) => (
  <div style={{color,fontSize:18,fontWeight:600,letterSpacing:3,marginBottom:12}}>{txt}</div>
);
const Glow = (color:string) => `drop-shadow(0 0 12px ${color}88)`;

// ─── 지식 그래프 ──────────────────────────────────────
interface GNode{id:string;label:string;bx:number;by:number;r:number;color:string;appear:number}
interface GEdge{from:string;to:string;appear:number}

const NODES:GNode[] = [
  {id:'wiki', label:'LLM 위키', bx:.50,by:.50,r:32,color:C.mint,   appear:10},
  {id:'n1',  label:'삼성 실적', bx:.15,by:.22,r:14,color:C.news,   appear:28},
  {id:'n2',  label:'반도체수출', bx:.78,by:.18,r:13,color:C.news,   appear:46},
  {id:'n3',  label:'금리 동결', bx:.09,by:.66,r:14,color:C.news,   appear:64},
  {id:'n4',  label:'환율 상승', bx:.85,by:.74,r:12,color:C.news,   appear:82},
  {id:'n5',  label:'외국인매수', bx:.55,by:.89,r:13,color:C.news,  appear:100},
  {id:'s1',  label:'삼성전자', bx:.30,by:.35,r:22,color:C.mint,  appear:122},
  {id:'s2',  label:'SK하이닉스',bx:.68,by:.30,r:20,color:C.mint, appear:140},
  {id:'s3',  label:'에코프로',  bx:.76,by:.63,r:17,color:C.mint, appear:158},
  {id:'sec1',label:'반도체섹터', bx:.44,by:.18,r:24,color:C.mint,  appear:180},
  {id:'sec2',label:'2차전지',   bx:.82,by:.46,r:19,color:C.mint,   appear:198},
  {id:'i1',  label:'수급빈집',  bx:.25,by:.74,r:24,color:C.mint,   appear:222},
  {id:'i2',  label:'대장주포착', bx:.61,by:.80,r:22,color:C.mint,  appear:240},
];
const EDGES:GEdge[] = [
  {from:'wiki',to:'s1',appear:268},{from:'wiki',to:'s2',appear:280},
  {from:'wiki',to:'s3',appear:292},{from:'wiki',to:'sec1',appear:304},
  {from:'wiki',to:'sec2',appear:316},{from:'wiki',to:'i1',appear:328},
  {from:'wiki',to:'i2',appear:340},{from:'n1',to:'s1',appear:356},
  {from:'n1',to:'sec1',appear:366},{from:'n2',to:'sec1',appear:376},
  {from:'n2',to:'s2',appear:386},{from:'n3',to:'i1',appear:396},
  {from:'n4',to:'s3',appear:406},{from:'n5',to:'i2',appear:416},
  {from:'s1',to:'sec1',appear:430},{from:'s2',to:'sec1',appear:442},
  {from:'s3',to:'sec2',appear:454},{from:'s1',to:'i1',appear:466},
  {from:'s2',to:'i2',appear:478},{from:'sec2',to:'i2',appear:490},
];
const GW=1380,GH=590;

const nodePos = (node:GNode,frame:number) => {
  const ph=node.id.charCodeAt(0)+(node.id.charCodeAt(node.id.length-1)||0);
  return {
    x:(node.bx+Math.sin(frame*.02+ph*.65)*.030)*GW,
    y:(node.by+Math.cos(frame*.015+ph*.82)*.024)*GH,
  };
};
const isLight = (c:string) => c===C.mint||c===C.news;

const KGraph:React.FC<{frame:number;extraNodes?:GNode[];extraEdges?:GEdge[]}> = ({frame,extraNodes=[],extraEdges=[]}) => {
  const allN=[...NODES,...extraNodes];
  const allE=[...EDGES,...extraEdges];
  return (
    <svg width={GW} height={GH} viewBox={`0 0 ${GW} ${GH}`} style={{overflow:'visible'}}>
      <defs>
        <filter id="gLg"><feGaussianBlur stdDeviation="10" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <filter id="gMd"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <filter id="gSm"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      {allE.filter(e=>frame>=e.appear).map((e,i)=>{
        const fn=allN.find(n=>n.id===e.from); const tn=allN.find(n=>n.id===e.to);
        if(!fn||!tn) return null;
        const fp=nodePos(fn,frame),tp=nodePos(tn,frame);
        const prog=Math.min(1,(frame-e.appear)/22);
        const isIns=fn.color===C.mint||tn.color===C.mint;
        return <line key={i} x1={fp.x} y1={fp.y}
          x2={fp.x+(tp.x-fp.x)*prog} y2={fp.y+(tp.y-fp.y)*prog}
          stroke={isIns?`${C.mint}44`:'rgba(255,255,255,0.15)'} strokeWidth={isIns?2:1.5}/>;
      })}
      {allN.filter(n=>frame>=n.appear).map((node,i)=>{
        const pos=nodePos(node,frame);
        const prog=Math.min(1,(frame-node.appear)/14);
        const scale=interpolate(prog,[0,.55,1],[0,1.25,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
        const isCore=node.id==='wiki';
        const isExt=extraNodes.some(n=>n.id===node.id);
        const isMint=!isCore&&node.color===C.mint;
        const isIns=node.color===C.mint;
        const filter=isCore?'url(#gLg)':isMint||isExt?'url(#gMd)':isIns?'url(#gSm)':undefined;
        return (
          <g key={i} transform={`translate(${pos.x},${pos.y}) scale(${scale})`} filter={filter}>
            {isCore&&<>
              <circle r={node.r+22} fill="none" stroke={C.mint} strokeWidth={1} opacity={.10+Math.sin(frame*.03)*.05}/>
              <circle r={node.r+13} fill="none" stroke={C.mint} strokeWidth={1} opacity={.20+Math.sin(frame*.04+1)*.08}/>
              <circle r={node.r+6} fill="none" stroke={C.mint} strokeWidth={2} opacity={.36+Math.sin(frame*.04+2)*.10}/>
            </>}
            {isMint&&<circle r={node.r+6} fill="none" stroke={C.mint} strokeWidth={1} opacity={.18+Math.sin(frame*.035+i)*.08}/>}
            {isExt&&<circle r={node.r+7} fill="none" stroke={node.color} strokeWidth={2.5} opacity={.5+Math.sin(frame*.05)*.15}/>}
            <circle r={node.r} fill={node.color} opacity={isCore?.94:isIns?(.82+Math.sin(frame*.07+i)*.1):.78}/>
            <text textAnchor="middle" dominantBaseline="middle"
              fill={isLight(node.color)?C.bg:C.white}
              fontSize={node.r>20?14:12} fontWeight={700} style={{fontFamily:FONT.main}}>
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// ══════════════════════════════════════════════════════
// 1단계: 문제인식 (S01~S04) — accent: C.bull (#FF4336)
// 기준: wiki/strategy_remotion_파이널가이드.md
// ══════════════════════════════════════════════════════

// S01 — 오프닝 패턴 | 하루에 몇 시간?
const S01:React.FC = () => {
  const f = useCurrentFrame();
  // 가이드 §4 오프닝 패턴: 페이드인 → 슬라이드업 → 스케일
  const titleOpacity = interpolate(f,[0,30],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const titleY       = interpolate(f,[30,75],[80,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const titleScale   = interpolate(f,[0,20],[0.8,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  // 카운터: 카운트업 + 탄성 스케일 (가이드 §4 차트/통계 패턴)
  const hrs      = countUp(f,50,3,70);
  const cntScale = interpolate(spr(f,50,24),[0,1],[0.7,1.1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  // 빨간 언더라인 성장
  const lineW = interpolate(f,[200,280],[0,700],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return (
    <Wrap no={1} accent={C.bull} label="문제인식">
      <Ctr gap={20}>
        <div style={{opacity:titleOpacity,transform:`translateY(${titleY}px) scale(${titleScale})`}}>
          {Lbl('매일 반복되는 이 질문',C.dim)}
          {TitleXL(<>하루에 주식 정보 찾는 데<br/><span style={{color:C.bull,filter:Glow(C.bull)}}>몇 시간이나</span> 쓰십니까?</>)}
        </div>
        <div style={{opacity:fi(f,48,20),transform:`scale(${cntScale})`,
          display:'flex',alignItems:'baseline',justifyContent:'center',gap:16}}>
          <div style={{color:C.bull,fontSize:140,fontWeight:900,fontFamily:FONT.mono,
            filter:Glow(C.bull),lineHeight:1}}>{hrs}</div>
          <div style={{color:C.bull,fontSize:54,fontWeight:700}}>시간+</div>
          <div style={{color:C.dim,fontSize:28,fontWeight:500}}>/ 하루</div>
        </div>
        <div style={{opacity:fi(f,130,22),transform:`translateY(${su(f,130,22)}px)`}}>
          {Body('텔레그램 · 유튜브 · 블로그를 쉼 없이 오가지만',C.dim)}
          {Body(<>돌아오는 건 <span style={{color:C.bull,fontWeight:700}}>엄청난 시간 낭비와 피로감</span>뿐입니다</>)}
        </div>
        <div style={{opacity:fi(f,198,18),width:lineW,height:5,margin:'0 auto',
          background:`linear-gradient(90deg,transparent,${C.bull},transparent)`,
          boxShadow:`0 0 20px ${C.bull}AA`}}/>
      </Ctr>
    </Wrap>
  );
};

// S02 — 본문 패턴 | 팩트를 가려낼 수가 없다
const S02:React.FC = () => {
  const f = useCurrentFrame();
  // 가이드 §4 오프닝 패턴 (타이틀)
  const titleOpacity = interpolate(f,[0,30],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const titleY       = interpolate(f,[30,75],[80,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const sources = [
    {icon:'📡',name:'텔레그램',sub:'루머와 찌라시 범람'},
    {icon:'🎬',name:'유튜브',  sub:'상반된 의견들 충돌'},
    {icon:'💬',name:'블로그',  sub:'검증 안 된 정보들'},
  ];
  return (
    <Wrap no={2} accent={C.bull} label="문제인식">
      <Ctr gap={28}>
        <div style={{opacity:titleOpacity,transform:`translateY(${titleY}px)`}}>
          {Title(<>팩트인지 <span style={{color:C.bull,filter:Glow(C.bull)}}>가려낼 수가 없습니다</span></>)}
        </div>
        {/* 가이드 §4 본문 패턴: startFrame = 30 + i*20, 좌→우 슬라이드인 */}
        <div style={{display:'flex',gap:24,justifyContent:'center'}}>
          {sources.map((s,i)=>{
            const sf = 50 + i*22;
            const op = interpolate(f,[sf,sf+15],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
            const tx = interpolate(f,[sf,sf+15],[-40,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
            return (
              <div key={i} style={{
                opacity:op, transform:`translateX(${tx}px)`,
                backgroundColor:`${C.bull}10`,border:`2px solid ${C.bull}55`,
                borderRadius:18,padding:'32px 36px',flex:1,
                boxShadow:`0 0 ${osc(f,.04+i*.01,10,6)}px ${C.bull}28`,
              }}>
                <div style={{fontSize:48,marginBottom:16}}>{s.icon}</div>
                <div style={{color:C.white,fontSize:28,fontWeight:700,marginBottom:10}}>{s.name}</div>
                <div style={{color:C.dim,fontSize:22,fontWeight:500,lineHeight:1.5}}>{s.sub}</div>
              </div>
            );
          })}
        </div>
        <div style={{opacity:fi(f,158,22),transform:`translateY(${su(f,158,22)}px)`}}>
          {Body(<>잘못된 정보로 인한 <span style={{color:C.bull,fontWeight:700}}>뼈아픈 계좌 손실</span>을 겪기도 합니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// S03 — CTA/강조 패턴 | 호재야, 악재야?
const S03:React.FC = () => {
  const f = useCurrentFrame();
  // 가이드 §4 오프닝 패턴 (타이틀)
  const titleOpacity = interpolate(f,[0,30],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const titleY       = interpolate(f,[30,75],[80,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  // 가이드 §4 CTA/강조 패턴: 글리치 + 펄스 (deterministic)
  const glitch = Math.sin(f*0.1) > 0.7;
  const pulse  = Math.sin(f*0.05)*0.2+1;
  const qs = [{q:'호재야?',d:55},{q:'악재야?',d:88}];
  return (
    <Wrap no={3} accent={C.bull} label="문제인식">
      <Ctr gap={36}>
        <div style={{opacity:titleOpacity,transform:`translateY(${titleY}px)`}}>
          {Title(<>이 정보가 내 종목에<br/>정확히 <span style={{color:C.bull,filter:Glow(C.bull)}}>어떤 영향을 미치나?</span></>)}
        </div>
        <div style={{display:'flex',gap:48,justifyContent:'center'}}>
          {qs.map(({q,d},i)=>{
            const entered = spr(f,d,22);
            const gx = glitch ? (i===0?6:-6) : 0;
            return (
              <div key={i} style={{
                opacity:entered,
                transform:`scale(${interpolate(entered,[0,1],[0.8,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}) translateX(${gx}px)`,
                backgroundColor:`${C.bull}18`,border:`3px solid ${C.bull}`,
                borderRadius:24,padding:'40px 72px',
                boxShadow:`0 0 ${osc(f,.05+i*.02,22,14)*pulse}px ${C.bull}66`,
              }}>
                <div style={{color:C.bull,fontSize:64,fontWeight:900,
                  filter:Glow(C.bull),transform:`scale(${pulse})`}}>{q}</div>
              </div>
            );
          })}
        </div>
        <div style={{
          opacity:spr(f,158,24),transform:`translateY(${spry(f,158,24,30)}px)`,
          backgroundColor:`${C.bull}0E`,border:`1px solid ${C.bull}44`,
          borderRadius:16,padding:'26px 48px',
        }}>
          {Body('숨은 뜻을 혼자서 해석하기는 너무 막막합니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// S04 — 클로징 패턴 | 고급 정보는 항상 도망간다
const S04:React.FC = () => {
  const f = useCurrentFrame();
  // 가이드 §4 클로징 패턴: 스케일업 + 글로우 + 펄스
  const titleScale    = interpolate(f,[0,20],[0.7,1.1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const glowIntensity = Math.sin(f*0.03)*25+15;
  const ctaPulse      = Math.sin(f*0.03)*0.5+0.75;
  return (
    <Wrap no={4} accent={C.bull} label="문제인식">
      <Ctr gap={30}>
        <div style={{opacity:fi(f,0,30),transform:`scale(${titleScale})`}}>
          {TitleXL(<>진짜 '고급 정보'는<br/><span style={{color:C.bull,filter:Glow(C.bull)}}>항상 한발 앞서<br/>도망가 버립니다</span></>)}
        </div>
        <div style={{opacity:fi(f,90,22),transform:`translateY(${su(f,90,22)}px)`}}>
          {Body('수익으로 직결되는 진짜 정보는 도대체 어디 숨어있는 건지...',C.dim)}
        </div>
        <div style={{
          opacity:fi(f,140,20),transform:`scale(${ctaPulse})`,
          backgroundColor:`${C.bull}12`,border:`2.5px solid ${C.bull}`,
          borderRadius:20,padding:'30px 50px',
          boxShadow:`0 0 ${glowIntensity}px ${C.bull}77,
                     0 0 ${glowIntensity*2}px ${C.bull}28`,
        }}>
          {Body(<><span style={{color:C.bull,fontWeight:700,fontSize:36}}>매일매일 답답하기만 합니다</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 2단계: 일반적 해결책 (S05~S08) — accent: C.mint
// ══════════════════════════════════════════════════════

const S05:React.FC = () => {
  const f=useCurrentFrame();
  const methods=[
    {icon:'💳',txt:'비싼 유료 기사 구독',d:38},
    {icon:'🎬',txt:'은밀한 유료 영상 구매',d:60},
    {icon:'🔔',txt:'뉴스 속보 알림 24시간',d:82},
  ];
  return (
    <Wrap no={5} accent={C.mint} label="일반적 해결책">
      <Ctr>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('"돈을 쓰면 고급 정보를 얻을 수 있지 않을까?"',C.mint)}
          {Title(<>흔히 선택하는 방법들</>)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          {methods.map((m,i)=>(
            <div key={i} style={{
              opacity:spr(f,m.d,22),
              transform:`translateX(${interpolate(spr(f,m.d,22),[0,1],[-50,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
              display:'flex',alignItems:'center',gap:24,
              backgroundColor:C.card,border:`1px solid ${C.mint}44`,
              borderRadius:14,padding:'20px 36px',
              boxShadow:`0 0 ${osc(f,.04+i*.01,6,4)}px ${C.mint}22`,
            }}>
              <span style={{fontSize:40,flexShrink:0}}>{m.icon}</span>
              {Body(m.txt,C.white)}
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,155,20),marginTop:4}}>
          {Body('이렇게라도 하면 남들보다 조금 더 유리한 무기를 장착한 것 같은 기분...',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S06:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={6} accent={C.mint} label="일반적 해결책">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('남들보다 1초라도 빨리!',C.mint)}
          {TitleXL(<>증권가 찌라시가 돌 때마다<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>급하게 매수 버튼</span>을 누르죠</>)}
        </div>
        <div style={{opacity:spr(f,70,26),display:'flex',alignItems:'center',justifyContent:'center',gap:0}}>
          {['📰 찌라시 도착','','⚡ 급하게 매수','','😱 결과는...?'].map((txt,i)=>(
            i%2===1
              ? <Arrow key={i} color={C.mint} w={68} h={44} t={5}/>
              : <div key={i} style={{
                  backgroundColor:`${C.mint}15`,border:`2px solid ${C.mint}66`,
                  borderRadius:14,padding:'16px 28px',
                  color:C.white,fontSize:26,fontWeight:600,
                  boxShadow:`0 0 10px ${C.mint}22`,
                }}>{txt}</div>
          ))}
        </div>
        <div style={{opacity:fi(f,140,20),transform:`translateY(${su(f,140,20)}px)`}}>
          {Body('속보 보고 다급하게 샀다가 최고점에 물리신 적, 다들 한 번쯤 있으시죠?',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S07:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={7} accent={C.mint} label="일반적 해결책">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>하루 종일 <span style={{color:C.mint}}>속보 알림에 묶여</span> 있습니다</>)}
        </div>
        <div style={{opacity:spr(f,50,24),
          backgroundColor:'#090b18',border:'1px solid rgba(255,255,255,0.12)',
          borderRadius:18,overflow:'hidden'}}>
          <div style={{backgroundColor:'#111428',padding:'14px 22px',display:'flex',gap:10,alignItems:'center'}}>
            <div style={{width:13,height:13,borderRadius:'50%',backgroundColor:'#FF5F56'}}/>
            <div style={{width:13,height:13,borderRadius:'50%',backgroundColor:'#FFBD2E'}}/>
            <div style={{width:13,height:13,borderRadius:'50%',backgroundColor:'#27C93F'}}/>
            <span style={{color:C.mint,fontFamily:FONT.mono,fontSize:16,marginLeft:10,fontWeight:600}}>📲 실시간 알림</span>
          </div>
          <div style={{padding:'24px 32px',display:'flex',flexDirection:'column',gap:14}}>
            {[
              {txt:'🔔 [속보] 미 연준 금리 동결 발표',d:55},
              {txt:'🔔 [긴급] 반도체 수출 데이터 서프라이즈',d:80},
              {txt:'🔔 [찌라시] 삼성전자 대규모 자사주 매입설',d:105},
              {txt:'🔔 [속보] 원달러 환율 급등',d:130},
            ].map((n,i)=>(
              <div key={i} style={{opacity:fi(f,n.d,16),color:C.white,fontFamily:FONT.mono,fontSize:22,fontWeight:500}}>{n.txt}</div>
            ))}
          </div>
        </div>
        <div style={{opacity:fi(f,170,18),transform:`translateY(${su(f,170,18)}px)`}}>
          {Body('정보의 양만 늘어났을 뿐, 진짜 인사이트는 여전히 없습니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S08:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={8} accent={C.mint} label="일반적 해결책">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>든든한 기분이 드는 것 같지만...</>)}
        </div>
        <div style={{display:'flex',gap:28,opacity:fi(f,50,22)}}>
          <div style={{flex:1,opacity:spr(f,52,22),
            backgroundColor:`${C.mint}12`,border:`1px solid ${C.mint}44`,
            borderRadius:16,padding:'28px 32px'}}>
            {Lbl('기대했던 것',C.mint)}
            {Body('유리한 무기 장착',C.white)}
            {Body('남들보다 빠른 정보',C.white)}
          </div>
          <div style={{display:'flex',alignItems:'center',opacity:fi(f,75,18)}}>
            <Arrow color={C.mint} w={60} h={44} t={5}/>
          </div>
          <div style={{flex:1,opacity:spr(f,88,22),
            backgroundColor:`${C.mint}12`,border:`2px solid ${C.mint}55`,
            borderRadius:16,padding:'28px 32px',
            boxShadow:`0 0 ${osc(f,.04,12,8)}px ${C.mint}33`}}>
            {Lbl('실제 현실',C.mint)}
            {Body('여전히 혼자 끙끙',C.white)}
            {Body('계좌는 제자리걸음',C.white)}
          </div>
        </div>
        <div style={{opacity:fi(f,150,20),transform:`translateY(${su(f,150,20)}px)`}}>
          {Body(<><span style={{color:C.mint,fontWeight:700}}>방법만 바뀌었을 뿐,</span> 본질적인 문제는 전혀 해결되지 않았습니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 3단계: 한계 (S09~S12) — accent: C.mint
// ══════════════════════════════════════════════════════

const S09:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={9} accent={C.mint} label="해결책의 한계">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,26,60)}px)`}}>
          {Lbl('냉정한 현실 직시',C.mint)}
          {TitleXL(<>하지만 현실은<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>어땠나요?</span></>)}
        </div>
        <div style={{opacity:fi(f,80,22),transform:`translateY(${su(f,80,22)}px)`}}>
          {Body('비싼 돈 주고 유료 정보를 결제해도,',C.dim)}
          {Body('결국 내 종목·상황에 맞게 적용하려면 혼자 끙끙대야 합니다',C.white)}
        </div>
        <div style={{
          opacity:fi(f,145,20),
          width:interpolate(f,[145,200],[0,500],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),
          height:4,backgroundColor:C.mint,margin:'0 auto',
          boxShadow:`0 0 14px ${C.mint}88`
        }}/>
      </Ctr>
    </Wrap>
  );
};

const S10:React.FC = () => {
  const f=useCurrentFrame();
  const fails=[
    {icon:'📌',txt:'속보·찌라시 보고 급매수 → 최고점에 물림'},
    {icon:'🧩',txt:'파편화된 정보 → 머릿속에서 정리 불가'},
    {icon:'💸',txt:'시간과 돈은 배로 → 계좌는 파랗게 멍들어'},
  ];
  return (
    <Wrap no={10} accent={C.mint} label="해결책의 한계">
      <Ctr>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>파편화된 정보는<br/><span style={{color:C.mint}}>감정적 뇌동매매</span>로 이어집니다</>)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          {fails.map((item,i)=>(
            <div key={i} style={{
              opacity:spr(f,40+i*24,22),
              transform:`translateX(${interpolate(spr(f,40+i*24,22),[0,1],[60,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
              display:'flex',alignItems:'center',gap:20,
              backgroundColor:`${C.mint}10`,border:`1px solid ${C.mint}44`,
              borderRadius:14,padding:'20px 34px',
            }}>
              <div style={{color:C.mint,fontSize:32,flexShrink:0,fontWeight:700}}>✗</div>
              <span style={{fontSize:32,flexShrink:0}}>{item.icon}</span>
              {Body(item.txt,C.white)}
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,158,20),marginTop:4}}>
          {Body('결국 감정에 휩쓸린 뇌동매매로 이어집니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S11:React.FC = () => {
  const f=useCurrentFrame();
  const infos=[
    {label:'정보 A',sub:'텔레그램 찌라시'},
    {label:'정보 B',sub:'유튜브 의견'},
    {label:'정보 C',sub:'뉴스 속보'},
    {label:'정보 D',sub:'블로그 분석'},
  ];
  return (
    <Wrap no={11} accent={C.mint} label="해결책의 한계">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>수많은 조각 정보들이<br/><span style={{color:C.mint}}>하나로 정리되지 않습니다</span></>)}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:16,opacity:fi(f,45,22)}}>
          {infos.map((item,i)=>(
            <div key={i} style={{
              opacity:spr(f,48+i*16,18),
              transform:`scale(${spr(f,48+i*16,18)})`,
              backgroundColor:C.card,border:'1px solid rgba(255,255,255,0.1)',
              borderRadius:12,padding:'20px 28px',
            }}>
              <div style={{color:C.white,fontSize:28,fontWeight:700,marginBottom:8}}>{item.label}</div>
              <div style={{color:C.dim,fontSize:22,fontWeight:500}}>{item.sub}</div>
            </div>
          ))}
        </div>
        <div style={{opacity:spr(f,130,24),transform:`translateY(${spry(f,130,24,30)}px)`,
          backgroundColor:`${C.mint}10`,border:`2px solid ${C.mint}55`,
          borderRadius:16,padding:'24px 40px',
          boxShadow:`0 0 ${osc(f,.04,12,7)}px ${C.mint}22`}}>
          {Body(<>남이 떠먹여 주는 조각 정보에만 의존해 봐야<br/><span style={{color:C.mint,fontWeight:700}}>결국 남 좋은 일만 시켜주는 꼴입니다</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S12:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={12} accent={C.mint} label="해결책의 한계">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>수많은 변수 속에서<br/><span style={{color:C.mint}}>정보를 '데이터화'할 능력</span>이 없습니다</>)}
        </div>
        <div style={{opacity:spr(f,60,26),display:'flex',alignItems:'center',justifyContent:'center',gap:0}}>
          {['정보 수집량 ⬆','','시간·비용 ⬆','','계좌 수익률 ⬇'].map((txt,i)=>(
            i%2===1
              ? <Arrow key={i} color={C.mint} w={60} h={40} t={5}/>
              : <div key={i} style={{
                  backgroundColor:`${C.mint}12`,border:`1px solid ${C.mint}44`,
                  borderRadius:12,padding:'14px 26px',
                  color:C.white,fontSize:26,fontWeight:600,
                }}>{txt}</div>
          ))}
        </div>
        <div style={{opacity:fi(f,150,20),transform:`translateY(${su(f,150,20)}px)`}}>
          {Body(<><span style={{color:C.mint,fontWeight:700}}>방법만 바뀌었을 뿐,</span><br/>본질적인 문제는 전혀 해결되지 않은 겁니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 4단계: 방향 전환 (S13~S16) — accent: C.mint
// ══════════════════════════════════════════════════════

const S13:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={13} accent={C.mint} label="방향 전환">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,26,60)}px)`}}>
          {Lbl('AI 시대의 주식 투자',C.mint)}
          {TitleXL(<>이제 방향을<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>완전히 바꿔야 합니다</span></>)}
        </div>
        <div style={{opacity:fi(f,90,22),transform:`translateY(${su(f,90,22)}px)`}}>
          {Body('AI가 모든 것을 순식간에 분석하는 지금 시대의 주식 투자는',C.dim)}
          {Body(<>더 이상 <span style={{color:C.mint,fontWeight:700}}>'누가 더 빨리 뉴스를 클릭하느냐'</span>의 피곤한 속도전이 아닙니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S14:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={14} accent={C.mint} label="방향 전환">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>진짜 중요한 건<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>핵심 인사이트를 정리하는 능력</span>입니다</>)}
        </div>
        <div style={{display:'flex',gap:28,opacity:fi(f,55,22)}}>
          <div style={{flex:1,opacity:spr(f,57,22),
            backgroundColor:`${C.mint}10`,border:`1px solid ${C.mint}33`,
            borderRadius:16,padding:'28px 32px',textAlign:'center'}}>
            {Lbl('과거 방식',C.mint)}
            {Body('누가 더 빨리 클릭하느냐',C.dim)}
            {Body('쏟아지는 정보 수동 수집',C.dim)}
          </div>
          <div style={{display:'flex',alignItems:'center',opacity:fi(f,72,18)}}>
            <Arrow color={C.mint} w={70} h={48} t={6}/>
          </div>
          <div style={{flex:1,opacity:spr(f,88,22),
            backgroundColor:`${C.mint}12`,border:`2px solid ${C.mint}55`,
            borderRadius:16,padding:'28px 32px',textAlign:'center',
            boxShadow:`0 0 ${osc(f,.04,14,8)}px ${C.mint}22`}}>
            {Lbl('지금 필요한 것',C.mint)}
            {Body('체계적 수집 자동화',C.white)}
            {Body('우선순위별 인사이트 정리',C.white)}
          </div>
        </div>
        <div style={{opacity:fi(f,150,20),transform:`translateY(${su(f,150,20)}px)`}}>
          {Body('사방에 흩어진 정보를 내 주식 지식으로 데이터화하는 과정!',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S15:React.FC = () => {
  const f=useCurrentFrame();
  const rows=[
    {before:'둥둥 떠다니는 뉴스·텍스트',after:'확실한 매수 근거 데이터'},
    {before:'파편화된 조각 정보',after:'유기적으로 연결된 지식'},
    {before:'감정적 뇌동매매',after:'데이터 기반 매매 판단'},
  ];
  return (
    <Wrap no={15} accent={C.mint} label="방향 전환">
      <Ctr gap={20} maxW={1100}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>텍스트를 <span style={{color:C.mint,filter:Glow(C.mint)}}>데이터로</span> 변환합니다</>)}
          {Sub('흔들리지 않는 나만의 고유한 인사이트 구축',C.mint)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:14}}>
          {rows.map((row,i)=>(
            <div key={i} style={{
              opacity:spr(f,55+i*20,20),
              display:'flex',alignItems:'center',gap:16,
            }}>
              <div style={{flex:1,backgroundColor:`${C.mint}10`,border:`1px solid ${C.mint}33`,borderRadius:12,padding:'16px 26px',color:C.dim,fontSize:26,fontWeight:500,textDecoration:'line-through'}}>{row.before}</div>
              <Arrow color={C.mint} w={60} h={40} t={5}/>
              <div style={{flex:1,backgroundColor:`${C.mint}12`,border:`1px solid ${C.mint}55`,borderRadius:12,padding:'16px 26px',color:C.white,fontSize:26,fontWeight:700,
                boxShadow:`0 0 ${osc(f,.05,6,4)}px ${C.mint}22`}}>{row.after}</div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,155,18),color:C.mint,fontSize:30,fontWeight:700,marginTop:4,filter:Glow(C.mint)}}>
          생각만 해봐도 멋지지 않습니까?
        </div>
      </Ctr>
    </Wrap>
  );
};

const S16:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={16} accent={C.mint} label="방향 전환">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('정보에 끌려다니는 대신',C.mint)}
          {Title(<>정보를 <span style={{color:C.mint,filter:Glow(C.mint)}}>내 지식으로 데이터화</span>하는 시스템</>)}
        </div>
        <div style={{opacity:spr(f,60,26),display:'flex',alignItems:'center',justifyContent:'center',gap:0}}>
          {[
            {label:'📡 정보 수집',sub:'뉴스·채널·리포트',c:C.card,bc:'rgba(255,255,255,0.15)'},
            null,
            {label:'🤖 AI 분석',sub:'핵심 인사이트 추출',c:`${C.mint}15`,bc:C.mint},
            null,
            {label:'📚 지식 누적',sub:'나만의 LLM 위키',c:`${C.mint}15`,bc:C.mint},
          ].map((item,i)=>(
            item===null
              ? <Arrow key={i} color={C.mint} w={72} h={48} t={6}/>
              : <div key={i} style={{
                  opacity:spr(f,62+Math.floor(i/2)*26,20),
                  transform:`scale(${spr(f,62+Math.floor(i/2)*26,20)})`,
                  backgroundColor:item.c,
                  border:`2px solid ${item.bc}`,
                  borderRadius:16,padding:'26px 36px',textAlign:'center',minWidth:210,
                  boxShadow:i===2?`0 0 ${osc(f,.04,14,8)}px ${C.mint}33`:undefined,
                }}>
                  <div style={{color:C.white,fontSize:28,fontWeight:700,marginBottom:8}}>{item.label}</div>
                  <div style={{color:C.dim,fontSize:18,fontWeight:500}}>{item.sub}</div>
                </div>
          ))}
        </div>
        <div style={{opacity:fi(f,155,20),transform:`translateY(${su(f,155,20)}px)`}}>
          {Body(<>결국 정보에 끌려다니는 대신, <span style={{color:C.mint,fontWeight:700}}>정보가 내 자산으로 쌓입니다</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 5단계: 다른 대안의 한계 (S17~S19) — accent: C.mint
// ══════════════════════════════════════════════════════

const S17:React.FC = () => {
  const f=useCurrentFrame();
  const cursor=Math.floor(f*.6)%2===0;
  return (
    <Wrap no={17} accent={C.mint} label="대안의 한계">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>매일 복붙하는<br/><span style={{color:C.mint}}>또 다른 끔찍한 노가다</span></>)}
        </div>
        <div style={{opacity:spr(f,45,24),
          backgroundColor:'#090b18',border:'1px solid rgba(255,255,255,0.1)',
          borderRadius:18,overflow:'hidden'}}>
          <div style={{backgroundColor:'#111428',padding:'14px 22px',display:'flex',gap:10,alignItems:'center'}}>
            {['#FF5F56','#FFBD2E','#27C93F'].map((c,i)=><div key={i} style={{width:13,height:13,borderRadius:'50%',backgroundColor:c}}/>)}
            <span style={{color:C.dim,fontFamily:FONT.mono,fontSize:16,marginLeft:12}}>일반 AI 채팅창</span>
          </div>
          <div style={{padding:'24px 32px',display:'flex',flexDirection:'column',gap:14}}>
            {[
              {txt:'"오늘 반도체 뉴스 요약해줘"',c:C.mint,d:52},
              {txt:'... (요약 결과)',c:C.dim,d:76},
              {txt:'"그럼 삼성전자는 호재야?"',c:C.mint,d:114},
              {txt:'... (또 다른 단편적 답변)',c:C.dim,d:138},
              {txt:'"SK하이닉스는?"',c:C.mint,d:176},
            ].map((l,i)=>(
              <div key={i} style={{opacity:fi(f,l.d,16),color:l.c,fontFamily:FONT.mono,fontSize:22,fontWeight:500}}>
                {l.txt}{i===4&&cursor&&<span style={{opacity:.9}}>_</span>}
              </div>
            ))}
          </div>
        </div>
        <div style={{opacity:fi(f,198,18),transform:`translateY(${su(f,198,18)}px)`}}>
          {Body('처음 며칠은 신기해서 하겠지만, 결국 이것도 끔찍한 노가다입니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S18:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={18} accent={C.mint} label="대안의 한계">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('치명적인 구조적 문제',C.mint)}
          {TitleXL(<>지식의<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>휘발성</span> 문제</>)}
        </div>
        <div style={{opacity:spr(f,55,26),display:'flex',alignItems:'center',justifyContent:'center',gap:0}}>
          {['💡 인사이트 도출','','창 닫기 ✕','','허공으로 사라짐 💨'].map((txt,i)=>(
            i%2===1
              ? <Arrow key={i} color={i===1?C.mint:C.mint} w={60} h={40} t={5}/>
              : <div key={i} style={{
                  backgroundColor:i===4?`${C.mint}15`:C.card,
                  border:`2px solid ${i===4?C.mint:C.mint}55`,
                  borderRadius:12,padding:'16px 28px',
                  color:i===4?C.mint:C.white,fontSize:24,fontWeight:i===4?700:600,
                }}>{txt}</div>
          ))}
        </div>
        <div style={{opacity:spr(f,130,24),transform:`translateY(${spry(f,130,24,30)}px)`,
          backgroundColor:`${C.mint}10`,border:`2px solid ${C.mint}44`,
          borderRadius:16,padding:'28px 40px',
          boxShadow:`0 0 ${osc(f,.04,12,7)}px ${C.mint}22`}}>
          {Body(<>어제 힘들게 뽑아낸 인사이트와 오늘의 시황이<br/><span style={{color:C.mint,fontWeight:700}}>내 지식 창고에 온전히 누적되지 않습니다</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S19:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={19} accent={C.mint} label="대안의 한계">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>매일 새 창을 열어<br/><span style={{color:C.mint}}>파편화된 질문만 반복</span>합니다</>)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:14}}>
          {[
            {day:'1일차',txt:'새 창 열기 → 오늘 뉴스 복붙 → 요약 → 창 닫기'},
            {day:'2일차',txt:'새 창 열기 → 오늘 뉴스 복붙 → 요약 → 창 닫기'},
            {day:'3일차',txt:'새 창 열기 → 오늘 뉴스 복붙 → 요약 → 창 닫기'},
          ].map((item,i)=>(
            <div key={i} style={{
              opacity:spr(f,42+i*22,20),
              display:'flex',gap:20,alignItems:'center',
              backgroundColor:C.card,border:'1px solid rgba(255,255,255,0.08)',
              borderRadius:12,padding:'18px 28px',
            }}>
              <div style={{color:C.mint,fontSize:20,fontWeight:700,flexShrink:0,fontFamily:FONT.mono}}>{item.day}</div>
              <div style={{color:C.dim,fontSize:24,fontWeight:500,fontFamily:FONT.mono}}>{item.txt}</div>
            </div>
          ))}
          <div style={{
            opacity:spr(f,120,22),
            display:'flex',gap:20,alignItems:'center',
            backgroundColor:`${C.mint}10`,border:`2px solid ${C.mint}44`,
            borderRadius:12,padding:'18px 28px',
          }}>
            <div style={{color:C.mint,fontSize:20,fontWeight:700,flexShrink:0,fontFamily:FONT.mono}}>N일차</div>
            <div style={{color:C.mint,fontSize:24,fontWeight:700}}>정보가 내 자산으로 쌓이지 않는다</div>
          </div>
        </div>
        <div style={{opacity:fi(f,168,20),transform:`translateY(${su(f,168,20)}px)`}}>
          {Body('진짜 시스템을 결코 만들 수 없다는 겁니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 6단계: 솔루션 (S20~S24) — accent: C.mint ★ 핵심 ★
// ══════════════════════════════════════════════════════

const S20:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={20} accent={C.mint} label="솔루션">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,26,60)}px)`}}>
          {Lbl('저만의 자동화 방법',C.mint)}
          {TitleXL(<><span style={{color:C.mint,filter:Glow(C.mint)}}>Claude AI</span>를<br/>파이프라인 첫 단계에<br/>배치했습니다</>)}
        </div>
        <div style={{opacity:fi(f,100,22),transform:`translateY(${su(f,100,22)}px)`}}>
          {Body(<>심지어 제가 <span style={{color:C.mint,fontWeight:700}}>자는 동안에도</span> 이 AI가<br/>주요 채널과 뉴스를 싹 다 훑고,<br/>시장의 핵심 인사이트만 완벽하게 도출해 냅니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S21:React.FC = () => {
  const f=useCurrentFrame();
  const flowPulse=osc(f,.05,.5,.3);
  return (
    <Wrap no={21} accent={C.mint} label="솔루션">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>자동화 파이프라인</>)}
          {Sub('제가 묻지 않아도 알아서 정리됩니다',C.mint)}
        </div>
        <div style={{opacity:fi(f,55,20),display:'flex',alignItems:'center',justifyContent:'center',gap:0}}>
          {[
            {label:'📡 채널·뉴스',sub:'자동 수집',c:C.card,bc:'rgba(255,255,255,0.2)',idx:0},
            null,
            {label:'🤖 Claude AI',sub:'핵심 분석',c:`${C.mint}15`,bc:C.mint,idx:1},
            null,
            {label:'📚 LLM 위키',sub:'지식 누적',c:`${C.mint}15`,bc:C.mint,idx:2},
          ].map((item,i)=>(
            item===null
              ? <Arrow key={i} color={C.mint} w={72} h={48} t={6}/>
              : <div key={i} style={{
                  opacity:spr(f,60+item.idx*26,22),
                  transform:`scale(${spr(f,60+item.idx*26,22)})`,
                  backgroundColor:item.c,border:`2px solid ${item.bc}`,
                  borderRadius:18,padding:'28px 38px',textAlign:'center',minWidth:220,
                  boxShadow:item.idx===1?`0 0 ${flowPulse*22}px ${C.mint}44`:undefined,
                }}>
                  <div style={{color:C.white,fontSize:28,fontWeight:700,marginBottom:8}}>{item.label}</div>
                  <div style={{color:C.dim,fontSize:18,fontWeight:500}}>{item.sub}</div>
                </div>
          ))}
        </div>
        <div style={{opacity:fi(f,160,20),transform:`translateY(${su(f,160,20)}px)`}}>
          {Body(<>심지어 <span style={{color:C.mint,fontWeight:700}}>제가 자는 동안에도</span> 이 AI가 알아서 작동합니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S22:React.FC = () => {
  const f=useCurrentFrame();
  const newsItems=['📰 삼성전자 실적 발표','📡 반도체 수출 데이터 서프라이즈','🏦 미 연준 금리 결정','💱 원달러 환율 급등','📊 외국인 대규모 순매수'];
  return (
    <Wrap no={22} accent={C.mint} label="자동 수집·분석">
      <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',padding:'90px 100px',gap:24}}>
        <div style={{maxWidth:1140,width:'100%'}}>
          <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`,textAlign:'center',marginBottom:32}}>
            {Title(<>자는 동안 <span style={{color:C.mint,filter:Glow(C.mint)}}>자동으로 수집·분석</span>됩니다</>)}
          </div>
          <div style={{display:'flex',gap:32,alignItems:'flex-start'}}>
            <div style={{flex:1,display:'flex',flexDirection:'column',gap:12}}>
              {Lbl('오늘 주요 뉴스',C.dim)}
              {newsItems.map((item,i)=>(
                <div key={i} style={{
                  opacity:spr(f,35+i*16,16),
                  transform:`translateX(${interpolate(spr(f,35+i*16,16),[0,1],[-36,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
                  backgroundColor:C.card,border:'1px solid rgba(255,255,255,0.1)',
                  borderRadius:12,padding:'14px 24px',
                  color:C.white,fontSize:24,fontWeight:500,
                }}>{item}</div>
              ))}
            </div>
            <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:10,paddingTop:60}}>
              <div style={{opacity:fi(f,90,18)}}>
                <Arrow color={C.mint} w={68} h={44} t={6}/>
              </div>
              <div style={{color:C.mint,fontSize:17,fontWeight:600,opacity:fi(f,95,18)}}>자동 분석</div>
            </div>
            <div style={{flex:1.1}}>
              {Lbl('LLM 위키에 누적',C.mint)}
              <div style={{
                opacity:spr(f,115,26),
                transform:`scale(${spr(f,115,26)})`,
                backgroundColor:`${C.mint}12`,border:`2px solid ${C.mint}44`,
                borderRadius:16,padding:'26px 30px',
                display:'flex',flexDirection:'column',gap:14,
                boxShadow:`0 0 ${osc(f,.04,14,8)}px ${C.mint}22`,
              }}>
                {['✅ 삼성전자 — 수급 분석 완료','✅ 반도체 섹터 — 인사이트 추출','✅ 시황 요약 — 대시보드 업데이트','✅ 외국인 매수 — 종목 연결 완료'].map((txt,i)=>(
                  <div key={i} style={{opacity:spr(f,122+i*16,16),color:C.white,fontSize:24,fontWeight:500}}>{txt}</div>
                ))}
              </div>
              <div style={{opacity:fi(f,200,18),marginTop:14}}>
                {Body(<><span style={{color:C.mint,fontWeight:700}}>묻지 않아도 알아서</span> 정리됩니다</>,C.white)}
              </div>
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </Wrap>
  );
};

const S23:React.FC = () => {
  const f=useCurrentFrame();
  const graphFrame=Math.max(0,f-18);
  const nodeCount=Math.min(NODES.length,Math.max(0,Math.floor((graphFrame-10)/17)));
  const edgeCount=Math.min(EDGES.length,Math.max(0,Math.floor((graphFrame-268)/11)));
  const cPulse=osc(f,.08,.88,.1);
  return (
    <Wrap no={23} accent={C.mint} label="지식 그래프">
      <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',padding:'72px 60px 84px',gap:18}}>
        <div style={{textAlign:'center'}}>
          <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
            {Title(<>단편적인 뉴스가<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>유기적으로 연결됩니다</span></>)}
          </div>
          <div style={{opacity:fi(f,38,18)}}>
            {Body('과거의 지식과 오늘의 시황이 얽히며 살아있는 지식망이 형성됩니다',C.dim)}
          </div>
        </div>
        <div style={{opacity:fi(f,16,18),position:'relative'}}>
          <KGraph frame={graphFrame}/>
          <div style={{position:'absolute',bottom:-8,right:0,display:'flex',gap:16,opacity:fi(f,420,20)}}>
            {[
              {c:C.news,  label:'뉴스'},
              {c:C.mint,label:'종목'},
              {c:C.mint,  label:'섹터/허브'},
              {c:C.mint,  label:'인사이트'},
            ].map((item,i)=>(
              <div key={i} style={{display:'flex',alignItems:'center',gap:7}}>
                <div style={{width:11,height:11,borderRadius:'50%',backgroundColor:item.c,
                  boxShadow:item.c===C.mint?`0 0 7px ${C.mint}99`:undefined}}/>
                <span style={{color:C.dim,fontSize:15,fontFamily:FONT.mono}}>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{display:'flex',gap:32,justifyContent:'center',opacity:fi(f,260,20)}}>
          {[
            {count:nodeCount,label:'지식 노드',color:C.mint},
            {count:edgeCount,label:'연결 관계',color:C.mint},
          ].map((item,i)=>(
            <div key={i} style={{textAlign:'center'}}>
              <div style={{color:item.color,fontSize:52,fontWeight:800,fontFamily:FONT.mono,
                transform:`scale(${cPulse})`,display:'inline-block',
                filter:`drop-shadow(0 0 10px ${item.color}77)`}}>{item.count}</div>
              <div style={{color:C.dim,fontSize:18,fontWeight:500,marginTop:4}}>{item.label}</div>
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </Wrap>
  );
};

const S24_EXTRA:GNode[] = [
  {id:'x1',label:'오늘 시황',  bx:.36,by:.83,r:14,color:C.news,  appear:70},
  {id:'x2',label:'POSCO홀딩스',bx:.13,by:.41,r:16,color:C.mint,appear:120},
  {id:'x3',label:'새 인사이트', bx:.89,by:.27,r:18,color:C.mint, appear:170},
  {id:'x4',label:'매물대 분석', bx:.05,by:.29,r:15,color:C.mint, appear:230},
  {id:'x5',label:'LG에너지솔루션',bx:.91,by:.57,r:15,color:C.mint,appear:290},
];
const S24_EXTRA_E:GEdge[] = [
  {from:'wiki',to:'x1',appear:85},{from:'wiki',to:'x2',appear:135},
  {from:'wiki',to:'x3',appear:185},{from:'wiki',to:'x4',appear:245},
  {from:'wiki',to:'x5',appear:305},{from:'x3',to:'i2',appear:200},
  {from:'x4',to:'i1',appear:260},{from:'x2',to:'s1',appear:150},
];

const S24:React.FC = () => {
  const f=useCurrentFrame();
  const graphFrame=SDUR+f;
  const totalNodes=13+Math.min(5,Math.floor(f/75));
  const totalEdges=20+Math.min(8,Math.floor(f/62));
  const todayNodes=Math.min(5,Math.floor(f/84)+1);
  const statPulse=osc(f,.05,.86,.12);
  return (
    <Wrap no={24} accent={C.mint} label="지식의 복리">
      <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',padding:'72px 60px 84px',gap:18}}>
        <div style={{textAlign:'center',opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>매일 쌓이고, 매일 <span style={{color:C.mint,filter:Glow(C.mint)}}>복리로 성장합니다</span></>)}
        </div>
        <div style={{position:'relative',opacity:fi(f,5,14)}}>
          <KGraph frame={graphFrame} extraNodes={S24_EXTRA} extraEdges={S24_EXTRA_E}/>
          {S24_EXTRA.map((node,i)=>{
            if(f<node.appear||f>node.appear+65) return null;
            const alpha=fi(f,node.appear,10)*(1-fi(f,node.appear+55,10));
            return (
              <div key={i} style={{
                position:'absolute',
                left:node.bx*GW,top:node.by*GH-58,
                transform:'translateX(-50%)',
                backgroundColor:`${C.mint}22`,border:`1px solid ${C.mint}77`,
                borderRadius:8,padding:'5px 14px',
                color:C.mint,fontSize:15,fontWeight:700,
                opacity:alpha,whiteSpace:'nowrap',
                boxShadow:`0 0 12px ${C.mint}44`,
              }}>+ {node.label}</div>
            );
          })}
        </div>
        <div style={{display:'flex',gap:22,justifyContent:'center',opacity:fi(f,50,22)}}>
          {[
            {label:'누적 지식 페이지',val:`${totalNodes}`,unit:'페이지',c:C.mint},
            {label:'연결 관계',val:`${totalEdges}`,unit:'개',c:C.mint},
            {label:'오늘 추가',val:`+${todayNodes}`,unit:'노드',c:C.mint},
          ].map((item,i)=>(
            <div key={i} style={{
              opacity:spr(f,55+i*16,18),transform:`scale(${spr(f,55+i*16,18)})`,
              backgroundColor:`${item.c}12`,border:`1px solid ${item.c}44`,
              borderRadius:14,padding:'18px 30px',textAlign:'center',
              boxShadow:`0 0 ${osc(f,.04+i*.01,8,5)}px ${item.c}33`,
            }}>
              <div style={{
                color:item.c,fontSize:48,fontWeight:800,fontFamily:FONT.mono,
                transform:`scale(${statPulse})`,display:'inline-block',
                filter:`drop-shadow(0 0 12px ${item.c}77)`,
              }}>{item.val}<span style={{fontSize:22}}> {item.unit}</span></div>
              <div style={{color:C.dim,fontSize:17,fontWeight:500,marginTop:4}}>{item.label}</div>
            </div>
          ))}
        </div>
        <div style={{
          opacity:fi(f,340,22),
          backgroundColor:`${C.mint}10`,border:`2px solid ${C.mint}44`,
          borderRadius:14,padding:'20px 44px',textAlign:'center',maxWidth:800,
          boxShadow:`0 0 ${osc(f,.04,16,10)}px ${C.mint}22`,
        }}>
          {Body(<>과거의 지식과 오늘의 시황이 유기적으로 얽히며<br/><span style={{color:C.mint,fontWeight:700}}>지식이 눈덩이처럼 불어납니다</span></>)}
        </div>
      </AbsoluteFill>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 6단계 보너스: 대시보드 (S25) — accent: C.mint
// ══════════════════════════════════════════════════════

const S25:React.FC = () => {
  const f=useCurrentFrame();
  const items=[
    {icon:'📊',title:'수급빈집 탐지',val:'3종목 발견',color:C.mint},
    {icon:'🎯',title:'대장주 후보',val:'SK하이닉스 ↑',color:C.mint},
    {icon:'📈',title:'반도체 섹터',val:'수급 유입 중',color:C.mint},
    {icon:'💡',title:'오늘의 인사이트',val:'대형주 매수세',color:C.mint},
  ];
  return (
    <Wrap no={25} accent={C.mint} label="완성된 대시보드">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>하나의 대시보드로<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>시장 흐름을 한눈에</span></>)}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:18,width:'100%'}}>
          {items.map((item,i)=>(
            <div key={i} style={{
              opacity:spr(f,38+i*16,18),
              transform:`scale(${spr(f,38+i*16,18)})`,
              backgroundColor:`${item.color}12`,border:`2px solid ${item.color}44`,
              borderRadius:16,padding:'26px 32px',
              display:'flex',alignItems:'center',gap:18,textAlign:'left',
              boxShadow:`0 0 ${osc(f,.04+i*.008,7,5)}px ${item.color}22`,
            }}>
              <span style={{fontSize:44}}>{item.icon}</span>
              <div>
                <div style={{color:item.color,fontSize:18,fontWeight:600,marginBottom:6}}>{item.title}</div>
                <div style={{color:C.white,fontSize:30,fontWeight:800}}>{item.val}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,150,20),transform:`translateY(${su(f,150,20)}px)`}}>
          {Body(<>남들의 생각을 찾아다닐 필요 없이<br/><span style={{color:C.mint,fontWeight:700}}>완벽하게 업데이트된 나만의 인사이트</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 7단계: CTA (S26~S28) — accent: C.mint / C.mint
// ══════════════════════════════════════════════════════

const S26:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={28} accent={C.mint} label="CTA">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('솔직하게 말씀드립니다',C.mint)}
          {Title(<>저는 복잡한 코드를 짜는<br/><span style={{color:C.mint}}>전문 개발자가 아닙니다</span></>)}
        </div>
        <div style={{opacity:spr(f,55,26),
          backgroundColor:C.card,border:`1px solid rgba(255,255,255,0.12)`,
          borderRadius:18,padding:'32px 44px',
          display:'flex',flexDirection:'column',gap:12}}>
          {[
            {txt:'매일 HTS 창을 보며 피를 말리는',w:false},
            {txt:'시장에서 치열하게 살아남기 위해 발버둥 치던',w:false},
            {txt:'여러분과 똑같이 평범한 개인 투자자입니다',w:true},
          ].map((item,i)=>(
            <div key={i} style={{opacity:spr(f,58+i*20,20)}}>
              {Body(item.txt,item.w?C.white:C.dim,item.w?{fontWeight:700}:undefined)}
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,155,20),transform:`translateY(${su(f,155,20)}px)`}}>
          {Body(<>하지만 <span style={{color:C.mint,fontWeight:700}}>'변하지 않으면 도태된다'</span>는 절박함 하나로<br/>이 시스템을 만들고 있습니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S27:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={29} accent={C.mint} label="CTA">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Title(<>유튜브 채널을 오픈한 이유는<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>하나입니다</span></>)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          {[
            {icon:'🤝',txt:'같은 고민을 하셨던 분들과 함께 공부하기 위해서',d:45},
            {icon:'🎁',txt:'제가 구축한 이 편리한 시스템의 가치를 나누고 싶어서',d:68},
            {icon:'🚀',txt:'지식 자동화의 강력한 퍼포먼스를 직접 경험하실 수 있도록',d:91},
          ].map((item,i)=>(
            <div key={i} style={{
              opacity:spr(f,item.d,22),
              transform:`translateX(${interpolate(spr(f,item.d,22),[0,1],[-44,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
              backgroundColor:`${C.mint}10`,border:`1px solid ${C.mint}33`,
              borderRadius:14,padding:'20px 30px',
              display:'flex',alignItems:'center',gap:18,textAlign:'left',
            }}>
              <span style={{fontSize:36,flexShrink:0}}>{item.icon}</span>
              {Body(item.txt,C.white)}
            </div>
          ))}
        </div>
        <div style={{opacity:spr(f,158,24),transform:`translateY(${spry(f,158,24,30)}px)`,
          backgroundColor:`${C.mint}12`,border:`2px solid ${C.mint}44`,
          borderRadius:14,padding:'20px 40px',
          boxShadow:`0 0 ${osc(f,.04,14,9)}px ${C.mint}22`}}>
          {Body(<>조만간 여러분도 이 <span style={{color:C.mint,fontWeight:700}}>지식 자동화 정식 서비스</span>를 경험하실 수 있습니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S28:React.FC = () => {
  const f=useCurrentFrame();
  const btnPulse=osc(f,.06,.78,.18);
  return (
    <Wrap no={31} accent={C.mint} label="시작">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,26,60)}px)`}}>
          {Lbl('지식이 무기가 되는 새로운 투자',C.mint)}
          {TitleXL(<>혼자만의 외로운 투자가 아닌<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>함께하는 여정</span></>)}
        </div>
        <div style={{opacity:spr(f,55,26),transform:`translateY(${spry(f,55,26,30)}px)`,
          backgroundColor:`${C.mint}10`,border:`2px solid ${C.mint}55`,
          borderRadius:18,padding:'30px 44px',
          boxShadow:`0 0 ${osc(f,.04,18,12)}px ${C.mint}22`}}>
          {Body(<>그 첫걸음을 <span style={{color:C.mint,fontWeight:700,fontSize:32}}>함께 기대해 주시기 바랍니다</span></>)}
        </div>
        <div style={{display:'flex',gap:20,justifyContent:'center',opacity:fi(f,105,22)}}>
          {[
            {label:'👍 좋아요',bg:C.mint},
            {label:'🔔 구독',bg:C.mint},
            {label:'🔔 알림 설정',bg:C.mint},
          ].map((btn,i)=>(
            <div key={i} style={{
              opacity:spr(f,112+i*16,18),
              transform:`scale(${spr(f,112+i*16,18)*btnPulse})`,
              backgroundColor:btn.bg,color:C.bg,
              fontSize:28,fontWeight:800,
              borderRadius:50,padding:'18px 44px',
              boxShadow:`0 0 ${osc(f,.06+i*.01,16,12)}px ${btn.bg}77`,
            }}>{btn.label}</div>
          ))}
        </div>
        <div style={{opacity:fi(f,178,20),transform:`translateY(${su(f,178,20)}px)`}}>
          {Body('로또의 주식 — 구독과 좋아요가 큰 힘이 됩니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// LLM 위키 시스템 공개 & 다음 영상 예고 (S_LLMWiki)
// ══════════════════════════════════════════════════════

const S_LLMWiki: React.FC = () => {
  const f = useCurrentFrame();
  const namePulse = osc(f,.035,1,.04);
  const btnPulse  = osc(f,.05,.82,.16);
  return (
    <Wrap no={25} accent={C.mint} label="시스템 공개">
      <Ctr gap={28}>

        {/* 리드인 */}
        <div style={{opacity:fi(f,8,16),transform:`translateY(${spry(f,8,20,40)}px)`}}>
          {Lbl('자, 이제 소개드립니다',C.mint)}
          {Body('이 시스템의 이름은',C.dim)}
        </div>

        {/* LLM 위키 — 핵심 공개 */}
        <div style={{
          opacity:spr(f,40,30),
          transform:`scale(${spr(f,40,30)*namePulse})`,
          filter:Glow(C.mint),
        }}>
          {TitleXL('LLM 위키',C.mint,{letterSpacing:'-3px'})}
        </div>

        {/* "라는 시스템입니다" */}
        <div style={{opacity:fi(f,82,22),transform:`translateY(${su(f,82,22)}px)`}}>
          {Sub('라는 시스템입니다',C.white,{marginBottom:0})}
        </div>

        {/* 다음 영상 예고 카드 */}
        <div style={{
          opacity:spr(f,130,28),
          transform:`translateY(${spry(f,130,28,30)}px)`,
          backgroundColor:`${C.mint}14`,border:`2px solid ${C.mint}66`,
          borderRadius:18,padding:'26px 48px',
          boxShadow:`0 0 ${osc(f,.05,18,10)}px ${C.mint}44`,
        }}>
          <div style={{color:C.mint,fontSize:16,fontWeight:700,letterSpacing:3,marginBottom:10}}>
            COMING NEXT
          </div>
          {Body('다음 영상에서 자세하게 소개드리겠습니다',C.white,{fontWeight:600})}
        </div>

        {/* 맥동 기대 버튼 */}
        <div style={{
          opacity:fi(f,188,20),
          transform:`scale(${btnPulse})`,
          backgroundColor:`${C.mint}15`,border:`2px solid ${C.mint}55`,
          borderRadius:50,padding:'16px 52px',display:'inline-block',
          boxShadow:`0 0 ${osc(f,.05,14,9)}px ${C.mint}44`,
        }}>
          {Body('기대해 주세요!',C.mint,{fontWeight:700})}
        </div>

      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 솔루션 전환: 자동화 방법 예고 (S_Teaser)
// ══════════════════════════════════════════════════════

const S_Teaser: React.FC = () => {
  const f = useCurrentFrame();
  const lineW = interpolate(f,[100,160],[0,560],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const arrowX = osc(f,.06,0,10);
  return (
    <Wrap no={20} accent={C.mint} label="솔루션 예고">
      <Ctr gap={36}>

        {/* 1. "그래서" 전환 레이블 */}
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('그래서 직접 찾았습니다',C.mint)}
          {TitleXL(<>저만의<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>자동화 방법</span></>)}
        </div>

        {/* 2. "매일 사용하고 있는" 뱃지 */}
        <div style={{
          opacity:spr(f,55,26),
          transform:`scale(${spr(f,55,26)})`,
          backgroundColor:`${C.mint}12`,border:`2px solid ${C.mint}55`,
          borderRadius:50,padding:'16px 52px',display:'inline-block',
          boxShadow:`0 0 ${osc(f,.04,16,10)}px ${C.mint}33`,
        }}>
          {Body('매일 직접 사용하고 있는',C.mint,{fontWeight:700})}
        </div>

        {/* 3. 민트 언더라인 */}
        <div style={{
          opacity:fi(f,100,18),
          width:lineW,height:3,backgroundColor:C.mint,
          margin:'0 auto',boxShadow:`0 0 12px ${C.mint}88`,
        }}/>

        {/* 4. 살짝 보여드릴게요 */}
        <div style={{opacity:fi(f,118,24),transform:`translateY(${su(f,118,24)}px)`}}>
          {Sub('살짝 보여드릴게요',C.white)}
        </div>

        {/* 5. 앞으로 향하는 맥동 화살표 */}
        <div style={{
          opacity:fi(f,158,20),
          transform:`translateX(${arrowX}px)`,
          filter:Glow(C.mint),
          display:'flex',justifyContent:'center',
        }}>
          <Arrow color={C.mint} w={96} h={58} t={7}/>
        </div>

      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 7단계 추가: AI의 한계 & 인간의 인사이트 (S26~S27 신규)
// ══════════════════════════════════════════════════════

const S_AILimit: React.FC = () => {
  const f = useCurrentFrame();
  const panicX = interpolate(spr(f,38,28),[0,1],[-220,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const madX   = interpolate(spr(f,62,28),[0,1],[220,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const shake  = Math.sin(f*0.8)*interpolate(f,[90,130],[2,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return (
    <Wrap no={26} accent={C.mint} label="AI의 한계">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('가장 중요한 깨달음',C.mint)}
          {Title(<>아무리 강력한 AI라도<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>읽어낼 수 없는 것이 있습니다</span></>)}
        </div>
        <div style={{display:'flex',gap:44,justifyContent:'center',alignItems:'center'}}>
          <div style={{
            opacity:spr(f,38,28),
            transform:`translateX(${panicX}px) rotate(${shake}deg)`,
            backgroundColor:`${C.mint}14`,border:`2px solid ${C.mint}66`,
            borderRadius:22,padding:'34px 56px',textAlign:'center',minWidth:230,
            boxShadow:`0 0 ${osc(f,.06,12,8)}px ${C.mint}44`,
          }}>
            {Sub('패닉',C.mint)}
            {Body('공포에 의한 투매',C.dim)}
          </div>
          <div style={{opacity:fi(f,72,18),color:C.dim,fontSize:40,fontWeight:300,lineHeight:1}}>+</div>
          <div style={{
            opacity:spr(f,62,28),
            transform:`translateX(${madX}px) rotate(${-shake}deg)`,
            backgroundColor:`${C.mint}14`,border:`2px solid ${C.mint}66`,
            borderRadius:22,padding:'34px 56px',textAlign:'center',minWidth:230,
            boxShadow:`0 0 ${osc(f,.05,12,8)}px ${C.mint}44`,
          }}>
            {Sub('광기',C.mint)}
            {Body('탐욕에 의한 과열',C.dim)}
          </div>
        </div>
        <div style={{
          opacity:fi(f,128,22),
          transform:`translateY(${su(f,128,22)}px)`,
          backgroundColor:`${C.mint}10`,border:`1px solid ${C.mint}44`,
          borderRadius:16,padding:'24px 52px',
        }}>
          {Body(<><span style={{color:C.mint,fontWeight:700}}>인간의 감정과 심리</span>는<br/>어떤 AI도 완벽히 읽어낼 수 없습니다</>,C.white)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S_HumanInsight: React.FC = () => {
  const f = useCurrentFrame();
  const steps = [
    {label:'데이터',role:'연료',accent:C.dim,   card:C.card,             border:'rgba(255,255,255,0.18)'},
    {label:'AI',   role:'엔진',accent:C.mint,   card:`${C.mint}15`,     border:C.mint},
    {label:'인간',  role:'운전자',accent:C.mint,card:`${C.mint}18`,  border:C.mint},
  ];
  return (
    <Wrap no={27} accent={C.mint} label="인간의 인사이트">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('이 시스템을 만들며 깨달은 것',C.mint)}
          {Title(<>데이터는 연료, AI는 엔진<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>시장을 운전하는 건 인간의 인사이트</span></>)}
        </div>
        <div style={{display:'flex',alignItems:'center',justifyContent:'center',gap:0}}>
          {steps.map((step,i)=>(
            <React.Fragment key={i}>
              <div style={{
                opacity:spr(f,45+i*24,22),
                transform:`scale(${spr(f,45+i*24,22)})`,
                backgroundColor:step.card,border:`2px solid ${step.border}`,
                borderRadius:18,padding:'30px 40px',textAlign:'center',minWidth:200,
                boxShadow:i===2?`0 0 ${osc(f,.05,20,12)}px ${C.mint}44`:undefined,
              }}>
                {Sub(step.label,step.accent,{marginBottom:8})}
                {Lbl(step.role,C.dim)}
              </div>
              {i<steps.length-1&&(
                <div style={{opacity:fi(f,62+i*24,18),margin:'0 6px'}}>
                  <Arrow color={C.mint} w={68} h={44} t={5}/>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
        <div style={{
          opacity:spr(f,148,26),
          transform:`translateY(${spry(f,148,26,30)}px)`,
          backgroundColor:`${C.mint}12`,border:`2px solid ${C.mint}55`,
          borderRadius:16,padding:'26px 56px',
          boxShadow:`0 0 ${osc(f,.04,20,12)}px ${C.mint}33`,
        }}>
          {Body(<><span style={{color:C.mint,fontWeight:700}}>인사이트</span>가 있는 사람이 시장을 이깁니다</>,C.white)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 7단계 추가: 서비스 준비 CTA (S30 신규)
// ══════════════════════════════════════════════════════

const S_ServiceCTA: React.FC = () => {
  const f = useCurrentFrame();
  const btnPulse = osc(f,.06,.8,.18);
  return (
    <Wrap no={30} accent={C.mint} label="서비스 준비">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('조만간 오픈 예정',C.mint)}
          {Title(<>나만의 <span style={{color:C.mint,filter:Glow(C.mint)}}>투자 방향</span>을<br/>완성하실 수 있도록</>)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:18}}>
          {[
            {txt:'운에 맡기는 투자',mark:'✗',highlight:false},
            {txt:'AI 데이터기반 인사이트 투자',mark:'✓',highlight:true},
          ].map(({txt,mark,highlight},i)=>(
            <div key={i} style={{
              opacity:spr(f,48+i*30,24),
              transform:`translateX(${interpolate(spr(f,48+i*30,24),[0,1],[-50,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
              display:'flex',alignItems:'center',gap:24,
              backgroundColor:highlight?`${C.mint}16`:`${C.mint}10`,
              border:`2px solid ${highlight?C.mint:C.mint}44`,
              borderRadius:16,padding:'24px 38px',
            }}>
              <div style={{color:highlight?C.mint:C.mint,fontSize:36,fontWeight:900,flexShrink:0,fontFamily:FONT.mono}}>{mark}</div>
              {Body(txt,highlight?C.white:C.dim,highlight?{fontWeight:700}:undefined)}
            </div>
          ))}
        </div>
        <div style={{
          opacity:spr(f,138,26),
          transform:`scale(${spr(f,138,26)*btnPulse})`,
          backgroundColor:`${C.mint}22`,border:`2px solid ${C.mint}`,
          borderRadius:50,padding:'20px 72px',
          boxShadow:`0 0 ${osc(f,.05,20,12)}px ${C.mint}77`,
          display:'inline-block',
        }}>
          {Sub('서비스 준비 중',C.mint,{marginBottom:0})}
        </div>
        <div style={{opacity:fi(f,200,20),transform:`translateY(${su(f,200,20)}px)`}}>
          {Body('지식 자동화 투자 여정, 함께하실 분들을 기다립니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 7단계 추가: 커뮤니티 마무리 (S32 신규)
// ══════════════════════════════════════════════════════

const S_Community: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Wrap no={32} accent={C.mint} label="마무리">
      <Ctr gap={36}>
        <div style={{opacity:fi(f,8),transform:`translateY(${spry(f,8,24,50)}px)`}}>
          {Lbl('잠깐 여담',C.mint)}
          {Title(<>다른 커뮤니티에서도<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>함께 공부하고 있어요</span></>)}
        </div>
        <div style={{
          opacity:spr(f,55,26),
          transform:`scale(${spr(f,55,26)})`,
          backgroundColor:`${C.mint}10`,border:`1px solid ${C.mint}44`,
          borderRadius:22,padding:'34px 68px',
          boxShadow:`0 0 ${osc(f,.04,14,8)}px ${C.mint}22`,
        }}>
          {Body('알고 계신 분들은',C.dim,{marginBottom:8})}
          {Sub('반갑게 인사해 주세요!',C.mint,{marginBottom:0})}
        </div>
        <div style={{
          opacity:fi(f,148,32),
          transform:`translateY(${su(f,148,32)}px)`,
          filter:Glow(C.mint),
        }}>
          {TitleXL('감사합니다',C.mint,{letterSpacing:'-2px'})}
        </div>
      </Ctr>
    </Wrap>
  );
};

// ══════════════════════════════════════════════════════
// 오프닝 훅 — 5초 하이라이트 예고 (HOOK_DUR=150)
// ══════════════════════════════════════════════════════

const S_Hook: React.FC = () => {
  const f = useCurrentFrame();
  const fadeOut = interpolate(f,[132,150],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const teasers = [
    {text:'AI가 절대 읽지 못하는 시장의 패닉과 광기', frame:42},
    {text:'20년 경력으로 완성한 나만의 자동화 투자법', frame:63},
    {text:'LLM 위키 시스템 — 이 영상에서 최초 공개',   frame:84},
  ];
  return (
    <AbsoluteFill style={{backgroundColor:C.bg,fontFamily:FONT.main,opacity:fadeOut}}>
      <Particles f={f} color={C.mint}/>
      <GlowBg f={f} color={C.mint}/>
      <div style={{position:'absolute',top:0,left:0,right:0,height:6,backgroundColor:C.mint}}/>
      <div style={{position:'absolute',top:0,left:`${(f*.7)%120-15}%`,width:'6%',height:6,
        background:`linear-gradient(90deg,transparent,${C.mint}CC,transparent)`,opacity:.8}}/>
      <div style={{position:'absolute',bottom:24,left:0,right:0,textAlign:'center',color:C.dim,fontFamily:FONT.mono,fontSize:16,opacity:.5}}>
        로또의 주식 — AI 지식 자동화 시스템
      </div>
      <Ctr gap={22}>
        <div style={{opacity:fi(f,5,14),transform:`translateY(${spry(f,5,16,30)}px)`}}>
          {Lbl('이 영상에서 공개합니다',C.mint)}
        </div>
        <div style={{opacity:spr(f,12,24),transform:`scale(${spr(f,12,24)})`}}>
          {TitleXL(<>나만의 투자 시스템을<br/><span style={{color:C.mint,filter:Glow(C.mint)}}>AI로 완성하는 법</span></>)}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:14,marginTop:8}}>
          {teasers.map(({text,frame},i)=>(
            <div key={i} style={{
              opacity:spr(f,frame,18),
              transform:`translateX(${interpolate(spr(f,frame,18),[0,1],[-40,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
              display:'flex',alignItems:'center',gap:18,
              backgroundColor:`${C.mint}0C`,border:`1px solid ${C.mint}33`,
              borderRadius:12,padding:'12px 28px',
            }}>
              <div style={{color:C.mint,fontFamily:FONT.mono,fontWeight:700,fontSize:20,flexShrink:0}}>
                {String(i+1).padStart(2,'0')}
              </div>
              {Body(text,C.white)}
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,110,18),transform:`scale(${osc(f,.06,1,.025)})`,filter:Glow(C.mint)}}>
          {Sub('끝까지 보시면 달라집니다',C.mint,{marginBottom:0})}
        </div>
      </Ctr>
    </AbsoluteFill>
  );
};

// ─── 메인 컴포지션 ────────────────────────────────────
const SCENES = [S01,S02,S03,S04,S05,S06,S07,S08,S09,S10,S11,S12,S13,S14,S15,S16,S17,S18,S19,S_Teaser,S20,S21,S22,S23,S24,S_LLMWiki,S25,S_AILimit,S_HumanInsight,S26,S27,S_ServiceCTA,S28,S_Community];

export const LongformComposition:React.FC = () => (
  <AbsoluteFill style={{backgroundColor:C.bg}}>
    <Sequence from={0} durationInFrames={HOOK_DUR}>
      <S_Hook/>
    </Sequence>
    {SCENES.map((SceneComp,i)=>(
      <Sequence key={i} from={HOOK_DUR+i*SDUR} durationInFrames={SDUR}>
        <SceneComp/>
      </Sequence>
    ))}
  </AbsoluteFill>
);
