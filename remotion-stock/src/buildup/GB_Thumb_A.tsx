// GB_Thumb_A v2 — 국민성장펀드 강조 + 실사 인포그래픽 이미지
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { C, FONT } from '../constants';

export const GB_Thumb_A = () => (
  <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

    {/* ── 배경 글로우 ── */}
    <div style={{ position: 'absolute', top: -180, left: -80, width: 700, height: 600, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,67,54,0.15) 0%, transparent 65%)' }} />
    <div style={{ position: 'absolute', bottom: -100, right: 340, width: 500, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,208,0.12) 0%, transparent 65%)' }} />

    {/* ── 좌측 수직 강조선 ── */}
    <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 7, background: 'linear-gradient(180deg, #FF4336 0%, #FF9800 50%, #00FFD0 100%)' }} />

    {/* ── 좌측 메인 콘텐츠 ── */}
    <div style={{ position: 'absolute', left: 56, top: 0, bottom: 0, width: 760, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 0 }}>

      {/* 날짜 배지 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div style={{ background: '#FF4336', borderRadius: 6, padding: '5px 16px', fontSize: 20, fontWeight: 900, color: '#fff', letterSpacing: 2 }}>
          6월 15일
        </div>
        <div style={{ fontSize: 20, color: '#666', fontWeight: 600 }}>실제 집행 시작</div>
      </div>

      {/* 내일부터 */}
      <div style={{ fontSize: 96, fontWeight: 900, lineHeight: 0.95, letterSpacing: -3, color: '#fff' }}>
        내일<span style={{ color: '#FF4336' }}>부터</span>
      </div>

      {/* 구분선 */}
      <div style={{ width: 680, height: 3, background: 'linear-gradient(90deg, #FF4336 0%, #FF9800 40%, #00FFD0 80%, transparent 100%)', margin: '14px 0 10px', borderRadius: 2 }} />

      {/* 국민성장펀드 — 크게 강조 */}
      <div style={{
        fontSize: 110, fontWeight: 900, color: C.main,
        letterSpacing: -3, lineHeight: 1,
        textShadow: '0 0 40px rgba(0,255,208,0.45)',
      }}>
        국민성장펀드
      </div>

      {/* 이것 때문에 기회입니다 */}
      <div style={{ marginTop: 10 }}>
        <span style={{ fontSize: 52, fontWeight: 900, color: '#999', letterSpacing: -1 }}>이것 때문에 </span>
        <span style={{ fontSize: 64, fontWeight: 900, color: '#fff', letterSpacing: -1 }}>기회입니다</span>
      </div>


    </div>

    {/* ── 우측 실사 이미지 패널 ── */}
    <div style={{
      position: 'absolute', right: 0, top: 0, bottom: 0, width: 460,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(255,255,255,0.02)',
      borderLeft: '1px solid rgba(0,255,208,0.1)',
    }}>
      {/* 이미지 */}
      <div style={{ position: 'relative', width: 400, height: 540 }}>
        {/* 이미지 외곽 글로우 */}
        <div style={{
          position: 'absolute', inset: -4,
          borderRadius: 16,
          boxShadow: '0 0 30px rgba(0,255,208,0.25), 0 0 60px rgba(0,255,208,0.1)',
          border: '1.5px solid rgba(0,255,208,0.3)',
          pointerEvents: 'none',
          zIndex: 2,
        }} />
        <Img
          src={staticFile('images/fund_img_14.jpg')}
          style={{
            width: '100%', height: '100%',
            objectFit: 'cover',
            borderRadius: 12,
            display: 'block',
          }}
        />
        {/* 이미지 하단 그라디언트 (배경과 자연스럽게) */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 80,
          background: 'linear-gradient(transparent, rgba(0,0,0,0.6))',
          borderRadius: '0 0 12px 12px',
        }} />
      </div>
    </div>

    {/* 채널명 */}
    <div style={{ position: 'absolute', bottom: 20, left: 56, fontSize: 17, color: '#3a3a3a', fontWeight: 600, letterSpacing: 2 }}>
      로또의 주식인사이트
    </div>

  </AbsoluteFill>
);
