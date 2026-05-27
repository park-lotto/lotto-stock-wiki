import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate } from 'remotion';
import { FONT } from './theme';

const C = {
  bg:'#0F112A', white:'#FFFFFF', mint:'#00FFD4', orange:'#FFC000',
  bull:'#FF4336', dim:'rgba(255,255,255,0.45)', card:'rgba(255,255,255,0.07)',
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

// ── 파티클 & 글로우 ────────────────────────────────────
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

// ── 공통 레이아웃 ──────────────────────────────────────
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
        color:C.dim,fontFamily:FONT.mono,fontSize:16,opacity:.5}}>로또의 주식 — 데이터 탐정</div>
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
  <div style={{color,fontSize:46,fontWeight:700,lineHeight:1.3,marginBottom:14,...ex}}>{txt}</div>
);
const Body = (txt:React.ReactNode,color=C.white,ex?:React.CSSProperties) => (
  <div style={{color,fontSize:28,fontWeight:500,lineHeight:1.65,...ex}}>{txt}</div>
);
const Lbl = (txt:React.ReactNode,color=C.dim) => (
  <div style={{color,fontSize:18,fontWeight:600,letterSpacing:3,marginBottom:12}}>{txt}</div>
);

// ── 수출 데이터 카드 ────────────────────────────────────
const DataCard:React.FC<{label:string;value:number;suffix?:string;color?:string;appear:number}> = ({label,value,suffix='%',color=C.bull,appear}) => {
  const f=useCurrentFrame();
  const v=countUp(f,appear,value,80);
  const sc=1+(1-Math.min(1,(f-appear)/24))*.12;
  return (
    <div style={{
      opacity:fi(f,appear,16),transform:`scale(${sc})`,
      background:`${color}14`,border:`1px solid ${color}55`,
      borderRadius:16,padding:'24px 36px',minWidth:230,textAlign:'center',
    }}>
      <div style={{color:C.dim,fontSize:18,fontFamily:FONT.mono,letterSpacing:2,marginBottom:10}}>{label}</div>
      <div style={{color,fontSize:68,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,filter:Glow(color)}}>
        +{v}{suffix}
      </div>
    </div>
  );
};

// ── 체크마크 ───────────────────────────────────────────
const CheckMark:React.FC<{f:number;appear:number;color?:string;size?:number}> = ({f,appear,color=C.mint,size=80}) => {
  const circP=Math.min(1,Math.max(0,(f-appear)/20));
  const chkP=Math.min(1,Math.max(0,(f-appear)/30));
  const cLen=2*Math.PI*44;
  const pLen=200;
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" style={{display:'inline-block'}}>
      <circle cx="50" cy="50" r="44" fill="none" stroke={`${color}33`} strokeWidth="4"/>
      <circle cx="50" cy="50" r="44" fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={cLen} strokeDashoffset={cLen*(1-circP)}
        strokeLinecap="round" transform="rotate(-90 50 50)"
        style={{filter:`drop-shadow(0 0 4px ${color})`}}/>
      <polyline points="25,52 42,68 75,36" fill="none" stroke={color} strokeWidth="7"
        strokeLinecap="round" strokeLinejoin="round"
        strokeDasharray={pLen} strokeDashoffset={pLen*(1-chkP)}
        style={{filter:`drop-shadow(0 0 6px ${color})`}}/>
    </svg>
  );
};

// ══════════════════════════════════════════════════════
// SCENES S01 ~ S28
// ══════════════════════════════════════════════════════

const S01:React.FC = () => {
  const f=useCurrentFrame();
  const fname='5월_잠정수출데이터.xlsx';
  const n=Math.floor(interpolate(f,[40,140],[0,fname.length],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}));
  const cur=Math.floor(f/15)%2===0;
  return (
    <Wrap no={1} accent={C.mint} label="데이터 탐정">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,10,20)}}>
          {Lbl('오늘 아침 루틴')}
          {TitleXL(<>수출 데이터가<br/>들어왔습니다</>)}
        </div>
        <div style={{
          opacity:fi(f,38,16),transform:`translateY(${su(f,38,16)}px)`,
          fontFamily:FONT.mono,fontSize:32,color:C.mint,letterSpacing:2,
          background:'rgba(0,255,212,0.06)',padding:'28px 48px',
          borderRadius:14,border:`1px solid ${C.mint}33`,
        }}>📁 {fname.slice(0,n)}{cur?'▋':' '}</div>
        <div style={{opacity:fi(f,160,24),transform:`translateY(${su(f,160,24)}px)`}}>
          {Body('제일 먼저 하는 것이 있습니다',C.dim)}
          {Body(<>그냥 읽는 게 아닙니다. <span style={{color:C.mint,fontWeight:700}}>신호등을 찾습니다.</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const SHEETS=['디램','HBM','낸드','SSD+미국','MLCC','PCB','솔더볼','CCL','광섬유','변압기','변압기+미국','양극재','동박','알루미늄박','ESS+미국','증착장비','반도체장비','전력기기','기타부품'];

const S02:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={2} accent={C.mint} label="데이터 탐정">
      <Ctr gap={20} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('시트 구성')}
          {Title(<>총 <span style={{color:C.mint}}>19개</span> 시트가 있습니다</>)}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:'10px 14px',marginTop:8}}>
          {SHEETS.map((s,i)=>(
            <div key={s} style={{
              opacity:fi(f,50+i*10,16),transform:`translateY(${su(f,50+i*10,16)}px)`,
              background:C.card,border:'1px solid rgba(255,255,255,0.12)',
              borderRadius:8,padding:'10px 8px',color:C.white,fontSize:17,fontWeight:600,
            }}>{s}</div>
          ))}
        </div>
        <div style={{opacity:fi(f,270,20)}}>
          {Body(<>반도체 소재부터 전력기기까지<br/><span style={{color:C.mint}}>전부 다 읽지 않습니다</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S03:React.FC = () => {
  const f=useCurrentFrame();
  const pulse=0.6+Math.sin(f*0.1)*0.3;
  return (
    <Wrap no={3} accent={C.bull} label="데이터 탐정">
      <Ctr gap={36}>
        <div style={{opacity:fi(f,8,20)}}>
          {Lbl('필터링 방법')}
          {TitleXL(<>신호등 색깔로만<br/>먼저 봅니다</>)}
        </div>
        <div style={{display:'flex',gap:48,justifyContent:'center',alignItems:'center',opacity:fi(f,80,20)}}>
          {[
            {color:C.bull,label:'빨간불',desc:'강한 신호',on:true},
            {color:'#FFC000',label:'노란불',desc:'중간 신호',on:false},
            {color:'#555',label:'없음',desc:'무신호',on:false},
          ].map((item,i)=>(
            <div key={i} style={{opacity:fi(f,84+i*22,18),textAlign:'center'}}>
              <div style={{
                width:80,height:80,borderRadius:'50%',margin:'0 auto 12px',
                backgroundColor:item.on?item.color:'rgba(255,255,255,0.1)',
                border:`3px solid ${item.on?item.color:'rgba(255,255,255,0.2)'}`,
                boxShadow:item.on?`0 0 ${20*pulse}px ${item.color}, 0 0 ${40*pulse}px ${item.color}66`:'none',
              }}/>
              <div style={{color:item.on?item.color:C.dim,fontSize:20,fontWeight:700}}>{item.label}</div>
              <div style={{color:C.dim,fontSize:16,marginTop:4}}>{item.desc}</div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,200,20),transform:`translateY(${su(f,200,20)}px)`}}>
          {Body(<><span style={{color:C.bull,fontWeight:700}}>🔴 빨간불이 켜진 시트만</span> 골라냅니다</>)}
          {Body('나머지는 전부 건너뜁니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S04:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={4} accent={C.bull} label="시트 01 · 디램">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('첫 번째 시트')}
          {Title(<>디램 — <span style={{color:C.bull}}>빨간불</span></>)}
        </div>
        <div style={{display:'flex',gap:40,justifyContent:'center',flexWrap:'wrap'}}>
          <DataCard label="물량 YoY" value={456} appear={60}/>
          <DataCard label="판가 YoY" value={491} appear={80}/>
        </div>
        <div style={{opacity:fi(f,200,20)}}>
          <div style={{background:'rgba(255,67,54,0.1)',border:'1px solid rgba(255,67,54,0.3)',borderRadius:12,padding:'20px 32px'}}>
            {Body(<>판가 절대값 <span style={{color:C.bull,fontWeight:800}}>82,820달러 / kg</span></>)}
            {Body(<>1년 전 대비 <span style={{color:C.bull}}>6배</span> 비싸게 팔리고 있습니다</>,C.dim)}
          </div>
        </div>
        <div style={{opacity:fi(f,290,20)}}>{Body(<><span style={{color:C.bull,fontWeight:700}}>🔴 빨간불.</span> 다음 시트.</>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S05:React.FC = () => {
  const f=useCurrentFrame();
  const old=countUp(f,50,14000,70);
  const now=countUp(f,130,82820,90);
  return (
    <Wrap no={5} accent={C.bull} label="디램 판가 비교">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('1년 전 vs 지금')}
          {Title(<>같은 무게인데<br/><span style={{color:C.bull}}>6배 비싸게</span> 팔리고 있습니다</>)}
        </div>
        <div style={{display:'flex',gap:48,justifyContent:'center',alignItems:'stretch'}}>
          <div style={{
            opacity:fi(f,44,20),transform:`translateX(${interpolate(f,[44,64],[-60,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            background:'rgba(255,255,255,0.05)',border:'1px solid rgba(255,255,255,0.15)',
            borderRadius:16,padding:'28px 40px',textAlign:'center',minWidth:260,
          }}>
            <div style={{color:C.dim,fontSize:18,letterSpacing:2,marginBottom:12}}>1년 전</div>
            <div style={{color:'rgba(255,255,255,0.5)',fontSize:56,fontWeight:900,fontFamily:FONT.mono}}>${old.toLocaleString()}</div>
            <div style={{color:C.dim,fontSize:16,marginTop:8}}>/ kg</div>
          </div>
          <div style={{display:'flex',alignItems:'center',opacity:fi(f,90,16),color:C.bull,fontSize:48,fontWeight:900}}>→</div>
          <div style={{
            opacity:fi(f,120,20),transform:`translateX(${interpolate(f,[120,140],[60,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            background:'rgba(255,67,54,0.12)',border:`2px solid ${C.bull}66`,
            borderRadius:16,padding:'28px 40px',textAlign:'center',minWidth:260,
            boxShadow:`0 0 40px ${C.bull}33`,
          }}>
            <div style={{color:C.bull,fontSize:18,letterSpacing:2,marginBottom:12}}>지금</div>
            <div style={{color:C.bull,fontSize:56,fontWeight:900,fontFamily:FONT.mono,filter:Glow(C.bull)}}>${now.toLocaleString()}</div>
            <div style={{color:C.bull,fontSize:16,marginTop:8,opacity:.7}}>/ kg</div>
          </div>
        </div>
        <div style={{opacity:fi(f,240,20)}}>{Body('수요가 공급을 압도하고 있다는 신호',C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S06:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={6} accent={C.bull} label="시트 02 · HBM">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('두 번째 시트')}
          {Title(<>HBM — <span style={{color:C.bull}}>빨간불</span></>)}
        </div>
        <div style={{display:'flex',gap:40,justifyContent:'center',flexWrap:'wrap'}}>
          <DataCard label="물량 YoY" value={102} appear={60}/>
          <DataCard label="판가 YoY" value={114} appear={80}/>
        </div>
        <div style={{opacity:fi(f,200,20)}}>
          <div style={{background:'rgba(255,67,54,0.08)',border:'1px solid rgba(255,67,54,0.25)',borderRadius:12,padding:'18px 28px'}}>
            {Body(<>판가 절대값 <span style={{color:C.bull,fontWeight:800}}>76,386달러 / kg</span></>)}
          </div>
        </div>
        <div style={{opacity:fi(f,280,16)}}>{Body(<><span style={{color:C.bull,fontWeight:700}}>🔴 빨간불.</span> 계속 갑니다.</>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S07:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={7} accent={C.bull} label="시트 03 · SSD+미국향">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('세 번째 시트')}
          {Title(<>SSD + 미국향<br/><span style={{color:C.bull,fontSize:52}}>이건 특이합니다</span></>)}
        </div>
        <div style={{display:'flex',gap:40,justifyContent:'center',flexWrap:'wrap'}}>
          <DataCard label="물량 YoY" value={479} appear={60}/>
          <DataCard label="판가 YoY" value={441} appear={80}/>
        </div>
        <div style={{opacity:fi(f,200,20)}}>
          {Body(<>미국향 폭발 = <span style={{color:C.orange,fontWeight:700}}>하이퍼스케일러 서버 증설</span> 신호</>)}
        </div>
        <div style={{display:'flex',justifyContent:'center',gap:20,marginTop:4}}>
          {['Amazon','Microsoft','Google'].map((name,i)=>(
            <div key={name} style={{
              opacity:fi(f,250+i*18,16),
              transform:`scale(${1+(1-Math.min(1,(f-250-i*18)/20))*.15})`,
              background:'rgba(255,192,0,0.1)',border:'1px solid rgba(255,192,0,0.3)',
              borderRadius:12,padding:'12px 22px',color:C.orange,fontSize:20,fontWeight:700,
            }}>{name}</div>
          ))}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S08:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={8} accent={C.orange} label="데이터 탐정">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,20)}}>
          {Lbl('신호의 의미')}
          {TitleXL(<>AI 서버를<br/><span style={{color:C.orange}}>미친듯이</span> 짓고 있다</>)}
        </div>
        <div style={{opacity:fi(f,100,20)}}>
          {Body('아마존 · 구글 · 마이크로소프트')}
          {Body('하이퍼스케일러들이 서버 증설을 가속합니다',C.dim)}
        </div>
        <div style={{opacity:fi(f,180,20),background:'rgba(255,192,0,0.08)',border:'1px solid rgba(255,192,0,0.25)',borderRadius:12,padding:'20px 32px'}}>
          {Body(<>SSD 미국향 폭발 = <span style={{color:C.orange,fontWeight:700}}>AI 인프라 확장 신호</span></>)}
        </div>
        <div style={{opacity:fi(f,260,18)}}>{Body(<><span style={{color:C.bull,fontWeight:700}}>🔴 빨간불. 다음 시트 갑니다.</span></>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S09:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.5+Math.sin(f*0.12)*0.3;
  return (
    <Wrap no={9} accent={C.mint} label="데이터 탐정">
      <Ctr gap={36}>
        <div style={{opacity:fi(f,10,24),transform:`scale(${1+(1-Math.min(1,(f-10)/24))*.3})`}}>
          <div style={{
            color:C.mint,fontSize:120,fontWeight:900,lineHeight:1,letterSpacing:'-2px',
            filter:`drop-shadow(0 0 ${24*glow}px ${C.mint})`,
          }}>잠깐.</div>
        </div>
        <div style={{opacity:fi(f,80,20),transform:`translateY(${su(f,80,20)}px)`}}>
          {Title(<>시트 번호 <span style={{color:C.mint}}>25번</span></>)}
          {Sub('솔더볼입니다')}
        </div>
        <div style={{opacity:fi(f,180,20)}}>
          {Body(<>여기서 <span style={{color:C.mint,fontWeight:700}}>멈춥니다</span></>,C.dim)}
        </div>
        <div style={{opacity:fi(f,240,18),background:`${C.mint}10`,border:`1px solid ${C.mint}44`,borderRadius:12,padding:'14px 28px',fontFamily:FONT.mono,fontSize:22,color:C.mint}}>솔더볼</div>
      </Ctr>
    </Wrap>
  );
};

const S10:React.FC = () => {
  const f=useCurrentFrame();
  const CHAIN=['SK하이닉스','HBM 칩','패키징','솔더볼','기판 부착'];
  return (
    <Wrap no={10} accent={C.mint} label="솔더볼이란?">
      <Ctr gap={28} maxW={1100}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('솔더볼이란')}
          {Title(<>반도체 패키징에<br/><span style={{color:C.mint}}>반드시 필요한</span> 부품입니다</>)}
        </div>
        <div style={{display:'flex',alignItems:'center',justifyContent:'center',flexWrap:'nowrap'}}>
          {CHAIN.map((item,i)=>(
            <React.Fragment key={i}>
              <div style={{
                opacity:fi(f,70+i*28,18),
                transform:`scale(${1+(1-Math.min(1,(f-70-i*28)/18))*.12})`,
                background:i===3?`${C.mint}20`:C.card,
                border:`1px solid ${i===3?C.mint:'rgba(255,255,255,0.15)'}`,
                borderRadius:10,padding:'14px 18px',
                color:i===3?C.mint:C.white,fontSize:18,fontWeight:700,textAlign:'center',
                boxShadow:i===3?`0 0 20px ${C.mint}44`:'none',minWidth:100,
              }}>{item}</div>
              {i<CHAIN.length-1&&(
                <div style={{opacity:fi(f,88+i*28,14),color:C.mint,fontSize:22,fontWeight:700,padding:'0 6px',flexShrink:0}}>→</div>
              )}
            </React.Fragment>
          ))}
        </div>
        <div style={{opacity:fi(f,230,20),transform:`translateY(${su(f,230,20)}px)`}}>
          {Body(<>HBM을 <span style={{color:C.mint}}>패키징할 때 반드시 필요한</span> 납 공 모양의 소재</>)}
          {Body('HBM이 늘면, 솔더볼도 늘어납니다',C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S11:React.FC = () => {
  const f=useCurrentFrame();
  const CARDS=[
    {label:'물량 YoY',value:97,suffix:'%',color:C.bull,appear:60},
    {label:'판가 YoY',value:75,suffix:'%',color:C.bull,appear:72},
    {label:'판가 절대값',value:177,suffix:'$/kg',color:C.orange,appear:84},
  ];
  return (
    <Wrap no={11} accent={C.bull} label="시트 25 · 솔더볼">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('솔더볼 수출 데이터')}
          {Title(<>숫자를 <span style={{color:C.bull}}>봅시다</span></>)}
        </div>
        <div style={{display:'flex',gap:32,justifyContent:'center',flexWrap:'wrap'}}>
          {CARDS.map((c,i)=>(
            <div key={i} style={{
              opacity:fi(f,c.appear,16),
              transform:`scale(${1+(1-Math.min(1,(f-c.appear)/22))*.12})`,
              background:`${c.color}12`,border:`1px solid ${c.color}55`,
              borderRadius:16,padding:'24px 36px',textAlign:'center',minWidth:230,
            }}>
              <div style={{color:C.dim,fontSize:18,fontFamily:FONT.mono,letterSpacing:2,marginBottom:10}}>{c.label}</div>
              <div style={{color:c.color,fontSize:66,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,filter:Glow(c.color)}}>
                {c.suffix==='$/kg'?'':'+'}
                {countUp(f,c.appear,c.value,80)}
                {c.suffix}
              </div>
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,200,20),background:'rgba(255,67,54,0.08)',border:'1px solid rgba(255,67,54,0.25)',borderRadius:12,padding:'16px 28px'}}>
          {Body(<><span style={{color:C.bull,fontWeight:700}}>역대 최고</span> 수준입니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S12:React.FC = () => {
  const f=useCurrentFrame();
  const W=800,H=280;
  const PTS=[
    {x:0.00,y:0.30},{x:0.10,y:0.38},{x:0.20,y:0.46},
    {x:0.30,y:0.52},{x:0.40,y:0.56},{x:0.50,y:0.53},
    {x:0.60,y:0.42},{x:0.65,y:0.36}, // Nov 25 꺾임
    {x:0.72,y:0.44},{x:0.80,y:0.54},
    {x:0.90,y:0.65},{x:1.00,y:0.78}, // May 26 +75%
  ];
  const prog=Math.min(1,Math.max(0,(f-60)/150));
  const cnt=Math.floor(prog*PTS.length);
  const vis=PTS.slice(0,Math.max(2,cnt));
  const pathStr=vis.map((p,i)=>`${i===0?'M':'L'}${p.x*W},${H-p.y*H}`).join(' ');
  const dipVis=prog>0.55;
  const endVis=prog>=0.98;
  return (
    <Wrap no={12} accent={C.mint} label="솔더볼 판가 추이">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('판가 시계열')}
          {Title(<>꺾임 → <span style={{color:C.mint}}>재가속</span></>)}
        </div>
        <div style={{opacity:fi(f,52,18)}}>
          <svg width={W} height={H+50} viewBox={`0 0 ${W} ${H+50}`} style={{overflow:'visible'}}>
            {[0.25,0.5,0.75].map((y,i)=>(
              <line key={i} x1={0} y1={H-y*H} x2={W} y2={H-y*H} stroke="rgba(255,255,255,0.07)" strokeWidth={1}/>
            ))}
            <path d={`${pathStr} L${vis[vis.length-1].x*W},${H} L0,${H} Z`} fill={`${C.mint}14`}/>
            <path d={pathStr} fill="none" stroke={C.mint} strokeWidth={3} style={{filter:`drop-shadow(0 0 4px ${C.mint})`}}/>
            {dipVis&&(
              <g opacity={Math.min(1,(f-(60+150*.55))/20)}>
                <circle cx={PTS[7].x*W} cy={H-PTS[7].y*H} r={9} fill={C.bull} style={{filter:Glow(C.bull)}}/>
                <text x={PTS[7].x*W} y={H-PTS[7].y*H-18} fill={C.bull} fontSize={16} fontFamily={FONT.mono} textAnchor="middle">-2%</text>
                <text x={PTS[7].x*W} y={H+28} fill={C.dim} fontSize={13} fontFamily={FONT.mono} textAnchor="middle">Nov 25</text>
              </g>
            )}
            {endVis&&(
              <g opacity={Math.min(1,(f-(60+150*.98))/20)}>
                <circle cx={PTS[11].x*W} cy={H-PTS[11].y*H} r={11} fill={C.bull} style={{filter:`drop-shadow(0 0 8px ${C.bull})`}}/>
                <text x={PTS[11].x*W-8} y={H-PTS[11].y*H-18} fill={C.bull} fontSize={18} fontFamily={FONT.mono} fontWeight={700} textAnchor="end">+75%</text>
                <text x={PTS[11].x*W} y={H+28} fill={C.dim} fontSize={13} fontFamily={FONT.mono} textAnchor="middle">May 26</text>
              </g>
            )}
          </svg>
        </div>
        <div style={{opacity:fi(f,250,20)}}>{Body(<>수요가 공급을 <span style={{color:C.bull,fontWeight:700}}>압도</span>하고 있습니다</>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S13:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.7+Math.sin(f*0.08)*0.2;
  return (
    <Wrap no={13} accent={C.bull} label="데이터 탐정">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,10,28),transform:`scale(${0.7+Math.min(1,(f-10)/28)*0.3})`}}>
          <div style={{
            color:C.bull,fontSize:100,fontWeight:900,lineHeight:1.1,letterSpacing:'-2px',
            filter:`drop-shadow(0 0 ${20*glow}px ${C.bull}) drop-shadow(0 0 ${50*glow}px ${C.bull}88)`,
          }}>수요가<br/>공급을<br/>압도</div>
        </div>
        <div style={{opacity:fi(f,160,22)}}>
          {Body('솔더볼 시장에 강한 수급 불균형이 발생했습니다')}
        </div>
        <div style={{opacity:fi(f,220,20),background:'rgba(255,67,54,0.1)',border:'1px solid rgba(255,67,54,0.3)',borderRadius:12,padding:'18px 28px'}}>
          {Body(<>이제 질문이 생깁니다<br/><span style={{color:C.mint,fontWeight:700}}>솔더볼을 만드는 한국 회사가 어디입니까?</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S14:React.FC = () => {
  const f=useCurrentFrame();
  const ps=1+Math.sin(f*0.1)*0.03;
  return (
    <Wrap no={14} accent={C.mint} label="데이터 탐정">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,20),transform:`translateY(${su(f,8,20)}px)`}}>
          {Lbl('다음 단계')}
          {TitleXL(<>솔더볼을 만드는<br/><span style={{color:C.mint}}>한국 회사</span>는?</>)}
        </div>
        <div style={{opacity:fi(f,80,24),transform:`scale(${ps})`,fontSize:110,lineHeight:1,
          filter:`drop-shadow(0 0 ${12+Math.sin(f*0.1)*8}px ${C.mint})`}}>❓</div>
        <div style={{opacity:fi(f,200,22),transform:`translateY(${su(f,200,22)}px)`}}>
          {Body('수출 신호만으로는 부족합니다',C.dim)}
          {Body(<>수급 데이터를 <span style={{color:C.mint,fontWeight:700}}>교차 검증</span>해야 합니다</>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S15:React.FC = () => {
  const f=useCurrentFrame();
  const fname='수급오실레이터.xlsm';
  const n=Math.floor(interpolate(f,[50,160],[0,fname.length],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}));
  const cur=Math.floor(f/15)%2===0;
  return (
    <Wrap no={15} accent={C.orange} label="데이터 탐정">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,8,20)}}>
          {Lbl('두 번째 파일')}
          {Title(<>수급 데이터를<br/><span style={{color:C.orange}}>열어봅니다</span></>)}
        </div>
        <div style={{
          opacity:fi(f,44,16),
          fontFamily:FONT.mono,fontSize:30,color:C.orange,letterSpacing:2,
          background:'rgba(255,192,0,0.06)',padding:'28px 48px',
          borderRadius:14,border:`1px solid ${C.orange}33`,
        }}>📊 {fname.slice(0,n)}{cur?'▋':' '}</div>
        <div style={{opacity:fi(f,180,20),transform:`translateY(${su(f,180,20)}px)`}}>
          {Body('외국인과 기관이 얼마나 들어와 있는지')}
          {Body(<><span style={{color:C.orange,fontWeight:700}}>시가총액 대비 수치</span>로 보여줍니다</>,C.dim)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S16:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={16} accent={C.orange} label="수급오실레이터">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('오실레이터 원리')}
          {Title(<>낮을수록 = <span style={{color:C.orange}}>빈집</span></>)}
        </div>
        <div style={{opacity:fi(f,60,20)}}>
          <div style={{background:'rgba(255,192,0,0.08)',border:'1px solid rgba(255,192,0,0.25)',borderRadius:16,padding:'28px 48px',fontFamily:FONT.mono}}>
            <div style={{color:C.dim,fontSize:18,marginBottom:12}}>계산 방식</div>
            <div style={{color:C.orange,fontSize:30,fontWeight:700}}>(외국인 + 기관 순매수) ÷ 시가총액</div>
            <div style={{color:C.dim,fontSize:18,marginTop:14}}>최근 5일 누적</div>
          </div>
        </div>
        <div style={{opacity:fi(f,180,20)}}>
          {[
            {icon:'📈',label:'높음 (+)',desc:'외인·기관 이미 들어와 있음 → 팔 사람 많음',color:C.bull},
            {icon:'🏠',label:'낮음 (-)',desc:'외인·기관 빠진 빈집 상태 → 탄력 극대화',color:C.mint},
          ].map((item,i)=>(
            <div key={i} style={{
              opacity:fi(f,185+i*30,18),
              display:'flex',alignItems:'center',gap:16,
              background:`${item.color}0C`,border:`1px solid ${item.color}33`,
              borderRadius:10,padding:'14px 20px',marginBottom:10,textAlign:'left',
            }}>
              <span style={{fontSize:26}}>{item.icon}</span>
              <div>
                <div style={{color:item.color,fontSize:20,fontWeight:700}}>{item.label}</div>
                <div style={{color:C.dim,fontSize:16}}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S17:React.FC = () => {
  const f=useCurrentFrame();
  const W=720,H=260;
  const prog=Math.min(1,Math.max(0,(f-50)/120));
  const pts=Array.from({length:100},(_,i)=>{
    const x=(i/99)*W;
    const z=(i/99-.5)*6;
    const y=H*.9-Math.exp(-z*z/2)/Math.sqrt(2*Math.PI)*H*2.2;
    return {x,y};
  });
  const cnt=Math.floor(prog*pts.length);
  const vis=pts.slice(0,Math.max(2,cnt));
  const pStr=vis.map((p,i)=>`${i===0?'M':'L'}${p.x},${p.y}`).join(' ');
  const markerX=W*0.08;
  const markerOp=prog>0.7?Math.min(1,(f-(50+120*.7))/20):0;
  const zoneOp1=prog>0.5?Math.min(1,(f-(50+120*.5))/20):0;
  const zoneOp2=prog>0.6?Math.min(1,(f-(50+120*.6))/20):0;
  return (
    <Wrap no={17} accent={C.orange} label="수급 분포">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('수급 분포 곡선')}
          {Title(<>현재 위치를 <span style={{color:C.orange}}>찾습니다</span></>)}
        </div>
        <div style={{opacity:fi(f,44,16)}}>
          <svg width={W} height={H+60} viewBox={`0 0 ${W} ${H+60}`} style={{overflow:'visible'}}>
            <line x1={0} y1={H*.9} x2={W} y2={H*.9} stroke="rgba(255,255,255,0.15)" strokeWidth={1}/>
            {pStr&&<path d={`${pStr} L${vis[vis.length-1].x},${H*.9} L0,${H*.9} Z`} fill="rgba(255,192,0,0.06)"/>}
            {pStr&&<path d={pStr} fill="none" stroke={C.orange} strokeWidth={2.5} style={{filter:`drop-shadow(0 0 4px ${C.orange}88)`}}/>}
            <rect x={0} y={0} width={W*.25} height={H*.9} fill={`${C.mint}14`} opacity={zoneOp1}/>
            <rect x={0} y={0} width={W*.10} height={H*.9} fill={`${C.mint}22`} opacity={zoneOp2}/>
            {markerOp>0&&(
              <g opacity={markerOp}>
                <line x1={markerX} y1={0} x2={markerX} y2={H*.9} stroke={C.mint} strokeWidth={2.5} strokeDasharray="6 4" style={{filter:`drop-shadow(0 0 4px ${C.mint})`}}/>
                <circle cx={markerX} cy={H*.65} r={10} fill={C.mint} style={{filter:`drop-shadow(0 0 8px ${C.mint})`}}/>
                <text x={markerX+16} y={H*.62} fill={C.mint} fontSize={16} fontWeight={700} fontFamily={FONT.mono}>현재</text>
              </g>
            )}
            <text x={W*.08} y={H+30} fill={C.mint} fontSize={13} fontFamily={FONT.mono} textAnchor="middle" opacity={markerOp}>하위 10%</text>
            <text x={W*.5} y={H+30} fill={C.dim} fontSize={13} fontFamily={FONT.mono} textAnchor="middle" opacity={Math.min(1,prog*2)}>평균</text>
            <text x={W*.92} y={H+30} fill={C.dim} fontSize={13} fontFamily={FONT.mono} textAnchor="middle" opacity={Math.min(1,prog*2)}>상위 10%</text>
          </svg>
        </div>
        <div style={{opacity:fi(f,220,20)}}>{Body(<><span style={{color:C.mint,fontWeight:700}}>초록 영역 = 빈집 상태</span><br/>외국인·기관이 빠져 있습니다</>,C.dim)}</div>
      </Ctr>
    </Wrap>
  );
};

const S18:React.FC = () => {
  const f=useCurrentFrame();
  const ROWS=[
    {label:'상위 10%',val:'+0.000728',color:C.bull},
    {label:'상위 25%',val:'+0.000377',color:'#FF7043'},
    {label:'평균',val:'-0.0000585',color:C.dim},
    {label:'하위 25%',val:'-0.000286',color:C.orange},
    {label:'하위 10%',val:'-0.001160',color:C.mint,note:'← 완전 빈집'},
  ];
  return (
    <Wrap no={18} accent={C.orange} label="수급 기준값">
      <Ctr gap={20}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('오실레이터 기준값')}
          {Title(<>빈집 판정 기준입니다</>)}
        </div>
        <div>
          {ROWS.map((row,i)=>(
            <div key={i} style={{
              opacity:fi(f,60+i*24,18),
              transform:`translateX(${interpolate(f,[60+i*24,80+i*24],[-40,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
              display:'flex',justifyContent:'space-between',alignItems:'center',
              padding:'14px 28px',marginBottom:6,
              background:i===4?`${C.mint}14`:`${row.color}0A`,
              border:`1px solid ${i===4?C.mint:row.color}44`,borderRadius:10,
            }}>
              <div style={{color:row.color,fontSize:22,fontWeight:700}}>{row.label}</div>
              <div style={{display:'flex',alignItems:'center',gap:12}}>
                <div style={{color:row.color,fontSize:22,fontFamily:FONT.mono}}>{row.val}</div>
                {'note' in row&&<div style={{color:C.dim,fontSize:16}}>{(row as typeof ROWS[4]).note}</div>}
              </div>
            </div>
          ))}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S19:React.FC = () => {
  const f=useCurrentFrame();
  const cp=Math.min(1,Math.max(0,(f-40)/80));
  const lx=370-cp*80, rx=430+cp*80;
  const R=145, CY=220;
  const op=Math.min(1,Math.max(0,(f-140)/60));
  return (
    <Wrap no={19} accent={C.mint} label="교집합">
      <Ctr gap={24}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('교집합 완성')}
          {Title(<>두 가지가 <span style={{color:C.mint}}>겹치는 종목</span>을 찾습니다</>)}
        </div>
        <div style={{opacity:fi(f,36,16)}}>
          <svg width={800} height={440} viewBox="0 0 800 440" style={{overflow:'visible'}}>
            <circle cx={lx} cy={CY} r={R} fill={`${C.bull}1A`} stroke={C.bull} strokeWidth={2.5} opacity={cp}/>
            <circle cx={rx} cy={CY} r={R} fill={`${C.orange}1A`} stroke={C.orange} strokeWidth={2.5} opacity={cp}/>
            <clipPath id="ddLeft"><circle cx={lx} cy={CY} r={R}/></clipPath>
            <circle cx={rx} cy={CY} r={R} fill={`${C.mint}44`} clipPath="url(#ddLeft)" opacity={op} style={{filter:`drop-shadow(0 0 14px ${C.mint})`}}/>
            <text x={lx-10} y={CY-R-28} fill={C.bull} fontSize={20} fontWeight={700} textAnchor="middle" fontFamily={FONT.main} opacity={cp}>수출 신호</text>
            <text x={lx-10} y={CY-R-6} fill={C.bull} fontSize={16} textAnchor="middle" fontFamily={FONT.main} opacity={cp}>🔴 빨간불</text>
            <text x={rx+10} y={CY-R-28} fill={C.orange} fontSize={20} fontWeight={700} textAnchor="middle" fontFamily={FONT.main} opacity={cp}>수급 빈집</text>
            <text x={rx+10} y={CY-R-6} fill={C.orange} fontSize={16} textAnchor="middle" fontFamily={FONT.main} opacity={cp}>하위 25%</text>
            <text x={400} y={CY+8} fill={C.mint} fontSize={18} fontWeight={700} textAnchor="middle" fontFamily={FONT.mono} opacity={op}>탑픽</text>
          </svg>
        </div>
        <div style={{opacity:fi(f,240,20)}}>
          {Body(<>빈집 상태 + 수출 신호 강세<br/><span style={{color:C.mint,fontWeight:700}}>= 테마 재점화 시 탄력 극대화</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S20:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={20} accent={C.bull} label="검증 1">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>{Lbl('조건 1 확인')}{Title(<>수출 신호 <span style={{color:C.bull}}>확인</span></>)}</div>
        <div style={{opacity:fi(f,60,24),display:'flex',justifyContent:'center'}}><CheckMark f={f} appear={64} color={C.bull} size={120}/></div>
        <div>
          {['솔더볼 물량 YoY +97%','솔더볼 판가 YoY +75%','판가 절대값 177달러/kg 역대 최고'].map((item,i)=>(
            <div key={i} style={{opacity:fi(f,125+i*28,18),display:'flex',alignItems:'center',gap:12,color:C.white,fontSize:24,marginBottom:10}}>
              <span style={{color:C.bull,fontSize:18}}>✓</span>{item}
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,260,20),background:`${C.bull}18`,border:`1px solid ${C.bull}44`,borderRadius:12,padding:'16px 28px'}}>
          {Body(<><span style={{color:C.bull,fontWeight:800}}>🔴 수출 신호 켜짐</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S21:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={21} accent={C.mint} label="검증 2">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>{Lbl('조건 2 확인')}{Title(<>수급 빈집 <span style={{color:C.mint}}>확인</span></>)}</div>
        <div style={{opacity:fi(f,60,24),display:'flex',justifyContent:'center'}}><CheckMark f={f} appear={64} color={C.mint} size={120}/></div>
        <div>
          {['오실레이터 하위 25% 이하','외국인·기관 수급 이탈 상태','팔 사람 없는 빈집 구조'].map((item,i)=>(
            <div key={i} style={{opacity:fi(f,125+i*28,18),display:'flex',alignItems:'center',gap:12,color:C.white,fontSize:24,marginBottom:10}}>
              <span style={{color:C.mint,fontSize:18}}>✓</span>{item}
            </div>
          ))}
        </div>
        <div style={{opacity:fi(f,260,20),background:`${C.mint}14`,border:`1px solid ${C.mint}44`,borderRadius:12,padding:'16px 28px'}}>
          {Body(<><span style={{color:C.mint,fontWeight:800}}>✅ 수급 빈집 확인</span></>)}
        </div>
      </Ctr>
    </Wrap>
  );
};

const S22:React.FC = () => {
  const f=useCurrentFrame();
  const glow=0.6+Math.sin(f*0.08)*0.3;
  const sc=1+(1-Math.min(1,(f-30)/40))*0.4;
  const pulse=0.85+Math.sin(f*0.06)*0.12;
  return (
    <Wrap no={22} accent={C.mint} label="결론">
      <AbsoluteFill style={{display:'flex',flexDirection:'column',justifyContent:'center',alignItems:'center',textAlign:'center',padding:'80px 120px'}}>
        <div style={{position:'absolute',inset:0,background:`radial-gradient(ellipse at 50% 50%, ${C.mint}${Math.floor(glow*30).toString(16).padStart(2,'0')} 0%, transparent 55%)`,opacity:fi(f,20,40)}}/>
        <div style={{opacity:fi(f,14,20),marginBottom:16}}>{Lbl('교집합 완성',C.mint)}</div>
        <div style={{
          opacity:fi(f,30,28),transform:`scale(${sc})`,
          color:C.mint,fontSize:112,fontWeight:900,letterSpacing:'-3px',lineHeight:1.05,
          filter:`drop-shadow(0 0 ${28*glow}px ${C.mint}) drop-shadow(0 0 ${60*glow}px ${C.mint}88)`,
          marginBottom:20,
        }}>덕산하이메탈</div>
        <div style={{opacity:fi(f,100,24)}}>{Sub('솔더볼 1위 제조사',C.dim)}</div>
        <div style={{opacity:fi(f,160,22),display:'flex',gap:20,justifyContent:'center',marginTop:12}}>
          {[
            {label:'수출 신호',icon:'🔴',color:C.bull},
            {label:'수급 빈집',icon:'✅',color:C.mint},
          ].map((item,i)=>(
            <div key={i} style={{
              opacity:fi(f,165+i*24,18),
              transform:`scale(${pulse})`,
              background:`${item.color}18`,border:`2px solid ${item.color}66`,
              borderRadius:14,padding:'16px 28px',
              fontSize:22,fontWeight:700,color:item.color,
              boxShadow:`0 0 20px ${item.color}44`,
            }}>{item.icon} {item.label}</div>
          ))}
        </div>
        <div style={{opacity:fi(f,260,24),marginTop:20}}>
          {Body(<>두 가지가 겹쳤습니다<br/><span style={{color:C.mint,fontWeight:700}}>테마 재점화 시 탄력 극대화 구간</span></>)}
        </div>
      </AbsoluteFill>
    </Wrap>
  );
};

const S23:React.FC = () => {
  const f=useCurrentFrame();
  return (
    <Wrap no={23} accent={C.orange} label="진입 전략">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('지금 바로 사면 안 됩니다',C.bull)}
          {Title(<>진입 조건 <span style={{color:C.orange}}>2가지</span></>)}
        </div>
        {[
          {no:'01',title:'수급오실레이터 하위 25% 이하 재확인',desc:'수급 데이터 ingest 완료 후 재확인',color:C.orange},
          {no:'02',title:'5일선 재돌파 + 거래량 증가 동반',desc:'두 조건 충족 시 1/3 선진입으로 시작',color:C.mint},
        ].map((item,i)=>(
          <div key={i} style={{
            opacity:fi(f,80+i*60,20),
            transform:`translateX(${interpolate(f,[80+i*60,100+i*60],[-60,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            background:`${item.color}0E`,border:`1px solid ${item.color}44`,
            borderRadius:14,padding:'22px 28px',textAlign:'left',
            display:'flex',gap:20,alignItems:'flex-start',
          }}>
            <div style={{color:item.color,fontSize:40,fontWeight:900,fontFamily:FONT.mono,lineHeight:1,minWidth:50}}>{item.no}</div>
            <div>
              <div style={{color:item.color,fontSize:22,fontWeight:700,marginBottom:6}}>{item.title}</div>
              <div style={{color:C.dim,fontSize:18}}>{item.desc}</div>
            </div>
          </div>
        ))}
      </Ctr>
    </Wrap>
  );
};

const S24:React.FC = () => {
  const f=useCurrentFrame();
  const W=700,H=200;
  const lp=Math.min(1,Math.max(0,(f-100)/80));
  const priceY=H*.28, stopY=H*.74;
  const pStr=`M 60,${priceY+40} L${W*.4},${priceY} L${W*lp},${priceY+18}`;
  return (
    <Wrap no={24} accent={C.bull} label="리스크 관리">
      <Ctr gap={28}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('손절 기준')}
          {Title(<>기계적으로 <span style={{color:C.bull}}>끊습니다</span></>)}
        </div>
        <div style={{opacity:fi(f,50,16)}}>
          <svg width={W} height={H+40} viewBox={`0 0 ${W} ${H+40}`} style={{overflow:'visible'}}>
            <path d={pStr} fill="none" stroke={C.mint} strokeWidth={2.5} style={{filter:`drop-shadow(0 0 4px ${C.mint})`}}/>
            {lp>0.3&&<line x1={60} y1={stopY} x2={W*Math.min(1,(lp-.3)/.7+.3)} y2={stopY} stroke={C.bull} strokeWidth={2} strokeDasharray="8 4"/>}
            {lp>0.5&&<text x={W*.52+8} y={stopY-10} fill={C.bull} fontSize={16} fontFamily={FONT.mono} opacity={Math.min(1,(f-(100+80*.5))/20)}>20일선 = 손절라인</text>}
            {lp>0.2&&<circle cx={W*.4} cy={priceY} r={7} fill={C.mint} style={{filter:`drop-shadow(0 0 6px ${C.mint})`}}/>}
          </svg>
        </div>
        <div style={{opacity:fi(f,200,20)}}>
          <div style={{background:`${C.bull}12`,border:`1px solid ${C.bull}44`,borderRadius:12,padding:'18px 28px'}}>
            {Body(<><span style={{color:C.bull,fontWeight:700}}>20일선 이탈 시 기계적 손절</span></>)}
            {Body('감정이 아니라 숫자가 결정합니다',C.dim)}
          </div>
        </div>
      </Ctr>
    </Wrap>
  );
};

const S25:React.FC = () => {
  const f=useCurrentFrame();
  const STEPS=[
    {icon:'📁',text:'수출 파일 열었습니다',color:C.mint},
    {icon:'🔴',text:'빨간불 시트 찾았습니다',color:C.bull},
    {icon:'💡',text:'솔더볼 신호 포착했습니다',color:C.orange},
    {icon:'📊',text:'수급 교집합 냈습니다',color:C.orange},
    {icon:'✅',text:'덕산하이메탈 걸렸습니다',color:C.mint},
  ];
  return (
    <Wrap no={25} accent={C.mint} label="오늘 루틴">
      <Ctr gap={18}>
        <div style={{opacity:fi(f,8,18)}}>
          {Lbl('매일 아침 루틴')}
          {Title(<>오늘 한 것 <span style={{color:C.mint}}>정리</span></>)}
        </div>
        {STEPS.map((step,i)=>(
          <div key={i} style={{
            opacity:fi(f,60+i*40,20),
            transform:`translateX(${interpolate(f,[60+i*40,80+i*40],[-50,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`,
            display:'flex',alignItems:'center',gap:16,
            background:`${step.color}0A`,border:`1px solid ${step.color}33`,
            borderRadius:12,padding:'14px 24px',textAlign:'left',
          }}>
            <span style={{fontSize:26,minWidth:36}}>{step.icon}</span>
            <div style={{color:step.color,fontSize:22,fontWeight:700}}>{i+1}. {step.text}</div>
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
    <Wrap no={26} accent={C.mint} label="데이터 탐정">
      <Ctr gap={32}>
        <div style={{opacity:fi(f,14,30),transform:`scale(${0.75+Math.min(1,(f-14)/30)*.25})`}}>
          <div style={{
            color:C.mint,fontSize:88,fontWeight:900,lineHeight:1.15,letterSpacing:'-2px',
            filter:`drop-shadow(0 0 ${18*glow}px ${C.mint}) drop-shadow(0 0 ${44*glow}px ${C.mint}66)`,
          }}>데이터가<br/>말하면<br/>듣는다</div>
        </div>
        <div style={{opacity:fi(f,160,22),transform:`translateY(${su(f,160,22)}px)`}}>
          {Body('특별한 감이 있어서가 아닙니다',C.dim)}
          {Body(<><span style={{color:C.mint}}>데이터가 신호를 보내면</span> 그걸 받는 겁니다</>)}
        </div>
      </Ctr>
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
          {Title(<>이 루틴을<br/><span style={{color:C.orange}}>자동화</span>합니다</>)}
        </div>
        <div style={{opacity:fi(f,80,22),background:'rgba(255,192,0,0.08)',border:'1px solid rgba(255,192,0,0.3)',borderRadius:16,padding:'28px 40px',textAlign:'center'}}>
          <div style={{color:C.orange,fontSize:28,fontWeight:700,marginBottom:12}}>자동화 시스템 공개</div>
          {Body('자는 동안 데이터가 들어오고')}
          {Body(<>아침에 일어나면 <span style={{color:C.orange}}>신호가 정리</span>되어 있습니다</>,C.dim)}
        </div>
        <div style={{opacity:fi(f,220,20)}}>{Body('로또의 주식 위키 시스템을 보여드립니다',C.dim)}</div>
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
        <div style={{opacity:fi(f,80,20)}}>{Body('올라오는 날 바로 보실 수 있습니다',C.dim)}</div>
        <div style={{
          opacity:fi(f,120,24),transform:`scale(${pulse})`,
          display:'inline-block',margin:'0 auto',
          background:C.mint,borderRadius:16,padding:'20px 60px',
          color:C.bg,fontSize:32,fontWeight:900,
          boxShadow:`0 0 ${30*pulse}px ${C.mint}88, 0 0 ${60*pulse}px ${C.mint}44`,
        }}>🔔 구독 + 알림</div>
        <div style={{opacity:fi(f,220,22)}}>{Body('오늘도 수익 나는 하루 되세요')}</div>
        <div style={{opacity:fi(f,270,20)}}>{Lbl('로또의 주식',C.mint)}</div>
      </Ctr>
    </Wrap>
  );
};

// ── 메인 컴포지션 ──────────────────────────────────────
const SCENES=[S01,S02,S03,S04,S05,S06,S07,S08,S09,S10,
              S11,S12,S13,S14,S15,S16,S17,S18,S19,S20,
              S21,S22,S23,S24,S25,S26,S27,S28];

export const DataDetectiveVideo:React.FC = () => (
  <AbsoluteFill style={{backgroundColor:C.bg}}>
    {SCENES.map((Scene,i)=>(
      <Sequence key={i} from={i*SDUR} durationInFrames={SDUR}>
        <Scene/>
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const DATA_DETECTIVE_FRAMES = SDUR * TOTAL;
