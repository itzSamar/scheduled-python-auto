import React from 'react';
import {EYE_DARK, MOUTH_DARK, TONGUE} from '../lib/colors';
import type {MouthShape} from '../types';
import type {Expression} from './expressions';
import {arcGeo, circleGeo, flatMat, halfDiscGeo, roundRectGeo, teardropGeo, wavyGeo} from './geometry';

type Mode = '2d' | '3d';

/**
 * Places a flat feature on the face. Coordinates are in head radii (u right, v up).
 * 3D: projected onto the head sphere and turned to its surface normal. 2D: stacked in front of the head disc.
 */
const Feature: React.FC<{u: number; v: number; mode: Mode; R: number; layer?: number; rot?: number; k?: number; children: React.ReactNode}> = ({
	u,
	v,
	mode,
	R,
	layer = 1,
	rot = 0,
	k = 1,
	children,
}) => {
	if (mode === '2d') {
		return (
			<group position={[u * R, v * R, 0.004 + layer * 0.002]} rotation={[0, 0, rot]} scale={R * k}>
				{children}
			</group>
		);
	}
	const z = Math.sqrt(Math.max(0.06, 1 - u * u - v * v));
	const len = Math.hypot(u, v, z);
	const [nx, ny, nz] = [u / len, v / len, z / len];
	const lift = 1.006 + layer * 0.003;
	return (
		<group position={[nx * R * lift, ny * R * lift, nz * R * lift]} rotation={[-Math.asin(ny), Math.atan2(nx, nz), 0, 'YXZ']}>
			<group rotation={[0, 0, rot]} scale={R * k}>
				{children}
			</group>
		</group>
	);
};

/** Feature size multipliers; tuned so faces read on a phone in wide shots. */
const EYE_K = 1.32;
const BROW_K = 1.2;
const MOUTH_K = 1.5;

const Ellipse: React.FC<{w: number; h: number; color: string; x?: number; y?: number; z?: number; opacity?: number}> = ({
	w,
	h,
	color,
	x = 0,
	y = 0,
	z = 0,
	opacity = 1,
}) => <mesh geometry={circleGeo()} material={flatMat(color, opacity)} position={[x, y, z]} scale={[w, h, 1]} />;

const Eye: React.FC<{expr: Expression; blink: number; side: number}> = ({expr, blink, side}) => {
	const es = expr.eyeScale;
	const open = 1 - blink * 0.92;
	switch (expr.eye) {
		case 'happy':
			return <mesh geometry={arcGeo(0.1, 0.055, 0.25, Math.PI - 0.5)} material={flatMat(EYE_DARK)} position={[0, -0.04, 0]} />;
		case 'closed':
			return <mesh geometry={arcGeo(0.1, 0.055, Math.PI + 0.25, Math.PI - 0.5)} material={flatMat(EYE_DARK)} position={[0, 0.05, 0]} />;
		case 'squint':
			return <Ellipse w={0.22} h={Math.max(0.03, 0.1 * open)} color={EYE_DARK} />;
		case 'halflid':
			return (
				<group>
					<Ellipse w={0.2} h={Math.max(0.03, 0.15 * open)} y={-0.035} color={EYE_DARK} />
					<mesh geometry={roundRectGeo(0.27, 0.045, 0.022)} material={flatMat(EYE_DARK)} position={[0, 0.045, 0.001]} rotation={[0, 0, -side * 0.12]} />
				</group>
			);
		case 'wide':
		case 'normal':
		default: {
			const w = (expr.eye === 'wide' ? 0.25 : 0.2) * es;
			const h = (expr.eye === 'wide' ? 0.32 : 0.27) * es * open;
			const hl = expr.eye === 'wide' ? 0.1 : 0.075;
			return (
				<group>
					<Ellipse w={w} h={Math.max(0.025, h)} color={EYE_DARK} />
					{blink < 0.5 ? <Ellipse w={hl} h={hl} x={0.035} y={h * 0.22} z={0.002} color="#ffffff" /> : null}
				</group>
			);
		}
	}
};

const TalkMouth: React.FC<{shape: MouthShape}> = ({shape}) => {
	switch (shape) {
		case 'closed':
			return <mesh geometry={roundRectGeo(0.2, 0.045, 0.022)} material={flatMat(MOUTH_DARK)} />;
		case 'mid':
			return <Ellipse w={0.2} h={0.11} color={MOUTH_DARK} />;
		case 'open':
			return (
				<group>
					<Ellipse w={0.22} h={0.22} color={MOUTH_DARK} />
					<Ellipse w={0.13} h={0.07} y={-0.06} z={0.002} color={TONGUE} />
				</group>
			);
		case 'wide':
			return <Ellipse w={0.3} h={0.12} color={MOUTH_DARK} />;
		case 'round':
			return <Ellipse w={0.13} h={0.15} color={MOUTH_DARK} />;
		case 'teeth':
			return (
				<group>
					<mesh geometry={roundRectGeo(0.29, 0.13, 0.05)} material={flatMat(MOUTH_DARK)} />
					<mesh geometry={roundRectGeo(0.25, 0.085, 0.035)} material={flatMat('#ffffff')} position={[0, 0, 0.002]} />
				</group>
			);
		default:
			return null;
	}
};

const BaseMouth: React.FC<{expr: Expression}> = ({expr}) => {
	switch (expr.mouth) {
		case 'smile':
			return <mesh geometry={arcGeo(0.13, 0.05, Math.PI + 0.55, Math.PI - 1.1)} material={flatMat(MOUTH_DARK)} position={[0, 0.08, 0]} />;
		case 'frown':
			return <mesh geometry={arcGeo(0.13, 0.05, 0.6, Math.PI - 1.2)} material={flatMat(MOUTH_DARK)} position={[0, -0.1, 0]} />;
		case 'bigsmile':
			return (
				<group position={[0, 0.03, 0]}>
					<mesh geometry={halfDiscGeo()} material={flatMat(MOUTH_DARK)} scale={[0.32, 0.32, 1]} />
					<Ellipse w={0.14} h={0.07} y={-0.1} z={0.002} color={TONGUE} />
				</group>
			);
		case 'smirk':
			return <mesh geometry={arcGeo(0.12, 0.045, Math.PI + 0.9, 1.5)} material={flatMat(MOUTH_DARK)} position={[0.03, 0.07, 0]} rotation={[0, 0, 0.25]} />;
		case 'o':
			return <Ellipse w={0.12} h={0.15} color={MOUTH_DARK} />;
		case 'wavy':
			return <mesh geometry={wavyGeo(0.22, 0.022, 0.04)} material={flatMat(MOUTH_DARK)} />;
		case 'grin':
			return (
				<group>
					<mesh geometry={roundRectGeo(0.3, 0.13, 0.05)} material={flatMat(MOUTH_DARK)} />
					<mesh geometry={roundRectGeo(0.26, 0.08, 0.03)} material={flatMat('#ffffff')} position={[0, 0, 0.002]} />
				</group>
			);
		case 'flat':
		default:
			return <mesh geometry={roundRectGeo(0.17, 0.042, 0.021)} material={flatMat(MOUTH_DARK)} />;
	}
};

export type FaceProps = {
	mode: Mode;
	R: number;
	expr: Expression;
	mouth: MouthShape | null;
	blink: number;
	gaze: number;
	/** 2D only: fake head turn by sliding the features. */
	turn?: number;
	lashes?: boolean;
	glasses?: boolean;
};

export const Face: React.FC<FaceProps> = ({mode, R, expr, mouth, blink, gaze, turn = 0, lashes = false, glasses = false}) => {
	const shift = gaze * 0.05 + turn * 0.14;
	const talking = mouth !== null && mouth !== 'rest';
	const openEye = (expr.eye === 'normal' || expr.eye === 'wide') && blink < 0.5;
	return (
		<group>
			{glasses ? (
				<Feature u={shift} v={0.1} mode={mode} R={R} layer={4} k={EYE_K}>
					<mesh geometry={roundRectGeo(0.12, 0.035, 0.017)} material={flatMat(EYE_DARK)} />
				</Feature>
			) : null}
			{[-1, 1].map((side) => (
				<React.Fragment key={side}>
					<Feature u={side * 0.36 + shift} v={0.08} mode={mode} R={R} layer={2} k={EYE_K}>
						<Eye expr={expr} blink={blink} side={side} />
						{lashes && openEye ? (
							<mesh
								geometry={roundRectGeo(0.1, 0.032, 0.016)}
								material={flatMat(EYE_DARK)}
								position={[side * 0.1, 0.12 * expr.eyeScale, 0.001]}
								rotation={[0, 0, side * 0.55]}
							/>
						) : null}
					</Feature>
					{glasses ? (
						<Feature u={side * 0.36 + shift} v={0.08} mode={mode} R={R} layer={4} k={EYE_K}>
							<mesh geometry={arcGeo(0.165, 0.034, 0, Math.PI * 2)} material={flatMat(EYE_DARK)} />
						</Feature>
					) : null}
					<Feature
						u={side * 0.36 + shift * 0.8}
						v={0.44 + expr.browY + (side > 0 ? expr.browAsym : 0)}
						mode={mode}
						R={R}
						layer={2}
						rot={-side * expr.browInner}
						k={BROW_K}
					>
						<mesh geometry={roundRectGeo(0.26, 0.055, 0.027)} material={flatMat(EYE_DARK)} />
					</Feature>
					{expr.blush > 0 ? (
						<Feature u={side * 0.53 + shift * 0.6} v={-0.17} mode={mode} R={R} layer={1}>
							<Ellipse w={0.22} h={0.11} color="#ff8fa3" opacity={Math.min(0.85, 0.55 * expr.blush + 0.15)} />
						</Feature>
					) : null}
					{expr.tears ? (
						<Feature u={side * 0.36 + shift} v={-0.2} mode={mode} R={R} layer={3}>
							<mesh geometry={roundRectGeo(0.065, 0.3, 0.032)} material={flatMat('#7cc8ff')} />
						</Feature>
					) : null}
				</React.Fragment>
			))}
			<Feature u={shift * 0.7} v={-0.4} mode={mode} R={R} layer={2} k={MOUTH_K}>
				{talking ? <TalkMouth shape={mouth} /> : <BaseMouth expr={expr} />}
			</Feature>
			{expr.sweat ? (
				<Feature u={0.7} v={0.42} mode={mode} R={R} layer={3}>
					<mesh geometry={teardropGeo()} material={flatMat('#8fd3ff')} scale={[0.17, 0.2, 1]} />
				</Feature>
			) : null}
			{expr.anger ? (
				<Feature u={-0.55} v={0.6} mode={mode} R={R} layer={3}>
					<mesh geometry={roundRectGeo(0.2, 0.055, 0.027)} material={flatMat('#e23b3b')} rotation={[0, 0, 0.785]} />
					<mesh geometry={roundRectGeo(0.2, 0.055, 0.027)} material={flatMat('#e23b3b')} rotation={[0, 0, -0.785]} />
				</Feature>
			) : null}
		</group>
	);
};
