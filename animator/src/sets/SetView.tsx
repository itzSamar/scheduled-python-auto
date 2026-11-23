import React from 'react';
import {boxGeo, coneGeo, cylGeo, flatMat, flatOutlinedMat, sphereGeo, toonMat} from '../characters/geometry';
import type {Prop, SetSpec} from './locations';

type Mode = '2d' | '3d';

/** 2D pseudo-depth for ground bands: further back sits higher on screen. */
const bandLift = (z: number) => Math.min(0.9, Math.max(0, (-z - 0.2) * 0.26));

/** 2D pseudo-depth for standing objects, bucketed so nearby parts of one object stay together. */
export const propLift = (z: number) => (z > -0.6 ? 0 : z > -1.45 ? 0.25 : z > -2.5 ? 0.55 : z > -5 ? 0.75 : 0.9);

/** 2D parallax factor by depth: far layers drift with the camera, near layers against it. */
const parallax = (z: number) => (z < -5 ? 0.45 : z < -1.5 ? 0.18 : z > 0.6 ? -0.15 : 0);

const anchorZ = (p: Prop) => p.a ?? p.p[2];

const isGroundPlate = (p: Prop) => p.kind === 'box' && p.s[1] <= 0.16 && p.p[1] <= 0.05;
const isFlatDisc = (p: Prop) => p.kind === 'cyl' && p.h <= 0.03 && p.p[1] <= 0.05 && !p.rotX;

const material = (mode: Mode, color: string, glow?: number) => (mode === '3d' ? toonMat(color, glow ?? 0) : flatOutlinedMat(color));

const PropMesh: React.FC<{prop: Prop; mode: Mode; offset?: [number, number, number]}> = ({prop, mode, offset = [0, 0, 0]}) => {
	const pos: [number, number, number] = [prop.p[0] + offset[0], prop.p[1] + offset[1], prop.p[2] + offset[2]];
	switch (prop.kind) {
		case 'box':
			return (
				<mesh
					geometry={boxGeo(prop.s[0], prop.s[1], prop.s[2], prop.round ?? 0)}
					material={material(mode, prop.c, prop.glow)}
					position={pos}
					rotation={[0, prop.rotY ?? 0, prop.rotZ ?? 0]}
				/>
			);
		case 'cyl':
			return (
				<mesh
					geometry={cylGeo(prop.rt, prop.rb, prop.h, prop.seg ?? 28)}
					material={material(mode, prop.c, prop.glow)}
					position={pos}
					rotation={[prop.rotX ?? 0, 0, 0]}
					scale={prop.sc ?? [1, 1, 1]}
				/>
			);
		case 'sphere':
			return <mesh geometry={sphereGeo(prop.r)} material={material(mode, prop.c, prop.glow)} position={pos} scale={prop.sc ?? [1, 1, 1]} />;
		case 'cone':
			return (
				<mesh
					geometry={coneGeo(prop.r, prop.h, prop.seg ?? 20)}
					material={material(mode, prop.c)}
					position={pos}
					rotation={[0, prop.rotY ?? 0, 0]}
				/>
			);
		default:
			return null;
	}
};

/** Ground plates (floors, roads, rugs) become horizontal bands in the flat 2D view. */
const GroundBand2D: React.FC<{prop: Prop; xShift: number}> = ({prop, xShift}) => {
	let zFront: number;
	let zBack: number;
	let width: number;
	if (prop.kind === 'box') {
		zFront = prop.p[2] + prop.s[2] / 2;
		zBack = prop.p[2] - prop.s[2] / 2;
		width = prop.s[0];
	} else if (prop.kind === 'cyl') {
		const depth = prop.rt * 2 * (prop.sc?.[2] ?? 1);
		zFront = prop.p[2] + depth / 2;
		zBack = prop.p[2] - depth / 2;
		width = prop.rt * 2 * (prop.sc?.[0] ?? 1);
	} else {
		return null;
	}
	const yBottom = bandLift(zFront) - (zFront > 1.5 ? 6 : 0);
	const yTop = bandLift(zBack) + 0.02;
	const h = Math.max(0.03, yTop - yBottom);
	const geo = prop.kind === 'cyl' ? cylGeo(0.5, 0.5, 0.01, 40) : boxGeo(width, h, 0.01);
	return prop.kind === 'cyl' ? (
		<mesh
			geometry={geo}
			material={flatMat(prop.c)}
			position={[prop.p[0] + xShift, (yBottom + yTop) / 2, zBack - 0.05]}
			rotation={[Math.PI / 2, 0, 0]}
			scale={[width, 1, h]}
		/>
	) : (
		<mesh geometry={geo} material={flatMat(prop.c)} position={[prop.p[0] + xShift, (yBottom + yTop) / 2, zBack - 0.05]} />
	);
};

export const SetView: React.FC<{spec: SetSpec; mode: Mode; t: number; camX: number}> = ({spec, mode, t, camX}) => {
	const scrollPeriod = 14;
	const scrollX = spec.scrollSpeed > 0 ? -((t * spec.scrollSpeed) % scrollPeriod) : 0;

	if (mode === '3d') {
		return (
			<group>
				{spec.exterior ? null : (
					<>
						<mesh geometry={boxGeo(16, 9, 0.1)} material={toonMat(spec.wall)} position={[0, 4.5, -2.35]} />
						<mesh geometry={boxGeo(16, 0.1, 22)} material={toonMat(spec.floor)} position={[0, -0.05, 8.6]} />
					</>
				)}
				{spec.props.map((p, i) => (
					<PropMesh key={i} prop={p} mode="3d" />
				))}
				{spec.scrolling.length
					? [0, 1].map((k) => (
							<group key={k} position={[scrollX + k * scrollPeriod, 0, 0]}>
								{spec.scrolling.map((p, i) => (
									<PropMesh key={i} prop={p} mode="3d" />
								))}
							</group>
						))
					: null}
			</group>
		);
	}

	// Flat 2D: wall + floor bands, props lifted by depth, parallax per layer.
	const wallBase = propLift(-2.3);
	const horizon = 0.9;
	const lifted = (p: Prop): [number, number, number] => [camX * parallax(anchorZ(p)), propLift(anchorZ(p)), 0];
	return (
		<group>
			{spec.exterior ? (
				<mesh geometry={boxGeo(80, 20, 0.01)} material={flatMat(spec.floor)} position={[0, horizon - 10, -30]} />
			) : (
				<>
					<mesh geometry={boxGeo(80, 12, 0.01)} material={flatMat(spec.wall)} position={[camX * 0.18, wallBase + 6, -2.6]} />
					<mesh geometry={boxGeo(80, 12, 0.01)} material={flatMat(spec.floor)} position={[0, wallBase - 6, -2.55]} />
				</>
			)}
			{spec.props.map((p, i) =>
				isGroundPlate(p) || isFlatDisc(p) ? (
					<GroundBand2D key={i} prop={p} xShift={camX * parallax(anchorZ(p))} />
				) : (
					<PropMesh key={i} prop={p} mode="2d" offset={lifted(p)} />
				),
			)}
			{spec.scrolling.length
				? [0, 1].map((k) => (
						<group key={k} position={[scrollX + k * scrollPeriod, 0, 0]}>
							{spec.scrolling.map((p, i) =>
								isGroundPlate(p) ? <GroundBand2D key={i} prop={p} xShift={0} /> : <PropMesh key={i} prop={p} mode="2d" offset={lifted(p)} />,
							)}
						</group>
					))
				: null}
		</group>
	);
};
