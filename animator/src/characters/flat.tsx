import React from 'react';
import {OUTLINE} from '../lib/colors';
import {circleGeo, flatMat, halfDiscGeo, polyGeo, roundRectGeo} from './geometry';

/** Outline width for 2D shapes, in world units. */
export const OUT = 0.022;

type XYZ = {x?: number; y?: number; z?: number};

export const FlatEllipse: React.FC<XYZ & {w: number; h: number; color: string; outline?: boolean; opacity?: number}> = ({
	w,
	h,
	color,
	x = 0,
	y = 0,
	z = 0,
	outline = true,
	opacity = 1,
}) => (
	<>
		{outline ? <mesh geometry={circleGeo()} material={flatMat(OUTLINE)} position={[x, y, z - 0.001]} scale={[w + 2 * OUT, h + 2 * OUT, 1]} /> : null}
		<mesh geometry={circleGeo()} material={flatMat(color, opacity)} position={[x, y, z]} scale={[w, h, 1]} />
	</>
);

export const FlatRect: React.FC<XYZ & {w: number; h: number; r?: number; color: string; rot?: number; outline?: boolean}> = ({
	w,
	h,
	r = 0.02,
	color,
	x = 0,
	y = 0,
	z = 0,
	rot = 0,
	outline = true,
}) => (
	<group position={[x, y, z]} rotation={[0, 0, rot]}>
		{outline ? <mesh geometry={roundRectGeo(w + 2 * OUT, h + 2 * OUT, r + OUT)} material={flatMat(OUTLINE)} position={[0, 0, -0.001]} /> : null}
		<mesh geometry={roundRectGeo(w, h, r)} material={flatMat(color)} />
	</group>
);

/** Capsule-shaped limb between two points in the XY plane. */
export const FlatLimb: React.FC<{from: [number, number]; to: [number, number]; radius: number; color: string; z: number}> = ({
	from,
	to,
	radius,
	color,
	z,
}) => {
	const dx = to[0] - from[0];
	const dy = to[1] - from[1];
	const len = Math.max(0.001, Math.hypot(dx, dy));
	const angle = Math.atan2(dy, dx) - Math.PI / 2;
	return (
		<FlatRect
			x={(from[0] + to[0]) / 2}
			y={(from[1] + to[1]) / 2}
			z={z}
			w={radius * 2}
			h={len + radius * 2}
			r={radius}
			rot={angle}
			color={color}
		/>
	);
};

export const FlatHalfDisc: React.FC<XYZ & {w: number; h: number; color: string; rot?: number}> = ({w, h, color, x = 0, y = 0, z = 0, rot = 0}) => (
	<group position={[x, y, z]} rotation={[0, 0, rot]}>
		<mesh geometry={halfDiscGeo()} material={flatMat(OUTLINE)} position={[0, OUT * 0.5, -0.001]} scale={[w + 2 * OUT, h + 2 * OUT, 1]} />
		<mesh geometry={halfDiscGeo()} material={flatMat(color)} scale={[w, h, 1]} />
	</group>
);

/** Polygon with an outline made by scaling the shape about the origin. */
export const FlatPoly: React.FC<XYZ & {id: string; pts: [number, number][]; color: string; outlineScale?: number}> = ({
	id,
	pts,
	color,
	x = 0,
	y = 0,
	z = 0,
	outlineScale = 1.08,
}) => (
	<group position={[x, y, z]}>
		<mesh geometry={polyGeo(id, pts)} material={flatMat(OUTLINE)} position={[0, 0, -0.001]} scale={[outlineScale, outlineScale, 1]} />
		<mesh geometry={polyGeo(id, pts)} material={flatMat(color)} />
	</group>
);
