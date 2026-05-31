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
    <div style={{ position: 'absolute', left: 56, top: 0, bottom: 0, width: 660, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 0 }}>

      {/* 날짜 배지 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div style={{ background: '#FF4336', borderRadius: 6, padding: '5px 16px', fontSize: 20, fontWeight: 900, color: '#fff', letterSpacing: 2 }}>
          6월 15일
        </div>
        <div style={{ fontSize: 20, color: '#666', fontWeight: 600 }}>실제 집행 시작</div>
        <div style={{ background: 'transparent', border: '1.5px solid #00FFD0', borderRadius: 6, padding: '5px 14px', fontSize: 18, fontWeight: 900, color: '#00FFD0', letterSpacing: 2 }}>
          확정
        </div>
      </div>

      {/* 내일부터 */}
      <div style={{ fontSize: 96, fontWeight: 900, lineHeight: 0.95, letterSpacing: -3, color: '#fff' }}>
        오늘<span style={{ color: '#FF4336' }}>부터</span>
      </div>

      {/* 구분선 */}
      <div style={{ width: 580, height: 3, background: 'linear-gradient(90deg, #FF4336 0%, #FF9800 40%, #00FFD0 80%, transparent 100%)', margin: '14px 0 10px', borderRadius: 2 }} />

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

    {/* ── 우측 실사 이미지 — 풀블리드 ── */}
    <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 580, overflow: 'hidden' }}>

      {/* 실사 이미지 */}
      <Img
        src={staticFile('images/배터리공장.png')}
        style={{
          width: '100%', height: '100%',
          objectFit: 'cover',
          display: 'block',
          filter: 'brightness(0.85) contrast(1.2) saturate(1.1)',
        }}
      />

      {/* 민트 색조 오버레이 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(0,255,208,0.07)',
      }} />

      {/* 스캔라인 */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.1) 0px, rgba(0,0,0,0.1) 1px, transparent 1px, transparent 3px)',
      }} />

      {/* 좌측 페이드 — 텍스트와 자연스럽게 블렌드 */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(90deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.4) 30%, transparent 60%)',
      }} />

      {/* 상단 페이드 */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 120,
        background: 'linear-gradient(rgba(0,0,0,0.5), transparent)',
      }} />

      {/* 하단 페이드 */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 120,
        background: 'linear-gradient(transparent, rgba(0,0,0,0.6))',
      }} />

    </div>

    {/* STOCK BRAIN 로고 */}
    <div style={{ position: 'absolute', bottom: 20, left: 56, display: 'flex', alignItems: 'center', gap: 0 }}>
      {/* 왼쪽 민트 액센트 바 */}
      <div style={{ width: 4, height: 36, background: '#00FFD0', borderRadius: 2, marginRight: 12, boxShadow: '0 0 10px #00FFD0, 0 0 20px rgba(0,255,208,0.6)' }} />
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
        <div style={{
          fontSize: 22, fontWeight: 900, color: '#00FFD0', letterSpacing: 6,
          textShadow: '0 0 10px #00FFD0, 0 0 25px rgba(0,255,208,0.7), 0 0 50px rgba(0,255,208,0.4)',
        }}>STOCK BRAIN</div>
      </div>
    </div>

  </AbsoluteFill>
);
