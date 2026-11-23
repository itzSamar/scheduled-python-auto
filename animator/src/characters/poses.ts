import {Euler, Quaternion, Vector3} from 'three';
import {clamp, easeOut, lerp, noise1} from '../lib/math';

/**
 * Arm pose relative to the arm hanging straight down.
 * raise: lift sideways (away from body); forward: swing toward the camera;
 * bend: elbow bend inward (negative = outward); bendFwd: forearm tilt toward the camera.
 * reach: cartoon arm stretch (1 = normal); big heads are out of reach otherwise.
 */
export type ArmPose = {raise: number; forward: number; bend: number; bendFwd: number; reach?: number};

export type Pose = {
	/** Arm on the side facing the other characters. */
	inner: ArmPose;
	/** Arm on the outside. */
	outer: ArmPose;
	hop: number;
	lean: number;
	tilt: number;
	headTilt: number;
	headNod: number;
	shoulderUp: number;
	walk: number;
	xOffset: number;
};

const REST: ArmPose = {raise: 0.1, forward: 0.06, bend: 0.2, bendFwd: 0.1};

const pose = (p: Partial<Pose>): Pose => ({
	inner: REST,
	outer: REST,
	hop: 0,
	lean: 0,
	tilt: 0,
	headTilt: 0,
	headNod: 0,
	shoulderUp: 0,
	walk: 0,
	xOffset: 0,
	...p,
});

const breathe = (t: number, seed: number): Partial<Pose> => ({
	tilt: 0.025 * Math.sin(t * 1.3 + seed),
	headTilt: 0.04 * Math.sin(t * 0.9 + seed * 2),
});

/** Body pose for `action`, `t` seconds after the action started. `outerSign` points away from the group. */
export const poseFor = (action: string, t: number, seed: number, outerSign: number, energy = 1): Pose => {
	const n = (i: number, speed = 1.8) => noise1(t * speed, seed + i * 31);
	const idle = breathe(t, seed);
	switch (action) {
		case 'talk':
			return pose({
				...idle,
				inner: {raise: 0.28 + 0.12 * n(1), forward: 0.55 + 0.3 * n(2) * energy, bend: 1.05 + 0.4 * n(3) * energy, bendFwd: 0.35},
				outer: {raise: 0.16, forward: 0.22 + 0.15 * n(4), bend: 0.6 + 0.25 * n(5), bendFwd: 0.15},
				headNod: 0.05 * n(6, 3.2),
			});
		case 'wave':
			return pose({
				...idle,
				outer: {raise: 2.55, forward: 0.25, bend: 0.35 + 0.4 * Math.sin(t * 9), bendFwd: 0},
				headTilt: 0.08,
			});
		case 'point':
			return pose({
				...idle,
				inner: {raise: 1.35, forward: 0.85 + 0.1 * Math.sin(t * 7), bend: 0.05, bendFwd: 0},
				lean: -0.06,
			});
		case 'hands_on_hips':
			return pose({
				...idle,
				inner: {raise: 0.78, forward: -0.1, bend: 2.15, bendFwd: 0.15},
				outer: {raise: 0.78, forward: -0.1, bend: 2.15, bendFwd: 0.15},
				lean: 0.05,
			});
		case 'cross_arms':
			return pose({
				...idle,
				inner: {raise: 0.2, forward: 0.7, bend: 1.9, bendFwd: 0.55},
				outer: {raise: 0.2, forward: 0.62, bend: 1.85, bendFwd: 0.45},
				lean: 0.06,
				headTilt: 0.07,
			});
		case 'facepalm':
			return pose({
				inner: {raise: -0.05, forward: 1.95, bend: 0.65, bendFwd: 1.2, reach: 1.35},
				headNod: 0.2,
				headTilt: 0.07 * Math.sin(t * 2.2),
				tilt: 0.02,
			});
		case 'shrug': {
			const lift = 0.5 + 0.5 * Math.sin(Math.min(t, 0.6) * Math.PI / 1.2);
			return pose({
				...idle,
				inner: {raise: 0.4, forward: 0.35, bend: -1.25 * lift, bendFwd: 0.7},
				outer: {raise: 0.4, forward: 0.35, bend: -1.25 * lift, bendFwd: 0.7},
				shoulderUp: 0.04 * lift,
				headTilt: 0.14,
			});
		}
		case 'jump': {
			const hop = t < 1 ? Math.abs(Math.sin(t * Math.PI * 2)) * 0.28 * (1 - t) : 0;
			return pose({
				...idle,
				inner: {raise: 2.3, forward: 0.2, bend: 0.3, bendFwd: 0},
				outer: {raise: 2.3, forward: 0.2, bend: 0.3, bendFwd: 0},
				hop,
			});
		}
		case 'walk_in': {
			const p = clamp(t / 1.1);
			const swing = Math.sin(t * 10) * (1 - easeOut(p));
			return pose({
				...idle,
				inner: {raise: 0.1, forward: 0.5 * swing, bend: 0.3, bendFwd: 0.1},
				outer: {raise: 0.1, forward: -0.5 * swing, bend: 0.3, bendFwd: 0.1},
				walk: 0.55 * swing,
				hop: Math.abs(Math.sin(t * 10)) * 0.03 * (1 - p),
				xOffset: outerSign * 2.8 * (1 - easeOut(p)),
			});
		}
		case 'celebrate':
			return pose({
				inner: {raise: 2.5 + 0.15 * Math.sin(t * 8), forward: 0.2, bend: 0.4, bendFwd: 0},
				outer: {raise: 2.5 + 0.15 * Math.sin(t * 8 + 1), forward: 0.2, bend: 0.4, bendFwd: 0},
				hop: Math.abs(Math.sin(t * 6)) * 0.12,
				headTilt: 0.1 * Math.sin(t * 6),
			});
		case 'cry':
			return pose({
				inner: {raise: -0.05, forward: 1.9, bend: 0.45, bendFwd: 1.3, reach: 1.3},
				outer: {raise: -0.05, forward: 1.9, bend: 0.45, bendFwd: 1.3, reach: 1.3},
				tilt: 0.03 * Math.sin(t * 14),
				headNod: 0.14,
			});
		case 'think':
			return pose({
				...idle,
				inner: {raise: -0.3, forward: 1.45, bend: 0.55, bendFwd: 1.3},
				outer: {raise: 0.12, forward: 0.55, bend: 1.7, bendFwd: 0.5},
				headTilt: 0.13,
				headNod: -0.07,
			});
		case 'idle':
		default:
			return pose({...idle});
	}
};

/** Emotion adds whole-body flavor on top of the action. */
export const applyEmotion = (p: Pose, emotion: string, t: number, seed: number): Pose => {
	switch (emotion) {
		case 'angry':
			return {...p, lean: p.lean - 0.06, tilt: p.tilt + 0.02 * noise1(t * 6, seed)};
		case 'shocked':
			return {...p, lean: p.lean + 0.08, hop: p.hop + (t < 0.35 ? Math.sin((t / 0.35) * Math.PI) * 0.08 : 0)};
		case 'laughing':
			return {...p, hop: p.hop + Math.abs(Math.sin(t * 9)) * 0.03, headTilt: p.headTilt + 0.06 * Math.sin(t * 9)};
		case 'sad':
		case 'crying':
			return {...p, headNod: p.headNod + 0.1, shoulderUp: p.shoulderUp - 0.02};
		case 'nervous':
			return {...p, tilt: p.tilt + 0.015 * Math.sin(t * 17)};
		case 'happy':
			return {...p, hop: p.hop + Math.abs(Math.sin(t * 4)) * 0.015};
		default:
			return p;
	}
};

const mixArm = (a: ArmPose, b: ArmPose, w: number): ArmPose => ({
	raise: lerp(a.raise, b.raise, w),
	forward: lerp(a.forward, b.forward, w),
	bend: lerp(a.bend, b.bend, w),
	bendFwd: lerp(a.bendFwd, b.bendFwd, w),
	reach: lerp(a.reach ?? 1, b.reach ?? 1, w),
});

export const mixPose = (a: Pose, b: Pose, w: number): Pose => ({
	inner: mixArm(a.inner, b.inner, w),
	outer: mixArm(a.outer, b.outer, w),
	hop: lerp(a.hop, b.hop, w),
	lean: lerp(a.lean, b.lean, w),
	tilt: lerp(a.tilt, b.tilt, w),
	headTilt: lerp(a.headTilt, b.headTilt, w),
	headNod: lerp(a.headNod, b.headNod, w),
	shoulderUp: lerp(a.shoulderUp, b.shoulderUp, w),
	walk: lerp(a.walk, b.walk, w),
	xOffset: lerp(a.xOffset, b.xOffset, w),
});

export const shoulderEuler = (arm: ArmPose, side: number) => new Euler(-arm.forward, 0, side * arm.raise);
export const elbowEuler = (arm: ArmPose, side: number) => new Euler(-arm.bendFwd, 0, -side * arm.bend);

/** Elbow and hand positions (relative to the shoulder) for drawing flat 2D arms. */
export const armChain = (arm: ArmPose, side: number, upper: number, lower: number) => {
	const qs = new Quaternion().setFromEuler(shoulderEuler(arm, side));
	const qe = new Quaternion().setFromEuler(elbowEuler(arm, side));
	const elbow = new Vector3(0, -upper, 0).applyQuaternion(qs);
	const hand = new Vector3(0, -lower, 0).applyQuaternion(qe).applyQuaternion(qs).add(elbow);
	return {elbow, hand};
};
