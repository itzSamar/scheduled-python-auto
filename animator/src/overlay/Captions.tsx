import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT_STACK} from '../fonts';
import type {Character, Timeline, TimelineBeat, Word} from '../types';

type Chunk = {words: Word[]; start: number; end: number; beat: TimelineBeat};

const MAX_WORDS = 3;
const MAX_CHARS = 14;
const HOLD_AFTER = 0.3;

const buildChunks = (tl: Timeline): Chunk[] => {
	const out: Chunk[] = [];
	tl.beats.forEach((beat, bi) => {
		const nextStart = tl.beats[bi + 1]?.start ?? tl.duration;
		const words = beat.words.filter((w) => w.text.trim().length > 0);
		const groups: Word[][] = [];
		let cur: Word[] = [];
		for (const w of words) {
			const chars = cur.reduce((n, x) => n + x.text.length + 1, 0) + w.text.length;
			if (cur.length && (cur.length >= MAX_WORDS || chars > MAX_CHARS)) {
				groups.push(cur);
				cur = [];
			}
			cur.push(w);
			if (/[.!?,;:]["')]?$/.test(w.text)) {
				groups.push(cur);
				cur = [];
			}
		}
		if (cur.length) {
			groups.push(cur);
		}
		groups.forEach((g, gi) => {
			const start = g[0].start;
			const end = gi < groups.length - 1 ? groups[gi + 1][0].start : Math.min(beat.end + HOLD_AFTER, nextStart);
			out.push({words: g, start, end: Math.max(end, start + 0.12), beat});
		});
	});
	return out;
};

const HIGHLIGHT = '#ffe14d';

export const Captions: React.FC<{timeline: Timeline; characters: Character[]}> = ({timeline, characters}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const chunks = useMemo(() => buildChunks(timeline), [timeline]);
	const chunk = chunks.find((c) => t >= c.start && t < c.end);
	if (!chunk) {
		return null;
	}
	const pop = spring({frame: Math.round((t - chunk.start) * fps), fps, config: {damping: 14, stiffness: 220, mass: 0.6}});
	const scale = interpolate(pop, [0, 1], [0.78, 1]);
	const speaker = chunk.beat.narration ? null : characters.find((c) => c.id === chunk.beat.speaker);
	let active = -1;
	chunk.words.forEach((w, i) => {
		if (t >= w.start) {
			active = i;
		}
	});

	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					top: '66%',
					left: 60,
					right: 60,
					transform: `translateY(-50%) scale(${scale})`,
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					gap: 18,
				}}
			>
				{speaker ? (
					<div
						style={{
							fontFamily: FONT_STACK,
							fontSize: 40,
							letterSpacing: 2,
							color: '#ffffff',
							background: speaker.look.outfitColor,
							border: '5px solid #1d1720',
							borderRadius: 999,
							padding: '6px 26px 4px',
							textTransform: 'uppercase',
							boxShadow: '0 6px 0 rgba(0,0,0,0.35)',
						}}
					>
						{speaker.name}
					</div>
				) : null}
				<div
					style={{
						fontFamily: FONT_STACK,
						fontSize: 98,
						lineHeight: 1.08,
						textAlign: 'center',
						textTransform: 'uppercase',
						letterSpacing: 1,
						display: 'flex',
						flexWrap: 'wrap',
						justifyContent: 'center',
						columnGap: 30,
					}}
				>
					{chunk.words.map((w, i) => {
						const on = i === active;
						return (
							<span
								key={i}
								style={{
									color: on ? HIGHLIGHT : '#ffffff',
									WebkitTextStroke: '16px #1d1720',
									paintOrder: 'stroke fill',
									textShadow: '0 8px 0 rgba(0,0,0,0.45)',
									transform: on ? 'scale(1.04) rotate(-2deg)' : undefined,
									display: 'inline-block',
									opacity: i <= active || active === -1 ? 1 : 0.92,
								}}
							>
								{w.text}
							</span>
						);
					})}
				</div>
			</div>
		</AbsoluteFill>
	);
};
