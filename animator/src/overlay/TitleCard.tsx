import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT_STACK} from '../fonts';
import type {Timeline} from '../types';

/** Reddit-style post card shown over the hook line. */
export const TitleCard: React.FC<{title: string; subreddit?: string; timeline: Timeline}> = ({title, subreddit, timeline}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const hook = timeline.beats[0];
	if (!hook) {
		return null;
	}
	const showUntil = hook.end + 0.35;
	const outFrame = Math.round(showUntil * fps);
	if (frame > outFrame + 10) {
		return null;
	}
	const enter = spring({frame: frame - 2, fps, config: {damping: 13, stiffness: 160}});
	const exit = interpolate(frame, [outFrame, outFrame + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const y = interpolate(enter, [0, 1], [-420, 0]) - exit * 420;
	const sub = subreddit ? `r/${subreddit.replace(/^r\//i, '')}` : 'r/story';

	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					top: 150,
					left: 70,
					right: 70,
					transform: `translateY(${y}px) rotate(${-1.5 + enter * 1.5}deg)`,
					background: '#ffffff',
					borderRadius: 34,
					border: '6px solid #1d1720',
					boxShadow: '0 14px 0 rgba(0,0,0,0.35)',
					padding: '30px 36px 34px',
					fontFamily: 'Helvetica Neue, Arial, sans-serif',
				}}
			>
				<div style={{display: 'flex', alignItems: 'center', gap: 18}}>
					<div
						style={{
							width: 74,
							height: 74,
							borderRadius: 37,
							background: '#ff4500',
							border: '5px solid #1d1720',
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							color: '#fff',
							fontFamily: FONT_STACK,
							fontSize: 34,
						}}
					>
						r/
					</div>
					<div style={{display: 'flex', flexDirection: 'column'}}>
						<div style={{fontWeight: 800, fontSize: 38, color: '#1d1720'}}>{sub}</div>
						<div style={{fontSize: 28, color: '#6b6b76'}}>u/OP · story time</div>
					</div>
				</div>
				<div style={{marginTop: 20, fontFamily: FONT_STACK, fontSize: 54, lineHeight: 1.12, color: '#1d1720'}}>{title}</div>
			</div>
		</AbsoluteFill>
	);
};
