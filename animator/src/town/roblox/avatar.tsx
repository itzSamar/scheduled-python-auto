import React, {useMemo} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {CanvasTexture, Color, MeshBasicMaterial, MeshStandardMaterial, SRGBColorSpace} from 'three';
import {RoundedBoxGeometry} from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import {shade} from '../../lib/colors';

/**
 * A Roblox-style avatar built from a short prompt.
 *
 * "smile, spiky brown hair, yellow shirt, blue jeans"
 * "mad, short gray hair, white shirt, black pants"
 * "shocked, long black hair, pink shirt, dark pants"
 *
 * Parts are separate rounded bricks (classic R6), the face is a decal,
 * and the material is smooth plastic. No ink outline.
 */

export type FaceKind = 'smile' | 'grin' | 'mad' | 'shocked' | 'smirk';
export type HairKind = 'short' | 'side' | 'long' | 'spiky' | 'bob' | 'bald';
export type Anim = 'idle' | 'walk' | 'sit' | 'reach' | 'cheer';

export type AvatarSpec = {
	skin: string;
	face: FaceKind;
	hair: HairKind;
	hairColor: string;
	shirt: string;
	pants: string;
};

const NAMED: Record<string, string> = {
	yellow: '#f6d34d',
	blue: '#3a7bff',
	teal: '#1f9d8a',
	red: '#e23d4a',
	pink: '#ff7b9c',
	black: '#2a2a2a',
	brown: '#6b4423',
	white: '#f3f4f6',
	green: '#3cba6e',
	purple: '#7b3ff0',
	orange: '#f08a2c',
	gray: '#c8c8c8',
	grey: '#c8c8c8',
	dark: '#2c3344',
	jeans: '#2c4f86',
	blonde: '#e6c36a',
	blond: '#e6c36a',
};

const geoCache = new Map<string, RoundedBoxGeometry>();
const matCache = new Map<string, MeshStandardMaterial>();
const faceCache = new Map<string, MeshBasicMaterial>();

const brick = (w: number, h: number, d: number, round = 0.05) => {
	const r = Math.min(round, w / 2 - 0.001, h / 2 - 0.001, d / 2 - 0.001);
	const key = `${w}:${h}:${d}:${r}`;
	let geo = geoCache.get(key);
	if (!geo) {
		geo = new RoundedBoxGeometry(w, h, d, 4, Math.max(0.02, r));
		geo.dispose = () => undefined;
		geoCache.set(key, geo);
	}
	return geo;
};

export const plastic = (color: string, roughness = 0.34) => {
	const key = `${color}:${roughness}`;
	let mat = matCache.get(key);
	if (!mat) {
		mat = new MeshStandardMaterial({color: new Color(color), roughness, metalness: 0});
		mat.dispose = () => undefined;
		matCache.set(key, mat);
	}
	return mat;
};

const drawFace = (kind: FaceKind, ctx: CanvasRenderingContext2D) => {
	ctx.clearRect(0, 0, 512, 512);
	ctx.fillStyle = '#1a1a1a';
	ctx.strokeStyle = '#1a1a1a';
	ctx.lineCap = 'round';
	ctx.lineJoin = 'round';
	const eye = (x: number, y: number, rx: number, ry: number) => {
		ctx.beginPath();
		ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
		ctx.fill();
	};
	if (kind === 'shocked') {
		eye(185, 210, 36, 44);
		eye(327, 210, 36, 44);
		ctx.beginPath();
		ctx.ellipse(256, 320, 28, 34, 0, 0, Math.PI * 2);
		ctx.lineWidth = 16;
		ctx.stroke();
		return;
	}
	if (kind === 'mad') {
		eye(190, 230, 22, 26);
		eye(322, 230, 22, 26);
		ctx.lineWidth = 16;
		ctx.beginPath();
		ctx.moveTo(150, 165);
		ctx.lineTo(220, 190);
		ctx.moveTo(362, 165);
		ctx.lineTo(292, 190);
		ctx.stroke();
		ctx.lineWidth = 14;
		ctx.beginPath();
		ctx.moveTo(200, 340);
		ctx.quadraticCurveTo(256, 312, 312, 340);
		ctx.stroke();
		return;
	}
	eye(186, 205, 26, 34);
	eye(326, 205, 26, 34);
	ctx.lineWidth = kind === 'grin' ? 22 : 16;
	ctx.beginPath();
	ctx.arc(256, kind === 'smirk' ? 250 : 240, kind === 'grin' ? 78 : 70, 0.18 * Math.PI, 0.82 * Math.PI);
	ctx.stroke();
};

const faceMaterial = (kind: FaceKind) => {
	let mat = faceCache.get(kind);
	if (!mat) {
		const canvas = document.createElement('canvas');
		canvas.width = 512;
		canvas.height = 512;
		const ctx = canvas.getContext('2d');
		if (!ctx) {
			throw new Error('canvas unavailable');
		}
		drawFace(kind, ctx);
		const tex = new CanvasTexture(canvas);
		tex.colorSpace = SRGBColorSpace;
		tex.needsUpdate = true;
		mat = new MeshBasicMaterial({map: tex, transparent: true});
		mat.dispose = () => undefined;
		tex.dispose = () => undefined;
		faceCache.set(kind, mat);
	}
	return mat;
};

export const parseAvatar = (prompt: string): AvatarSpec => {
	const p = prompt.toLowerCase();
	const spec: AvatarSpec = {
		skin: '#f6d34d',
		face: 'smile',
		hair: 'short',
		hairColor: '#5a3a28',
		shirt: '#3d7ea6',
		pants: '#2c3344',
	};
	if (/\bmad\b|\bangry\b/.test(p)) {
		spec.face = 'mad';
	} else if (/\bshock/.test(p)) {
		spec.face = 'shocked';
	} else if (/\bsmirk\b/.test(p)) {
		spec.face = 'smirk';
	} else if (/\bgrin\b/.test(p)) {
		spec.face = 'grin';
	}
	if (/\bbald\b/.test(p)) {
		spec.hair = 'bald';
	} else if (/\blong\b/.test(p)) {
		spec.hair = 'long';
	} else if (/\bspik/.test(p)) {
		spec.hair = 'spiky';
	} else if (/\bside\b|\bswept\b/.test(p)) {
		spec.hair = 'side';
	} else if (/\bbob\b/.test(p)) {
		spec.hair = 'bob';
	} else if (/\bshort\b/.test(p)) {
		spec.hair = 'short';
	}
	const hair = p.match(/\b(black|brown|blonde|blond|red|pink|blue|white|gray|grey)\s+hair\b/);
	if (hair) {
		spec.hairColor = NAMED[hair[1]];
	}
	const shirt = p.match(/\b(yellow|blue|teal|red|pink|black|white|green|purple|orange|gray|grey)\s+shirt\b/);
	if (shirt) {
		spec.shirt = NAMED[shirt[1]];
	}
	const pants = p.match(/\b(yellow|blue|teal|red|pink|black|white|green|purple|orange|gray|grey|dark|jeans)\s+(pants|jeans)\b/);
	if (pants) {
		spec.pants = NAMED[pants[1]];
	}
	return spec;
};

const HEAD = 0.7;
const TORSO_W = 0.74;
const TORSO_H = 0.78;
const TORSO_D = 0.4;
const LIMB_W = 0.28;
const LIMB_H = 0.78;
const GAP = 0.035;

const Hair: React.FC<{spec: AvatarSpec; y: number}> = ({spec, y}) => {
	if (spec.hair === 'bald') {
		return null;
	}
	const m = plastic(spec.hairColor, 0.22);
	const r = HEAD / 2;
	if (spec.hair === 'spiky') {
		return (
			<group position={[0, y + r * 0.55, 0]}>
				<mesh scale={[1.05, 0.45, 1.05]} material={m}>
					<sphereGeometry args={[r, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
				</mesh>
				{[-0.22, -0.07, 0.08, 0.22].map((x) => (
					<mesh key={x} position={[x, 0.22, 0.04]} rotation={[-0.35, 0, -x]} material={m}>
						<coneGeometry args={[0.11, 0.48, 8]} />
					</mesh>
				))}
			</group>
		);
	}
	if (spec.hair === 'long') {
		return (
			<group position={[0, y, 0]}>
				<mesh position={[0, r * 0.45, -0.04]} scale={[1.2, 0.62, 1.18]} material={m}>
					<sphereGeometry args={[r, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
				</mesh>
				<mesh position={[0, r * 0.62, r * 0.42]} scale={[1.15, 0.22, 0.42]} material={m}>
					<sphereGeometry args={[r * 0.72, 16, 12]} />
				</mesh>
				{[-1, 1].map((s) => (
					<mesh key={s} position={[s * r * 1.2, -0.38, -0.06]} material={m}>
						<capsuleGeometry args={[0.12, 0.62, 6, 12]} />
					</mesh>
				))}
				<mesh position={[0, -0.15, -r * 0.85]} scale={[0.9, 0.9, 0.45]} material={m}>
					<sphereGeometry args={[r, 16, 12]} />
				</mesh>
			</group>
		);
	}
	if (spec.hair === 'side') {
		return (
			<group position={[0, y, 0]}>
				<mesh position={[0.04, r * 0.48, -0.02]} scale={[1.22, 0.58, 1.16]} material={m}>
					<sphereGeometry args={[r, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
				</mesh>
				<mesh position={[0.34, -0.02, 0.1]} rotation={[0.1, 0, -0.65]} scale={[0.85, 1.15, 0.8]} material={m}>
					<sphereGeometry args={[r, 20, 14]} />
				</mesh>
				<mesh position={[0.02, r * 0.62, r * 0.4]} scale={[1.15, 0.2, 0.38]} material={m}>
					<sphereGeometry args={[r * 0.7, 16, 12]} />
				</mesh>
			</group>
		);
	}
	if (spec.hair === 'bob') {
		return (
			<group position={[0, y, 0]}>
				<mesh position={[0, r * 0.2, 0]} scale={[1.14, 0.85, 1.12]} material={m}>
					<sphereGeometry args={[r, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.72]} />
				</mesh>
			</group>
		);
	}
	return (
		<mesh position={[0, y + r * 0.42, -0.01]} scale={[1.08, 0.42, 1.08]} material={plastic(spec.hairColor, 0.22)}>
			<sphereGeometry args={[r, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
		</mesh>
	);
};

export const Avatar: React.FC<{
	prompt: string;
	position?: [number, number, number];
	rotationY?: number;
	anim?: Anim;
	phase?: number;
}> = ({prompt, position = [0, 0, 0], rotationY = 0, anim = 'idle', phase = 0}) => {
	const spec = useMemo(() => parseAvatar(prompt), [prompt]);
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const cycle = Math.sin(t * 7 + phase);
	const walking = anim === 'walk';
	const sitting = anim === 'sit';
	const arm = anim === 'cheer' ? -2.5 : anim === 'reach' ? -1.35 : walking ? cycle * 0.55 : Math.sin(t * 1.5 + phase) * 0.06;
	const leg = walking ? cycle * 0.45 : 0;
	const bob = walking ? Math.abs(cycle) * 0.04 : 0;
	const legH = LIMB_H;
	const torsoY = sitting ? 0.78 : legH + GAP + TORSO_H / 2;
	const headY = torsoY + TORSO_H / 2 + GAP + HEAD / 2;
	const skin = plastic(spec.skin, 0.4);
	const shirt = plastic(spec.shirt, 0.46);
	const pants = plastic(spec.pants, 0.5);
	const collar = plastic(shade(spec.shirt, -0.12), 0.46);

	return (
		<group position={[position[0], position[1] + bob, position[2]]} rotation={[0, rotationY, 0]}>
			<mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
				<circleGeometry args={[0.34, 20]} />
				<meshBasicMaterial color="#000000" transparent opacity={0.16} />
			</mesh>
			{[-1, 1].map((s) => (
				<group key={s} position={[s * 0.18, sitting ? 0.58 : legH, sitting ? 0.06 : 0]} rotation={[sitting ? -1.25 : s * leg, 0, 0]}>
					<mesh geometry={brick(LIMB_W, LIMB_H, LIMB_W, 0.06)} position={[0, -legH / 2, 0]} material={pants} castShadow />
				</group>
			))}
			<mesh geometry={brick(TORSO_W, TORSO_H, TORSO_D)} position={[0, torsoY, 0]} material={shirt} castShadow />
			<mesh geometry={brick(TORSO_W * 0.92, 0.08, TORSO_D + 0.01)} position={[0, torsoY + TORSO_H * 0.36, 0]} material={collar} />
			{[-1, 1].map((s) => (
				<group key={s} position={[s * (TORSO_W / 2 + LIMB_W / 2 + 0.02), torsoY + TORSO_H * 0.28, 0]} rotation={[s === 1 ? arm : walking ? -arm : arm * 0.25, 0, s * 0.04]}>
					<mesh geometry={brick(LIMB_W, LIMB_H, LIMB_W)} position={[0, -LIMB_H / 2, 0]} material={shirt} castShadow />
					<mesh geometry={brick(LIMB_W * 0.92, 0.12, LIMB_W * 0.92)} position={[0, -LIMB_H + 0.02, 0]} material={skin} castShadow />
				</group>
			))}
			<mesh geometry={brick(HEAD, HEAD * 0.94, HEAD, 0.16)} position={[0, headY, 0]} material={skin} castShadow />
			<mesh position={[0, headY, HEAD / 2 + 0.01]} scale={[HEAD * 0.86, HEAD * 0.86, 1]} material={faceMaterial(spec.face)}>
				<planeGeometry args={[1, 1]} />
			</mesh>
			<Hair spec={spec} y={headY} />
		</group>
	);
};
