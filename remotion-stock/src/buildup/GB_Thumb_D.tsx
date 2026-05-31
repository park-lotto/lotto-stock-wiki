// GB_Thumb_D — 달력 6/15 버전 + LFP 공장 실사 (살짝 모자이크)
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { C, FONT } from '../constants';

const CAL_DAYS = [
  [null, null, null, null, null, null,  1],
  [2,    3,    4,    5,    6,    7,    8],
  [9,   10,   11,   12,   13,   14,   15],
  [16,  17,   18,   19,   20,   21,   22],
  [23,  24,   25,   26,   27,   28,   29],
  [30, null, null, null, null, null, null],
];
const DOW = ['일','월','화','수','목','금','토'];

export const GB_Thumb_D = () => (
  <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

    {/* 배경 글로우 */}
    <div style={{ position: 'absolute', top: -150, left: -80, width: 600, height: 500, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,67,54,0.14) 0%, transparent 65%)' }} />
    <div style={{ position: 'absolute', bottom: -80, left: 300, width: 400, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,208,0.1) 0%, transparent 65%)' }} />

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
      gap: 16,
      borderLeft: '1px solid rgba(0,255,208,0.08)',
      overflow: 'hidden',
    }}>

      {/* LFP 공장 실사 — 배경으로 살짝 블러 */}
      <div style={{ position: 'absolute', inset: 0 }}>
        <Img
          src={staticFile('images/lfp_04.png')}
          style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'blur(3px) brightness(0.25)', transform: 'scale(1.05)' }}
        />
      </div>

      {/* 달력 (전경) */}
      <div style={{
        position: 'relative', zIndex: 2,
        background: 'rgba(0,0,0,0.75)',
        backdropFilter: 'blur(4px)',
        border: '1px solid rgba(0,255,208,0.2)',
        borderRadius: 20,
        padding: '18px 22px',
        width: 520,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', letterSpacing: 2 }}>2026년 6월</div>
          <div style={{ background: 'rgba(0,255,208,0.12)', border: '1px solid rgba(0,255,208,0.4)', borderRadius: 20, padding: '3px 12px', fontSize: 12, color: C.main, fontWeight: 700 }}>집행 시작월</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, marginBottom: 5 }}>
          {DOW.map((d, i) => (
            <div key={d} style={{ textAlign: 'center', fontSize: 12, fontWeight: 700, color: i === 0 ? '#FF4336' : i === 6 ? '#4A90E2' : '#444', padding: '3px 0' }}>{d}</div>
          ))}
        </div>

        {CAL_DAYS.map((week, wi) => (
          <div key={wi} style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, marginBottom: 3 }}>
            {week.map((day, di) => {
              const isTarget = day === 15;
              const isSun = di === 0;
              const isSat = di === 6;
              return (
                <div key={di} style={{
                  textAlign: 'center', padding: '7px 0',
                  borderRadius: isTarget ? '50%' : 5,
                  background: isTarget ? 'rgba(0,255,208,0.2)' : 'transparent',
                  border: isTarget ? '2px solid rgba(0,255,208,0.8)' : '1px solid transparent',
                  boxShadow: isTarget ? '0 0 16px rgba(0,255,208,0.5)' : 'none',
                }}>
                  <span style={{
                    fontSize: isTarget ? 20 : 14,
                    fontWeight: isTarget ? 900 : 400,
                    color: day === null ? 'transparent' : isTarget ? C.main : isSun ? '#FF4336' : isSat ? '#4A90E2' : '#666',
                  }}>
                    {day ?? '·'}
                  </span>
                  {isTarget && <div style={{ fontSize: 8, color: C.main, fontWeight: 700 }}>집행</div>}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* LFP 공장 실사 작은 카드 */}
      <div style={{ position: 'relative', zIndex: 2, width: 520, borderRadius: 14, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
        <Img
          src={staticFile('images/lfp_04.png')}
          style={{ width: '100%', height: 110, objectFit: 'cover', display: 'block' }}
        />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(0,0,0,0.6), transparent)' }} />
        <div style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)' }}>
          <div style={{ fontSize: 13, color: C.main, fontWeight: 700 }}>엘앤에프</div>
          <div style={{ fontSize: 11, color: '#888' }}>국내 최초 LFP 양극재 공장</div>
        </div>
      </div>

    </div>

    <div style={{ position: 'absolute', bottom: 20, left: 56, fontSize: 16, color: '#333', fontWeight: 600, letterSpacing: 2 }}>
      로또의 주식인사이트
    </div>

  </AbsoluteFill>
);
