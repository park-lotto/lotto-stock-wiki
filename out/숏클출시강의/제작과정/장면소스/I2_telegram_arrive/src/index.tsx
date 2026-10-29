import React from 'react';
import {registerRoot, Composition} from 'remotion';
import {Main} from './Main';
const Root = () => <Composition id="Main" component={Main} durationInFrames={360} fps={30} width={1920} height={1080} />;
registerRoot(Root);
