import {Theme} from './theme';

// 테크 테마의 코너 브래킷. draw(0→1)로 그려지는 길이 제어. warm 테마면 렌더 안 함.
export const Brackets: React.FC<{theme: Theme; draw: number}> = ({theme, draw}) => {
  if (!theme.brackets) return null;
  const t = 4;
  const len = 34 * draw;
  const corners = ['tl', 'tr', 'bl', 'br'] as const;
  return (
    <>
      {corners.map((c) => {
        const s: React.CSSProperties = {position: 'absolute', borderColor: theme.accent, borderStyle: 'solid', width: len, height: len, borderWidth: 0};
        if (c === 'tl') Object.assign(s, {top: -2, left: -2, borderTopWidth: t, borderLeftWidth: t});
        else if (c === 'tr') Object.assign(s, {top: -2, right: -2, borderTopWidth: t, borderRightWidth: t});
        else if (c === 'bl') Object.assign(s, {bottom: -2, left: -2, borderBottomWidth: t, borderLeftWidth: t});
        else Object.assign(s, {bottom: -2, right: -2, borderBottomWidth: t, borderRightWidth: t});
        return <span key={c} style={s} />;
      })}
    </>
  );
};
