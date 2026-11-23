import {rand01} from '../lib/math';

type V3 = [number, number, number];

/** `a`: anchor depth used by the flat 2D view so multi-part objects move as one. */
export type Prop =
	| {kind: 'box'; p: V3; s: V3; c: string; round?: number; rotY?: number; rotZ?: number; glow?: number; a?: number}
	| {kind: 'cyl'; p: V3; rt: number; rb: number; h: number; c: string; rotX?: number; sc?: V3; glow?: number; seg?: number; a?: number}
	| {kind: 'sphere'; p: V3; r: number; c: string; sc?: V3; glow?: number; a?: number}
	| {kind: 'cone'; p: V3; r: number; h: number; c: string; seg?: number; rotY?: number; a?: number};

const anchored = (props: Prop[], z: number): Prop[] => props.map((p) => ({...p, a: z}));

export type TimeOfDay = 'day' | 'evening' | 'night';

export type SetSpec = {
	exterior: boolean;
	seated: boolean;
	sky: string;
	wall: string;
	floor: string;
	props: Prop[];
	/** Props that scroll sideways (scenery passing a moving car). */
	scrolling: Prop[];
	scrollSpeed: number;
	hemiGround: string;
};

const TOD = {
	day: {sky: '#9fd8ff', window: '#cdeeff', glow: 0},
	evening: {sky: '#ffb08a', window: '#ffc58f', glow: 0.6},
	night: {sky: '#1f2b52', window: '#2a3a6b', glow: 1.1},
} as const;

const PRODUCT_COLORS = ['#e63946', '#f4a261', '#2a9d8f', '#e9c46a', '#457b9d', '#9b5de5', '#00bbf9', '#f15bb5'];

/** Box helper: x, bottom y, z, width, height, depth. */
const box = (x: number, y: number, z: number, w: number, h: number, d: number, c: string, extra: Partial<Prop> = {}): Prop =>
	({kind: 'box', p: [x, y + h / 2, z], s: [w, h, d], c, ...extra}) as Prop;
const cyl = (x: number, y: number, z: number, rt: number, rb: number, h: number, c: string, extra: Partial<Prop> = {}): Prop =>
	({kind: 'cyl', p: [x, y + h / 2, z], rt, rb, h, c, ...extra}) as Prop;
const ball = (x: number, y: number, z: number, r: number, c: string, extra: Partial<Prop> = {}): Prop =>
	({kind: 'sphere', p: [x, y, z], r, c, ...extra}) as Prop;
const cone = (x: number, y: number, z: number, r: number, h: number, c: string, extra: Partial<Prop> = {}): Prop =>
	({kind: 'cone', p: [x, y + h / 2, z], r, h, c, ...extra}) as Prop;

const WALL_Z = -2.3;

const windowOnWall = (x: number, y: number, w: number, h: number, tod: TimeOfDay): Prop[] =>
	anchored(
		[
			box(x, y - 0.05, WALL_Z + 0.03, w + 0.14, h + 0.1, 0.05, '#ffffff'),
			box(x, y, WALL_Z + 0.06, w, h, 0.03, TOD[tod].window, {glow: tod === 'night' ? 0 : 0.35}),
			box(x, y + h / 2 - 0.02, WALL_Z + 0.08, 0.04, h, 0.02, '#ffffff'),
			box(x, y - 0.12, WALL_Z + 0.12, w + 0.3, 0.06, 0.18, '#ffffff'),
		],
		WALL_Z,
	);

const frame = (x: number, y: number, w: number, h: number, art: string, frameColor = '#7a5230'): Prop[] =>
	anchored([box(x, y, WALL_Z + 0.03, w, h, 0.04, frameColor), box(x, y + 0.07, WALL_Z + 0.06, w - 0.14, h - 0.14, 0.02, art)], WALL_Z);

const plant = (x: number, z: number, scale = 1): Prop[] =>
	anchored(
		[
			cyl(x, 0, z, 0.2 * scale, 0.15 * scale, 0.38 * scale, '#c96f4a'),
			ball(x, 0.62 * scale, z, 0.3 * scale, '#4f9d4a'),
			ball(x - 0.17 * scale, 0.5 * scale, z + 0.05, 0.2 * scale, '#5fb35a'),
			ball(x + 0.18 * scale, 0.55 * scale, z + 0.02, 0.22 * scale, '#5fb35a'),
		],
		z,
	);

const tree = (x: number, z: number, s = 1, canopy = '#4f9d4a'): Prop[] =>
	anchored(
		[
			cyl(x, 0, z, 0.12 * s, 0.16 * s, 1.4 * s, '#8a5a3b'),
			ball(x, 1.85 * s, z, 0.75 * s, canopy),
			ball(x - 0.45 * s, 1.55 * s, z + 0.1, 0.5 * s, canopy),
			ball(x + 0.45 * s, 1.6 * s, z + 0.05, 0.52 * s, canopy),
		],
		z,
	);

const lampGlow = (tod: TimeOfDay) => (tod === 'day' ? 0.15 : TOD[tod].glow);

const kitchen = (tod: TimeOfDay): Prop[] => [
	box(0, 0, WALL_Z + 0.03, 14, 0.12, 0.05, '#e3cba0'),
	box(-0.6, 0, -2.0, 4.6, 0.86, 0.6, '#ffffff', {round: 0.03}),
	box(-0.6, 0.86, -2.0, 4.7, 0.07, 0.66, '#5f6b7a'),
	...[-2.4, -1.25, -0.1, 1.05].map((x) => box(x, 0.66, -1.69, 0.2, 0.035, 0.02, '#9aa3ad')),
	box(-1.9, 1.75, -2.12, 2.0, 0.75, 0.35, '#ffffff', {round: 0.02}),
	box(1.0, 1.75, -2.12, 1.4, 0.75, 0.35, '#ffffff', {round: 0.02}),
	...windowOnWall(-0.3, 1.15, 1.0, 0.95, tod),
	box(2.45, 0, -1.85, 0.95, 2.05, 0.75, '#dfe7ec', {round: 0.06}),
	box(2.06, 1.0, -1.46, 0.04, 0.5, 0.04, '#9aa3ad'),
	box(2.45, 1.3, -1.47, 0.95, 0.02, 0.01, '#b9c3cb'),
	cyl(-1.6, 0.93, -1.95, 0.1, 0.13, 0.24, '#e0574f'),
	ball(0.45, 1.0, -1.95, 0.08, '#f4a261'),
	ball(0.6, 1.0, -1.9, 0.075, '#7cc56b'),
	ball(0.52, 1.1, -1.95, 0.07, '#e63946'),
	cyl(1.0, 2.9, WALL_Z + 0.05, 0.22, 0.22, 0.05, '#ffffff', {rotX: Math.PI / 2}),
	cyl(1.0, 2.9, WALL_Z + 0.08, 0.025, 0.025, 0.04, '#333333', {rotX: Math.PI / 2}),
	cyl(-1.2, 3.2, -1.3, 0.01, 0.01, 2, '#333333'),
	cone(-1.2, 2.95, -1.3, 0.24, 0.26, '#f7d774', {seg: 16}),
	ball(-1.2, 2.93, -1.3, 0.09, '#fff6c9', {glow: lampGlow(tod) + 0.4}),
	cyl(1.4, 3.2, -1.3, 0.01, 0.01, 2, '#333333'),
	cone(1.4, 2.95, -1.3, 0.24, 0.26, '#f7d774', {seg: 16}),
	ball(1.4, 2.93, -1.3, 0.09, '#fff6c9', {glow: lampGlow(tod) + 0.4}),
];

const livingRoom = (tod: TimeOfDay): Prop[] => [
	box(0, 0, WALL_Z + 0.03, 14, 0.12, 0.05, '#a9c2b2'),
	cyl(0, 0, -0.4, 1.9, 1.9, 0.012, '#e09f7d', {sc: [1, 1, 0.55]}),
	box(0, 0, -1.75, 2.8, 0.42, 0.85, '#5b7fbf', {round: 0.08}),
	box(0, 0.35, -2.08, 2.8, 0.7, 0.25, '#5b7fbf', {round: 0.08}),
	box(-1.47, 0, -1.75, 0.26, 0.62, 0.88, '#4f6fae', {round: 0.08}),
	box(1.47, 0, -1.75, 0.26, 0.62, 0.88, '#4f6fae', {round: 0.08}),
	box(-0.66, 0.42, -1.7, 1.26, 0.14, 0.72, '#6d8fcf', {round: 0.05}),
	box(0.66, 0.42, -1.7, 1.26, 0.14, 0.72, '#6d8fcf', {round: 0.05}),
	box(-1.05, 0.55, -1.92, 0.42, 0.38, 0.14, '#f2c76e', {round: 0.06, rotZ: 0.15}),
	box(1.05, 0.55, -1.92, 0.42, 0.38, 0.14, '#e07a5f', {round: 0.06, rotZ: -0.15}),
	box(0, 0, -0.95, 1.2, 0.36, 0.55, '#8a5a3b', {round: 0.03}),
	cyl(0.3, 0.36, -0.95, 0.06, 0.06, 0.12, '#ffffff'),
	cyl(2.35, 0, -1.9, 0.03, 0.03, 1.6, '#3d3d3d'),
	cyl(2.35, 1.6, -1.9, 0.18, 0.28, 0.34, '#f7e7b5', {glow: lampGlow(tod)}),
	...frame(-1.0, 1.85, 0.9, 0.7, '#9ed0e6'),
	...frame(0.65, 1.95, 0.62, 0.82, '#f2c76e'),
	box(1.75, 2.75, -2.15, 1.4, 0.06, 0.3, '#8a5a3b'),
	...['#e63946', '#457b9d', '#e9c46a', '#2a9d8f', '#9b5de5'].map((c, i) => box(1.25 + i * 0.2, 2.81, -2.15, 0.14, 0.32 + (i % 2) * 0.06, 0.22, c)),
	...windowOnWall(-2.6, 1.2, 0.9, 1.2, tod),
	...plant(-2.2, -1.8),
];

const bedroom = (tod: TimeOfDay): Prop[] => [
	box(0, 0, WALL_Z + 0.03, 14, 0.12, 0.05, '#cdb8de'),
	box(0.9, 0, WALL_Z + 0.08, 2.1, 1.3, 0.1, '#8a5a3b', {round: 0.04}),
	box(0.9, 0, -1.25, 2.0, 0.38, 2.1, '#8a5a3b', {round: 0.03}),
	box(0.9, 0.38, -1.25, 1.9, 0.2, 2.0, '#ffffff', {round: 0.05}),
	box(0.9, 0.5, -0.95, 1.95, 0.13, 1.45, '#6fa8dc', {round: 0.05}),
	box(0.9, 0.58, -1.95, 1.2, 0.18, 0.42, '#ffffff', {round: 0.08}),
	box(-0.5, 0, -2.0, 0.5, 0.55, 0.45, '#a87b55', {round: 0.03}),
	cyl(-0.5, 0.55, -2.0, 0.08, 0.1, 0.25, '#e9c46a'),
	cyl(-0.5, 0.8, -2.0, 0.14, 0.2, 0.2, '#fdf1c7', {glow: lampGlow(tod)}),
	...windowOnWall(-1.75, 1.2, 1.1, 1.2, tod),
	...frame(0.9, 1.75, 0.75, 0.9, '#f28f8f', '#5b3a29'),
	box(-2.85, 0, -1.9, 1.0, 2.2, 0.7, '#b8865b', {round: 0.03}),
	box(-2.85, 1.1, -1.54, 0.02, 1.9, 0.01, '#8a5a3b'),
	cyl(-0.6, 0, -0.3, 0.9, 0.9, 0.012, '#f4b6c2', {sc: [1, 1, 0.5]}),
];

const office = (tod: TimeOfDay): Prop[] => {
	const desk = (x: number): Prop[] => anchored([
		box(x, 0.7, -1.8, 1.6, 0.05, 0.8, '#d9c3a0'),
		box(x - 0.75, 0, -1.8, 0.06, 0.7, 0.75, '#6b7280'),
		box(x + 0.75, 0, -1.8, 0.06, 0.7, 0.75, '#6b7280'),
		box(x, 0.75, -2.0, 0.08, 0.2, 0.08, '#374151'),
		box(x, 0.92, -2.0, 0.75, 0.48, 0.05, '#1f2937', {round: 0.02}),
		box(x, 0.96, -1.97, 0.66, 0.38, 0.02, '#6ec1ff', {glow: 0.45}),
		cyl(x, 0.3, -1.15, 0.24, 0.24, 0.08, '#374151'),
		box(x, 0.38, -0.95, 0.5, 0.55, 0.08, '#374151', {round: 0.04}),
		cyl(x, 0, -1.15, 0.03, 0.03, 0.3, '#6b7280'),
	], -1.8);
	return [
		box(0, 0, WALL_Z + 0.03, 14, 0.12, 0.05, '#b5bfcc'),
		...desk(-1.35),
		...desk(1.55),
		box(0, 1.55, WALL_Z + 0.03, 2.1, 1.05, 0.04, '#9ca3af'),
		box(0, 1.6, WALL_Z + 0.06, 1.95, 0.9, 0.02, '#ffffff'),
		box(-0.45, 2.1, WALL_Z + 0.08, 0.7, 0.04, 0.01, '#3b82f6'),
		box(0.2, 1.9, WALL_Z + 0.08, 0.9, 0.04, 0.01, '#ef4444'),
		box(-0.2, 1.75, WALL_Z + 0.08, 0.6, 0.04, 0.01, '#10b981'),
		box(2.75, 0, -1.6, 0.42, 0.9, 0.42, '#d1d5db', {round: 0.03}),
		cyl(2.75, 0.9, -1.6, 0.16, 0.16, 0.45, '#9fd8ff'),
		...plant(-2.8, -1.6, 1.4),
		cyl(-2.0, 2.9, WALL_Z + 0.05, 0.22, 0.22, 0.05, '#ffffff', {rotX: Math.PI / 2}),
		...windowOnWall(2.3, 1.45, 0.9, 1.1, tod),
	];
};

const classroom = (tod: TimeOfDay): Prop[] => {
	const studentDesk = (x: number, z: number): Prop[] =>
		anchored(
			[
				box(x, 0.6, z, 0.85, 0.05, 0.55, '#d9a066'),
				box(x - 0.36, 0, z, 0.05, 0.6, 0.05, '#6b7280'),
				box(x + 0.36, 0, z, 0.05, 0.6, 0.05, '#6b7280'),
			],
			z,
		);
	return [
		box(0, 0, WALL_Z + 0.03, 14, 0.12, 0.05, '#d6c89e'),
		box(0, 1.1, WALL_Z + 0.03, 3.4, 1.45, 0.04, '#8a5a3b'),
		box(0, 1.17, WALL_Z + 0.06, 3.2, 1.3, 0.02, '#2f5d50'),
		box(0, 1.08, WALL_Z + 0.12, 3.2, 0.04, 0.12, '#8a5a3b'),
		box(-0.6, 1.9, WALL_Z + 0.08, 0.9, 0.03, 0.01, '#f5f5f5'),
		box(0.4, 1.6, WALL_Z + 0.08, 1.3, 0.03, 0.01, '#f5f5f5'),
		box(-0.2, 1.4, WALL_Z + 0.08, 0.7, 0.03, 0.01, '#f5f5f5'),
		...PRODUCT_COLORS.map((c, i) => box(-2.45 + i * 0.7, 3.0, WALL_Z + 0.05, 0.45, 0.45, 0.02, c)),
		box(-2.1, 0, -1.6, 1.4, 0.78, 0.7, '#a0714f', {round: 0.03}),
		ball(-1.8, 1.05, -1.6, 0.17, '#5aa9e6'),
		cyl(-1.8, 0.78, -1.6, 0.03, 0.06, 0.12, '#444444'),
		cyl(2.2, 2.6, WALL_Z + 0.05, 0.22, 0.22, 0.05, '#ffffff', {rotX: Math.PI / 2}),
		...studentDesk(-2.6, 0.9),
		...studentDesk(2.6, 0.9),
		...windowOnWall(2.6, 1.3, 0.8, 1.1, tod),
	];
};

const restaurant = (tod: TimeOfDay): Prop[] => {
	const table = (x: number, z: number): Prop[] =>
		anchored(
			[
				cyl(x, 0, z, 0.62, 0.62, 0.72, '#d9534f', {seg: 32}),
				cyl(x, 0.72, z, 0.66, 0.66, 0.03, '#ffffff', {seg: 32}),
				cyl(x - 0.22, 0.75, z + 0.15, 0.13, 0.13, 0.015, '#f5f5f5'),
				cyl(x + 0.22, 0.75, z + 0.1, 0.13, 0.13, 0.015, '#f5f5f5'),
				cyl(x, 0.75, z - 0.15, 0.04, 0.04, 0.16, '#f7d774', {glow: lampGlow(tod)}),
			],
			z,
		);
	return [
		box(0, 0, WALL_Z + 0.03, 14, 1.0, 0.05, '#5c2a20'),
		box(0.9, 0, -1.9, 3.6, 1.0, 0.6, '#6b4532', {round: 0.03}),
		box(0.9, 1.0, -1.9, 3.7, 0.06, 0.7, '#d9c3a0'),
		...[-0.4, 0.5, 1.4, 2.3].flatMap((x) => [cyl(x, 0, -1.4, 0.03, 0.03, 0.72, '#3d3d3d'), cyl(x, 0.72, -1.4, 0.2, 0.2, 0.07, '#e9c46a')]),
		box(0.9, 1.75, WALL_Z + 0.03, 2.1, 1.05, 0.04, '#3b2a20'),
		box(0.9, 1.8, WALL_Z + 0.06, 1.95, 0.9, 0.02, '#1f2420'),
		...[0, 1, 2, 3].map((i) => box(0.9, 2.47 - i * 0.2, WALL_Z + 0.08, 1.4 - (i % 2) * 0.4, 0.04, 0.01, '#f5f5f5')),
		...[-1.0, 0.9, 2.8].flatMap((x) => [cyl(x, 2.75, -1.2, 0.01, 0.01, 2, '#222222'), ball(x, 2.68, -1.2, 0.14, '#ffd27a', {glow: lampGlow(tod) + 0.5})]),
		...table(-2.3, -0.6),
		...frame(-1.6, 1.6, 0.8, 0.95, '#f4a261', '#2b1d17'),
	];
};

const store = (_tod: TimeOfDay, seed: number): Prop[] => {
	const shelf = (x: number): Prop[] => {
		const out: Prop[] = [box(x, 0, -1.9, 1.7, 2.05, 0.55, '#c9ced4', {round: 0.02})];
		[0.42, 0.9, 1.38, 1.86].forEach((y, row) => {
			out.push(box(x, y - 0.03, -1.72, 1.65, 0.04, 0.5, '#9aa3ab'));
			for (let i = 0; i < 6; i++) {
				const c = PRODUCT_COLORS[Math.floor(rand01(seed + row * 17 + i * 3 + x * 7) * PRODUCT_COLORS.length)];
				const h = 0.24 + rand01(seed + i + row * 5) * 0.12;
				out.push(box(x - 0.68 + i * 0.27, y + 0.01, -1.68, 0.2, h, 0.28, c));
			}
		});
		return anchored(out, -1.9);
	};
	return [
		box(0, 0, WALL_Z + 0.03, 14, 0.12, 0.05, '#c4cbd2'),
		...shelf(-2.0),
		...shelf(1.95),
		box(0, 2.6, WALL_Z + 0.05, 2.4, 0.6, 0.05, '#e63946', {round: 0.04}),
		box(0, 2.65, WALL_Z + 0.09, 1.9, 0.12, 0.01, '#ffffff'),
		box(0, 2.82, WALL_Z + 0.09, 1.4, 0.08, 0.01, '#ffe08a'),
		box(-0.05, 0, -2.0, 1.1, 0.75, 0.5, '#f1d6a8', {round: 0.03}),
		...[0, 1, 2].map((i) => box(-0.4 + i * 0.35, 0.75, -2.0, 0.26, 0.36, 0.2, PRODUCT_COLORS[(i * 3 + seed) % PRODUCT_COLORS.length])),
		box(3.0, 0, -0.35, 0.65, 0.95, 1.5, '#3a5a8c', {round: 0.03}),
		box(3.0, 0.95, -0.55, 0.4, 0.28, 0.35, '#1f2937', {round: 0.02}),
	];
};

const street = (tod: TimeOfDay, seed: number): Prop[] => {
	const houseColors = ['#f4d6a0', '#a8d5e2', '#f2b5a7', '#c7e3b0', '#e8d3f0'];
	const houses: Prop[] = [];
	for (let i = 0; i < 5; i++) {
		const x = -6 + i * 3;
		const c = houseColors[(i + seed) % houseColors.length];
		houses.push(
			...anchored(
				[
					box(x, 0, -9, 2.4, 2.1, 2.0, c),
					cone(x, 2.1, -9, 1.95, 1.1, '#8b4c3a', {seg: 4, rotY: Math.PI / 4}),
					box(x - 0.55, 0.9, -7.98, 0.55, 0.55, 0.04, TOD[tod].window, {glow: tod === 'night' ? 1.2 : 0.2}),
					box(x + 0.55, 0, -7.98, 0.5, 0.95, 0.04, '#6b4532'),
				],
				-9,
			),
		);
	}
	return [
		box(0, -0.1, 0.6, 40, 0.1, 4.0, '#d4d4d4'),
		box(0, -0.1, -1.55, 40, 0.16, 0.3, '#b5b5b5'),
		box(0, -0.12, -4.3, 40, 0.1, 5.2, '#4b4f58'),
		...[-6, -3, 0, 3, 6].map((x) => box(x, -0.06, -4.3, 1.2, 0.02, 0.14, '#f5f5f5')),
		box(0, -0.1, -7.6, 40, 0.1, 2.2, '#d4d4d4'),
		box(0, -0.15, -15, 60, 0.1, 13, '#86c36f'),
		...houses,
		...tree(-2.7, -1.15, 0.9),
		...tree(3.1, -1.25, 1.0, '#5fb35a'),
		cyl(1.8, 0, -1.2, 0.05, 0.06, 3.2, '#3d3d3d'),
		ball(1.8, 3.25, -1.2, 0.17, '#fff3b0', {glow: tod === 'day' ? 0.2 : 1.4}),
		...anchored(
			[
				box(-1.6, 0.1, -3.3, 2.1, 0.5, 0.95, '#f2b134', {round: 0.12}),
				box(-1.75, 0.55, -3.3, 1.2, 0.45, 0.85, '#f2b134', {round: 0.12}),
				box(-1.75, 0.63, -3.3, 1.05, 0.32, 0.88, '#9fd8ff'),
				...[-2.3, -0.9].map((x) => cyl(x, -0.3, -3.3, 0.2, 0.2, 1.0, '#222222', {rotX: Math.PI / 2})),
			],
			-3.3,
		),
	];
};

const park = (tod: TimeOfDay): Prop[] => [
	box(0, -0.1, -10, 60, 0.1, 30, '#7cc56b'),
	box(0, -0.06, -0.1, 40, 0.02, 1.7, '#e6d3a3'),
	cyl(-2.6, -0.04, -3.6, 1.6, 1.6, 0.02, '#6ec1ff', {sc: [1, 1, 0.45]}),
	...tree(-3.2, -2.2, 1.1),
	...tree(2.6, -2.6, 1.2, '#5fb35a'),
	...tree(-0.5, -6.5, 1.4, '#4f9d4a'),
	...tree(4.5, -7.5, 1.3, '#5fb35a'),
	...tree(-5.0, -8.0, 1.5),
	...anchored(
		[
			box(1.8, 0.42, -1.35, 1.5, 0.08, 0.48, '#a0714f'),
			box(1.8, 0.62, -1.58, 1.5, 0.35, 0.06, '#a0714f'),
			...[1.15, 2.45].map((x) => box(x, 0, -1.35, 0.08, 0.42, 0.42, '#5b3a29')),
		],
		-1.35,
	),
	ball(-1.5, 0.2, -1.9, 0.38, '#4f9d4a'),
	ball(-1.0, 0.18, -1.95, 0.3, '#5fb35a'),
	ball(0.4, 0.2, -2.2, 0.35, '#4f9d4a'),
	cyl(-1.9, 0, -1.2, 0.05, 0.06, 2.8, '#3d3d3d'),
	ball(-1.9, 2.85, -1.2, 0.16, '#fff3b0', {glow: tod === 'day' ? 0.2 : 1.4}),
	...Array.from({length: 14}).map((_, i) => box(-7 + i, 0, -12, 0.08, 0.7, 0.08, '#f5f5f5')),
	box(0, 0.5, -12, 14, 0.06, 0.06, '#f5f5f5'),
];

const carInterior = (seed: number): Prop[] => {
	const body = ['#e0574f', '#3a7bd5', '#2a9d8f', '#f2b134'][seed % 4];
	return [
		box(0, -0.15, -6, 30, 0.1, 22, '#4b4f58'),
		...[-0.42, 0.42].flatMap((x) => [
			box(x, 0.0, -0.36, 0.62, 1.05, 0.25, '#3b3f4a', {round: 0.08}),
			box(x, 1.12, -0.38, 0.38, 0.24, 0.18, '#3b3f4a', {round: 0.06}),
		]),
		box(0, -0.2, 0.7, 2.7, 0.66, 0.55, '#2d3240', {round: 0.06}),
		box(0, 0.42, 0.95, 2.6, 0.06, 0.35, '#3b4152'),
		cyl(-0.42, 0.42, 0.62, 0.2, 0.2, 0.04, '#1f2330', {rotX: 1.1}),
		box(0, -0.2, 1.7, 2.9, 0.48, 1.4, body, {round: 0.15}),
		box(-1.33, -0.1, 0, 0.08, 0.9, 1.6, body),
		box(1.33, -0.1, 0, 0.08, 0.9, 1.6, body),
		box(-1.25, 0.6, 0.62, 0.08, 1.35, 0.08, body, {rotZ: -0.25}),
		box(1.25, 0.6, 0.62, 0.08, 1.35, 0.08, body, {rotZ: 0.25}),
		box(0, 1.9, 0, 2.6, 0.08, 1.4, body, {round: 0.03}),
		box(0, 1.84, 0.62, 0.32, 0.08, 0.04, '#222222'),
	];
};

const carScenery = (): Prop[] => [
	...tree(-4, -6, 1.1),
	...tree(-1, -7, 1.3, '#5fb35a'),
	...tree(2.5, -6.5, 1.0),
	...tree(5.5, -7.5, 1.4, '#5fb35a'),
	cyl(0.8, 0, -5, 0.05, 0.05, 2.6, '#3d3d3d'),
	cyl(-2.8, 0, -5, 0.05, 0.05, 2.6, '#3d3d3d'),
	box(0, -0.12, -12, 40, 0.1, 10, '#86c36f'),
];

const WALLS: Record<string, [string, string]> = {
	kitchen: ['#f4e4c1', '#d6b48c'],
	living_room: ['#cfe3d6', '#b98a5e'],
	bedroom: ['#e3d5f0', '#c9a37e'],
	office: ['#dde4ec', '#7d8a99'],
	classroom: ['#f1e7c9', '#b98d63'],
	restaurant: ['#8c3f31', '#4a332a'],
	store: ['#eef2f5', '#d4d9de'],
};

export const buildSet = (location: string, tod: TimeOfDay, seed: number): SetSpec => {
	const sky = TOD[tod].sky;
	const base = {sky, scrolling: [] as Prop[], scrollSpeed: 0, seated: false};
	switch (location) {
		case 'street':
			return {...base, exterior: true, wall: sky, floor: '#d4d4d4', props: street(tod, seed), hemiGround: '#b8b8b8'};
		case 'park':
			return {...base, exterior: true, wall: sky, floor: '#7cc56b', props: park(tod), hemiGround: '#6aa85a'};
		case 'car':
			return {
				...base,
				exterior: true,
				seated: true,
				wall: sky,
				floor: '#4b4f58',
				props: carInterior(seed),
				scrolling: carScenery(),
				scrollSpeed: 4.5,
				hemiGround: '#6b6b6b',
			};
		default: {
			const [wall, floor] = WALLS[location] ?? WALLS.living_room;
			const builders: Record<string, (t: TimeOfDay, s: number) => Prop[]> = {
				kitchen,
				living_room: livingRoom,
				bedroom,
				office,
				classroom,
				restaurant,
				store,
			};
			const props = (builders[location] ?? livingRoom)(tod, seed);
			return {...base, exterior: false, wall, floor, props, hemiGround: floor};
		}
	}
};
