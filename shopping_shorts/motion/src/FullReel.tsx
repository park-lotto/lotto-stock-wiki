import {AbsoluteFill, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ImpactText} from './ImpactText';
import {CountCard} from './CountCard';
import {ListReveal} from './ListReveal';
import {CalloutCard} from './CalloutCard';
import {resolveTheme, Theme} from './theme';

// 완성작: 릴스 한 편 전체를 씬별 리모션으로 재구성. themeName으로 장르별 톤 교체.
const FX: Record<string, React.FC<any>> = {impact: ImpactText, count: CountCard, list: ListReveal, callout: CalloutCard};

export type FullReelProps = {
  videoSrc: string;
  sections: {s: number; e: number; label: string}[];
  beats: {s: number; e: number; cap: string}[];
  fx: {s: number; e: number; comp: string; props: Record<string, unknown>}[];
  themeName?: string;
};

const mono = '"Consolas","Courier New",monospace';

const Header: React.FC<{label: string; t: Theme}> = ({label, t}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', top: 40, left: 36, opacity: o, transform: `translateX(${(1 - o) * -18}px)`, display: 'flex', alignItems: 'center', gap: 10}}>
      <span style={{width: 26, height: 3, background: t.accent, boxShadow: `0 0 8px ${t.accent}`}} />
      <span style={{fontFamily: t.labelMono ? mono : t.heading, fontSize: 21, letterSpacing: t.labelMono ? '0.22em' : '0.02em', color: '#fff', fontWeight: 700, textShadow: '0 1px 6px rgba(0,0,0,0.7)'}}>{label}</span>
    </div>
  );
};

const Caption: React.FC<{text: string; t: Theme}> = ({text, t}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 64, display: 'flex', justifyContent: 'center', opacity: o, padding: '0 40px'}}>
      <span style={{fontFamily: t.heading, fontSize: 33, fontWeight: 700, color: '#fff', padding: '7px 18px', background: 'rgba(0,0,0,0.42)', borderRadius: t.brackets ? 6 : 14, textAlign: 'center', textShadow: '0 2px 8px rgba(0,0,0,0.85)', maxWidth: '92%'}}>{text}</span>
    </div>
  );
};

export const FullReel: React.FC<FullReelProps> = ({videoSrc, sections, beats, fx, themeName = 'tech'}) => {
  const t = resolveTheme(themeName);
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const prog = frame / durationInFrames;
  const fr = (x: number) => Math.round(x * fps);

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <OffthreadVideo src={staticFile(videoSrc)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0) 18%, rgba(0,0,0,0) 66%, rgba(0,0,0,0.7) 100%)'}} />

      <div style={{position: 'absolute', top: 0, left: 0, height: 5, width: `${prog * 100}%`, background: t.accent, boxShadow: `0 0 10px ${t.accent}`}} />
      <div style={{position: 'absolute', top: 40, right: 36, fontFamily: mono, fontSize: 19, letterSpacing: '0.16em', color: t.accent, opacity: 0.9, textShadow: '0 1px 4px rgba(0,0,0,0.7)'}}>
        {String(Math.floor(frame / fps / 60)).padStart(2, '0')}:{String(Math.floor(frame / fps) % 60).padStart(2, '0')}
      </div>

      {sections.map((s, i) => (
        <Sequence key={`s${i}`} from={fr(s.s)} durationInFrames={fr(s.e) - fr(s.s)} name={`sec:${s.label}`}>
          <Header label={s.label} t={t} />
        </Sequence>
      ))}

      {beats.map((b, i) => (
        <Sequence key={`b${i}`} from={fr(b.s)} durationInFrames={fr(b.e) - fr(b.s)} name={`cap:${i}`}>
          <Caption text={b.cap} t={t} />
        </Sequence>
      ))}

      {fx.map((x, i) => {
        const Comp = FX[x.comp];
        if (!Comp) return null;
        return (
          <Sequence key={`f${i}`} from={fr(x.s)} durationInFrames={fr(x.e) - fr(x.s)} name={`fx:${x.comp}`}>
            <Comp {...x.props} theme={themeName} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
