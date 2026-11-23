import React, {useMemo} from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT_STACK, useStoryFont} from '../fonts';
import {TownScene} from './TownScene';
import type {TownProps, TownWord} from './types';

const cleanWord = (value: string) => value.replace(/[.,?!'"]/g, '');

const chunksOf = (words: TownWord[]) => {
	const chunks: {text: string; start: number; end: number}[] = [];
	let i = 0;
	while (i < words.length) {
		const word = words[i];
		const next = words[i + 1];
		const nextIsGta = !!next && /^gta$/i.test(cleanWord(next.text));
		const pairGta = !!next && /^gta$/i.test(cleanWord(word.text)) && /^6$/.test(cleanWord(next.text));
		const endsSentence = /[.?!]/.test(word.text);
		const shortPair = !!next && !endsSentence && !nextIsGta && !pairGta && cleanWord(word.text).length + cleanWord(next.text).length <= 12;
		const take = pairGta || shortPair ? 2 : 1;
		const slice = words.slice(i, i + take);
		chunks.push({text: slice.map((w) => w.text).join(' '), start: slice[0].start, end: slice[slice.length - 1].end});
		i += take;
	}
	return chunks;
};

const Caption: React.FC<{words: TownWord[]}> = ({words}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const chunks = useMemo(() => chunksOf(words), [words]);
	const chunk = chunks.find((c, i) => t >= c.start && t < (chunks[i + 1]?.start ?? c.end + 0.45));
	if (!chunk) {
		return null;
	}
	const shown = chunk.text.replace(/[.,]/g, '').replace(/\s+/g, ' ').trim().toUpperCase();
	const startFrame = Math.round(chunk.start * fps);
	const pop = interpolate(frame, [startFrame, startFrame + 5], [0.82, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const size = shown.length > 16 ? 78 : shown.length > 10 ? 100 : 124;
	return (
		<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', pointerEvents: 'none'}}>
			<div
				style={{
					transform: `scale(${pop})`,
					marginTop: 80,
					maxWidth: 960,
					textAlign: 'center',
					fontFamily: FONT_STACK,
					fontSize: size,
					lineHeight: 0.92,
					color: '#ffffff',
					WebkitTextStroke: '16px #111111',
					paintOrder: 'stroke fill',
					letterSpacing: -1,
					textShadow: '0 8px 0 #111111',
				}}
			>
				{shown}
			</div>
		</AbsoluteFill>
	);
};

export const InThisTown: React.FC<TownProps> = ({shots, words}) => {
	useStoryFont();
	const {fps, durationInFrames} = useVideoConfig();
	return (
		<AbsoluteFill style={{backgroundColor: '#8ecbff'}}>
			{shots.map((shot, i) => {
				const from = Math.round(shot.start * fps);
				const next = shots[i + 1];
				const to = next ? Math.round(next.start * fps) : durationInFrames;
				if (to <= from) {
					return null;
				}
				return (
					<Sequence key={`${shot.set}-${i}`} from={from} durationInFrames={to - from} name={shot.set}>
						<TownScene set={shot.set} />
					</Sequence>
				);
			})}
			<Caption words={words} />
		</AbsoluteFill>
	);
};
