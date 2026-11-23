import React from 'react';
import {shade} from '../lib/colors';
import type {Look} from '../types';
import {Face} from './Face';
import {FlatEllipse, FlatHalfDisc, FlatLimb, FlatPoly, FlatRect} from './flat';
import {outfitColors, type OutfitColors} from './outfit';
import {armChain, type ArmPose} from './poses';
import type {CharState} from './state';

const HEAD_R = 0.29;
const HIP_Y = 0.42;
const HEAD_LOCAL_Y = 0.88;

/** Hairline/bangs shape over the top of the head (head-radius units). */
const capPoints = (depth: number, scallops: number): [number, number][] => {
	const pts: [number, number][] = [];
	for (let i = 0; i <= 24; i++) {
		const a = 0.12 + (i / 24) * (Math.PI - 0.24);
		pts.push([Math.cos(a) * 1.07, Math.sin(a) * 1.07]);
	}
	for (let i = 0; i <= 20; i++) {
		const x = -0.98 + (i / 20) * 1.96;
		const y = depth + 0.07 * Math.abs(Math.sin((i / 20) * Math.PI * scallops));
		pts.push([x, y]);
	}
	return pts;
};

const scaled = (pts: [number, number][], s: number): [number, number][] => pts.map(([x, y]) => [x * s, y * s]);

const Hair2D: React.FC<{look: Look; hasCap: boolean}> = ({look, hasCap}) => {
	const c = look.hairColor;
	const R = HEAD_R;
	const bangs = (depth: number, scallops: number) =>
		hasCap ? null : <FlatPoly id={`bangs:${depth}:${scallops}`} pts={scaled(capPoints(depth, scallops), R)} color={c} z={0.003} outlineScale={1.0} />;
	const back = (node: React.ReactNode) => <group position={[0, 0, -0.03]}>{node}</group>;
	switch (look.hair) {
		case 'bald':
			return back(
				<>
					<FlatEllipse x={-R * 0.95} y={0.0} w={0.09} h={0.16} color={c} />
					<FlatEllipse x={R * 0.95} y={0.0} w={0.09} h={0.16} color={c} />
				</>,
			);
		case 'long':
			return (
				<>
					{back(<FlatRect y={-0.08} w={R * 2.5} h={R * 2.6} r={R * 1.1} color={c} />)}
					{bangs(0.38, 2)}
				</>
			);
		case 'bun':
			return (
				<>
					{back(<FlatEllipse y={R * 1.15} w={0.26} h={0.24} color={c} />)}
					{back(<FlatEllipse w={R * 2.2} h={R * 2.2} color={c} />)}
					{bangs(0.48, 1)}
				</>
			);
		case 'ponytail':
			return (
				<>
					{back(<FlatEllipse x={R * 1.05} y={-0.06} w={0.16} h={0.36} color={c} />)}
					{back(<FlatEllipse w={R * 2.2} h={R * 2.2} color={c} />)}
					{bangs(0.45, 2)}
				</>
			);
		case 'curly':
			return (
				<>
					{back(
						<>
							{Array.from({length: 9}).map((_, i) => {
								const a = (i / 8) * Math.PI;
								return <FlatEllipse key={i} x={Math.cos(a) * R * 0.98} y={R * 0.15 + Math.sin(a) * R * 0.9} w={0.19} h={0.19} color={c} />;
							})}
						</>,
					)}
					{bangs(0.4, 4)}
				</>
			);
		case 'spiky':
			return (
				<>
					{hasCap
						? null
						: back(
								<FlatPoly
									id="spikes"
									pts={[
										[-R * 1.0, R * 0.3],
										[-R * 0.8, R * 1.35],
										[-R * 0.45, R * 0.95],
										[-R * 0.15, R * 1.5],
										[R * 0.15, R * 1.0],
										[R * 0.5, R * 1.45],
										[R * 0.75, R * 0.9],
										[R * 1.05, R * 1.2],
										[R * 1.0, R * 0.3],
									]}
									color={c}
								/>,
							)}
					{bangs(0.55, 3)}
				</>
			);
		case 'bob':
			return (
				<>
					{back(<FlatRect y={-0.02} w={R * 2.45} h={R * 2.3} r={R * 1.0} color={c} />)}
					{bangs(0.3, 1)}
				</>
			);
		case 'short':
		default:
			return (
				<>
					{back(<FlatEllipse y={R * 0.08} w={R * 2.2} h={R * 2.15} color={c} />)}
					{bangs(0.5, 2)}
				</>
			);
	}
};

const Arm2D: React.FC<{side: number; arm: ArmPose; colors: OutfitColors; skin: string; shoulderUp: number}> = ({
	side,
	arm,
	colors,
	skin,
	shoulderUp,
}) => {
	const sx = side * 0.255;
	const sy = 0.5 + shoulderUp;
	const r = arm.reach ?? 1;
	const {elbow, hand} = armChain(arm, side, 0.25 * r, 0.22 * r);
	const front = hand.z > 0.04;
	const z = front ? 0.03 : -0.012;
	const e: [number, number] = [sx + elbow.x, sy + elbow.y];
	const h: [number, number] = [sx + hand.x, sy + hand.y];
	return (
		<group>
			<FlatLimb from={[sx, sy]} to={e} radius={0.062} color={colors.sleeve} z={z} />
			<FlatLimb from={e} to={h} radius={0.056} color={colors.forearm} z={z + 0.004} />
			<FlatEllipse x={h[0]} y={h[1]} z={z + 0.008} w={0.13} h={0.13} color={skin} />
		</group>
	);
};

const Torso2D: React.FC<{look: Look; colors: OutfitColors; female: boolean}> = ({look, colors, female}) => {
	const w = female ? 0.44 : 0.5;
	const o = look.outfit;
	return (
		<group>
			<FlatRect y={0.66} z={-0.004} w={0.13} h={0.14} r={0.04} color={look.skin} />
			{o === 'hoodie' ? <FlatEllipse y={0.6} z={-0.006} w={0.42} h={0.18} color={colors.accent} /> : null}
			<FlatRect y={0.31} w={w} h={0.62} r={0.16} color={colors.torso} />
			{o === 'dress' ? (
				<FlatPoly
					id={`skirt:${female}`}
					pts={[
						[-w * 0.46, 0.12],
						[w * 0.46, 0.12],
						[0.36, -0.28],
						[-0.36, -0.28],
					]}
					color={look.outfitColor}
					z={0.004}
					outlineScale={1.05}
				/>
			) : null}
			{o === 'hoodie' ? <FlatRect y={0.14} z={0.006} w={0.28} h={0.1} r={0.03} color={colors.accent} /> : null}
			{o === 'suit' ? (
				<>
					<FlatPoly
						id="suitV"
						pts={[
							[-0.09, 0.6],
							[0.09, 0.6],
							[0, 0.32],
						]}
						color="#f4f4f4"
						z={0.006}
						outlineScale={1.0}
					/>
					<FlatRect y={0.44} z={0.008} w={0.05} h={0.2} r={0.02} color="#c0392b" />
				</>
			) : null}
			{o === 'uniform' ? (
				<>
					<FlatRect x={0.11} y={0.42} z={0.006} w={0.08} h={0.06} r={0.015} color="#f2c94c" />
					<FlatRect x={-0.11} y={0.42} z={0.006} w={0.13} h={0.05} r={0.015} color="#ffffff" />
				</>
			) : null}
			{o === 'sweater' ? (
				<>
					<FlatRect y={0.35} z={0.006} w={w} h={0.06} r={0.01} color={colors.accent} outline={false} />
					<FlatEllipse y={0.6} z={0.006} w={0.2} h={0.08} color={colors.accent} />
				</>
			) : null}
			{o === 'apron' ? <FlatRect y={0.22} z={0.006} w={0.32} h={0.46} r={0.05} color={look.outfitColor} /> : null}
		</group>
	);
};

export const Character2D: React.FC<{state: CharState; yShift: number}> = ({state, yShift}) => {
	const {character: c, slot, pose} = state;
	const look = c.look;
	const colors = outfitColors(c);
	const female = c.gender === 'female';
	const kid = c.age === 'kid';
	const towardSign = -state.outerSign;
	const hasCap = look.accessory === 'cap';
	const seatedDrop = slot.seated ? -0.32 : 0;

	return (
		<group
			position={[slot.x + pose.xOffset, pose.hop * slot.scale + seatedDrop + yShift, slot.z]}
			scale={slot.scale}
			visible={state.visible}
		>
			{slot.seated
				? null
				: [-1, 1].map((side) => {
						const swing = side * pose.walk;
						const hip: [number, number] = [side * 0.1, HIP_Y];
						const foot: [number, number] = [side * 0.1 + Math.sin(swing) * 0.32, HIP_Y - Math.cos(swing) * 0.37];
						return (
							<group key={side}>
								<FlatLimb from={hip} to={foot} radius={0.075} color={colors.pants ?? look.skin} z={-0.02} />
								<FlatEllipse x={foot[0] + 0.02 * side} y={foot[1] - 0.02} z={-0.016} w={0.2} h={0.1} color={colors.shoes} />
							</group>
						);
					})}
			<group position={[0, HIP_Y, 0]} rotation={[0, 0, pose.tilt]}>
				<Torso2D look={look} colors={colors} female={female} />
				<Arm2D side={towardSign} arm={pose.inner} colors={colors} skin={look.skin} shoulderUp={pose.shoulderUp} />
				<Arm2D side={-towardSign} arm={pose.outer} colors={colors} skin={look.skin} shoulderUp={pose.shoulderUp} />
				<group position={[0, HEAD_LOCAL_Y - pose.headNod * 0.06, 0.02]} rotation={[0, 0, pose.headTilt]} scale={kid ? 1.12 : 1}>
					<FlatEllipse x={-HEAD_R * 0.97} y={-0.02} z={-0.002} w={0.1} h={0.13} color={look.skin} />
					<FlatEllipse x={HEAD_R * 0.97} y={-0.02} z={-0.002} w={0.1} h={0.13} color={look.skin} />
					<FlatEllipse w={HEAD_R * 2} h={HEAD_R * 2} color={look.skin} />
					<Hair2D look={look} hasCap={hasCap} />
					{look.accessory === 'beard' ? <FlatHalfDisc y={-HEAD_R * 0.6} z={0.002} w={HEAD_R * 1.62} h={HEAD_R * 0.9} color={look.hairColor} /> : null}
					{hasCap ? (
						<>
							<FlatHalfDisc y={HEAD_R * 0.52} z={0.02} w={HEAD_R * 2.25} h={HEAD_R * 1.25} rot={Math.PI} color={shade(look.outfitColor, -0.05)} />
							<FlatRect x={towardSign * HEAD_R * 0.55} y={HEAD_R * 0.54} z={0.021} w={HEAD_R * 1.3} h={0.05} r={0.02} color={shade(look.outfitColor, -0.12)} />
						</>
					) : null}
					<group position={[0, 0, 0.004]}>
						<Face
							mode="2d"
							R={HEAD_R}
							expr={state.expression}
							mouth={state.mouth}
							blink={state.blink}
							gaze={state.gaze}
							turn={state.facing}
							lashes={female}
							glasses={look.accessory === 'glasses'}
						/>
					</group>
				</group>
			</group>
		</group>
	);
};
