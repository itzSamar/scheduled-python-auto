import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Screenplay, Timeline} from '../types';

const MOOD_COLORS: Record<string, [string, string]> = {
	funny: ['#ffcf3f', '#ff7a45'],
	dramatic: ['#e04848', '#2b1d3a'],
	tense: ['#3a3f8f', '#11131f'],
	wholesome: ['#7dd87d', '#ffd36e'],
};

const WHIP_HALF = 0.22;
const FADE_HALF = 0.3;

/** Covers each scene cut: a fade through black for time skips, otherwise a diagonal whip. */
export const Transitions: React.FC<{timeline: Timeline; screenplay: Screenplay}> = ({timeline, screenplay}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	const i = timeline.scenes.findIndex((s, k) => k > 0 && Math.abs(t - s.start) <= Math.max(WHIP_HALF, FADE_HALF));
	if (i <= 0) {
		return null;
	}
	const cut = timeline.scenes[i];
	const timeSkip = screenplay.scenes[i]?.timeOfDay !== screenplay.scenes[i - 1]?.timeOfDay;

	if (timeSkip) {
		const opacity = interpolate(Math.abs(t - cut.start), [0, FADE_HALF * 0.35, FADE_HALF], [1, 1, 0], {extrapolateRight: 'clamp'});
		return <AbsoluteFill style={{backgroundColor: '#000000', opacity, pointerEvents: 'none'}} />;
	}
	if (Math.abs(t - cut.start) > WHIP_HALF) {
		return null;
	}
	const [main, accent] = MOOD_COLORS[screenplay.mood] ?? MOOD_COLORS.funny;
	const p = interpolate(t, [cut.start - WHIP_HALF, cut.start + WHIP_HALF], [0, 1], {easing: Easing.inOut(Easing.cubic)});
	const panelW = width * 2;
	const left = interpolate(p, [0, 1], [width * 1.15, -panelW - width * 0.15]);
	return (
		<AbsoluteFill style={{overflow: 'hidden', pointerEvents: 'none'}}>
			<div style={{position: 'absolute', top: -200, bottom: -200, left: left + 120, width: panelW, background: accent, transform: 'skewX(-12deg)'}} />
			<div style={{position: 'absolute', top: -200, bottom: -200, left, width: panelW - 120, background: main, transform: 'skewX(-12deg)'}} />
		</AbsoluteFill>
	);
};
