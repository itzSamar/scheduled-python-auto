import type {Slot} from '../characters/state';
import {clamp, easeInOut, noise1} from '../lib/math';
import type {TimelineBeat} from '../types';

export const ASPECT = 1080 / 1920;
export const FOV_3D = 30;
const TAN_HALF = Math.tan(((FOV_3D / 2) * Math.PI) / 180);

/** World-space framing: center (x, y), visible height h, plus 3D-only orbit and elevation (fraction of h). */
export type Framing = {x: number; y: number; h: number; yaw: number; shakeX: number; shakeY: number; roll: number; elev?: number};

export const parseCamera = (camera: string): {shot: string; focus: string | null} => {
	const [shot, focus] = camera.split(':');
	return {shot: shot || 'wide', focus: focus || null};
};

/** Center y that puts a head at `fromTop` (0 = top edge, 1 = bottom edge) of the frame. */
const centerForHead = (headY: number, h: number, fromTop: number) => headY - (0.5 - fromTop) * h;

const wideFraming = (slots: Slot[]): Framing => {
	const xs = slots.map((s) => s.x);
	const minX = Math.min(...xs, 0);
	const maxX = Math.max(...xs, 0);
	const seated = slots.some((s) => s.seated);
	const width = Math.max(seated ? 1.6 : 1.8, maxX - minX + 0.95);
	const h = Math.max(width / ASPECT, seated ? 2.6 : 3.2);
	const headY = Math.max(...slots.map((s) => s.headY), 1);
	return {x: (minX + maxX) / 2, y: centerForHead(headY, h, 0.4), h, yaw: 0, shakeX: 0, shakeY: 0, roll: 0};
};

/**
 * Camera framing for time t. Cuts happen at beat ownership boundaries; within a beat the
 * camera drifts slowly (scene-clock based so repeated shots don't jump).
 */
export const framingAt = (
	beat: TimelineBeat | undefined,
	slots: Map<string, Slot>,
	t: number,
	segStart: number,
	segEnd: number,
	sceneStart: number,
	seed: number,
): Framing => {
	const all = [...slots.values()];
	const elev = all.some((s) => s.seated) ? 0.2 : 0.05;
	return {...framingFor(beat, slots, all, t, segStart, segEnd, sceneStart, seed), elev};
};

const framingFor = (
	beat: TimelineBeat | undefined,
	slots: Map<string, Slot>,
	all: Slot[],
	t: number,
	segStart: number,
	segEnd: number,
	sceneStart: number,
	seed: number,
): Framing => {
	if (!beat || all.length === 0) {
		return wideFraming(all.length ? all : [{x: 0, z: 0, scale: 1, headY: 1.3, seated: false}]);
	}
	const {shot, focus} = parseCamera(beat.camera);
	const focusId = focus ?? beat.character;
	const f = slots.get(focusId) ?? slots.get(beat.character);
	const st = t - sceneStart;
	const sway = {x: Math.sin(st * 0.35 + seed) * 0.03, h: 1 + Math.sin(st * 0.22 + seed * 2) * 0.015};

	if (!f || shot === 'wide') {
		const w = wideFraming(all);
		return {...w, x: w.x + sway.x, h: w.h * sway.h};
	}

	const segT = clamp((t - segStart) / Math.max(0.3, segEnd - segStart));
	const tSeg = t - segStart;

	switch (shot) {
		case 'closeup': {
			const h = 1.5 * sway.h;
			return {x: f.x + sway.x * 0.4, y: centerForHead(f.headY, h, 0.4), h, yaw: 0, shakeX: 0, shakeY: 0, roll: 0};
		}
		case 'push_in': {
			const h = 2.7 + (1.45 - 2.7) * easeInOut(segT);
			return {x: f.x, y: centerForHead(f.headY, h, 0.38), h, yaw: 0, shakeX: 0, shakeY: 0, roll: 0};
		}
		case 'shake': {
			const amp = 0.06 * Math.exp(-3.2 * tSeg) + 0.006;
			const punch = 1 - 0.08 * Math.exp(-6 * tSeg);
			const h = 1.9 * punch;
			return {
				x: f.x,
				y: centerForHead(f.headY, h, 0.38),
				h,
				yaw: 0,
				shakeX: noise1(t * 22, seed) * amp * h,
				shakeY: noise1(t * 19, seed + 7) * amp * h,
				roll: noise1(t * 15, seed + 13) * amp * 0.5,
			};
		}
		case 'two_shot':
		default: {
			let partner: Slot | undefined;
			let best = Infinity;
			for (const [id, s] of slots) {
				if (id !== focusId && Math.abs(s.x - f.x) < best) {
					best = Math.abs(s.x - f.x);
					partner = s;
				}
			}
			if (!partner) {
				const h = 2.3 * sway.h;
				return {x: f.x + sway.x, y: centerForHead(f.headY, h, 0.36), h, yaw: 0, shakeX: 0, shakeY: 0, roll: 0};
			}
			const h = 2.5 * sway.h;
			const side = Math.sign(partner.x - f.x) || 1;
			return {
				x: f.x + (partner.x - f.x) * 0.38 + sway.x,
				y: centerForHead(Math.max(f.headY, partner.headY), h, 0.36),
				h,
				yaw: side * 0.24,
				shakeX: 0,
				shakeY: 0,
				roll: 0,
			};
		}
	}
};

/** Perspective camera placement for a framing (target plane z = 0). */
export const perspectivePose = (fr: Framing) => {
	const d = fr.h / (2 * TAN_HALF);
	const x = fr.x + fr.shakeX;
	const y = fr.y + fr.shakeY;
	return {
		position: [x + Math.sin(fr.yaw) * d, y + (fr.elev ?? 0.05) * fr.h, Math.cos(fr.yaw) * d] as [number, number, number],
		target: [x, y, 0] as [number, number, number],
		roll: fr.roll,
	};
};
