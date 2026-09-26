import React from 'react';
import {Composition} from 'remotion';
import {Guide, guideDuration, GuideProps} from './Guide';

export const Root: React.FC = () => (
  <Composition
    id="VertexGuide"
    component={Guide}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={300}
    defaultProps={{scenes: []} as GuideProps}
    calculateMetadata={({props}) => ({durationInFrames: guideDuration(props.scenes)})}
  />
);
