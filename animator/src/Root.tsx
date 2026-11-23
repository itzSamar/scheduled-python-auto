import React from 'react';
import {Composition, type CalculateMetadataFunction} from 'remotion';
import sample from './sample/episode.json';
import {StoryShort} from './StoryShort';
import type {EpisodeProps} from './types';

const FPS = 30;

const calculateMetadata: CalculateMetadataFunction<EpisodeProps> = ({props}) => ({
	durationInFrames: Math.max(1, Math.ceil(props.timeline.duration * FPS)),
});

export const Root: React.FC = () => (
	<Composition
		id="StoryShort"
		component={StoryShort}
		width={1080}
		height={1920}
		fps={FPS}
		durationInFrames={FPS * 60}
		defaultProps={sample as unknown as EpisodeProps}
		calculateMetadata={calculateMetadata}
	/>
);
