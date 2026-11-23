import React from 'react';
import {shade} from '../lib/colors';
import type {Look} from '../types';
import {Face} from './Face';
import {boxGeo, capsuleGeo, circleGeo, coneGeo, cylGeo, flatMat, sphereGeo, torusGeo, toonMat} from './geometry';
import {outfitColors, type OutfitColors} from './outfit';
import {elbowEuler, shoulderEuler, type ArmPose} from './poses';
import type {CharState} from './state';

const HEAD_R = 0.27;
const HIP_Y = 0.42;
const HEAD_LOCAL_Y = 0.88; // head center above the hips

const Arm: React.FC<{side: number; arm: ArmPose; colors: OutfitColors; skin: string; shoulderUp: number; female: boolean}> = ({
	side,
	arm,
	colors,
	skin,
	shoulderUp,
	female,
}) => {
	const r = arm.reach ?? 1;
	return (
		<group position={[side * (female ? 0.235 : 0.255), 0.5 + shoulderUp, 0]} rotation={shoulderEuler(arm, side)}>
			<mesh geometry={sphereGeo(0.068)} material={toonMat(colors.sleeve)} />
			<mesh geometry={capsuleGeo(0.062, 0.14 + 0.25 * (r - 1))} position={[0, -0.125 * r, 0]} material={toonMat(colors.sleeve)} />
			<group position={[0, -0.25 * r, 0]} rotation={elbowEuler(arm, side)}>
				<mesh geometry={capsuleGeo(0.056, 0.13 + 0.22 * (r - 1))} position={[0, -0.11 * r, 0]} material={toonMat(colors.forearm)} />
				<mesh geometry={sphereGeo(0.068)} position={[0, -0.24 * r, 0]} material={toonMat(skin)} />
			</group>
		</group>
	);
};

const Hair3D: React.FC<{look: Look; hasCap: boolean}> = ({look, hasCap}) => {
	const m = toonMat(look.hairColor);
	const R = HEAD_R;
	const cap = (len: number) => (
		<mesh geometry={sphereGeo(R * 1.07, 0, len)} material={m} rotation={[-0.42, 0, 0]} />
	);
	// Face-framing locks; without them pulled-back styles read as short hair from the front.
	const locks = hasCap
		? null
		: [-1, 1].map((s) => (
				<mesh key={s} geometry={sphereGeo(0.1)} material={m} position={[s * R * 0.9, -0.03, 0.03]} scale={[0.5, 1.45, 0.85]} />
			));
	switch (look.hair) {
		case 'bald':
			return (
				<>
					<mesh geometry={sphereGeo(0.07)} material={m} position={[-R * 0.92, 0.0, -0.06]} scale={[0.6, 1, 1]} />
					<mesh geometry={sphereGeo(0.07)} material={m} position={[R * 0.92, 0.0, -0.06]} scale={[0.6, 1, 1]} />
				</>
			);
		case 'long':
			return (
				<>
					{hasCap ? null : cap(1.25)}
					{locks}
					<mesh geometry={capsuleGeo(0.21, 0.36)} material={m} position={[0, -0.16, -0.12]} scale={[1.42, 1, 0.62]} />
				</>
			);
		case 'bun':
			return (
				<>
					{hasCap ? null : cap(1.2)}
					{locks}
					<mesh geometry={sphereGeo(0.12)} material={m} position={[0, R * 1.0, -0.12]} />
				</>
			);
		case 'ponytail':
			return (
				<>
					{hasCap ? null : cap(1.2)}
					{locks}
					<mesh geometry={sphereGeo(0.085)} material={m} position={[R * 0.6, R * 0.62, -R * 0.78]} />
					<mesh geometry={capsuleGeo(0.08, 0.26)} material={m} position={[R * 1.0, R * 0.08, -R * 0.7]} rotation={[0.2, 0, 0.5]} />
				</>
			);
		case 'curly':
			return (
				<>
					{hasCap ? null : cap(1.25)}
					{Array.from({length: 9}).map((_, i) => {
						const a = (i / 8) * Math.PI;
						return (
							<mesh
								key={i}
								geometry={sphereGeo(0.085)}
								material={m}
								position={[Math.cos(a) * R * 0.95, R * 0.25 + Math.sin(a) * R * 0.75, -0.06 - Math.sin(a) * 0.04]}
							/>
						);
					})}
				</>
			);
		case 'spiky':
			return (
				<>
					{cap(1.1)}
					{hasCap
						? null
						: [-0.6, -0.2, 0.2, 0.6].map((x, i) => (
								<mesh
									key={i}
									geometry={coneGeo(0.07, 0.2, 8)}
									material={m}
									position={[x * R, R * 1.0 - Math.abs(x) * 0.08, -0.02]}
									rotation={[-0.25, 0, -x * 0.7]}
								/>
							))}
				</>
			);
		case 'bob':
			return (
				<>
					{hasCap ? null : cap(1.45)}
					<mesh geometry={sphereGeo(0.12)} material={m} position={[-R * 0.88, -0.07, -0.02]} scale={[0.75, 1.5, 1.2]} />
					<mesh geometry={sphereGeo(0.12)} material={m} position={[R * 0.88, -0.07, -0.02]} scale={[0.75, 1.5, 1.2]} />
				</>
			);
		case 'short':
		default:
			return hasCap ? null : cap(1.15);
	}
};

const Torso3D: React.FC<{state: CharState; colors: OutfitColors; female: boolean}> = ({state, colors, female}) => {
	const look = state.character.look;
	const outfit = look.outfit;
	const r = female ? 0.205 : 0.225;
	const front = r * 0.75 + 0.004;
	return (
		<group>
			<mesh geometry={capsuleGeo(r, 0.16)} position={[0, 0.3, 0]} scale={[1, 1, 0.75]} material={toonMat(colors.torso)} />
			<mesh geometry={cylGeo(0.07, 0.075, 0.12)} position={[0, 0.64, 0]} material={toonMat(look.skin)} />
			{outfit === 'dress' ? (
				<mesh geometry={cylGeo(r * 0.95, 0.34, 0.36)} position={[0, 0.0, 0]} material={toonMat(look.outfitColor)} />
			) : null}
			{outfit === 'hoodie' ? (
				<>
					<mesh geometry={torusGeo(0.15, 0.06)} position={[0, 0.6, -0.07]} rotation={[Math.PI / 2 - 0.35, 0, 0]} material={toonMat(colors.accent)} />
					<mesh geometry={boxGeo(0.26, 0.1, 0.03, 0.012)} position={[0, 0.16, front - 0.02]} material={toonMat(colors.accent)} />
				</>
			) : null}
			{outfit === 'suit' ? (
				<>
					<mesh geometry={boxGeo(0.12, 0.3, 0.02)} position={[0, 0.44, front]} rotation={[0, 0, 0]} material={toonMat('#f4f4f4')} />
					<mesh geometry={boxGeo(0.05, 0.24, 0.02)} position={[0, 0.42, front + 0.012]} material={toonMat('#c0392b')} />
				</>
			) : null}
			{outfit === 'uniform' ? (
				<>
					<mesh geometry={boxGeo(0.07, 0.05, 0.02)} position={[0.1, 0.42, front]} material={toonMat('#f2c94c')} />
					<mesh geometry={boxGeo(0.12, 0.05, 0.02)} position={[-0.1, 0.42, front]} material={toonMat('#ffffff')} />
					<mesh geometry={torusGeo(0.085, 0.025)} position={[0, 0.6, 0]} rotation={[Math.PI / 2, 0, 0]} material={toonMat(colors.accent)} />
				</>
			) : null}
			{outfit === 'sweater' ? (
				<>
					<mesh geometry={torusGeo(0.085, 0.03)} position={[0, 0.6, 0]} rotation={[Math.PI / 2, 0, 0]} material={toonMat(colors.accent)} />
					<mesh geometry={cylGeo(r + 0.006, r + 0.006, 0.06)} position={[0, 0.34, 0]} scale={[1, 1, 0.75]} material={toonMat(colors.accent)} />
				</>
			) : null}
			{outfit === 'apron' ? (
				<mesh geometry={boxGeo(0.3, 0.46, 0.02, 0.01)} position={[0, 0.22, front - 0.01]} material={toonMat(look.outfitColor)} />
			) : null}
		</group>
	);
};

export const Character3D: React.FC<{state: CharState}> = ({state}) => {
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
			position={[slot.x + pose.xOffset, pose.hop * slot.scale + seatedDrop, slot.z]}
			rotation={[0, state.facing, 0]}
			scale={slot.scale}
			visible={state.visible}
		>
			{slot.seated ? null : (
				<mesh
					geometry={circleGeo()}
					material={flatMat('#000000', 0.22)}
					rotation={[-Math.PI / 2, 0, 0]}
					position={[0, 0.004 - pose.hop * slot.scale, 0.02]}
					scale={[0.8 * (1 - pose.hop), 0.5 * (1 - pose.hop), 1]}
				/>
			)}
			{slot.seated
				? null
				: [-1, 1].map((side) => (
						<group key={side} position={[side * 0.1, HIP_Y, 0]} rotation={[side * pose.walk, 0, 0]}>
							<mesh
								geometry={capsuleGeo(0.075, 0.24)}
								position={[0, -0.2, 0]}
								material={toonMat(colors.pants ?? look.skin)}
							/>
							<mesh geometry={sphereGeo(0.1)} position={[0, -0.38, 0.04]} scale={[0.9, 0.6, 1.35]} material={toonMat(colors.shoes)} />
						</group>
					))}
			<group position={[0, HIP_Y, 0]} rotation={[pose.lean, 0, pose.tilt]}>
				<Torso3D state={state} colors={colors} female={female} />
				<Arm side={towardSign} arm={pose.inner} colors={colors} skin={look.skin} shoulderUp={pose.shoulderUp} female={female} />
				<Arm side={-towardSign} arm={pose.outer} colors={colors} skin={look.skin} shoulderUp={pose.shoulderUp} female={female} />
				<group position={[0, HEAD_LOCAL_Y, 0]} rotation={[pose.headNod, 0, pose.headTilt]} scale={kid ? 1.12 : 1}>
					<mesh geometry={sphereGeo(HEAD_R)} material={toonMat(look.skin)} />
					<mesh geometry={sphereGeo(0.06)} position={[-HEAD_R * 0.98, -0.02, 0]} scale={[0.6, 1, 1]} material={toonMat(look.skin)} />
					<mesh geometry={sphereGeo(0.06)} position={[HEAD_R * 0.98, -0.02, 0]} scale={[0.6, 1, 1]} material={toonMat(look.skin)} />
					<Hair3D look={look} hasCap={hasCap} />
					{look.accessory === 'beard' ? (
						<mesh
							geometry={sphereGeo(HEAD_R * 1.035, 2.22, 0.86, 0.3, Math.PI - 0.6)}
							material={toonMat(look.hairColor)}
						/>
					) : null}
					{hasCap ? (
						<>
							<mesh geometry={sphereGeo(HEAD_R * 1.09, 0, 1.3)} material={toonMat(shade(look.outfitColor, -0.05))} rotation={[-0.25, 0, 0]} />
							<mesh
								geometry={cylGeo(0.2, 0.2, 0.025, 24)}
								position={[0, HEAD_R * 0.62, HEAD_R * 0.72]}
								rotation={[0.25, 0, 0]}
								scale={[1, 1, 0.8]}
								material={toonMat(shade(look.outfitColor, -0.12))}
							/>
						</>
					) : null}
					<Face
						mode="3d"
						R={HEAD_R}
						expr={state.expression}
						mouth={state.mouth}
						blink={state.blink}
						gaze={state.gaze}
						lashes={female}
						glasses={look.accessory === 'glasses'}
					/>
				</group>
			</group>
		</group>
	);
};
