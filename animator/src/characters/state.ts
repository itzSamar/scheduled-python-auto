import {expressionFor, reactionTo, type Expression} from './expressions';
import {applyEmotion, mixPose, poseFor, type Pose} from './poses';
import {activeBeatIndex, mouthAt, segmentStart} from '../lib/timeline';
import {clamp, easeOut, hashString, rand01} from '../lib/math';
import type {Character, MouthShape, TimelineBeat} from '../types';

export type Slot = {x: number; z: number; scale: number; headY: number; seated: boolean};

export type CharState = {
	character: Character;
	slot: Slot;
	pose: Pose;
	expression: Expression;
	emotion: string;
	mouth: MouthShape | null;
	/** -1..1 horizontal gaze; 0 looks at the camera. */
	gaze: number;
	/** Body turn toward the group, radians (3D) / face offset (2D). */
	facing: number;
	blink: number;
	/** Sign pointing away from the group (used for entrances and outer arm). */
	outerSign: number;
	visible: boolean;
};

const AGE_SCALE: Record<string, number> = {kid: 0.72, teen: 0.9, elderly: 0.95};
/** Head center height for scale 1 (see Character3D/2D proportions). */
export const HEAD_Y = 1.3;

export const scaleFor = (c: Character) => AGE_SCALE[c.age] ?? 1;

/** Stage positions for the characters on screen. Speakers are ordered by first appearance; OP stays left. */
export const layoutSlots = (characters: Character[], onscreen: string[], seated: boolean): Map<string, Slot> => {
	const ids = [...onscreen].sort((a, b) => (a === 'op' ? -1 : b === 'op' ? 1 : 0));
	const n = ids.length;
	const xs: Record<number, number[]> = {1: [0], 2: [-0.55, 0.55], 3: [-1.0, 0, 1.0], 4: [-1.42, -0.48, 0.48, 1.42]};
	const zs: Record<number, number[]> = {1: [0], 2: [0, 0], 3: [0, -0.3, 0], 4: [0, -0.25, -0.25, 0]};
	const byId = new Map(characters.map((c) => [c.id, c]));
	const out = new Map<string, Slot>();
	ids.forEach((id, i) => {
		const c = byId.get(id);
		if (!c) {
			return;
		}
		const scale = scaleFor(c);
		let x = (xs[n] ?? xs[4])[i] ?? 0;
		let z = (zs[n] ?? zs[4])[i] ?? 0;
		if (seated) {
			// Front seats, then back seat.
			x = [-0.42, 0.42, -0.38, 0.38][i] ?? 0;
			z = i < 2 ? 0 : -0.75;
		}
		out.set(id, {x, z, scale, headY: HEAD_Y * scale - (seated ? 0.32 : 0), seated});
	});
	return out;
};

const blinkAt = (t: number, seed: number) => {
	const period = 2.6 + rand01(seed) * 2.2;
	const phase = (t + rand01(seed + 1) * period) % period;
	const d = 0.13;
	return phase < d ? 1 - Math.abs(phase / d - 0.5) * 2 : 0;
};

/** Everything a character needs to draw itself at time t (seconds, absolute). */
export const characterState = (
	character: Character,
	slot: Slot,
	slots: Map<string, Slot>,
	beats: TimelineBeat[],
	t: number,
	sceneStart: number,
): CharState => {
	const seed = hashString(character.id) % 1000;
	const others = [...slots.entries()].filter(([id]) => id !== character.id);
	const centerX = others.length ? others.reduce((s, [, o]) => s + o.x, 0) / others.length : 0;
	const towardSign = others.length ? Math.sign(centerX - slot.x) || 1 : 1;
	const outerSign = -towardSign;

	const i = activeBeatIndex(beats, t);
	const beat = beats[i];
	const segStart = segmentStart(beats, i, sceneStart);

	const evalAt = (bi: number, time: number) => {
		const b = beats[bi];
		if (!b) {
			return {pose: poseFor('idle', time, seed, outerSign), emotion: 'neutral'};
		}
		const mine = b.character === character.id;
		const emotion = mine ? b.emotion : reactionTo(b.emotion);
		const action = mine ? b.action : 'idle';
		const actionT = Math.max(0, time - (mine ? Math.min(b.start, segmentStart(beats, bi, sceneStart) + 0.15) : sceneStart));
		const energy = b.emotion === 'angry' || b.emotion === 'shocked' ? 1.4 : 1;
		return {pose: applyEmotion(poseFor(action, actionT, seed, outerSign, energy), emotion, actionT, seed), emotion};
	};

	const cur = evalAt(i, t);
	let pose = cur.pose;
	const blendDur = 0.28;
	if (i > 0 && t - segStart < blendDur) {
		const prev = evalAt(i - 1, segStart);
		pose = mixPose(prev.pose, cur.pose, easeOut(clamp((t - segStart) / blendDur)));
	}

	// Characters who walk in later stay off stage until their entrance.
	const entrance = beats.findIndex((b) => b.character === character.id && b.action === 'walk_in');
	let visible = true;
	if (entrance >= 0 && i < entrance) {
		visible = false;
	}

	const speaking = beat && beat.speaker === character.id;
	const mouth = speaking ? mouthAt(beat, t) : null;

	let gaze = 0;
	if (beat) {
		const speakerSlot = slots.get(beat.speaker);
		if (beat.narration && character.id === 'op') {
			gaze = 0;
		} else if (speaking) {
			gaze = towardSign * 0.6;
		} else if (speakerSlot) {
			gaze = clamp((speakerSlot.x - slot.x) * 1.2, -1, 1);
		} else {
			gaze = towardSign * 0.3;
		}
	}
	const facing = beat?.narration && character.id === 'op' ? 0 : towardSign * (others.length ? 0.32 : 0);

	return {
		character,
		slot,
		pose,
		expression: expressionFor(cur.emotion),
		emotion: cur.emotion,
		mouth,
		gaze,
		facing,
		blink: blinkAt(t, seed),
		outerSign,
		visible,
	};
};
