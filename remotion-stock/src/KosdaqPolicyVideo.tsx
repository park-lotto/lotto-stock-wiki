import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from 'remotion';
import { FONT } from './theme';

const C = {
  bg:'#0F112A', white:'#FFFFFF', mint:'#00FFD4', orange:'#FFC000',
  bull:'#FF4336', dim:'rgba(255,255,255,0.45)', card:'rgba(255,255,255,0.07)',
  blue:'#4B8AFF',
};
const SDUR = 360;
const TOTAL = 28;

const fi = (f:number,s:number,d=20) =>
  interpolate(f,[s,s+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
const su = (f:number,s:number,d=20,dist=30) =>
  interpolate(f,[s,s+d],[dist,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
const countUp = (f:number,s:number,end:number,d=70) =>
  Math.floor(interpolate(f,[s,s+d],[0,end],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}));
const Glow = (color:string) => `drop-shadow(0 0 12px ${color}88)`;

const Particles:React.FC<{f:number;color?:string}> = ({f,color=C.mint}) => (
  <div style={{position:'absolute',inset:0,pointerEvents:'none',overflow:'hidden'}}>
    {Array.from({length:18},(_,i)=>(
      <div key={i} style={{
        position:'absolute',left:`${(i*13+7)%100}%`,
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
      {label&&<div style={{position:'absolute',top:28,left:60,color:accent,fontFamily:FONT.mono,
        fontSize:17,letterSpacing:4,fontWeight:600,opacity:fi(f,3)}}>{label}</div>}
      <div style={{position:'absolute',top:28,right:60,color:accent,fontFamily:FONT.mono,
        fontSize:17,opacity:.5}}>{String(no).padStart(2,'0')} / {TOTAL}</div>
      <div style={{position:'absolute',bottom:24,left:0,right:0,textAlign:'center',
        color:C.dim,fontFamily:FONT.mono,fontSize:16,opacity:.5}}>로또의 주식 — 코스닥 대변혁</div>
      {children}
    </AbsoluteFill>
  );
};

const Ctr:React.FC<{children:React.ReactNode;gap?:number;maxW?:number}> = ({children,gap=28,maxW=940}) => (
  <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',
    alignItems:'center',textAlign:'center',padding:'90px 140px',gap}}>
    <div style={{maxWidth:maxW,width:'100%'}}>{children}</div>
  </AbsoluteFill>
);

const TitleXL = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:80,fontWeight:900,lineHeight:1.1,letterSpacing:'-2px',marginBottom:18,...ex}}>{txt}</div>
);
const Title = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:64,fontWeight:800,lineHeight:1.18,letterSpacing:'-1px',marginBottom:18,...ex}}>{txt}</div>
);
const Sub = (txt:React.ReactNode,color=C.mint,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:42,fontWeight:700,lineHeight:1.3,marginBottom:14,...ex}}>{txt}</div>
);
const Body = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:28,fontWeight:500,lineHeight:1.65,...ex}}>{txt}</div>
);
const Lbl = (txt:React.ReactNode,color=C.dim) => (
  <div style={{color,fontSize:18,fontWeight:600,letterSpacing:3,marginBottom:12}}>{txt}</div>
);

// ── 파이차트 (conic-gradient 도넛) ────────────────────
const PieChart:React.FC<{f:number;appear:number;kosdaqPct:number;label?:string}> = ({f,appear,kosdaqPct,label}) => {
  const prog=Math.min(1,Math.max(0,(f-appear)/80));
  const kPct=prog*kosdaqPct;
  const kospiDeg=(1-kPct/100)*360;
  const hasK=kPct>0.2;
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:14}}>
      <div style={{
        width:250,height:250,borderRadius:'50%',position:'relative',
        background:hasK
          ?`conic-gradient(${C.blue} 0deg ${kospiDeg}deg, ${C.mint} ${kospiDeg}deg 360deg)`
          :C.blue,
        boxShadow:hasK?`0 0 40px ${C.mint}44`:'none',
      }}>
        <div style={{
          position:'absolute',inset:'22%',borderRadius:'50%',backgroundColor:C.bg,
          display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',
        }}>
          {hasK&&<>
            <div style={{color:C.mint,fontSize:26,fontWeight:900,fontFamily:FONT.mono,filter:Glow(C.mint)}}>{kPct.toFixed(1)}%</div>
            <div style={{color:C.dim,fontSize:13}}>코스닥</div>
          </>}
          {!hasK&&<div style={{color:C.white,fontSize:22,fontWeight:700,fontFamily:FONT.mono}}>100%</div>}
        </div>
      </div>
      {label&&<div style={{color:C.dim,fontSize:17,fontFamily:FONT.mono}}>{label}</div>}
    </div>
  );
};

// ── 수평 바 차트 ──────────────────────────────────────
const HBar:React.FC<{f:number;appear:number;value:number;maxVal:number;label:string;color:string;suffix?:string;decimals?:number}> = ({f,appear,value,maxVal,label,color,suffix='%',decimals=1}) => {
  const prog=Math.min(1,Math.max(0,(f-appear)/80));
  return (
    <div style={{marginBottom:16}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
        <div style={{color:C.dim,fontSize:18}}>{label}</div>
        <div style={{color,fontSize:18,fontFamily:FONT.mono,fontWeight:700}}>{(value*prog).toFixed(decimals)}{suffix}</div>
      </div>
      <div style={{background:'rgba(255,255,255,0.08)',borderRadius:6,height:16,overflow:'hidden'}}>
        <div style={{width:`${(value/maxVal)*100*prog}%`,height:'100%',background:color,borderRadius:6,boxShadow:`0 0 8px ${color}66`}}/>
      </div>
    </div>
  );
};

// ── 머니 플로우 파티클 다이어그램 ─────────────────────
const MoneyFlow:React.FC<{f:number;appear:number}> = ({f,appear}) => {
  const prog=Math.min(1,Math.max(0,(f-appear)/30));
  const pts=Array.from({length:14},(_,i)=>{
    const phase=((f*0.55+i*20)%260)/260;
    return {x:248+phase*320,y:155+Math.sin(phase*Math.PI*4+i)*16,op:phase<0.12?phase/.12:phase>.88?(1-phase)/.12:.85};
  });
  return (
    <svg width={860} height={290} viewBox="0 0 860 290" style={{overflow:'visible',opacity:prog}}>
      <rect x={8} y={95} width={232} height={120} rx={14} fill="rgba(75,138,255,0.15)" stroke={C.blue} strokeWidth={2}/>
      <text x={124} y={148} fill={C.white} fontSize={22} fontWeight={700} textAnchor="middle" fontFamily={FONT.main}>연기금 67개</text>
      <text x={124} y={176} fill={C.blue} fontSize={22} fontFamily={FONT.mono} textAnchor="middle" fontWeight={700}>1,400조원</text>
      <line x1={242} y1={155} x2={574} y2={155} stroke="rgba(0,255,212,0.2)" strokeWidth={2} strokeDasharray="8 4"/>
      <text x={408} y={128} fill={C.mint} fontSize={17} fontWeight={700} textAnchor="middle" fontFamily={FONT.mono}
        opacity={Math.min(1,(f-appear-50)/20)}>≈ 16.5조원 유입 예상</text>
      {pts.map((p,i)=>(
        <circle key={i} cx={p.x} cy={p.y} r={5.5} fill={C.mint} opacity={p.op}
          style={{filter:`drop-shadow(0 0 4px ${C.mint})`}}/>
      ))}
      <polygon points="574,143 608,155 574,167" fill={C.mint}
        opacity={Math.min(1,(f-appear)/20)} style={{filter:Glow(C.mint)}}/>
      <rect x={614} y={95} width={238} height={120} rx={14} fill={`${C.mint}10`} stroke={C.mint} strokeWidth={2}
        style={{filter:`drop-shadow(0 0 8px ${C.mint}33)`}}/>
      <text x={733} y={148} fill={C.white} fontSize={22} fontWeight={700} textAnchor="middle" fontFamily={FONT.main}>코스닥 시장</text>
      <text x={733} y={176} fill={C.mint} fontSize={20} fontFamily={FONT.mono} textAnchor="middle">코스닥150</text>
    </svg>
  );
};

// ── 섹터 히트맵 ────────────────────────────────────────
const SECTORS=[
  {name:'바이오·제약',pct:40,color:C.mint,hot:true},
  {name:'AI반도체',pct:18,color:'#A78BFA',hot:true},
  {name:'소프트웨어',pct:12,color:C.orange,hot:false},
  {name:'게임·엔터',pct:8,color:'#F59E0B',hot:false},
  {name:'에너지·소재',pct:7,color:'#6B7280',hot:false},
  {name:'기타',pct:15,color:'#374151',hot:false},
];
const SectorHeatmap:React.FC<{f:number;appear:number}> = ({f,appear}) => {
  const glow=0.6+Math.sin(f*0.08)*0.3;
  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:14}}>
      {SECTORS.map((s,i)=>(
        <div key={i} style={{
          opacity:fi(f,appear+i*18,18),
          transform:`scale(${1+(1-Math.min(1,(f-appear-i*18)/18))*.08})`,
          background:s.hot?`${s.color}18`:'rgba(255,255,255,0.04)',
          border:`${s.hot?2:1}px solid ${s.hot?s.color:'rgba(255,255,255,0.1)'}`,
          borderRadius:12,padding:'20px 24px',textAlign:'center',
          boxShadow:s.hot?`0 0 ${20*glow}px ${s.color}44`:'none',
        }}>
          <div style={{color:s.hot?s.color:C.dim,fontSize:19,fontWeight:700,marginBottom:8}}>{s.name}</div>
          <div style={{color:s.hot?s.color:'rgba(255,255,255,0.5)',fontSize:32,fontWeight:900,fontFamily:FONT.mono,
            filter:s.hot?`drop-shadow(0 0 6px ${s.color})`:'none'}}>{s.pct}%</div>
          {s.hot&&<div style={{color:s.color,fontSize:14,marginTop:4,opacity:.7}}>직접 수혜</div>}
        </div>
      ))}
    </div>
  );
};

// ══════════════════════════════════════════════════════
// SCENES
// ══════════════════════════════════════════════════════

const S01:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.7+Math.sin(f*0.09)*0.25;
  const num=countUp(f,30,499,60);
  return (
    <Wrap no={1} accent={C.bull} label="코스닥 대변혁">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8,20),transform:`translateY(${su(f,8,20)}px)`}}>
          {Lbl('2026년 5월 22일 오늘',C.bull)}
          {Body('코스닥 시장에 사이드카가 발동됐습니다',C.dim)}
        </div>
        <div style={{opacity:fi(f,28,30),transform:`scale(${0.6+Math.min(1,(f-28)/30)*.4})`}}>
          <div style={{
            color:C.bull,fontSize:144,fontWeight:900,lineHeight:1,fontFamily:FONT.mono,
            filter:`drop-shadow(0 0 ${28*glow}px ${C.bull}) drop-shadow(0 0 ${60*glow}px ${C.bull}88)`,
          }}>+{Math.floor(num/100)}.{String(num%100).padStart(2,'0')}%</div>
        </div>
        <div style={{opacity:fi(f,120,24),transform:`translateY(${su(f,120,24)}px)`}}>
          {Sub('사이드카 발동',C.bull)}
          {Body('프로그램 매수 5분 일시 정지',C.dim)}
        </div>
        <div style={{opacity:fi(f,220,20)}}>
          {Body(<>무슨 일이 일어난 걸까요<br/><span style={{color:C.bull,fontWeight:700}}>구조를 알면 흐름이 보입니다</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S02:React.FC = () => {
  const f=useCurrentFrame();
  const hrs=countUp(f,60,4,40);
  const min=countUp(f,100,30,40);
  return (
    <Wrap no={2} accent={C.orange} label="국민성장펀드">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('2026.05.22 오전')}
          {Title(<>국민성장펀드<br/><span style={{color:C.orange}}>완판</span></>)}
        </div>
        <div style={{display:'flex',gap:32,justifyContent:'center',alignItems:'center',opacity:fi(f,56,20)}}>
          <div style={{textAlign:'center'}}>
            <div style={{color:C.orange,fontSize:80,fontWeight:900,fontFamily:FONT.mono,filter:Glow(C.orange),lineHeight:1}}>{hrs}</div>
            <div style={{color:C.dim,fontSize:20,marginTop:6}}>시간</div>
          </div>
          <div style={{color:C.dim,fontSize:60,fontWeight:300}}>:</div>
          <div style={{textAlign:'center'}}>
            <div style={{color:C.orange,fontSize:80,fontWeight:900,fontFamily:FONT.mono,filter:Glow(C.orange),lineHeight:1}}>{String(min).padStart(2,'0')}</div>
            <div style={{color:C.dim,fontSize:20,marginTop:6}}>분</div>
          </div>
        </div>
        <div style={{opacity:fi(f,160,20)}}>
          <div style={{background:'rgba(255,192,0,0.1)',border:'1px solid rgba(255,192,0,0.3)',borderRadius:12,padding:'20px 32px'}}>
            {Body(<>5대 은행 물량 <span style={{color:C.orange,fontWeight:800}}>전량 완판</span></>)}
            {Body(<>국민 6,000억 + 재정 1,200억 = <span style={{color:C.orange}}>7,200억원</span></>,C.dim)}
          </div>
        </div>
        <div style={{opacity:fi(f,270,20)}}>{Body(<>코스닥 오픈런의 <span style={{color:C.orange,fontWeight:700}}>진짜 이유</span>가 있습니다</>)}</div>
      </Ctr>
    </Wrap>
  );
};

const S03:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.6+Math.sin(f*0.09)*0.3;
  return (
    <Wrap no={3} accent={C.mint} label="코스닥 대변혁">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,10,24),transform:`scale(${0.78+Math.min(1,(f-10)/24)*.22})`}}>
          <div style={{color:C.mint,fontSize:100,fontWeight:900,lineHeight:1.1,letterSpacing:'-2px',
            filter:`drop-shadow(0 0 ${20*glow}px ${C.mint})`}}>왜<br/>이렇게<br/>뜨거울까?</div>
        </div>
        <div style={{opacity:fi(f,140,22)}}>
          {Body('감으로 들어간 게 아닙니다')}
          {Body(<>정부가 <span style={{color:C.mint,fontWeight:700}}>1,400조원의 물길</span>을 바꿨습니다</>,C.dim)}
        </div>
        <div style={{opacity:fi(f,240,20)}}>{Body('구조를 알면 다음 흐름이 보입니다',C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S04:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={4} accent={C.blue} label="벤치마크 Before">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('기존 연기금 벤치마크')}
          {Title(<>코스피만 <span style={{color:C.blue}}>100%</span></>)}
        </div>
        <div style={{opacity:fi(f,50,20),display:'flex',justifyContent:'center',alignItems:'center',gap:52}}>
          <PieChart f={f} appear={54} kosdaqPct={0} label="기존 벤치마크"/>
          <div style={{textAlign:'left'}}>
            <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:16,opacity:fi(f,70,18)}}>
              <div style={{width:20,height:20,borderRadius:4,background:C.blue}}/>
              <div style={{color:C.white,fontSize:22}}>코스피 <span style={{color:C.blue,fontFamily:FONT.mono,fontWeight:700}}>100%</span></div>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:12,opacity:fi(f,90,18)}}>
              <div style={{width:20,height:20,borderRadius:4,background:'rgba(255,255,255,0.15)'}}/>
              <div style={{color:C.dim,fontSize:22}}>코스닥 <span style={{fontFamily:FONT.mono}}>0%</span></div>
            </div>
          </div>
        </div>
        <div style={{opacity:fi(f,200,20)}}>
          {Body('코스닥에 투자할 유인이 없었습니다',C.dim)}
          {Body('벤치마크에 없으니까요',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S05:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={5} accent={C.mint} label="벤치마크 After">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('2026.01.29 기획재정부 개정 후')}
          {Title(<>코스닥이 <span style={{color:C.mint}}>5% 들어왔다</span></>)}
        </div>
        <div style={{opacity:fi(f,50,20),display:'flex',justifyContent:'center',alignItems:'center',gap:52}}>
          <PieChart f={f} appear={54} kosdaqPct={5} label="새 벤치마크"/>
          <div style={{textAlign:'left'}}>
            <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:16,opacity:fi(f,70,18)}}>
              <div style={{width:20,height:20,borderRadius:4,background:C.blue}}/>
              <div style={{color:C.white,fontSize:22}}>코스피 <span style={{color:C.blue,fontFamily:FONT.mono,fontWeight:700}}>95%</span></div>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:12,opacity:fi(f,90,18)}}>
              <div style={{width:20,height:20,borderRadius:4,background:C.mint,boxShadow:`0 0 8px ${C.mint}`}}/>
              <div style={{color:C.mint,fontSize:22}}>코스닥150 <span style={{fontFamily:FONT.mono,fontWeight:700}}>5%</span></div>
            </div>
          </div>
        </div>
        <div style={{opacity:fi(f,200,20)}}>
          {Body(<><span style={{color:C.mint,fontWeight:700}}>사상 최초</span>로 코스닥이 벤치마크에 포함됐습니다</>)}
          {Body('이제 연기금은 코스닥을 사야 좋은 평가를 받습니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S06:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.6+Math.sin(f*0.07)*0.3;
  return (
    <Wrap no={6} accent={C.mint} label="코스닥 대변혁">
      <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',textAlign:'center',padding:'80px 120px'}}>
        <div style={{position:'absolute',inset:0,background:`radial-gradient(ellipse at 50% 50%, ${C.mint}${Math.floor(glow*26).toString(16).padStart(2,'0')} 0%, transparent 55%)`,opacity:fi(f,16,40)}}/>
        <div style={{opacity:fi(f,12,30),transform:`scale(${0.72+Math.min(1,(f-12)/30)*.28})`}}>
          <div style={{color:C.mint,fontSize:90,fontWeight:900,lineHeight:1.15,letterSpacing:'-2px',
            filter:`drop-shadow(0 0 ${22*glow}px ${C.mint}) drop-shadow(0 0 ${55*glow}px ${C.mint}88)`}}>
            1,400조의<br/>물길이<br/>바뀐다
          </div>
        </div>
        <div style={{opacity:fi(f,160,22),marginTop:24}}>
          {Body('67개 연기금이 움직이기 시작했습니다')}
          {Body(<>코스닥 비중 <span style={{color:C.mint}}>3.7%</span> → 하반기 <span style={{color:C.mint,fontWeight:700}}>5%+</span> 확대</>,C.dim)}
        </div>
      </AbsoluteFill>
    </Wrap>
  );
};

const S07:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={7} accent={C.mint} label="머니 플로우">
      <Ctr gap={24} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('자금 흐름')}
          {Title(<>코스닥으로 <span style={{color:C.mint}}>흘러간다</span></>)}
        </div>
        <div style={{opacity:fi(f,40,16)}}><MoneyFlow f={f} appear={44}/></div>
        <div style={{opacity:fi(f,240,20)}}>{Body('팔 사람 없는 빈집에 신규 수급이 유입',C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S08:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={8} accent={C.orange} label="비중 변화">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('연기금 코스닥 비중')}
          {Title(<>지금까지 겨우 <span style={{color:C.bull}}>3.7%</span></>)}
        </div>
        <div style={{opacity:fi(f,56,18),maxWidth:700,margin:'0 auto',width:'100%'}}>
          <HBar f={f} appear={60} value={3.7} maxVal={10} label="현재 코스닥 비중 (2024년)" color={C.bull}/>
          <HBar f={f} appear={110} value={5.0} maxVal={10} label="벤치마크 목표" color={C.mint}/>
          <HBar f={f} appear={160} value={7.5} maxVal={10} label="시장 예상 (하반기 집행 후)" color={C.orange}/>
        </div>
        <div style={{opacity:fi(f,260,20)}}>
          {Body(<>하반기 집행 시 <span style={{color:C.orange,fontWeight:700}}>최대 16.5조원</span> 유입 예상</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S09:React.FC = () => {
  const f=useCurrentFrame();
  const v=countUp(f,60,165,80);
  return (
    <Wrap no={9} accent={C.mint} label="유입 예상 자금">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('실제 유입 예상 자금')}
          {Title(<>1,400조가 아니라<br/><span style={{color:C.mint}}>그래도 16.5조</span></>)}
        </div>
        <div style={{opacity:fi(f,56,24),transform:`scale(${1+(1-Math.min(1,(f-56)/24))*.18})`}}>
          <div style={{color:C.mint,fontSize:120,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,filter:Glow(C.mint)}}>
            {(v/10).toFixed(1)}조
          </div>
        </div>
        <div style={{opacity:fi(f,180,20)}}>
          <div style={{background:`${C.mint}0E`,border:`1px solid ${C.mint}33`,borderRadius:12,padding:'18px 28px'}}>
            {Body('국민연금 제외 — 단, 가점 확대는 적용')}
            {Body('대형·중소형 연기금 기준 추정치',C.dim)}
          </div>
        </div>
        <div style={{opacity:fi(f,280,18)}}>{Body(<>코스닥 하루 거래대금 대비 <span style={{color:C.mint,fontWeight:700}}>수개월치 수급</span></>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S10:React.FC = () => {
  const f=useCurrentFrame();
  const STEPS=[
    {date:'2026.01.29',event:'기획재정부\n벤치마크 개편 의결',color:C.blue},
    {date:'2026 2Q',event:'연기금 코스닥150\n편입 시작',color:C.orange},
    {date:'2026 하반기',event:'대규모 자금\n집행 본격화',color:C.mint},
  ];
  const W=900;
  return (
    <Wrap no={10} accent={C.blue} label="정책 타임라인">
      <Ctr gap={28} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('정책 집행 타임라인')}
          {Title(<>상반기 준비 → <span style={{color:C.mint}}>하반기 집행</span></>)}
        </div>
        <div style={{opacity:fi(f,44,16)}}>
          <svg width={W} height={200} viewBox={`0 0 ${W} 200`} style={{overflow:'visible'}}>
            <line x1={60} y1={100} x2={W-60} y2={100} stroke="rgba(255,255,255,0.15)" strokeWidth={2}/>
            {STEPS.map((s,i)=>{
              const x=60+(W-120)*(i/2);
              const app=60+i*55;
              const op=fi(f,app,20);
              return (
                <g key={i} opacity={op}>
                  <circle cx={x} cy={100} r={13} fill={s.color} style={{filter:Glow(s.color)}}/>
                  <text x={x} y={62} fill={s.color} fontSize={16} fontFamily={FONT.mono} textAnchor="middle">{s.date}</text>
                  {s.event.split('\n').map((line,li)=>(
                    <text key={li} x={x} y={138+li*20} fill={C.white} fontSize={17} fontFamily={FONT.main} textAnchor="middle" fontWeight={600}>{line}</text>
                  ))}
                </g>
              );
            })}
          </svg>
        </div>
        <div style={{opacity:fi(f,250,20)}}>{Body(<>상반기 준비 → <span style={{color:C.mint,fontWeight:700}}>하반기 집중 집행</span> 예정</>)}</div>
      </Ctr>
    </Wrap>
  );
};

const S11:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={11} accent={C.orange} label="국민연금 예외">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('알아야 할 세부 사항')}
          {Title(<>국민연금은 <span style={{color:C.bull}}>제외</span>됩니다</>)}
        </div>
        <div style={{display:'flex',gap:24,justifyContent:'center'}}>
          {[
            {icon:'❌',label:'벤치마크 변경 제외',desc:'국민연금 초대형\n별도 기준 적용',color:C.bull},
            {icon:'✅',label:'가점 확대 적용',desc:'벤처투자 가점\n1점 → 2점',color:C.mint},
          ].map((item,i)=>(
            <div key={i} style={{
              opacity:fi(f,70+i*40,20),
              background:`${item.color}0E`,border:`1px solid ${item.color}44`,
              borderRadius:16,padding:'24px 32px',textAlign:'center',minWidth:280,
            }}>
              <div style={{fontSize:44,marginBottom:10}}>{item.icon}</div>
              <div style={{color:item.color,fontSize:21,fontWeight:700,marginBottom:8}}>{item.label}</div>
              <div style={{color:C.dim,fontSize:17,whiteSpace:'pre-line'}}>{item.desc}</div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,220,20)}}>
          {Body(<>실제 코스닥 유입 = <span style={{color:C.orange}}>16.5조원</span> 수준<br/>1,400조 전체 아님을 인지하세요</>,C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S12:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={12} accent={C.orange} label="혁신성장 가점">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('기금운용 평가 가점')}
          {Title(<>혁신성장 투자 가점<br/><span style={{color:C.orange}}>두 배 상향</span></>)}
        </div>
        <div style={{display:'flex',gap:40,justifyContent:'center',alignItems:'center',opacity:fi(f,68,20)}}>
          <div style={{opacity:fi(f,72,18),textAlign:'center'}}>
            <div style={{color:'rgba(255,255,255,0.4)',fontSize:86,fontWeight:900,fontFamily:FONT.mono,lineHeight:1}}>1점</div>
            <div style={{color:C.dim,fontSize:20,marginTop:8}}>기존</div>
          </div>
          <div style={{opacity:fi(f,100,18),color:C.orange,fontSize:60,fontWeight:900}}>→</div>
          <div style={{opacity:fi(f,120,18),textAlign:'center'}}>
            <div style={{color:C.orange,fontSize:86,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,filter:Glow(C.orange)}}>2점</div>
            <div style={{color:C.orange,fontSize:20,marginTop:8}}>개정 후</div>
          </div>
        </div>
        <div style={{opacity:fi(f,220,20)}}>
          {Body('국민성장펀드·벤처투자에 참여할수록')}
          {Body(<>기금평가 <span style={{color:C.orange,fontWeight:700}}>좋은 점수</span>를 받는 구조입니다</>,C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S13:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={13} accent={C.orange} label="국민성장펀드 구조">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('국민성장펀드 구조')}
          {Title(<>총 <span style={{color:C.orange}}>7,200억원</span> 조성</>)}
        </div>
        <div style={{opacity:fi(f,60,20),maxWidth:700,margin:'0 auto',width:'100%'}}>
          {[
            {label:'국민 모집',value:6000,total:7200,color:C.orange},
            {label:'정부 재정',value:1200,total:7200,color:C.blue},
          ].map((item,i)=>(
            <div key={i} style={{opacity:fi(f,65+i*40,18),marginBottom:18}}>
              <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                <div style={{color:C.dim,fontSize:18}}>{item.label}</div>
                <div style={{color:item.color,fontSize:20,fontWeight:700,fontFamily:FONT.mono}}>
                  {item.value.toLocaleString()}억원 ({Math.round(item.value/item.total*100)}%)
                </div>
              </div>
              <div style={{background:'rgba(255,255,255,0.08)',borderRadius:6,height:18,overflow:'hidden'}}>
                <div style={{
                  width:`${Math.min(1,(f-65-i*40)/80)*item.value/item.total*100}%`,
                  height:'100%',background:item.color,borderRadius:6,boxShadow:`0 0 8px ${item.color}66`,
                }}/>
              </div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,220,20)}}>
          <div style={{background:'rgba(255,192,0,0.08)',border:'1px solid rgba(255,192,0,0.3)',borderRadius:12,padding:'16px 28px'}}>
            {Body(<>5년간 총 <span style={{color:C.orange,fontWeight:700}}>150조원</span> 규모 정책펀드<br/><span style={{color:C.dim,fontSize:22}}>2026년 30조원 집행 계획</span></>)}
          </div>
        </div>
      </Ctr>
    </Wrap>
  );
};

const S14:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={14} accent={C.mint} label="코스닥 의무 비중">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('국민성장펀드 투자 의무')}
          {Title(<>코스닥을 <span style={{color:C.mint}}>반드시</span> 사야 합니다</>)}
        </div>
        <div style={{display:'flex',gap:40,justifyContent:'center',alignItems:'center'}}>
          <div style={{opacity:fi(f,60,20)}}><PieChart f={f} appear={64} kosdaqPct={30} label="자펀드 의무 비중"/></div>
          <div style={{textAlign:'left'}}>
            {[
              {label:'비상장 신규투자',val:'최소 10%',c:C.dim},
              {label:'코스닥 기술특례상장사',val:'최소 10%',c:C.mint},
              {label:'기타 코스닥',val:'10%+',c:C.orange},
              {label:'코스피',val:'10% 이내 제한',c:C.bull},
            ].map((item,i)=>(
              <div key={i} style={{
                opacity:fi(f,100+i*22,18),
                display:'flex',justifyContent:'space-between',gap:24,
                padding:'10px 0',borderBottom:'1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{color:C.dim,fontSize:17}}>{item.label}</div>
                <div style={{color:item.c,fontSize:17,fontWeight:700}}>{item.val}</div>
              </div>
            ))}
          </div>
        </div>
      </Ctr>
    </Wrap>
  );
};

const S15:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={15} accent={C.bull} label="코스피 제한">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('핵심 포인트')}
          {Title(<>코스피 투자는<br/><span style={{color:C.bull}}>10% 이내</span>로 제한</>)}
        </div>
        <div style={{opacity:fi(f,80,22)}}>
          <div style={{background:'rgba(255,67,54,0.12)',border:`2px solid ${C.bull}66`,borderRadius:16,padding:'28px 40px'}}>
            <div style={{color:C.bull,fontSize:40,fontWeight:900,marginBottom:12,filter:Glow(C.bull)}}>코스피 ≤ 10%</div>
            {Body('삼성전자·현대차 같은 대형주는 최소화')}
            {Body(<><span style={{color:C.mint,fontWeight:700}}>코스닥 바이오·기술주</span>에 집중 배분</>,C.dim)}
          </div>
        </div>
        <div style={{opacity:fi(f,230,20)}}>{Body('이게 바로 코스닥이 뜨거운 진짜 이유입니다',C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S16:React.FC = () => {
  const f=useCurrentFrame();
  const ITEMS=[
    {name:'차세대 바이오·백신',icon:'🧬',color:C.mint},
    {name:'소버린 AI',icon:'🤖',color:'#A78BFA'},
    {name:'OLED 디스플레이',icon:'📺',color:C.orange},
    {name:'새만금·인프라',icon:'🏗️',color:C.blue},
    {name:'첨단 소재',icon:'⚗️',color:'#F59E0B'},
    {name:'미래 모빌리티',icon:'🚀',color:'#EC4899'},
  ];
  return (
    <Wrap no={16} accent={C.orange} label="2차 메가프로젝트">
      <Ctr gap={24} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('2차 메가프로젝트 (2026.04.14)')}
          {Title(<>총 <span style={{color:C.orange}}>10조원</span> — 6개 산업군</>)}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:14}}>
          {ITEMS.map((s,i)=>(
            <div key={i} style={{
              opacity:fi(f,60+i*22,18),
              transform:`scale(${1+(1-Math.min(1,(f-60-i*22)/18))*.08})`,
              background:`${s.color}10`,border:`1px solid ${s.color}44`,
              borderRadius:12,padding:'18px 20px',textAlign:'center',
            }}>
              <div style={{fontSize:32,marginBottom:8}}>{s.icon}</div>
              <div style={{color:s.color,fontSize:18,fontWeight:700}}>{s.name}</div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,260,20)}}>{Body(<>코스닥 시총 비중이 높은 섹터에 <span style={{color:C.orange,fontWeight:700}}>직접 자금 배분</span></>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S17:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={17} accent={C.mint} label="FDA 임상 펀드">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('복지부 주도 특화 펀드 (2026.04)')}
          {Title(<>FDA 임상 3상<br/><span style={{color:C.mint}}>전용 펀드</span> 조성</>)}
        </div>
        <div style={{opacity:fi(f,70,24),transform:`scale(${1+(1-Math.min(1,(f-70)/24))*.16})`}}>
          <div style={{color:C.mint,fontSize:100,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,filter:Glow(C.mint)}}>1,500억</div>
          <div style={{color:C.dim,fontSize:22,marginTop:8}}>정부 예산 600억원 직접 투입</div>
        </div>
        <div style={{opacity:fi(f,180,20)}}>
          {['FDA 임상3상 추진 기업 직접 투자','2030년까지 FDA 승인 사례 창출','K-바이오 글로벌화 직접 지원'].map((item,i)=>(
            <div key={i} style={{opacity:fi(f,185+i*28,18),display:'flex',alignItems:'center',gap:12,color:C.white,fontSize:22,marginBottom:10}}>
              <span style={{color:C.mint}}>✓</span>{item}
            </div>
          ))}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S18:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={18} accent={C.mint} label="코스닥 섹터 구성">
      <Ctr gap={24} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('코스닥150 업종별 비중')}
          {Title(<>바이오가 <span style={{color:C.mint}}>40%</span>를 차지합니다</>)}
        </div>
        <SectorHeatmap f={f} appear={60}/>
        <div style={{opacity:fi(f,270,20)}}>{Body(<>코스닥 시총 상위 10개사 중 <span style={{color:C.mint,fontWeight:700}}>7개가 제약·바이오</span></>)}</div>
      </Ctr>
    </Wrap>
  );
};

const S19:React.FC = () => {
  const f=useCurrentFrame();
  const v=countUp(f,60,21,80);
  return (
    <Wrap no={19} accent={C.mint} label="K-바이오 기술이전">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('2025년 K-바이오 기술이전 규모')}
          {Title(<>사상 최고치를<br/><span style={{color:C.mint}}>경신했습니다</span></>)}
        </div>
        <div style={{opacity:fi(f,56,24),transform:`scale(${1+(1-Math.min(1,(f-56)/24))*.18})`}}>
          <div style={{color:C.mint,fontSize:110,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,filter:Glow(C.mint)}}>{v}조원</div>
          <div style={{color:C.dim,fontSize:22,marginTop:8}}>155억 달러 (글로벌 기술이전)</div>
        </div>
        <div style={{opacity:fi(f,180,20)}}>
          <div style={{background:`${C.mint}0E`,border:`1px solid ${C.mint}33`,borderRadius:12,padding:'18px 28px'}}>
            {Body(<>바이오·제약 3개월 등락률<br/><span style={{color:C.mint,fontWeight:700}}>+31.88%</span> — 코스닥 최강 업종 모멘텀</>)}
          </div>
        </div>
      </Ctr>
    </Wrap>
  );
};

const S20:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={20} accent={'#A78BFA'} label="소버린 AI">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('2차 메가프로젝트 주목 섹터')}
          {Title(<>소버린 AI —<br/><span style={{color:'#A78BFA'}}>두 번째 수혜</span></>)}
        </div>
        <div style={{opacity:fi(f,70,22)}}>
          <div style={{background:'rgba(167,139,250,0.1)',border:'1px solid rgba(167,139,250,0.3)',borderRadius:16,padding:'28px 40px'}}>
            {Body(<><span style={{color:'#A78BFA',fontWeight:700}}>국가 주도 AI 인프라</span> 구축</>)}
            {Body('AI 반도체 · 데이터센터 · 소프트웨어',C.dim)}
            {Body(<>코스닥 AI 관련주 <span style={{color:'#A78BFA'}}>직접 수혜</span></>)}
          </div>
        </div>
        <div style={{opacity:fi(f,230,20)}}>{Body('바이오 + AI = 코스닥 핵심 2대 섹터',C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S21:React.FC = () => {
  const f=useCurrentFrame();
  const BENEFITS=[
    {sector:'바이오·제약',reason:'코스닥150 40% + FDA 펀드 직접 수혜',color:C.mint,score:'★★★'},
    {sector:'AI 반도체',reason:'소버린AI 메가프로젝트 직접 배정',color:'#A78BFA',score:'★★★'},
    {sector:'OLED·디스플레이',reason:'2차 메가프로젝트 포함',color:C.orange,score:'★★'},
    {sector:'기술특례상장사',reason:'국민성장펀드 의무 10% 배분',color:C.blue,score:'★★'},
  ];
  return (
    <Wrap no={21} accent={C.mint} label="수혜 섹터 종합">
      <Ctr gap={18} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('정책 수혜 섹터')}
          {Title(<>어디로 <span style={{color:C.mint}}>흘러가는가</span></>)}
        </div>
        {BENEFITS.map((b,i)=>(
          <div key={i} style={{
            opacity:fi(f,60+i*36,20),
            transform:`translateX(${interpolate(f,[60+i*36,80+i*36],[-50,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            display:'flex',justifyContent:'space-between',alignItems:'center',
            background:`${b.color}0C`,border:`1px solid ${b.color}44`,
            borderRadius:12,padding:'16px 24px',
          }}>
            <div>
              <div style={{color:b.color,fontSize:22,fontWeight:700}}>{b.sector}</div>
              <div style={{color:C.dim,fontSize:16,marginTop:4}}>{b.reason}</div>
            </div>
            <div style={{color:b.color,fontSize:24,fontFamily:FONT.mono}}>{b.score}</div>
          </div>
        ))}
      </Ctr>
    </Wrap>
  );
};

const S22:React.FC = () => {
  const f=useCurrentFrame();
  const op=Math.min(1,Math.max(0,(f-140)/60));
  return (
    <Wrap no={22} accent={C.mint} label="투자 전략">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('탑픽 조건')}
          {Title(<>수급 빈집 + 정책 수혜<br/><span style={{color:C.mint}}>= 교집합</span></>)}
        </div>
        <div style={{opacity:fi(f,50,16)}}>
          <svg width={700} height={310} viewBox="0 0 700 310" style={{overflow:'visible'}}>
            <circle cx={275} cy={165} r={128} fill="rgba(255,67,54,0.14)" stroke={C.bull} strokeWidth={2.5} opacity={Math.min(1,(f-54)/40)}/>
            <circle cx={425} cy={165} r={128} fill="rgba(0,255,212,0.10)" stroke={C.mint} strokeWidth={2.5} opacity={Math.min(1,(f-54)/40)}/>
            <clipPath id="kpL"><circle cx={275} cy={165} r={128}/></clipPath>
            <circle cx={425} cy={165} r={128} fill={`${C.mint}44`} clipPath="url(#kpL)" opacity={op} style={{filter:`drop-shadow(0 0 14px ${C.mint})`}}/>
            <text x={215} y={120} fill={C.bull} fontSize={18} fontWeight={700} textAnchor="middle" opacity={Math.min(1,(f-54)/40)}>수급 빈집</text>
            <text x={215} y={143} fill={C.bull} fontSize={15} textAnchor="middle" opacity={Math.min(1,(f-54)/40)}>하위 25%</text>
            <text x={485} y={120} fill={C.mint} fontSize={18} fontWeight={700} textAnchor="middle" opacity={Math.min(1,(f-54)/40)}>정책 수혜</text>
            <text x={485} y={143} fill={C.mint} fontSize={15} textAnchor="middle" opacity={Math.min(1,(f-54)/40)}>섹터 포함</text>
            <text x={350} y={162} fill={C.mint} fontSize={16} fontWeight={700} textAnchor="middle" fontFamily={FONT.mono} opacity={op}>탑픽</text>
          </svg>
        </div>
        <div style={{opacity:fi(f,240,20)}}>{Body(<>수급오실레이터 하위 25% + 정책 수혜 섹터<br/><span style={{color:C.mint,fontWeight:700}}>두 가지 겹치면 가장 강한 셋업</span></>)}</div>
      </Ctr>
    </Wrap>
  );
};

const S23:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={23} accent={C.orange} label="목표 지수">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('증권가 코스닥 목표')}
          {Title(<>현재 <span style={{color:C.white}}>1,200선</span><br/>→ 목표 <span style={{color:C.orange}}>1,400pt</span></>)}
        </div>
        <div style={{opacity:fi(f,68,18),maxWidth:700,margin:'0 auto',width:'100%'}}>
          <HBar f={f} appear={72} value={1200} maxVal={1500} label="현재 코스닥 지수 (2026.05.22)" color={C.white} suffix="pt" decimals={0}/>
          <HBar f={f} appear={128} value={1400} maxVal={1500} label="증권가 목표 지수" color={C.orange} suffix="pt" decimals={0}/>
        </div>
        <div style={{opacity:fi(f,240,20)}}>
          {Body(<>목표 달성 시 <span style={{color:C.orange,fontWeight:700}}>약 +16.7%</span> 추가 상승 여력</>)}
          {Body('정책 집행 강도에 따라 상향 가능',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S24:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={24} accent={C.bull} label="리스크 체크">
      <Ctr gap={22}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('반드시 확인하세요')}
          {Title(<>리스크 <span style={{color:C.bull}}>3가지</span></>)}
        </div>
        {[
          {icon:'⚠️',text:'1,400조 전체가 아닌 16.5조 실투자',sub:'국민연금 벤치마크 제외 확인'},
          {icon:'⚠️',text:'정책 발표와 실제 집행의 시차',sub:'상반기 조정 → 하반기 집행 지연 가능'},
          {icon:'⚠️',text:'오늘 이미 +4.99% 급등 반영',sub:'단기 과열 후 재진입 타이밍 필요'},
        ].map((item,i)=>(
          <div key={i} style={{
            opacity:fi(f,70+i*42,20),
            transform:`translateX(${interpolate(f,[70+i*42,90+i*42],[-50,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            background:'rgba(255,67,54,0.08)',border:'1px solid rgba(255,67,54,0.3)',
            borderRadius:12,padding:'16px 24px',textAlign:'left',display:'flex',gap:16,alignItems:'flex-start',
          }}>
            <span style={{fontSize:24,flexShrink:0}}>{item.icon}</span>
            <div>
              <div style={{color:C.white,fontSize:20,fontWeight:700,marginBottom:4}}>{item.text}</div>
              <div style={{color:C.dim,fontSize:16}}>{item.sub}</div>
            </div>
          </div>
        ))}
      </Ctr>
    </Wrap>
  );
};

const S25:React.FC = () => {
  const f=useCurrentFrame();
  const SUMMARY=[
    {icon:'🔴',text:'코스닥 +4.99% 사이드카 발동',color:C.bull},
    {icon:'📋',text:'연기금 벤치마크 코스닥150 5% 편입',color:C.mint},
    {icon:'💰',text:'국민성장펀드 4.5시간 완판',color:C.orange},
    {icon:'🧬',text:'바이오·AI 직접 수혜 섹터',color:C.mint},
    {icon:'🎯',text:'수급 빈집 + 정책 교집합 = 탑픽',color:C.mint},
  ];
  return (
    <Wrap no={25} accent={C.mint} label="오늘 요약">
      <Ctr gap={14}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('오늘 핵심 요약')}
          {Title(<>알아야 할 <span style={{color:C.mint}}>5가지</span></>)}
        </div>
        {SUMMARY.map((s,i)=>(
          <div key={i} style={{
            opacity:fi(f,60+i*36,20),
            transform:`translateX(${interpolate(f,[60+i*36,80+i*36],[-50,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            display:'flex',alignItems:'center',gap:16,
            background:`${s.color}0A`,border:`1px solid ${s.color}33`,
            borderRadius:12,padding:'14px 20px',
          }}>
            <span style={{fontSize:24,minWidth:34}}>{s.icon}</span>
            <div style={{color:s.color,fontSize:20,fontWeight:700}}>{i+1}. {s.text}</div>
          </div>
        ))}
      </Ctr>
    </Wrap>
  );
};

const S26:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.6+Math.sin(f*0.07)*0.3;
  return (
    <Wrap no={26} accent={C.mint} label="코스닥 대변혁">
      <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',textAlign:'center',padding:'80px 120px'}}>
        <div style={{position:'absolute',inset:0,background:`radial-gradient(ellipse at 50% 50%, ${C.mint}${Math.floor(glow*26).toString(16).padStart(2,'0')} 0%, transparent 55%)`,opacity:fi(f,20,40)}}/>
        <div style={{opacity:fi(f,14,30),transform:`scale(${0.72+Math.min(1,(f-14)/30)*.28})`}}>
          <div style={{color:C.mint,fontSize:90,fontWeight:900,lineHeight:1.15,letterSpacing:'-2px',
            filter:`drop-shadow(0 0 ${22*glow}px ${C.mint}) drop-shadow(0 0 ${55*glow}px ${C.mint}88)`}}>
            1,400조의<br/>물길이<br/>바뀐다
          </div>
        </div>
        <div style={{opacity:fi(f,160,22),marginTop:20}}>
          {Body('구조를 안 사람이 먼저 들어갑니다')}
          {Body(<>수급 빈집에서 <span style={{color:C.mint,fontWeight:700}}>정책 수혜를 기다리는 것</span></>,C.dim)}
        </div>
      </AbsoluteFill>
    </Wrap>
  );
};

const S27:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={27} accent={C.orange} label="다음 영상">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('다음 영상 예고')}
          {Title(<>정책 수혜 섹터에서<br/><span style={{color:C.orange}}>탑픽을 찾는 법</span></>)}
        </div>
        <div style={{opacity:fi(f,80,22),background:'rgba(255,192,0,0.08)',border:'1px solid rgba(255,192,0,0.3)',borderRadius:16,padding:'28px 40px'}}>
          <div style={{color:C.orange,fontSize:24,fontWeight:700,marginBottom:12}}>수급오실레이터 + 정책 교집합</div>
          {Body('바이오·AI 섹터에서 빈집 종목 포착법')}
          {Body('데이터로 직접 보여드립니다',C.dim)}
        </div>
        <div style={{opacity:fi(f,230,20)}}>{Body('로또의 주식 위키 시스템 연계',C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S28:React.FC = () => {
  const f=useCurrentFrame();
  const pulse=0.7+Math.sin(f*0.12)*0.2;
  return (
    <Wrap no={28} accent={C.mint} label="구독 & 알림">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,22)}}>
          {TitleXL(<>구독이랑 알림<br/><span style={{color:C.mint}}>눌러두세요</span></>)}
        </div>
        <div style={{opacity:fi(f,80,20)}}>{Body('정책 집행 타이밍 놓치지 마세요',C.dim)}</div>
        <div style={{
          opacity:fi(f,120,24),transform:`scale(${pulse})`,
          display:'inline-block',margin:'0 auto',
          background:C.mint,borderRadius:16,padding:'20px 60px',
          color:C.bg,fontSize:32,fontWeight:900,
          boxShadow:`0 0 ${30*pulse}px ${C.mint}88, 0 0 ${60*pulse}px ${C.mint}44`,
        }}>🔔 구독 + 알림</div>
        <div style={{opacity:fi(f,220,22)}}>{Body('오늘도 수익 나는 하루 되세요')}</div>
        <div style={{opacity:fi(f,275,20)}}>{Lbl('로또의 주식',C.mint)}</div>
      </Ctr>
    </Wrap>
  );
};

// ── 메인 컴포지션 ──────────────────────────────────────
const SCENES=[S01,S02,S03,S04,S05,S06,S07,S08,S09,S10,
              S11,S12,S13,S14,S15,S16,S17,S18,S19,S20,
              S21,S22,S23,S24,S25,S26,S27,S28];

export const KosdaqPolicyVideo:React.FC = () => (
  <AbsoluteFill style={{backgroundColor:C.bg}}>
    {SCENES.map((Scene,i)=>(
      <Sequence key={i} from={i*SDUR} durationInFrames={SDUR}>
        <Scene/>
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const KOSDAQ_POLICY_FRAMES = SDUR * TOTAL;
