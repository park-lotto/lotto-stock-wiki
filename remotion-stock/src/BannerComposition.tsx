import React from 'react';
import { AbsoluteFill } from 'remotion';
import { FONT } from './theme';

const C = {
  bg:'#0F112A', white:'#FFFFFF', mint:'#00FFD4', orange:'#FFC000',
  bull:'#FF4336', dim:'rgba(255,255,255,0.45)',
};

// ─── 배경 노드 네트워크 ────────────────────────────────
// 좌측 클러스터
const LEFT_NODES = [
  {x:190,y:320,r:30,c:C.mint,hub:true},
  {x:70, y:220,r:13,c:'rgba(255,255,255,0.65)'},
  {x:340,y:190,r:11,c:'rgba(255,255,255,0.65)'},
  {x:60, y:520,r:15,c:C.orange},
  {x:360,y:470,r:18,c:C.orange},
  {x:180,y:640,r:13,c:C.bull},
  {x:430,y:310,r:13,c:C.bull},
  {x:100,y:720,r:10,c:'rgba(255,255,255,0.5)'},
  {x:470,y:600,r:10,c:C.mint},
];
const LEFT_EDGES = [[0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[1,3],[4,5],[2,4],[6,4],[7,5],[8,4]];

// 우측 클러스터
const RIGHT_NODES = [
  {x:1850,y:320,r:30,c:C.mint,hub:true},
  {x:1970,y:220,r:13,c:'rgba(255,255,255,0.65)'},
  {x:1700,y:190,r:11,c:'rgba(255,255,255,0.65)'},
  {x:1980,y:520,r:15,c:C.orange},
  {x:1680,y:470,r:18,c:C.orange},
  {x:1860,y:640,r:13,c:C.bull},
  {x:1610,y:310,r:13,c:C.bull},
  {x:1940,y:720,r:10,c:'rgba(255,255,255,0.5)'},
  {x:1570,y:600,r:10,c:C.mint},
];
const RIGHT_EDGES = [[0,1],[0,2],[0,3],[0,4],[0,5],[0,6],[1,3],[4,5],[2,4],[6,4],[7,5],[8,4]];

// 하단 서브 노드들
const BOT_NODES = [
  {x:600, y:940,r:10,c:C.mint},
  {x:720, y:880,r:8, c:C.orange},
  {x:820, y:970,r:9, c:C.bull},
  {x:950, y:900,r:8, c:'rgba(255,255,255,0.5)'},
  {x:1100,y:960,r:10,c:C.orange},
  {x:1220,y:870,r:8, c:C.mint},
  {x:1340,y:950,r:9, c:C.bull},
  {x:1450,y:890,r:8, c:'rgba(255,255,255,0.5)'},
];
const BOT_EDGES = [[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[0,3],[2,4]];

export const BannerComposition:React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor:C.bg,fontFamily:FONT.main,overflow:'hidden'}}>

      {/* ── 배경 방사형 글로우 ── */}
      <div style={{
        position:'absolute',inset:0,
        background:`
          radial-gradient(ellipse at 50% 45%, ${C.mint}0D 0%, transparent 50%),
          radial-gradient(ellipse at 15% 55%, ${C.orange}08 0%, transparent 38%),
          radial-gradient(ellipse at 85% 55%, ${C.mint}07 0%, transparent 38%)
        `,
      }}/>

      {/* ── 도트 그리드 ── */}
      <svg style={{position:'absolute',inset:0,width:'100%',height:'100%',opacity:.18}}>
        <defs>
          <pattern id="dg" x="0" y="0" width="44" height="44" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill={C.mint}/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dg)"/>
      </svg>

      {/* ── 좌우 페이드 오버레이 (중앙 콘텐츠 보호) ── */}
      <div style={{position:'absolute',inset:0,
        background:`linear-gradient(90deg,transparent 0%,transparent 32%,${C.bg}AA 50%,${C.bg}AA 50%,transparent 68%,transparent 100%)`}}/>

      {/* ── 네트워크 그래프 SVG ── */}
      <svg style={{position:'absolute',inset:0,width:'100%',height:'100%'}}>
        {/* 좌측 엣지 */}
        {LEFT_EDGES.map(([a,b],i)=>(
          <line key={`le${i}`}
            x1={LEFT_NODES[a].x} y1={LEFT_NODES[a].y}
            x2={LEFT_NODES[b].x} y2={LEFT_NODES[b].y}
            stroke="rgba(0,255,212,0.14)" strokeWidth={1.5}/>
        ))}
        {/* 우측 엣지 */}
        {RIGHT_EDGES.map(([a,b],i)=>(
          <line key={`re${i}`}
            x1={RIGHT_NODES[a].x} y1={RIGHT_NODES[a].y}
            x2={RIGHT_NODES[b].x} y2={RIGHT_NODES[b].y}
            stroke="rgba(0,255,212,0.14)" strokeWidth={1.5}/>
        ))}
        {/* 하단 엣지 */}
        {BOT_EDGES.map(([a,b],i)=>(
          <line key={`be${i}`}
            x1={BOT_NODES[a].x} y1={BOT_NODES[a].y}
            x2={BOT_NODES[b].x} y2={BOT_NODES[b].y}
            stroke="rgba(255,255,255,0.08)" strokeWidth={1}/>
        ))}

        {/* 좌측 노드 */}
        {LEFT_NODES.map((n,i)=>(
          <g key={`ln${i}`} opacity={n.hub?.92:.65}>
            {n.hub&&<>
              <circle cx={n.x} cy={n.y} r={n.r+16} fill="none" stroke={C.mint} strokeWidth={1} opacity={.18}/>
              <circle cx={n.x} cy={n.y} r={n.r+8}  fill="none" stroke={C.mint} strokeWidth={1.5} opacity={.28}/>
            </>}
            <circle cx={n.x} cy={n.y} r={n.r} fill={n.c}/>
          </g>
        ))}
        {/* 우측 노드 */}
        {RIGHT_NODES.map((n,i)=>(
          <g key={`rn${i}`} opacity={n.hub?.92:.65}>
            {n.hub&&<>
              <circle cx={n.x} cy={n.y} r={n.r+16} fill="none" stroke={C.mint} strokeWidth={1} opacity={.18}/>
              <circle cx={n.x} cy={n.y} r={n.r+8}  fill="none" stroke={C.mint} strokeWidth={1.5} opacity={.28}/>
            </>}
            <circle cx={n.x} cy={n.y} r={n.r} fill={n.c}/>
          </g>
        ))}
        {/* 하단 노드 */}
        {BOT_NODES.map((n,i)=>(
          <circle key={`bn${i}`} cx={n.x} cy={n.y} r={n.r} fill={n.c} opacity={.5}/>
        ))}

        {/* 허브 → 중앙 연결선 (장식) */}
        <line x1={LEFT_NODES[0].x} y1={LEFT_NODES[0].y} x2={900} y2={576}
          stroke={`${C.mint}14`} strokeWidth={1} strokeDasharray="8 12"/>
        <line x1={RIGHT_NODES[0].x} y1={RIGHT_NODES[0].y} x2={1148} y2={576}
          stroke={`${C.mint}14`} strokeWidth={1} strokeDasharray="8 12"/>
      </svg>

      {/* ── 상단 어센트 바 ── */}
      <div style={{position:'absolute',top:0,left:0,right:0,height:8,backgroundColor:C.mint,
        boxShadow:`0 0 24px ${C.mint}88`}}/>
      <div style={{position:'absolute',top:0,left:'30%',width:'40%',height:8,
        background:`linear-gradient(90deg,transparent,${C.mint}EE,transparent)`,opacity:.8}}/>

      {/* ── 하단 바 ── */}
      <div style={{position:'absolute',bottom:0,left:0,right:0,height:5,backgroundColor:C.mint,opacity:.45}}/>

      {/* ── 모서리 브라켓 ── */}
      <svg style={{position:'absolute',top:18,left:18,opacity:.55}} width={70} height={70}>
        <path d="M 0 70 L 0 0 L 70 0" fill="none" stroke={C.mint} strokeWidth={3} strokeLinecap="round"/>
      </svg>
      <svg style={{position:'absolute',top:18,right:18,opacity:.55}} width={70} height={70}>
        <path d="M 70 70 L 70 0 L 0 0" fill="none" stroke={C.mint} strokeWidth={3} strokeLinecap="round"/>
      </svg>
      <svg style={{position:'absolute',bottom:18,left:18,opacity:.55}} width={70} height={70}>
        <path d="M 0 0 L 0 70 L 70 70" fill="none" stroke={C.mint} strokeWidth={3} strokeLinecap="round"/>
      </svg>
      <svg style={{position:'absolute',bottom:18,right:18,opacity:.55}} width={70} height={70}>
        <path d="M 70 0 L 70 70 L 0 70" fill="none" stroke={C.mint} strokeWidth={3} strokeLinecap="round"/>
      </svg>

      {/* ══ 중앙 콘텐츠 (유튜브 세이프존 기준) ══ */}
      <div style={{
        position:'absolute',
        left:251,right:251,
        top:0,bottom:0,
        display:'flex',flexDirection:'column',
        justifyContent:'center',alignItems:'center',
        textAlign:'center',
        gap:22,
      }}>

        {/* 배지 */}
        <div style={{
          display:'inline-flex',alignItems:'center',gap:10,
          backgroundColor:`${C.orange}18`,
          border:`1.5px solid ${C.orange}66`,
          borderRadius:40,padding:'10px 30px',
        }}>
          <div style={{
            color:C.orange,fontSize:24,fontWeight:700,letterSpacing:3,
            textShadow:`0 0 12px ${C.orange}66`,
          }}>20년 경력 주식 전문가</div>
        </div>

        {/* 채널명 */}
        <div style={{lineHeight:1,userSelect:'none'}}>
          <div style={{
            color:C.white,
            fontSize:86,
            fontWeight:900,
            letterSpacing:'-2px',
            lineHeight:1.05,
            textShadow:'0 2px 30px rgba(0,0,0,0.5)',
          }}>로또의</div>
          <div style={{
            color:C.mint,
            fontSize:120,
            fontWeight:900,
            letterSpacing:'-4px',
            lineHeight:1.0,
            textShadow:`0 0 50px ${C.mint}88, 0 0 100px ${C.mint}44, 0 2px 30px rgba(0,0,0,0.5)`,
          }}>주식인사이트</div>
        </div>

        {/* 구분선 */}
        <div style={{
          width:480,height:3,
          background:`linear-gradient(90deg,transparent,${C.mint},transparent)`,
          boxShadow:`0 0 20px ${C.mint}CC`,
          borderRadius:2,
        }}/>

        {/* 태그라인 */}
        <div style={{
          color:'rgba(255,255,255,0.75)',
          fontSize:30,fontWeight:500,letterSpacing:2,
          lineHeight:1.5,
        }}>
          AI 지식 자동화 · 수급 분석 · 대장주 포착
        </div>

        {/* 키워드 뱃지들 */}
        <div style={{display:'flex',gap:16,justifyContent:'center',flexWrap:'wrap'}}>
          {[
            {txt:'📊 수급빈집 추적',c:C.mint},
            {txt:'🎯 대장주 포착',  c:C.orange},
            {txt:'🤖 AI 자동화',    c:C.mint},
            {txt:'💡 단기 스윙',    c:C.orange},
          ].map((tag,i)=>(
            <div key={i} style={{
              backgroundColor:'rgba(255,255,255,0.06)',
              border:`1px solid ${tag.c}44`,
              borderRadius:30,padding:'10px 24px',
              color:'rgba(255,255,255,0.7)',
              fontSize:22,fontWeight:500,letterSpacing:1,
            }}>{tag.txt}</div>
          ))}
        </div>

      </div>

      {/* ── 하단 채널 URL 워터마크 ── */}
      <div style={{
        position:'absolute',bottom:22,left:0,right:0,
        textAlign:'center',
        color:'rgba(255,255,255,0.3)',
        fontFamily:FONT.mono,
        fontSize:20,
        letterSpacing:3,
      }}>유튜브 검색 → 로또의 주식인사이트</div>

    </AbsoluteFill>
  );
};
