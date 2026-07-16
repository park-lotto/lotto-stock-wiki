import {Composition} from 'remotion';
import {SwipeLeft} from './SwipeLeft';
import {Sparkle} from './Sparkle';
import {ImpactText} from './ImpactText';
import {CountCard} from './CountCard';
import {ListReveal} from './ListReveal';
import {CalloutCard} from './CalloutCard';
import {SceneRemotion} from './SceneRemotion';
import {FullReel} from './FullReel';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="SwipeLeft" component={SwipeLeft} durationInFrames={18} fps={30} width={720} height={1280} />
    <Composition id="Sparkle" component={Sparkle} durationInFrames={30} fps={30} width={300} height={300} />
    <Composition
      id="ImpactText"
      component={ImpactText}
      durationInFrames={45}
      fps={30}
      width={720}
      height={1280}
      defaultProps={{word: '쫀득하고 촉촉하니까'}}
    />
    <Composition
      id="CountCard"
      component={CountCard}
      durationInFrames={60}
      fps={30}
      width={720}
      height={1280}
      defaultProps={{label: 'COOKING · 소요시간', value: 5, suffix: '분', position: 'bottom'}}
    />
    <Composition
      id="ListReveal"
      component={ListReveal}
      durationInFrames={80}
      fps={30}
      width={720}
      height={1280}
      defaultProps={{title: '준비물 · READY', items: ['식초', '물감', '비닐풍선', '마법가루'], position: 'bottom'}}
    />
    <Composition
      id="CalloutCard"
      component={CalloutCard}
      durationInFrames={70}
      fps={30}
      width={720}
      height={1280}
      defaultProps={{icon: '🍓', name: '딸기 풍선', tag: '과학놀이 · DIY', position: 'bottom', from: 'right'}}
    />
    <Composition
      id="SceneRemotion"
      component={SceneRemotion}
      durationInFrames={120}
      fps={30}
      width={720}
      height={1280}
      defaultProps={{
        videoSrc: 'scene.mp4',
        header: 'STEP 02 · 준비물',
        tc: '00:09 · 00:13',
        caption: '식초에 물감 섞은 물을 비닐에 쏙',
        items: ['식초', '물감', '비닐풍선', '마법가루'],
      }}
    />
    <Composition
      id="FullReel"
      component={FullReel}
      durationInFrames={748}
      fps={30}
      width={720}
      height={1280}
      defaultProps={{
        videoSrc: 'full.mp4',
        sections: [
          {s: 0.0, e: 7.0, label: 'STEP 01 · 아이 반응'},
          {s: 7.0, e: 9.0, label: 'STEP 02 · 5분 완성'},
          {s: 9.0, e: 15.4, label: 'STEP 03 · 만들기'},
          {s: 15.4, e: 19.6, label: 'STEP 04 · 폭발'},
          {s: 19.6, e: 25.0, label: 'STEP 05 · 마무리'},
        ],
        beats: [
          {s: 0.0, e: 1.2, cap: '이거 만들어줬더니'},
          {s: 1.2, e: 3.2, cap: '딸이 "엄마 마법사야?"'},
          {s: 3.2, e: 5.2, cap: '비싼 장난감 사줘도 관심 없더니'},
          {s: 5.2, e: 7.0, cap: '이건 너무 좋아하는 거 있죠'},
          {s: 7.0, e: 9.0, cap: '간단한 재료로 5분이면 완성'},
          {s: 9.0, e: 11.2, cap: '식초에 물감 섞은 물을 비닐에 쏙'},
          {s: 11.2, e: 13.3, cap: '풍선 안에 숨기고 마법 가루를'},
          {s: 13.3, e: 15.4, cap: '풍선 안에 넣어 묶어주면 끝'},
          {s: 15.4, e: 17.5, cap: '팡 치면 풍선이 저절로 빵빵'},
          {s: 17.5, e: 19.6, cap: '과학 호기심 완전 폭발'},
          {s: 19.6, e: 21.6, cap: '재밌게 미술 공부까지'},
          {s: 21.6, e: 23.3, cap: '엄마표 교육놀이로 완전 딱'},
          {s: 23.3, e: 25.0, cap: '딸기 남겨주세요'},
        ],
        fx: [
          {s: 1.4, e: 3.2, comp: 'callout', props: {icon: '🍓', name: '딸기 풍선', tag: '과학놀이 · DIY', position: 'top', from: 'left'}},
          {s: 7.1, e: 9.0, comp: 'count', props: {label: 'COOKING · 소요시간', value: 5, suffix: '분', position: 'top'}},
          {s: 9.3, e: 13.2, comp: 'list', props: {title: '준비물 · READY', items: ['식초', '물감', '비닐풍선', '마법가루'], position: 'bottom'}},
          {s: 15.6, e: 17.4, comp: 'impact', props: {word: '팡!', position: 'top'}},
          {s: 17.7, e: 19.5, comp: 'impact', props: {word: '완전 폭발!', position: 'top'}},
          {s: 21.7, e: 23.2, comp: 'callout', props: {icon: '✨', name: '교육놀이', tag: '완전 딱!', position: 'bottom', from: 'right'}},
          {s: 23.4, e: 25.0, comp: 'impact', props: {word: '딸기 남겨주세요', position: 'top'}},
        ],
      }}
    />
  </>
);
