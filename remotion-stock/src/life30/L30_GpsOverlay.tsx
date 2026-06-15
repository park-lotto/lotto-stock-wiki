/**
 * L30_GpsOverlay — GPS 좌표 오버레이
 *
 * 영상 레퍼런스: frame 0160
 *   위치: 우상단
 *   형식:
 *     LAT  37.7749° N
 *     LNG  122.4194° W
 *     SAN FRANCISCO · CA
 */

import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { L30C, L30G, L30V } from './L30_constants';

interface L30_GpsOverlayProps {
  showAt?: number;
  lat?:    string;   // "37.7749° N"
  lng?:    string;   // "122.4194° W"
  city?:   string;   // "SAN FRANCISCO · CA"
}

export const L30_GpsOverlay: React.FC<L30_GpsOverlayProps> = ({
  showAt = 0,
  lat    = '37.7749° N',
  lng    = '122.4194° W',
  city   = 'SAN FRANCISCO · CA',
}) => {
  const f  = useCurrentFrame();
  const op = interpolate(f, [showAt, showAt + 16], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const tx = interpolate(op, [0, 1], [14, 0]);

  const mono: React.CSSProperties = {
    fontFamily:    L30C.fontMono,
    fontSize:      10,
    fontWeight:    400,
    letterSpacing: '2px',
    color:         L30C.lime,
    lineHeight:    1.8,
    textShadow:    L30G.lime.text,
  };

  return (
    <div style={{
      position:  'absolute',
      top:       28,
      right:     L30V.PAD,
      opacity:   op,
      transform: `translateX(${tx}px)`,
      textAlign: 'right',
      pointerEvents: 'none',
    }}>
      <div style={mono}>
        <span style={{ opacity: 0.55 }}>LAT</span>{'  '}{lat}
      </div>
      <div style={mono}>
        <span style={{ opacity: 0.55 }}>LNG</span>{'  '}{lng}
      </div>
      <div style={{
        ...mono,
        fontSize:      9,
        letterSpacing: '3px',
        textTransform: 'uppercase',
        marginTop:     4,
        opacity:       0.75,
      }}>
        {city}
      </div>
    </div>
  );
};
