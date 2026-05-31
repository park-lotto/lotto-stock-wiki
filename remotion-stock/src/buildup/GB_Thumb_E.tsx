// GB_Thumb_E — 뉴스 헤드라인 버전 + LFP 공장 블러
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { C, FONT } from '../constants';

const HEADLINES = [
  { source: '경향신문', title: '국민성장펀드 2차, 이르면 8월 출시', hot: true },
  { source: '매일경제', title: "'조기 완판' 국민참여성장펀드... 2차분 출시할 것\"" },
  { source: '매일경제', title: '[매경데스크] 코스닥의 시간 오려면' },
];

export const GB_Thumb_E = () => (
  <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

    {/* 배경 글로우 */}
    <div style={{ position: 'absolute', top: -150, left: -80, width: 600, height: 500, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,67,54,0.14) 0%, transparent 65%)' }} />
    <div style={{ position: 'absolute', bottom: -80, right: 200, width: 400, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,208,0.1) 0%, transparent 65%)' }} />

    {/* 좌측 수직선 */}
    <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 7, background: 'linear-gradient(180deg, #FF4336 0%, #FF9800 50%, #00FFD0 100%)' }} />

    {/* ── 좌측 텍스트 ── */}
    <div style={{ position: 'absolute', left: 56, top: 0, bottom: 0, width: 520, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <div style={{ background: '#FF4336', borderRadius: 6, padding: '5px 16px', fontSize: 20, fontWeight: 900, color: '#fff', letterSpacing: 2 }}>6월 15일</div>
        <div style={{ fontSize: 18, color: '#555' }}>실제 집행 시작</div>
      </div>

      <div style={{ fontSize: 86, fontWeight: 900, lineHeight: 0.95, letterSpacing: -3, color: '#fff', marginBottom: 4 }}>
        내일<span style={{ color: '#FF4336' }}>부터</span>
      </div>

      <div style={{ width: 480, height: 3, background: 'linear-gradient(90deg, #FF4336, #FF9800, #00FFD0, transparent)', margin: '14px 0 10px', borderRadius: 2 }} />

      <div style={{ fontSize: 78, fontWeight: 900, color: C.main, letterSpacing: -2, lineHeight: 1, textShadow: '0 0 30px rgba(0,255,208,0.4)' }}>
        국민성장펀드
      </div>

      <div style={{ marginTop: 10 }}>
        <span style={{ fontSize: 42, fontWeight: 900, color: '#777' }}>이것 때문에 </span>
        <span style={{ fontSize: 52, fontWeight: 900, color: '#fff' }}>기회입니다</span>
      </div>

    </div>

    {/* ── 우측 패널 ── */}
    <div style={{
      position: 'absolute', right: 0, top: 0, bottom: 0, width: 620,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: 12,
      borderLeft: '1px solid rgba(0,255,208,0.08)',
      overflow: 'hidden',
    }}>

      {/* LFP 공장 배경 — 살짝 모자이크(blur) */}
      <div style={{ position: 'absolute', inset: 0 }}>
        <Img
          src={staticFile('images/lfp_04.png')}
          style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(2px) brightness(0.2)', transform: 'scale(1.05)' }}
        />
      </div>

      {/* 뉴스 헤더 */}
      <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ background: 'rgba(0,255,208,0.12)', border: '1px solid rgba(0,255,208,0.3)', borderRadius: 20, padding: '4px 14px', fontSize: 13, color: C.main, fontWeight: 700 }}>📰 실시간 뉴스</div>
        <div style={{ fontSize: 13, color: '#444' }}>2026.05.31 최신순</div>
      </div>

      {/* 뉴스 카드들 */}
      <div style={{ position: 'relative', zIndex: 2, width: 540, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {HEADLINES.map(({ source, title, hot }, i) => (
          <div key={i} style={{
            background: 'rgba(0,0,0,0.8)',
            backdropFilter: 'blur(8px)',
            border: hot ? '1px solid rgba(255,67,54,0.5)' : '1px solid rgba(255,255,255,0.07)',
            borderRadius: 12,
            padding: '14px 18px',
            display: 'flex', gap: 12, alignItems: 'flex-start',
          }}>
            <div style={{ fontSize: 11, color: hot ? '#FF4336' : '#555', fontWeight: 700, minWidth: 50, marginTop: 2 }}>{source}</div>
            <div style={{ fontSize: hot ? 18 : 15, fontWeight: hot ? 800 : 500, color: hot ? '#fff' : '#888', lineHeight: 1.4 }}>{title}</div>
            {hot && <div style={{ marginLeft: 'auto', background: '#FF4336', borderRadius: 4, padding: '2px 8px', fontSize: 11, color: '#fff', fontWeight: 900, flexShrink: 0 }}>HOT</div>}
          </div>
        ))}
      </div>

      {/* LFP 공장 실사 카드 */}
      <div style={{ position: 'relative', zIndex: 2, width: 540, borderRadius: 12, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
        <Img
          src={staticFile('images/lfp_04.png')}
          style={{ width: '100%', height: 105, objectFit: 'cover', display: 'block' }}
        />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(0,0,0,0.7), rgba(0,0,0,0.2))' }} />
        <div style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)' }}>
          <div style={{ fontSize: 14, color: C.main, fontWeight: 800 }}>🏭 엘앤에프 LFP 양극재 공장</div>
          <div style={{ fontSize: 11, color: '#777', marginTop: 2 }}>국내 최초 · 2,200억 저리대출 5/28 승인</div>
        </div>
      </div>

    </div>

    <div style={{ position: 'absolute', bottom: 20, left: 56, fontSize: 16, color: '#333', fontWeight: 600, letterSpacing: 2 }}>
      로또의 주식인사이트
    </div>

  </AbsoluteFill>
);
