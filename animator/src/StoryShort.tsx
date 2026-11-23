import React from 'react';
import {AbsoluteFill, Html5Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {useStoryFont} from './fonts';
import {Captions} from './overlay/Captions';
import {TitleCard} from './overlay/TitleCard';
import {Transitions} from './overlay/Transitions';
import {SceneView} from './scene/SceneView';
import type {EpisodeProps, SceneStyle} from './types';

/** "mixed" alternates 3D and 2D scenes, opening in 3D. */
export const sceneStyle = (style: EpisodeProps['style'], sceneIndex: number): SceneStyle =>
	style === 'mixed' ? (sceneIndex % 2 === 0 ? '3d' : '2d') : style;

export const StoryShort: React.FC<EpisodeProps> = (props) => {
	useStoryFont();
	const {fps, durationInFrames} = useVideoConfig();
	const {timeline, screenplay} = props;
	const audio = props.audioSrc ? (/^(https?:|data:|blob:)/.test(props.audioSrc) ? props.audioSrc : staticFile(props.audioSrc)) : null;

	return (
		<AbsoluteFill style={{backgroundColor: '#000000'}}>
			{timeline.scenes.map((s, i) => {
				const from = Math.round(s.start * fps);
				const next = timeline.scenes[i + 1];
				const to = next ? Math.round(next.start * fps) : durationInFrames;
				if (to <= from || !screenplay.scenes[i]) {
					return null;
				}
				return (
					<Sequence key={i} from={from} durationInFrames={to - from} name={`Scene ${i + 1}: ${screenplay.scenes[i].location}`}>
						<SceneView episode={props} sceneIndex={i} mode={sceneStyle(props.style, i)} />
					</Sequence>
				);
			})}
			<Transitions timeline={timeline} screenplay={screenplay} />
			<TitleCard title={screenplay.title} subreddit={props.subreddit} timeline={timeline} />
			<Captions timeline={timeline} characters={screenplay.characters} />
			{audio ? <Html5Audio src={audio} /> : null}
		</AbsoluteFill>
	);
};
