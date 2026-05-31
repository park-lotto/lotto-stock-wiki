// GB_Thumb_B — 국민성장펀드 중앙 임팩트형 (흰/민트 강렬 대비)
import { AbsoluteFill } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const GB_Thumb_B = () => (
  <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

    {/* 배경: 중앙 민트 glow */}
    <div style={{ position: 'absolute', top: '30%', left: '50%', transform: 'translate(-50%,-50%)', width: 800, height: 500, borderRadius: '50%', background: 'radial-gradient(ellipse, rgba(0,255,208,0.1) 0%, transparent 70%)' }} />

    {/* 상단 배지 라인 */}
    <div style={{ position: 'absolute', top: 40, left: 64, right: 64, display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{ background: 'rgba(0,255,208,0.12)', border: '1.5px solid rgba(0,255,208,0.5)', borderRadius: 30, padding: '8px 24px', fontSize: 22, color: C.main, fontWeight: 800, letterSpacing: 2 }}>
        💰 국민성장펀드
      </div>
      <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(0,255,208,0.4), transparent)' }} />
    </div>

    {/* 메인 텍스트 블록 */}
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 0 }}>

      {/* 내일부터 */}
      <div style={{ fontSize: 88, fontWeight: 900, color: '#555', letterSpacing: 4, lineHeight: 1 }}>
        내일부터
      </div>

      {/* 큰 화살표 */}
      <div style={{ fontSize: 52, color: C.main, lineHeight: 1, margin: '4px 0' }}>↓</div>

      {/* 이것 때문에 */}
      <div style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: 1, lineHeight: 1 }}>
        이것 때문에
      </div>

      {/* 기회입니다 — BIGGEST */}
      <div style={{
        fontSize: 160, fontWeight: 900, color: C.main,
        textShadow: GLOW.strong.text,
        letterSpacing: -4, lineHeight: 0.9,
        marginTop: 4,
      }}>
        기회
      </div>
      <div style={{ fontSize: 72, fontWeight: 900, color: C.main, letterSpacing: -1, textShadow: GLOW.mid.text }}>
        입니다
      </div>

    </div>

    {/* 하단 수혜주 바 */}
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      height: 80,
      background: 'rgba(0,255,208,0.06)',
      borderTop: '1px solid rgba(0,255,208,0.2)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 40,
    }}>
      {[
        { emoji: '🏭', name: '엘앤에프', color: '#FF4336' },
        { emoji: '🔋', name: '에코프로비엠', color: '#FF9800' },
        { emoji: '⚡', name: '효성중공업·LS', color: C.main },
      ].map(({ emoji, name, color }) => (
        <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 24 }}>{emoji}</span>
          <span style={{ fontSize: 22, fontWeight: 700, color }}>{name}</span>
        </div>
      ))}
    </div>

    {/* 채널명 */}
    <div style={{ position: 'absolute', bottom: 90, right: 64, fontSize: 18, color: '#333', fontWeight: 600, letterSpacing: 2 }}>
      로또의 주식인사이트
    </div>

  </AbsoluteFill>
);
